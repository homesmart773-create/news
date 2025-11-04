# KR Morning Briefing (뉴스 + 증시 요약)

이 리포는 매일 아침(한국 시간) 다음 파일을 자동 생성합니다.
- briefing.json: 단축어(Shortcuts)가 읽는 데이터

포함 내용
- 뉴스: 네이버 뉴스 RSS 8개 카테고리
  - politics(정치), economy(경제), society(사회), culture(문화),
    world(세계), technology(기술), entertainment(연예), sports(스포츠)
  - 각 카테고리 상위 9건
- 상한가: 네이버 금융 상한가 페이지에서 실제 상한가 종목 Top10
- 섹터 추천: data/sectors.json 기반(섹터별 목록)

주의
- 네이버 금융/뉴스 구조 변경 시 수집 로직이 영향을 받을 수 있습니다.

## 사용법
1) 이 파일 구조로 저장 후 커밋
2) Actions 탭 Enable → Run workflow 실행(또는 스케줄 자동)
3) 결과 확인
   - https://raw.githubusercontent.com/계정/리포명/main/briefing.json

## 단축어 연결 팁(뉴스 파트만 갱신)
- catmap/catkeys를 아래 8개로 교체
  - catmap: { politics: '정치', economy: '경제', society: '사회', culture: '문화', world: '세계', technology: '기술', entertainment: '연예', sports: '스포츠' }
  - catkeys: [politics, economy, society, culture, world, technology, entertainment, sports]
- 상한가(limit_up)는 name만 말하게 설정(이미 구성된 반복 안에서 키=name만 사용)
- 섹터(sectors/sector_order)는 기존 로직 그대로
