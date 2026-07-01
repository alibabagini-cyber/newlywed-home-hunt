---
name: newlywed-home-hunt
description: >-
  Korea newlywed / first-home hunting toolkit. Use when the user wants to
  compare Korean apartment real-transaction prices (MOLIT), rank candidate
  neighborhoods with a live-vs-invest lens, or compare mortgage / jeonse
  (lease-deposit) / credit loan rates from the FSS finlife open API.
  Triggers: 신혼집, 집 알아봐, 아파트 실거래가, 전세/매매 비교, 대출 금리 비교,
  주택담보대출, 전세자금대출, real estate price, mortgage rate compare.
license: MIT
---

# Newlywed Home Hunt (신혼집 탐색 툴킷)

한국에서 신혼집(또는 첫 집)을 알아볼 때 쓰는 3단 워크플로우를 CLI로 묶은 스킬.
국토교통부(MOLIT) 실거래 신고 데이터 + 금융감독원 금융상품한눈에 대출 데이터를 쓴다.

## When to use this skill

- "고척동 84㎡ 실거래가 얼마야?" → `realprice_search.py`
- "신길 대방 신대방 중에 어디가 나아?" → `compare_areas.py`
- "지금 전세대출 금리 제일 싼 데?" → `loan_compare.py`
- 세 개를 순서대로 쓰면: 지역 좁히기 → 매물 가격대 확인 → 대출 자금계획.

## Setup (한 번만)

1. Python 3.9+ 필요. 외부 패키지 없음 (표준 라이브러리만).
2. 실거래 조회(`realprice_search.py`, `compare_areas.py`)는 **키 없이 바로 작동**.
   공개 프록시(k-skill-proxy)가 국토부 API 키를 대신 처리한다.
3. 대출 비교(`loan_compare.py`)만 금감원 키 필요:
   - `cp .env.example .env` 후 `.env`에 `FSS_FINLIFE_KEY=발급키` 입력
   - 키 발급: https://finlife.fss.or.kr → 오픈API 인증키 신청 (무료, 즉시)
   - 실행 전 `set -a; source .env; set +a` 또는 `export FSS_FINLIFE_KEY=...`

## Workflow (권장 순서)

### 1단계 — 지역 좁히기 (compare_areas.py)
후보 동네를 실거래 데이터로 비교해 순위를 낸다. 두 렌즈 중 하나 선택:
- `--lens live` (실거주형): 가격 접근성 0.5 + 신축도 0.3 + 재개발 0.2
- `--lens invest` (투자형): 재개발 기대 0.5 + 가격여력 0.3 + 접근성 0.2

```bash
python3 scripts/compare_areas.py --area 84 --budget 80000 \
    --regions 고척동 개봉동 천왕동 --lens invest --months 4
```

### 2단계 — 매물 가격대 확인 (realprice_search.py)
1순위 지역의 실거래를 평형·예산으로 필터해 대표 후보를 본다.

```bash
python3 scripts/realprice_search.py --region 고척동 --area 84 \
    --min-price 60000 --max-price 80000 --months 6 --limit 10
```

### 3단계 — 자금계획: 대출 비교 (loan_compare.py)
매매면 주담대, 전세면 전세대출을 최저금리순으로 본다.

```bash
python3 scripts/loan_compare.py --kind mortgage --group bank --limit 10
python3 scripts/loan_compare.py --kind jeonse --group all --limit 10
python3 scripts/loan_compare.py --kind credit --group bank
```

## Decision framework

집을 고를 때 두 축을 분리해서 본다 (references/decision-checklist.md 참고):
- **실거주 가치**: 출퇴근, 생활 인프라, 신축도, 평형/구조.
- **투자 가치**: 재개발/재건축 기대, 가격 선반영 정도, 대단지 여부, 희소성.
- 예산은 매매가만이 아니라 **대출 금리 × 상환기간**까지 포함해 월 부담으로 환산.

## 데이터 정확성 주의 (중요)

- 모두 **국토부 실거래 신고가** 기준. 현재 매물 호가(부동산 사이트)와 다를 수 있다.
- 대출 금리는 **공시 금리**. 실제 적용금리는 신용도·담보·우대조건에 따라 달라진다.
- 신용대출은 `crdt_lend_rate_type=A`(실제 대출금리)만 사용. 기준금리(B)/가산금리(C)를
  섞으면 비현실적으로 낮은 값(예: 0.01%)이 나오므로 절대 혼용 금지.
- 가격 단위: `price_10k` = 만원 (71000 = 7억 1천만원).

## Files

- `scripts/realprice_search.py` — 실거래 조회 (region-code → trade → dedupe → filter → rank)
- `scripts/compare_areas.py` — 후보 지역 가중 스코어 비교 (live/invest 렌즈)
- `scripts/loan_compare.py` — 금감원 대출 3종 비교 (mortgage/jeonse/credit)
- `references/decision-checklist.md` — 실거주 vs 투자 의사결정 체크리스트
- `references/data-sources.md` — API 엔드포인트/필드/단위 레퍼런스
- `.env.example` — 대출 API 키 자리 (실제 키는 .env, git에 안 올라감)
