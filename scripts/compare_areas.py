#!/usr/bin/env python3
"""
compare_areas.py — 여러 후보 지역을 실거래 데이터 + 가중 스코어로 비교

원본 신혼집 탐색(2026-05)에서 쓴 이중렌즈 랭킹을 재현:
  - 실거주형(live): 가격 접근성 + 신축도(생활 편의)
  - 투자형(invest): 재개발 업사이드 + 가격여력(선반영 덜 됨)

각 지역의 실거래를 자동 수집해 평형대 가격 통계를 뽑고,
사용자가 준 정성 점수(재개발 기대)와 합쳐 순위를 낸다.

사용 예:
  python3 compare_areas.py --area 84 --budget 80000 \
      --regions 고척동 개봉동 천왕동 온수동 --lens invest
  python3 compare_areas.py --area 59 --budget 70000 --regions 신길동 대방동 --lens live

가중치 (원본 세션 기준):
  invest: 재개발 0.5 / 평형적합(가격여력) 0.3 / 가격접근성 0.2
  live  : 가격접근성 0.5 / 신축도 0.3 / 재개발 0.2
"""
from __future__ import annotations
import argparse, sys, statistics
import realprice_search as rp

# 후보 지역별 재개발 기대 점수(1~5). 원본 세션 판단 시드 — 사용자가 --redev로 덮어쓸 수 있음.
DEFAULT_REDEV: dict[str, float] = {
    "노량진동": 5, "흑석동": 5, "대방동": 4, "신길동": 4, "보라매": 4, "신대방동": 4,
    "개봉동": 5, "고척동": 5, "천왕동": 3, "온수동": 3, "오류동": 4, "구로동": 3,
    "신도림동": 2, "상도동": 3, "봉천동": 3, "신림동": 3, "가산동": 3, "독산동": 4,
}


def area_stats(region: str, area: int, months: int) -> dict | None:
    hit = rp.resolve_lawd(region)
    if not hit:
        return None
    lawd, name = hit
    items = []
    for ym in rp.months_back(months):
        for it in rp.fetch_proxy(lawd, ym):
            it["ym"] = ym
            items.append(it)
    items = rp.dedupe(items)
    # 동 단위 입력이면 그 동으로 필터
    if region.endswith("동"):
        items = [x for x in items if x.get("district") == region]
    lo, hi = rp.AREA_BANDS.get(area, (area - 5, area + 8))
    band = [x for x in items if lo <= (x.get("area_m2") or 0) <= hi and (x.get("price_10k") or 0) > 0]
    if not band:
        return {"region": region, "name": name, "count": 0}
    prices = sorted(x["price_10k"] for x in band)
    builds = [x.get("build_year") or 0 for x in band if x.get("build_year")]
    return {
        "region": region, "name": name, "count": len(band),
        "min": prices[0], "median": prices[len(prices) // 2], "max": prices[-1],
        "avg_build": round(statistics.mean(builds)) if builds else 0,
    }


def normalize(vals: list[float], invert: bool = False) -> list[float]:
    """0~1 정규화. invert=True면 작을수록 높은 점수(가격 등)."""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    out = [(v - lo) / (hi - lo) for v in vals]
    return [1 - o for o in out] if invert else out


def main():
    ap = argparse.ArgumentParser(description="후보 지역 실거래 비교 + 가중 스코어 랭킹")
    ap.add_argument("--regions", nargs="+", required=True, help="비교할 지역명 리스트")
    ap.add_argument("--area", type=int, default=84, help="평형 (기본 84)")
    ap.add_argument("--budget", type=int, help="예산 상한 (만원). 접근성 점수 기준")
    ap.add_argument("--months", type=int, default=4, help="최근 N개월 (기본 4)")
    ap.add_argument("--lens", choices=["live", "invest"], default="invest",
                    help="live=실거주형, invest=투자형(기본)")
    ap.add_argument("--redev", nargs="*", default=[],
                    help="재개발 점수 덮어쓰기 (예: 고척동=5 개봉동=4)")
    args = ap.parse_args()

    redev = dict(DEFAULT_REDEV)
    for kv in args.redev:
        if "=" in kv:
            k, v = kv.split("=", 1)
            try:
                redev[k] = float(v)
            except ValueError:
                pass

    stats = []
    for r in args.regions:
        s = area_stats(r, args.area, args.months)
        if s and s.get("count", 0) > 0:
            stats.append(s)
        else:
            print(f"[skip] {r}: 실거래 없음/조회 실패", file=sys.stderr)

    if not stats:
        print("비교할 데이터가 없음.", file=sys.stderr)
        sys.exit(2)

    medians = [s["median"] for s in stats]
    builds = [s["avg_build"] for s in stats]
    redevs = [redev.get(s["region"], 3) for s in stats]

    price_access = normalize(medians, invert=True)   # 쌀수록↑
    newness = normalize(builds)                        # 신축일수록↑
    redev_n = normalize([float(x) for x in redevs])    # 재개발 기대↑
    headroom = price_access                            # 가격여력 = 접근성과 동일 축

    if args.lens == "invest":
        w = {"redev": 0.5, "headroom": 0.3, "access": 0.2}
        scores = [w["redev"] * redev_n[i] + w["headroom"] * headroom[i] + w["access"] * price_access[i]
                  for i in range(len(stats))]
    else:  # live
        w = {"access": 0.5, "new": 0.3, "redev": 0.2}
        scores = [w["access"] * price_access[i] + w["new"] * newness[i] + w["redev"] * redev_n[i]
                  for i in range(len(stats))]

    ranked = sorted(zip(scores, stats, redevs), key=lambda x: -x[0])

    lens_ko = "투자형(재개발 업사이드)" if args.lens == "invest" else "실거주형(가격+생활편의)"
    print(f"■ {args.area}㎡ 비교 · 렌즈={lens_ko} · 최근 {args.months}개월")
    if args.budget:
        print(f"  예산 상한: {args.budget/10000:.1f}억")
    print("=" * 78)
    for rank, (score, s, rd) in enumerate(ranked, 1):
        within = ""
        if args.budget:
            within = "예산내" if s["median"] <= args.budget else "예산초과"
        print(f"{rank}. {s['region']:<8} 점수 {score:.2f} | "
              f"중위 {s['median']/10000:.2f}억 (최저 {s['min']/10000:.1f}~최고 {s['max']/10000:.1f}) | "
              f"평균준공 {s['avg_build']}년 | 재개발 {rd:.0f}/5 | {s['count']}건 {within}")
    print("-" * 78)
    top = ranked[0][1]
    print(f"→ {lens_ko} 1순위: {top['region']} (중위 {top['median']/10000:.2f}억)")
    print("※ 국토부 실거래 신고 기준. 현재 매물 호가와 다를 수 있음. 재개발 점수는 정성 시드값(--redev로 조정).")


if __name__ == "__main__":
    main()
