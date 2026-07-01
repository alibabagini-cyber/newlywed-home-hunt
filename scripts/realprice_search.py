#!/usr/bin/env python3
"""
realprice_search.py — 한국 아파트 실거래가 조회 (국토교통부 MOLIT 신고 데이터 기준)

기본 경로: k-skill-proxy 공개 프록시 (별도 API 키 불필요, zero-setup).
선택 경로: data.go.kr 본인 키 직결 (--source molit, .env DATA_GO_KR_KEY).

사용 예:
  python3 realprice_search.py --region 고척동 --area 84 --months 6
  python3 realprice_search.py --region 구로구 --min-price 60000 --max-price 80000
  python3 realprice_search.py --lawd 11530 --district 고척동 --area 59

가격 단위: price_10k = 만원 (예: 71000 = 7억 1천만원)
"""
from __future__ import annotations
import argparse, json, sys, urllib.parse, urllib.request, urllib.error, datetime, os

PROXY_BASE = os.environ.get("KSKILL_PROXY_BASE_URL", "https://k-skill-proxy.nomadamas.org")
MOLIT_BASE = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev"


def _get(url: str, timeout: int = 30, retries: int = 4) -> str:
    import time
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": "newlywed-home-hunt/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:  # rate limited → exponential backoff
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(1.0)
    raise last if last else RuntimeError("request failed")


def resolve_lawd(region: str) -> tuple[str, str] | None:
    """지역명 → (lawd_cd, 정식명). 프록시 region-code 사용. '동' 단위는 구 단위로 넓혀 재시도."""
    def _q(q):
        url = f"{PROXY_BASE}/v1/real-estate/region-code?" + urllib.parse.urlencode({"q": q})
        try:
            data = json.loads(_get(url, 20))
        except Exception:
            return None
        res = data.get("results") or []
        return (res[0]["lawd_cd"], res[0]["name"]) if res else None

    hit = _q(region)
    if hit:
        return hit
    # 여러 토큰이면 구/시/군 토큰으로 재시도 (예: "서울 구로구 고척동")
    for token in region.replace(",", " ").split():
        if token.endswith(("구", "시", "군")):
            hit = _q(token)
            if hit:
                return hit
    # 단일 '동'이면 행정구역 검색(공개 API)으로 상위 구를 해석해 재시도
    if region.endswith("동"):
        gu = _dong_to_gu(region)
        if gu:
            hit = _q(gu)
            if hit:
                return hit
    return None


def _dong_to_gu(dong: str) -> str | None:
    """동 이름 → 상위 자치구. 행정안전부 공개 주소 검색으로 해석 (키 불필요)."""
    try:
        url = "https://www.juso.go.kr/addrlink/addrLinkApi.do?" + urllib.parse.urlencode({
            "confmKey": "devU01TX0FVVEgyMDIz...",  # 데모키 자리 — 실패 시 아래 fallback
            "currentPage": 1, "countPerPage": 1, "keyword": dong, "resultType": "json",
        })
        data = json.loads(_get(url, 15))
        juso = data["results"]["juso"][0]
        return juso.get("siNm", "") and juso.get("sggNm") or None
    except Exception:
        pass
    # 오프라인 fallback: 자주 쓰는 서울 동→구 매핑 (신혼집 후보 지역 위주)
    DONG_GU = {
        "고척동": "구로구", "개봉동": "구로구", "오류동": "구로구", "구로동": "구로구",
        "신도림동": "구로구", "천왕동": "구로구", "온수동": "구로구", "항동": "구로구",
        "대방동": "동작구", "노량진동": "동작구", "상도동": "동작구", "사당동": "동작구",
        "신대방동": "동작구", "흑석동": "동작구",
        "신길동": "영등포구", "여의도동": "영등포구", "당산동": "영등포구", "문래동": "영등포구",
        "영등포동": "영등포구", "대림동": "영등포구", "양평동": "영등포구",
        "봉천동": "관악구", "신림동": "관악구", "가산동": "금천구", "독산동": "금천구",
    }
    return DONG_GU.get(dong)


def months_back(n: int) -> list[str]:
    """최근 n개월 YYYYMM 리스트 (최신순)."""
    today = datetime.date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def fetch_proxy(lawd_cd: str, ym: str) -> list[dict]:
    url = f"{PROXY_BASE}/v1/real-estate/apartment/trade?" + urllib.parse.urlencode(
        {"lawd_cd": lawd_cd, "deal_ymd": ym}
    )
    try:
        data = json.loads(_get(url, 30))
    except Exception as e:
        print(f"[warn] {ym} 조회 실패: {e}", file=sys.stderr)
        return []
    return data.get("items") or []


def fetch_molit(lawd_cd: str, ym: str, key: str) -> list[dict]:
    """data.go.kr 직결 (본인 키). 프록시와 동일 shape로 정규화."""
    url = f"{MOLIT_BASE}/getRTMSDataSvcAptTradeDev?" + urllib.parse.urlencode(
        {"serviceKey": key, "LAWD_CD": lawd_cd, "DEAL_YMD": ym, "numOfRows": 1000, "_type": "json"}
    )
    try:
        data = json.loads(_get(url, 30))
        items = data["response"]["body"]["items"]["item"]
    except Exception as e:
        print(f"[warn] MOLIT {ym} 조회 실패: {e}", file=sys.stderr)
        return []
    if isinstance(items, dict):
        items = [items]
    out = []
    for it in items:
        try:
            price = int(str(it.get("dealAmount", "")).replace(",", "").strip() or 0)
        except ValueError:
            price = 0
        out.append({
            "name": it.get("aptNm", "").strip(),
            "district": it.get("umdNm", "").strip(),
            "area_m2": float(it.get("excluUseAr", 0) or 0),
            "floor": int(it.get("floor", 0) or 0),
            "price_10k": price,
            "deal_date": f"{it.get('dealYear')}-{int(it.get('dealMonth',0)):02d}-{int(it.get('dealDay',0)):02d}",
            "build_year": int(it.get("buildYear", 0) or 0),
            "deal_type": it.get("dealingGbn", "").strip() or "-",
        })
    return out


def dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        key = (it.get("name"), it.get("area_m2"), it.get("floor"), it.get("price_10k"), it.get("deal_date"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


AREA_BANDS = {  # 평형 → (전용면적 하한, 상한)
    59: (55, 65), 74: (68, 78), 84: (75, 92), 114: (105, 125), 134: (125, 145),
}


def main():
    ap = argparse.ArgumentParser(description="한국 아파트 실거래가 조회 (MOLIT 신고 데이터)")
    ap.add_argument("--region", help="지역명 (예: 고척동, 구로구). --lawd 대신 사용")
    ap.add_argument("--lawd", help="5자리 법정동코드 (예: 11530)")
    ap.add_argument("--district", help="동 이름 필터 (예: 고척동)")
    ap.add_argument("--area", type=int, help="평형 필터 (59/74/84/114/134 중 하나 또는 임의 전용㎡ 근사)")
    ap.add_argument("--months", type=int, default=6, help="최근 N개월 (기본 6)")
    ap.add_argument("--min-price", type=int, help="최저가 (만원)")
    ap.add_argument("--max-price", type=int, help="최고가 (만원)")
    ap.add_argument("--limit", type=int, default=30, help="출력 최대 건수")
    ap.add_argument("--source", choices=["proxy", "molit"], default="proxy",
                    help="proxy=키 불필요(기본), molit=data.go.kr 본인 키(DATA_GO_KR_KEY)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    # lawd 확정
    lawd, name = args.lawd, args.lawd
    if not lawd:
        if not args.region:
            ap.error("--region 또는 --lawd 중 하나 필요")
        hit = resolve_lawd(args.region)
        if not hit:
            print(f"지역코드를 찾지 못함: {args.region}", file=sys.stderr)
            sys.exit(2)
        lawd, name = hit
        # region이 '동'이면 district 필터 자동 지정
        if args.region.endswith("동") and not args.district:
            args.district = args.region

    key = os.environ.get("DATA_GO_KR_KEY", "")
    if args.source == "molit" and not key:
        print("[error] --source molit 인데 DATA_GO_KR_KEY 환경변수가 없음", file=sys.stderr)
        sys.exit(2)

    # 수집
    all_items = []
    for ym in months_back(args.months):
        items = fetch_molit(lawd, ym, key) if args.source == "molit" else fetch_proxy(lawd, ym)
        for it in items:
            it["ym"] = ym
        all_items.extend(items)

    items = dedupe(all_items)

    # 필터
    if args.district:
        items = [x for x in items if x.get("district") == args.district]
    if args.area:
        lo, hi = AREA_BANDS.get(args.area, (args.area - 5, args.area + 8))
        items = [x for x in items if lo <= (x.get("area_m2") or 0) <= hi]
    if args.min_price:
        items = [x for x in items if (x.get("price_10k") or 0) >= args.min_price]
    if args.max_price:
        items = [x for x in items if (x.get("price_10k") or 0) <= args.max_price]

    # 랭킹: 신축 우선 → 저가 → 고층
    items.sort(key=lambda x: (-(x.get("build_year") or 0), x.get("price_10k") or 0, -(x.get("floor") or 0)))

    if args.json:
        print(json.dumps({"lawd": lawd, "name": name, "count": len(items), "items": items[:args.limit]},
                         ensure_ascii=False, indent=2))
        return

    print(f"[{name}] lawd={lawd} · 최근 {args.months}개월 · 조회 {len(items)}건")
    prices = [x["price_10k"] for x in items if isinstance(x.get("price_10k"), (int, float)) and x["price_10k"] > 0]
    if prices:
        prices_sorted = sorted(prices)
        med = prices_sorted[len(prices_sorted) // 2]
        print(f"가격요약(만원): 최저 {min(prices):,} · 중위 {med:,} · 최고 {max(prices):,}")
    print("-" * 76)
    for x in items[:args.limit]:
        eok = (x.get("price_10k") or 0) / 10000
        print(f"{x.get('name','?'):<18} {x.get('district',''):<8} "
              f"{x.get('area_m2',0):>6.1f}㎡ {x.get('floor',0):>3}층 "
              f"{eok:>6.2f}억 {x.get('build_year','?')}년 {x.get('deal_date','')}")
    if not items:
        print("(해당 조건에 실거래 없음 — 지역/기간/평형/가격 조건을 완화해 보세요)")


if __name__ == "__main__":
    main()
