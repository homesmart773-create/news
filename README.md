# KR Morning Briefing (네이버 뉴스 API + 상한가 + 섹터)

이 리포는 매일 아침(한국 시간) `briefing.json`을 자동 생성합니다.

포함 내용
- 뉴스(8개 카테고리): 네이버 검색 뉴스 Open API로 수집(키 없으면 네이버 RSS로 자동 폴백)
  - politics(정치), economy(경제), society(사회), culture(문화),
    world(세계), technology(기술), entertainment(연예), sports(스포츠)
  - 카테고리당 최대 9건
- 상한가: 네이버 금융 상한가 페이지에서 실제 상한가 종목 Top10
- 섹터 추천: data/sectors.json 기반(섹터별 목록)

## 네이버 검색 뉴스 API 설정(권장)
- GitHub Secrets에 아래 2개 등록
  - `NAVER_CLIENT_ID` : 네이버 Client ID
  - `NAVER_CLIENT_SECRET` : 네이버 Client Secret
- 등록하지 않더라도 RSS 폴백으로 동작합니다.

## 결과(JSON)
- news: 카테고리별 [{title, url, src}]
- limit_up: 실제 상한가 10개 [{name, reason:""}]
- sectors: 섹터명 → 종목 배열
- sector_order: 섹터 표시 순서(없으면 단축어에서 기본 목록 사용)

## 단축어 연결 팁
- catmap/catkeys를 아래 8개로
  - catmap: { politics:'정치', economy:'경제', society:'사회', culture:'문화', world:'세계', technology:'기술', entertainment:'연예', sports:'스포츠' }
  - catkeys: [politics, economy, society, culture, world, technology, entertainment, sports]
- 상한가: limit_up 반복에서 키=name만 말하기(이유는 사용 안 함).
- 섹터: sectors/sector_order 그대로 사용(또는 별도 단축어에서 brief를 입력으로 받아 실행).
