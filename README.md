# KR Morning Briefing (네이버 뉴스 API + 상한가 + 섹터)

이 리포는 매일 아침(한국 시간) `briefing.json`을 생성합니다.

포함 내용
- 뉴스: 네이버 뉴스 Open API(키 제공 시) → 실패/미제공 시 네이버 RSS 8카테고리 폴백
  - politics(정치), economy(경제), society(사회), culture(문화),
    world(세계), technology(기술), entertainment(연예), sports(스포츠)
  - 카테고리당 최대 9건
- 상한가: 네이버 금융 상한가 페이지 파싱(실제 상한가 Top10)
- 섹터 추천: data/sectors.json 기반

## 네이버 뉴스 Open API 사용(선택)
- GitHub 리포지토리 → Settings → Secrets and variables → Actions → New repository secret
  - NAVER_CLIENT_ID
  - NAVER_CLIENT_SECRET
- 키가 없으면 자동으로 네이버 RSS(8카테고리)로 폴백합니다.

## 상한가(네이버 API 여부)
- 네이버 공식 상한가 Open API는 없습니다.
- 본 리포는 https://finance.naver.com/sise/sise_upper.naver 페이지를 파싱해 실제 상한가 종목 10개를 제공합니다.
  - 더 정확한 공식 데이터가 필요하면 KRX/증권사 API(키 필요)로 변경 가능합니다.

## 결과(JSON)
- news: 카테고리별 [{title, url, src}]
- limit_up: 실제 상한가 10개 [{name, reason:""}] (reason은 빈 문자열)
- sectors: 섹터명 → 종목 배열
- sector_order: 섹터 표시 순서(없으면 단축어에서 기본목록 사용)

## 단축어 연결 팁
- catmap/catkeys를 8개 키로 교체
  - catmap: { politics:'정치', economy:'경제', society:'사회', culture:'문화', world:'세계', technology:'기술', entertainment:'연예', sports:'스포츠' }
  - catkeys: [politics, economy, society, culture, world, technology, entertainment, sports]
- 상한가: limit_up 반복에서 name만 말하기
- 섹터: sectors/sector_order 그대로 사용

## 스케줄
- UTC 일~목 22:20 (KST 월~금 07:20) 자동 실행
