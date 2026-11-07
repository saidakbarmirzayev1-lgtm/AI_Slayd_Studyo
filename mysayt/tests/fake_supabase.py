"""Sinov uchun xotiradagi soxta Supabase (faqat loyihada ishlatiladigan metodlar)."""
from datetime import datetime, timezone
import itertools, re


class Res:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


def _dt(v):
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _cmp(a, b):
    da, db = _dt(a), _dt(b)
    if da and db:
        return (da > db) - (da < db)
    try:
        return (float(a) > float(b)) - (float(a) < float(b))
    except Exception:
        return (str(a) > str(b)) - (str(a) < str(b))


class Query:
    def __init__(self, db, table):
        self.db, self.t = db, table
        self.op, self.payload = "select", None
        self.cols, self.count_mode = "*", None
        self.filters, self.orders, self._range, self._limit = [], [], None, None

    # ---- builders
    def select(self, cols="*", count=None, **_):
        self.op, self.cols, self.count_mode = "select", cols, count
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def upsert(self, rows):
        self.op, self.payload = "upsert", rows
        return self

    def update(self, patch):
        self.op, self.payload = "update", patch
        return self

    def delete(self):
        self.op = "delete"
        return self

    def _f(self, fn):
        self.filters.append(fn)
        return self

    def eq(self, c, v):
        return self._f(lambda r: r.get(c) == v)

    def neq(self, c, v):
        return self._f(lambda r: r.get(c) != v)

    def gte(self, c, v):
        return self._f(lambda r: r.get(c) is not None and _cmp(r.get(c), v) >= 0)

    def gt(self, c, v):
        return self._f(lambda r: r.get(c) is not None and _cmp(r.get(c), v) > 0)

    def lt(self, c, v):
        return self._f(lambda r: r.get(c) is not None and _cmp(r.get(c), v) < 0)

    def in_(self, c, vals):
        return self._f(lambda r: r.get(c) in list(vals))

    def like(self, c, pat):
        rx = re.compile("^" + re.escape(pat).replace("%", ".*") + "$", re.I)
        return self._f(lambda r: bool(rx.match(str(r.get(c) or ""))))

    ilike = like

    def or_(self, expr):
        conds = []
        for part in expr.split(","):
            col, op, val = part.split(".", 2)
            conds.append((col, op, val))

        def fn(r):
            for col, op, val in conds:
                v = r.get(col)
                if op == "is" and val == "null" and v is None:
                    return True
                if op == "gt" and v is not None and _cmp(v, val) > 0:
                    return True
                if op == "lt" and v is not None and _cmp(v, val) < 0:
                    return True
                if op == "eq" and str(v) == val:
                    return True
            return False
        return self._f(fn)

    def order(self, c, desc=False):
        self.orders.append((c, desc))
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # ---- execute
    def execute(self):
        tbl = self.db.tables.setdefault(self.t, [])
        self.db.check(self.t, self.op, self.payload, self.cols)
        if self.op in ("insert", "upsert"):
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for r in rows:
                r = dict(r)
                pk = self.db.pk.get(self.t)
                if self.op == "upsert" and pk:
                    ex = next((x for x in tbl if x.get(pk) == r.get(pk)), None)
                    if ex:
                        ex.update(r)
                        out.append(dict(ex))
                        continue
                if pk and any(x.get(pk) == r.get(pk) and r.get(pk) is not None for x in tbl):
                    raise Exception("duplicate key value violates unique constraint 23505")
                if self.t in self.db.serial and "id" not in r:
                    r["id"] = next(self.db.serial[self.t])
                r.setdefault("created_at", datetime.now(timezone.utc).isoformat())
                defaults = self.db.defaults.get(self.t, {})
                for k, v in defaults.items():
                    r.setdefault(k, v)
                tbl.append(r)
                out.append(dict(r))
            return Res(out)
        rows = [r for r in tbl if all(f(r) for f in self.filters)]
        if self.op == "update":
            for r in rows:
                r.update(self.payload)
            return Res([dict(r) for r in rows])
        if self.op == "delete":
            for r in rows:
                tbl.remove(r)
            return Res([dict(r) for r in rows])
        for c, desc in reversed(self.orders):
            rows.sort(key=lambda r: (r.get(c) is None, str(r.get(c))), reverse=desc)
        total = len(rows)
        if self._range:
            rows = rows[self._range[0]: self._range[1] + 1]
        if self._limit is not None:
            rows = rows[: self._limit]
        if self.cols not in ("*", None):
            keep = [c.strip() for c in self.cols.split(",")]
            rows = [{k: r.get(k) for k in keep} for r in rows]
        else:
            rows = [dict(r) for r in rows]
        return Res(rows, total if self.count_mode else None)


class _Admin:
    def __init__(self, db):
        self.db = db

    def get_user_by_id(self, uid):
        meta = self.db.auth_meta.get(uid, {})
        return type("R", (), {"user": type("U", (), {"app_metadata": meta})()})()

    def create_user(self, *_a, **_k):
        return None

    def generate_link(self, *_a, **_k):
        raise Exception("not used in tests")


class _Auth:
    def __init__(self, db):
        self.db, self.admin = db, _Admin(db)

    def get_user(self, token):
        u = self.db.tokens.get(token)
        if not u:
            raise Exception("invalid jwt")
        return type("R", (), {"user": type("U", (), {"id": u[0], "email": u[1]})()})()


class FakeSB:
    def __init__(self):
        self.tables, self.tokens, self.auth_meta = {}, {}, {}
        self.pk = {"app_settings": "key", "payment_events": "order_id", "tg_links": "tg_id", "user_usage": "user_id"}
        self.serial = {"ads": itertools.count(1), "admin_audit": itertools.count(1), "usage_ledger": itertools.count(1)}
        self.defaults = {"ads": {"impressions": 0, "clicks": 0, "active": True, "weight": 1}}
        self.missing_cols = set()          # migratsiya ishga tushirilmagan holatni taqlid qilish
        self.missing_tables = set()
        self.auth = _Auth(self)

    def check(self, table, op, payload, cols):
        if table in self.missing_tables:
            raise Exception(f'relation "{table}" does not exist')
        if self.missing_cols and table == "user_usage":
            touched = set()
            if isinstance(payload, dict):
                touched |= set(payload)
            touched |= {c.strip() for c in str(cols).split(",")}
            if touched & self.missing_cols:
                raise Exception("column does not exist")

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params):
        db = self

        class R:
            def execute(self_inner):
                if name == "ad_bump":
                    for r in db.tables.get("ads", []):
                        if r["id"] == params["p_id"]:
                            col = "clicks" if params["p_kind"] == "click" else "impressions"
                            r[col] = int(r.get(col) or 0) + 1
                    return Res([])
                raise Exception("unknown rpc")
        return R()

    def add_user(self, uid, email, token=None, **extra):
        row = {"user_id": uid, "email": email, "free_credits": 300, "paid_credits": 0, "slide_credits": 300,
               "last_reset_time": datetime.now(timezone.utc).isoformat(), "blocked": False, "total_tokens": 0,
               "last_active": datetime.now(timezone.utc).isoformat(), "plan": "free", "unlimited": False}
        row.update(extra)
        self.tables.setdefault("user_usage", []).append(row)
        if token:
            self.tokens[token] = (uid, email)
        return row
