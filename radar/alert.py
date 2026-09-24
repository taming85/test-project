# -*- coding: utf-8 -*-
"""신규 계약 알림.

- SLACK_WEBHOOK_URL 이 있으면 Slack 으로 전송
- GitHub Actions 환경이면 이슈로도 남긴다 (GITHUB_TOKEN 자동 제공)
- 둘 다 없으면 stdout 에 마크다운 출력
"""
from __future__ import annotations

import json
import os
import sys


def won(amount):
    if not amount:
        return "미공개"
    if amount >= 1e12:
        return f"{amount/1e12:,.2f}조원"
    return f"{amount/1e8:,.0f}억원"


def render(new_events, site=None):
    lines = [f"### 신규 계약 {len(new_events)}건 감지", ""]
    lines.append("| 계약일 | 공급사 | 발주처 | 금액 | 구분 |")
    lines.append("|---|---|---|---|---|")
    total = 0
    for e in sorted(new_events, key=lambda r: r["date"], reverse=True):
        total += e.get("amount") or 0
        lines.append(
            f"| {e['date']} | **{e['supplier']}** | {'·'.join(e['customers'])} | "
            f"{won(e.get('amount'))} | {'설비·장비' if e.get('equipment') else '부품·모듈'} |")
    lines.append("")
    lines.append(f"- 금액 공개분 합계: **{total/1e8:,.0f}억원**")
    if site:
        lines.append(f"- 대시보드: {site}")
    return "\n".join(lines)


def to_slack(md, webhook):
    import httpx
    r = httpx.post(webhook, json={"text": md}, timeout=30)
    return r.status_code, r.text[:120]


def to_github_issue(md, title):
    import httpx
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not (token and repo):
        return None
    r = httpx.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": md, "labels": ["radar-alert"]},
        timeout=30,
    )
    return r.status_code, r.json().get("html_url", "") if r.status_code < 300 else r.text[:160]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/new_events.json"
    site = os.getenv("RADAR_SITE_URL", "")
    try:
        new_events = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        print(f"신규 이벤트 파일을 읽을 수 없음: {exc}")
        return 0
    if not new_events:
        print("[ALERT] 신규 계약 없음")
        return 0
    md = render(new_events, site)
    print(md)
    webhook = os.getenv("SLACK_WEBHOOK_URL", "")
    if webhook:
        print("slack:", to_slack(md, webhook))
    res = to_github_issue(md, f"[레이더] 신규 계약 {len(new_events)}건")
    if res:
        print("issue:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
