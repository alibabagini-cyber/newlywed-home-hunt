#!/usr/bin/env python3
"""
loan_compare.py — 금융감독원 금융상품한눈에 대출상품 비교

신혼집 자금계획용: 주택담보대출 / 전세자금대출 / 개인신용대출 금리를 은행·2금융권에서
한 번에 뽑아 최저금리순으로 비교한다. 출처: 금융감독원 finlife.fss.or.kr Open API.

키: 환경변수 FSS_FINLIFE_KEY (repo엔 .env.example 자리만, 실제 키는 .env). HTTPS 전용.

사용 예:
  python3 loan_compare.py --kind mortgage --limit 10
  python3 loan_compare.py --kind jeonse --group bank
  python3 loan_compare.py --kind credit --group all

금리 단위: %
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.parse, urllib.request, time

BASE = "https://finlife.fss.or.kr/finlifeapi"

ENDPOINTS = {
    "mortgage": "mortgageLoanProductsSearch.json",   # 주택담보대출
    "jeonse":   "rentHouseLoanProductsSearch.json",  # 전세자금대출
    "credit":   "creditLoanProductsSearch.json",     # 개인신용대출
}

# 권역 코드 (topFinGrpNo)
GROUPS = {
    "bank": ["020000"],           # 은행
    "sb":   ["030300"],           # 저축은행
    "insu": ["050000"],           # 보험
    "card": ["060000"],           # 여신전문(카드/캐피탈)
    "all":  ["020000", "030300", "050000", "060000"],
}


def _get(url: str, timeout: int = 30, retries: int = 4) -> dict:
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 newlywed-home-hunt/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
            if not body.strip():
                raise ValueError("empty reply")
            return json.loads(body)
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last if last else RuntimeError("request failed")


def fetch(kind: str, group_codes: list[str], key: str) -> tuple[list[dict], list[dict]]:
    """(baseList=상품, optionList=금리옵션) 병합해서 반환."""
    base_all, opt_all = [], []
    ep = ENDPOINTS[kind]
    for gcode in group_codes:
        page = 1
        while True:
            url = f"{BASE}/{ep}?" + urllib.parse.urlencode(
                {"auth": key, "topFinGrpNo": gcode, "pageNo": page})
            try:
                data = _get(url)
            except Exception as e:
                print(f"[warn] {gcode} p{page} 실패: {e}", file=sys.stderr)
                break
            res = data.get("result", {})
            if res.get("err_cd") not in ("000", None):
                print(f"[warn] {gcode}: {res.get('err_msg')}", file=sys.stderr)
                break
            base_all.extend(res.get("baseList") or [])
            opt_all.extend(res.get("optionList") or [])
            if page >= (res.get("max_page_no") or 1):
                break
            page += 1
    return base_all, opt_all


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_rows(kind: str, base: list[dict], opts: list[dict]) -> list[dict]:
    """상품(base) + 금리옵션(opt)을 조인. 상품별 대표금리 행 생성.

    - mortgage/jeonse: 옵션의 lend_rate_min(최저 대출금리)이 대표.
    - credit: crdt_lend_rate_type='A'(대출금리)만 사용. 기준금리(B)/가산금리(C)는 제외
      (소비자가 실제 부담하는 건 A). 1등급(crdt_grad_1)과 평균(crdt_grad_avg)을 표시.
    """
    by_key: dict[tuple, list[dict]] = {}
    for o in opts:
        k = (o.get("fin_co_no"), o.get("fin_prdt_cd"))
        by_key.setdefault(k, []).append(o)

    rows = []
    for b in base:
        k = (b.get("fin_co_no"), b.get("fin_prdt_cd"))
        os_ = by_key.get(k, [])
        rep_rate = None      # 대표금리(정렬 기준)
        avg_rate = None      # 신용대출 평균금리(참고)
        rate_note = ""

        if kind == "credit":
            # 실제 대출금리 타입(A)만
            a_opts = [o for o in os_ if o.get("crdt_lend_rate_type") == "A"]
            g1 = [v for o in a_opts if (v := _num(o.get("crdt_grad_1"))) is not None]
            gavg = [v for o in a_opts if (v := _num(o.get("crdt_grad_avg"))) is not None]
            rep_rate = min(g1) if g1 else (min(gavg) if gavg else None)
            avg_rate = min(gavg) if gavg else None
            rate_note = "1등급 기준" if g1 else ("평균" if gavg else "")
        else:
            mins = [v for o in os_ if (v := _num(o.get("lend_rate_min"))) is not None]
            rep_rate = min(mins) if mins else None
            rate_note = "최저"

        rows.append({
            "company": b.get("kor_co_nm", "").strip(),
            "product": b.get("fin_prdt_nm", "").strip(),
            "join_way": b.get("join_way", "").strip(),
            "min_rate": rep_rate,
            "avg_rate": avg_rate,
            "rate_note": rate_note,
            "month": b.get("dcls_month", ""),
            "prepay_fee": (b.get("erly_rpay_fee", "") or "").replace("\n", " ")[:60],
        })
    rows.sort(key=lambda x: (x["min_rate"] is None, x["min_rate"] if x["min_rate"] is not None else 99))
    return rows


KIND_KO = {"mortgage": "주택담보대출", "jeonse": "전세자금대출", "credit": "개인신용대출"}


def main():
    ap = argparse.ArgumentParser(description="금감원 금융상품한눈에 대출 비교 (HTTPS 전용)")
    ap.add_argument("--kind", choices=list(ENDPOINTS), required=True,
                    help="mortgage=주담대 / jeonse=전세대출 / credit=신용대출")
    ap.add_argument("--group", choices=list(GROUPS), default="bank",
                    help="bank(기본)/sb(저축은행)/insu(보험)/card/all")
    ap.add_argument("--limit", type=int, default=15, help="출력 건수")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("FSS_FINLIFE_KEY", "")
    if not key:
        print("[error] FSS_FINLIFE_KEY 환경변수가 없음. .env 확인 "
              "(발급: https://finlife.fss.or.kr → 오픈API 인증키)", file=sys.stderr)
        sys.exit(2)

    base, opts = fetch(args.kind, GROUPS[args.group], key)
    rows = build_rows(args.kind, base, opts)

    if args.json:
        print(json.dumps({"kind": args.kind, "count": len(rows), "rows": rows[:args.limit]},
                         ensure_ascii=False, indent=2))
        return

    grp_ko = {"bank": "은행", "sb": "저축은행", "insu": "보험", "card": "여신전문", "all": "전체권역"}[args.group]
    print(f"■ {KIND_KO[args.kind]} · {grp_ko} · 최저금리순 (출처: 금감원 금융상품한눈에)")
    print("=" * 80)
    for i, r in enumerate(rows[:args.limit], 1):
        rate = f"{r['min_rate']:.2f}%" if r["min_rate"] is not None else "  -  "
        note = f" ({r['rate_note']})" if r.get("rate_note") else ""
        print(f"{i:>2}. [{rate:>7}]{note} {r['company'][:16]:<16} {r['product'][:30]}")
        if r["join_way"]:
            print(f"      가입: {r['join_way'][:40]}")
    print("-" * 80)
    print(f"기준월: {rows[0]['month'] if rows else '-'} · 총 {len(rows)}개 상품")
    print("※ 공시 최저금리. 실제 적용금리는 신용도·담보·우대조건에 따라 달라짐. 상담 시 재확인 필수.")


if __name__ == "__main__":
    main()
