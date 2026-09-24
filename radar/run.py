# -*- coding: utf-8 -*-
"""수집 실행 CLI (수집 -> 정규화 -> Supabase 적재 -> 리포트).

사용법:
    python -m radar.run                 # 기본: 최근 365일 리포트, DB 적재
    python -m radar.run --when 30d      # 구글뉴스 최근 30일만
    python -m radar.run --no-db         # DB 적재 생략
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib

from radar import config, db, extract
from radar import report as reporter
from radar.sources import dart, gnews

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def run(days: int, when, use_db: bool) -> dict:
    DATA.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    kst = dt.timezone(dt.timedelta(hours=9))
    today = dt.datetime.now(kst).date()
    run_id = None

    print("[1/5] 구글뉴스 수집")
    queries = gnews.build_queries(config.CUSTOMERS, config.WATCHLIST, config.NEWS_QUERIES)
    articles = gnews.collect(queries, when=when)
    print(f"      질의 {len(queries)}개 -> 기사 {len(articles)}건")
    (DATA / f"articles_{today}.json").write_text(
        json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[2/5] DART 공시 수집")
    dart_rows = []
    if dart.enabled():
        dart_rows = dart.supply_contracts(
            (today - dt.timedelta(days=days)).strftime("%Y%m%d"), today.strftime("%Y%m%d"))
        print(f"      공급계약 공시 {len(dart_rows)}건")
    else:
        print("      OPENDART_KEY 없음 - 건너뜀")
    (DATA / f"dart_{today}.json").write_text(
        json.dumps(dart_rows, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[3/5] 이벤트 정규화 / 중복제거")
    events = extract.build(articles)
    print(f"      계약 이벤트 {len(events)}건")
    (DATA / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=1), encoding="utf-8")

    new_count = 0
    new_events = []
    if use_db:
        print("[4/5] Supabase 적재")
        try:
            db.ensure_schema()
            run_id = db.start_run()
            new_events = db.upsert_events(events, run_id)
            new_count = len(new_events)
            db.finish_run(run_id, len(articles), len(events), new_count)
            print(f"      신규 {new_count}건 / 누적 이벤트 {len(events)}건")
        except Exception as exc:
            print(f"      DB 적재 실패: {exc}")
            if run_id:
                try:
                    db.finish_run(run_id, len(articles), len(events), 0, note=str(exc)[:300])
                except Exception:
                    pass
    else:
        print("[4/5] Supabase 적재 생략 (--no-db)")

    if new_events:
        (DATA / "new_events.json").write_text(
            json.dumps(new_events, ensure_ascii=False, indent=1), encoding="utf-8")
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("\n" + json.dumps(new_events, ensure_ascii=False) + "\n")

    print("[5/5] 리포트 생성")
    md = reporter.render(events, days=days)
    out = REPORTS / f"{today}-report.md"
    out.write_text(md, encoding="utf-8")
    print(f"      {out}")
    return {"events": events, "new": new_count, "new_events": new_events, "report": str(out)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--when", default=None, help="예: 30d, 6m, 1y")
    ap.add_argument("--no-db", action="store_true")
    a = ap.parse_args()
    run(a.days, a.when, not a.no_db)


if __name__ == "__main__":
    main()
