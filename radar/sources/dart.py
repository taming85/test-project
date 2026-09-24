# -*- coding: utf-8 -*-
"""DART(금융감독원 전자공시) 수집기 - 계약 금액의 정본 소스.

인증: https://opendart.fss.or.kr 에서 무료 API 키 발급 후
      환경변수 OPENDART_KEY (GitHub Actions: Repository secret)

동작:
  1) /api/list.json  -> 기간 내 접수된 공시 목록(report_nm, corp_name, rcept_no)
  2) report_nm 이 "단일판매·공급계약" 류인 건만 필터
  3) 공시 본문에서 계약금액/계약상대방/계약기간 추출 후 상대방이 발주처면 채택
장점: 금액이 정확하고 시점이 명확. 상장 공급사라면 누락 없이 전수 조회 가능.
"""
from __future__ import annotations

import os

import httpx

BASE = "https://opendart.fss.or.kr/api"
KEY = os.getenv("OPENDART_KEY", "")

SUPPLY_REPORT_KEYWORDS = ["단일판매", "공급계약", "수주"]


def enabled() -> bool:
    return bool(KEY)


def list_filings(start: str, end: str, page=1, count=100) -> dict:
    if not enabled():
        raise RuntimeError("OPENDART_KEY 미설정 - https://opendart.fss.or.kr 에서 발급")
    r = httpx.get(f"{BASE}/list.json", params={
        "crtfc_key": KEY, "bgn_de": start, "end_de": end,
        "page_no": page, "page_count": count,
    }, timeout=40)
    r.raise_for_status()
    return r.json()


def supply_contracts(start: str, end: str, max_pages=5) -> list[dict]:
    """기간 내 단일판매·공급계약류 공시만 반환."""
    rows = []
    for p in range(1, max_pages + 1):
        data = list_filings(start, end, page=p)
        items = data.get("list", [])
        if not items:
            break
        for it in items:
            nm = it.get("report_nm", "")
            if any(k in nm for k in SUPPLY_REPORT_KEYWORDS):
                rows.append({
                    "date": it.get("rcept_dt"),
                    "corp": it.get("corp_name"),
                    "report": nm,
                    "rcept_no": it.get("rcept_no"),
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it.get('rcept_no')}",
                })
    return rows
