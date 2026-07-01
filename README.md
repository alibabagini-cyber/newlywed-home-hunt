# 신혼집 탐색 툴킷 (Newlywed Home Hunt)

한국에서 신혼집·첫 집을 알아볼 때 쓰는 3단 CLI 툴킷입니다.

- **실거래가 조회** — 국토교통부 신고 데이터로 아파트 실거래가 확인
- **지역 비교** — 후보 동네를 "실거주형 / 투자형" 두 관점으로 순위
- **대출 비교** — 금융감독원 데이터로 주택담보/전세/신용대출 금리 비교

Python 표준 라이브러리만 쓰고, 실거래 조회는 **API 키 없이 바로** 됩니다.
Claude Code(또는 다른 코딩 에이전트)에 스킬로 넣어두면 자연어로 물어봐도 알아서 씁니다.

---

## 빠른 시작

### 1. 준비물
- Python 3.9 이상 (`python3 --version`으로 확인)
- 인터넷 연결
- (대출 비교만) 금융감독원 무료 API 키

### 2. 실거래·지역비교는 바로 실행

```bash
# 고척동 84㎡ 최근 6개월 실거래
python3 scripts/realprice_search.py --region 고척동 --area 84 --months 6

# 여러 동네 투자형으로 비교
python3 scripts/compare_areas.py --area 84 --budget 80000 \
    --regions 고척동 개봉동 천왕동 --lens invest
```

### 3. 대출 비교는 키 한 번만 넣기

1. https://finlife.fss.or.kr 접속 → 회원가입/로그인
2. 상단 "오픈API" → "인증키 신청" (무료, 보통 즉시 발급)
3. 발급받은 키를 넣기:

```bash
cp .env.example .env
# .env 파일 열어서 FSS_FINLIFE_KEY=발급받은키 입력

# 실행 전에 키 불러오기
set -a; source .env; set +a

python3 scripts/loan_compare.py --kind mortgage --group bank
```

---

## 사용법

### 실거래가 조회 (realprice_search.py)

| 옵션 | 설명 | 예시 |
|---|---|---|
| `--region` | 지역명 (동/구) | `고척동`, `구로구` |
| `--area` | 평형 | `59`, `84`, `114` |
| `--months` | 최근 N개월 | `6` |
| `--min-price` / `--max-price` | 예산 (만원) | `60000` = 6억 |
| `--limit` | 출력 건수 | `10` |

```bash
python3 scripts/realprice_search.py --region 신길동 --area 59 --max-price 90000
```

### 지역 비교 (compare_areas.py)

```bash
# 실거주형(가격+생활편의)
python3 scripts/compare_areas.py --area 59 --budget 70000 \
    --regions 신길동 대방동 신대방동 --lens live

# 투자형(재개발 업사이드) + 재개발 점수 직접 조정
python3 scripts/compare_areas.py --area 84 \
    --regions 고척동 개봉동 --lens invest --redev 고척동=5 개봉동=4
```

### 대출 비교 (loan_compare.py)

```bash
python3 scripts/loan_compare.py --kind mortgage --group bank   # 주택담보대출
python3 scripts/loan_compare.py --kind jeonse --group all      # 전세자금대출
python3 scripts/loan_compare.py --kind credit --group bank     # 신용대출
```

`--group`: `bank`(은행) / `sb`(저축은행) / `insu`(보험) / `card`(여신) / `all`(전체)

---

## 꼭 알아두기

- 실거래가는 **국토부 신고가** 기준입니다. 지금 부동산에 나온 호가와 다를 수 있어요.
- 대출 금리는 **공시 금리**입니다. 실제 받는 금리는 신용점수·담보·우대조건에 따라 달라집니다.
  최종 결정 전에 은행 상담으로 꼭 재확인하세요.
- 가격 단위는 만원입니다 (71000 = 7억 1천만원).

## 데이터 출처

- 아파트 실거래가: 국토교통부 실거래가 공개시스템 (data.go.kr)
- 지역코드 프록시: k-skill-proxy (공개 프록시, 키 대행)
- 대출 상품/금리: 금융감독원 금융상품한눈에 (finlife.fss.or.kr)

## 라이선스

MIT
