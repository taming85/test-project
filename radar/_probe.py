
import radar.db as db
db.ensure_schema()
with db.connect() as c:
    print(c.execute("select tablename from pg_tables where schemaname='public'").fetchall())
    print(c.execute("select policyname from pg_policies where schemaname='public'").fetchall())
