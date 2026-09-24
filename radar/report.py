# -*- coding: utf-8 -*-
"""수집 결과 -> 마크다운 샘플 리포트."""
from __future__ import annotations

import datetime as dt


def won(amount):
    if not amount:
        return "미공개"
    if amount >= 1e12:
        return f"{amount/1e12:,.2f}조원"
    return f"{amount/1e8:,.0f}억원"


def bucket(e):
    return "설비/장비" if e["equipment"] else "부품(참고)"


def render(events, title="현대모비스·현대트랜시스 배터리 계약 레이더", days=365):
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    cutoff = (now - dt.timedelta(days=days)).date()
    recent = [e for e in events if dt.date.fromisoformat(e["date"]) >= cutoff]
    equip = [e for e in recent if e["equipment"]]
    parts = [e for e in recent if not e["equipment"]]

    L = []
    L.append(f"# {title}")
    L.append("")
    L.append(f"- 생성시각: {now:%Y-%m-%d %H:%M} KST")
    L.append(f"- 집계구간: 최근 {days}일 ({cutoff} 이후)")
    L.append(f"- 총 계약 이벤트: **{len(recent)}건** (설비/장비 {len(equip)}건 · 부품 {len(parts)}건)")
    disclosed = sum(e["amount"] or 0 for e in recent)
    L.append(f"- 금액 공개분 합계: **{disclosed/1e8:,.0f}억원** "
             f"(금액 미공개 {sum(1 for e in recent if not e['amount'])}건)")
    L.append("")

    if recent:
        L.append("## 요약 (최근 3개월)")
        last90 = (now - dt.timedelta(days=90)).date()
        r90 = [e for e in recent if dt.date.fromisoformat(e["date"]) >= last90]
        for e in r90:
            L.append(f"- **{e['date']}** {e['supplier']} → {'·'.join(e['customers'])} "
                     f"**{won(e['amount'])}** [{bucket(e)}]")
        if not r90:
            L.append("- 해당 없음")
        L.append("")

    for label, subset in (("설비·장비 계약 (직접 경쟁 영역)", equip),
                          ("부품·모듈 공급계약 (참고)", parts)):
        L.append(f"## {label}")
        L.append("")
        L.append("| 계약일 | 공급사 | 발주처 | 금액 | 제목(요약) | 출처 |")
        L.append("|---|---|---|---|---|---|")
        for e in subset:
            t = e["title"].rsplit(" - ", 1)[0]
            L.append(f"| {e['date']} | **{e['supplier']}** | {'·'.join(e['customers'])} | "
                     f"**{won(e['amount'])}** | {t[:70]} | {e.get('source') or '-'} |")
        if not subset:
            L.append("| - | - | - | - | 해당 없음 | - |")
        L.append("")

    L.append("## 공급사별 누적 (집계구간 전체)")
    L.append("")
    L.append("| 공급사 | 건수 | 금액합계(공개분) | 최근계약일 |")
    L.append("|---|---|---|---|")
    agg = {}
    for e in recent:
        a = agg.setdefault(e["supplier"], {"n": 0, "sum": 0, "last": e["date"]})
        a["n"] += 1
        a["sum"] += e["amount"] or 0
        a["last"] = max(a["last"], e["date"])
    for s, a in sorted(agg.items(), key=lambda x: -x[1]["sum"]):
        L.append(f"| {s} | {a['n']} | {won(a['sum']) if a['sum'] else '미공개'} | {a['last']} |")
    L.append("")

    L.append("## 데이터 출처 및 신뢰도")
    L.append("")
    L.append("| 소스 | 내용 | 강점 | 한계 |")
    L.append("|---|---|---|---|")
    L.append("| Google News RSS | 관련 기사 수집 | 키 불필요, 수 시간~수일 선행, 비상장/미공시 계약도 포착 | 금액이 기사에 없으면 미공개, 링크가 Google 리다이렉트 |")
    L.append("| DART Open API | 상장사 단일판매·공급계약 공시 | 금액·상대방·계약기간 정확, 전수 조회 | 상장 공급사만, 비상장 발주처 공시 없음 |")
    L.append("")
    L.append("> 금액이 '미공개'인 건은 후속 단계에서 본문 정밀추출 또는 DART 공시 대조로 보강합니다.")
    return "\n".join(L)
