# -*- coding: utf-8 -*-
"""Supabase(Postgres) 스키마 생성 및 이벤트 적재.

접속: Supabase는 신규 프로젝트의 직접 접속(DB호스트)이 IPv6 전용이라
     IPv4 전용 환경에서는 IPv4 지원 풀러(aws-0-<region>.pooler.supabase.com:6543)를 쓴다.
설정 우선순위: 환경변수 > ~/API_KEYS.yaml
  SUPABASE_POOLER_HOST, SUPABASE_POOLER_PORT, SUPABASE_DB_USER, SUPABASE_DB_PASSWORD,
  SUPABASE_DB_NAME (기본 postgres), SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import json
import os
import pathlib
import yaml

DEFAULT_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"
DEFAULT_PORT = 6543

DDL = """
create table if not exists public.crawl_runs (
  id            bigserial primary key,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  articles      integer default 0,
  events        integer default 0,
  new_events    integer default 0,
  status        text default 'running',
  note          text
);

create table if not exists public.contracts (
  id               bigserial primary key,
  event_key        text not null unique,
  contract_date    date not null,
  supplier         text not null,
  customer         text not null,
  amount_won       bigint,
  amount_disclosed boolean not null default false,
  category         text not null,
  region_site      text,
  title            text,
  source           text,
  url              text,
  first_seen_at    timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  crawl_run_id     bigint references public.crawl_runs(id)
);

alter table public.contracts add column if not exists source_kind text not null default 'news';
alter table public.contracts add column if not exists dart_no text;
alter table public.contracts add column if not exists detail jsonb;

create index if not exists contracts_date_idx on public.contracts (contract_date desc);
create index if not exists contracts_supplier_idx on public.contracts (supplier);

create or replace view public.v_supplier_totals as
select supplier,
       count(*)                                   as deals,
       sum(amount_won) filter (where amount_won is not null) as amount_total,
       max(contract_date)                         as last_date
from public.contracts
group by supplier;

alter table public.contracts  enable row level security;
alter table public.crawl_runs enable row level security;
drop policy if exists "public read contracts" on public.contracts;
create policy "public read contracts" on public.contracts for select to anon using (true);
drop policy if exists "public read runs" on public.crawl_runs;
create policy "public read runs" on public.crawl_runs for select to anon using (true);
"""


def _load_yaml_defaults() -> dict:
    p = pathlib.Path.home() / "API_KEYS.yaml"
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text()).get("supabase", {}) or {}
    except Exception:
        return {}


def settings() -> dict:
    y = _load_yaml_defaults()
    ref = ""
    url = os.getenv("SUPABASE_URL") or y.get("url") or ""
    if url:
        ref = url.split("//")[-1].split(".")[0]
    return {
        "url": url,
        "anon_key": os.getenv("SUPABASE_ANON_KEY") or y.get("anon_key", ""),
        "secret_key": os.getenv("SUPABASE_SECRET_KEY") or y.get("secret_key", ""),
        "host": os.getenv("SUPABASE_POOLER_HOST") or DEFAULT_HOST,
        "port": int(os.getenv("SUPABASE_POOLER_PORT") or DEFAULT_PORT),
        "dbname": os.getenv("SUPABASE_DB_NAME") or y.get("database") or "postgres",
        "user": os.getenv("SUPABASE_DB_USER") or (f"postgres.{ref}" if ref else "postgres"),
        "password": os.getenv("SUPABASE_DB_PASSWORD") or y.get("pwd", ""),
    }


def connect():
    import psycopg
    s = settings()
    return psycopg.connect(
        host=s["host"], port=s["port"], dbname=s["dbname"], user=s["user"],
        password=s["password"], sslmode="require", connect_timeout=15,
    )


def ensure_schema(conn=None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    finally:
        if own:
            conn.close()


def event_key(e: dict) -> str:
    amount = int(e["amount"]) if e.get("amount") else 0
    return "|".join([e["supplier"], "&".join(e["customers"]), e["date"], str(amount)])


def upsert_events(events, run_id=None) -> list:
    """contracts 업서트 후 새로 삽입된 이벤트 목록 반환."""
    if not events:
        return []
    with connect() as conn:
        with conn.cursor() as cur:
            new = []
            for e in events:
                cur.execute(
                    """
                    insert into public.contracts
                      (event_key, contract_date, supplier, customer, amount_won,
                       amount_disclosed, category, title, source, url, crawl_run_id,
                       source_kind, dart_no, detail)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict (event_key) do update set
                      updated_at = now(),
                      source_kind = excluded.source_kind,
                      dart_no = excluded.dart_no,
                      detail = excluded.detail,
                      amount_won = coalesce(excluded.amount_won, public.contracts.amount_won)
                    returning (xmax = 0) as inserted
                    """,
                    (
                        event_key(e), e["date"], e["supplier"], "&".join(e["customers"]),
                        int(e["amount"]) if e.get("amount") else None,
                        bool(e.get("amount")),
                        "equipment" if e.get("equipment") else "parts",
                        e.get("title"), e.get("source"), e.get("link"), run_id,
                        e.get("source_kind", "news"), e.get("dart_no"),
                        json.dumps(e.get("detail") or {}, ensure_ascii=False),
                    ),
                )
                if cur.fetchone()[0]:
                    new.append(e)
        conn.commit()
    return new


PURGE_SQL = """
delete from public.contracts n
using public.contracts d
where n.source_kind = 'news'
  and d.source_kind = 'dart'
  and n.supplier = d.supplier
  and n.id <> d.id
  and n.customer like '%%' || split_part(d.customer, '&', 1) || '%%'
  and abs((n.contract_date - d.contract_date)) <= %s
returning n.id, n.supplier, n.contract_date;
"""


def purge_superseded(window_days=14) -> int:
    """공시(DART)로 대체된 뉴스 기반 행 삭제. 중복 집계 방지용."""
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(PURGE_SQL, (window_days,))
            removed = cur.fetchall()
        conn.commit()
    for r in removed:
        print(f"      중복 삭제: {r[1]} {r[2]} (공시 우선)")
    return len(removed)


def start_run() -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("insert into public.crawl_runs default values returning id")
            rid = cur.fetchone()[0]
        conn.commit()
    return rid


def finish_run(rid, articles, events, new_events, note="") -> None:
    with connect() as conn:
        conn.execute(
            "update public.crawl_runs set finished_at=now(), articles=%s, events=%s,"
            " new_events=%s, status='ok', note=%s where id=%s",
            (articles, events, new_events, note, rid),
        )
        conn.commit()
