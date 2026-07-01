# 데이터 소스 레퍼런스

## 1. 아파트 실거래가 — k-skill-proxy (키 불필요)

기본 base: `https://k-skill-proxy.nomadamas.org` (환경변수 `KSKILL_PROXY_BASE_URL`로 override)

### 지역코드 조회
```
GET /v1/real-estate/region-code?q={지역명}
→ {"results":[{"lawd_cd":"11530","name":"서울특별시 구로구"}]}
```
- **구/시 단위만 매칭됨.** "고척동" 같은 동 단위는 빈 결과.
  → 스크립트는 동→구 매핑 테이블(서울 신혼 후보지 위주)로 fallback 후 동 이름으로 필터.

### 실거래 조회
```
GET /v1/real-estate/apartment/trade?lawd_cd={코드}&deal_ymd={YYYYMM}
→ {"items":[{name, district, area_m2, floor, price_10k, deal_date, build_year, deal_type}]}
```
- `price_10k`: 만원 단위 (71000 = 7억 1천만원).
- **429 Too Many Requests** 자주 뜸 → exponential backoff 재시도 필수 (1.5s × 시도수).
- 다른 asset: `officetel`/`villa`/`single-house`/`commercial`, dealType: `trade`/`rent`.

## 2. 아파트 실거래가 — data.go.kr 직결 (본인 키, 선택)

`--source molit` + 환경변수 `DATA_GO_KR_KEY`.
```
GET https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev
    ?serviceKey={키}&LAWD_CD={5자리}&DEAL_YMD={YYYYMM}&numOfRows=1000&_type=json
```
- 응답 필드가 프록시와 다름(aptNm/umdNm/excluUseAr/dealAmount/dealYear...) → 스크립트가 정규화.
- 키 발급: https://www.data.go.kr → "아파트 매매 실거래가 상세 자료" 활용신청.

## 3. 대출 상품 — 금융감독원 금융상품한눈에 (본인 키)

base: `https://finlife.fss.or.kr/finlifeapi` (**HTTPS 전용 — HTTP 쓰지 말 것**)
인증: `auth={FSS_FINLIFE_KEY}`

| kind | endpoint |
|---|---|
| mortgage (주담대) | `mortgageLoanProductsSearch.json` |
| jeonse (전세대출) | `rentHouseLoanProductsSearch.json` |
| credit (신용대출) | `creditLoanProductsSearch.json` |

권역 `topFinGrpNo`: 020000(은행) / 030300(저축은행) / 050000(보험) / 060000(여신).

### 응답 구조
- `result.baseList`: 상품 메타 (kor_co_nm, fin_prdt_nm, join_way, erly_rpay_fee...)
- `result.optionList`: 금리 옵션. `(fin_co_no, fin_prdt_cd)`로 baseList와 조인.
- 페이징: `max_page_no` / `now_page_no`.

### 금리 필드 (중요 — 종류별로 다름)
- **주담대/전세**: `lend_rate_min` (최저 대출금리) 사용.
- **신용대출**: `crdt_lend_rate_type` 이 **A=대출금리 / B=기준금리 / C=가산금리** 세 종류.
  반드시 **A만** 사용. B/C를 섞으면 0.01% 같은 비현실적 최저값이 나옴.
  등급별 금리 `crdt_grad_1`(1등급) ~ `crdt_grad_avg`(평균).

### 함정
- HTTPS인데 간헐적 `Empty reply from server` → `--retry` / 재시도 루프로 해결.
- 브라우저 UA(`Mozilla/5.0`) 붙이면 안정적.
- 키 발급: https://finlife.fss.or.kr → 오픈API 인증키 신청.
