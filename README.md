# KR Morning Briefing (뉴스 + 증시 요약)

이 리포는 매일 아침(한국 시간) 다음 산출물을 자동 생성합니다.
- briefing.json: 단축어에서 읽는 데이터(JSON)
- briefing.html: 클릭 가능한 브리핑 페이지(제목 탭하면 원문 기사)

포함 내용
- 뉴스: 경제/정치/연예/증시 (Google News RSS, 키 없음)
- 상한가: 전일 상한가 추정(뉴스 휴리스틱)
- 섹터 추천: data/sectors.json 기반

사용법
1) 이 구조로 파일 생성 후 커밋
2) Actions 탭 Enable → Run workflow 실행(또는 스케줄 자동)
3) 생성된 파일
   - JSON Raw: https://raw.githubusercontent.com/계정/리포명/main/briefing.json
   - HTML Raw: https://raw.githubusercontent.com/계정/리포명/main/briefing.html
   - (GitHub Pages 사용 시) https://계정.github.io/리포명/briefing.html

단축어 팁
- URL → URL 콘텐츠 가져오기(응답: JSON) → 입력에서 사전 가져오기
- 뉴스: news.economy / politics / entertainment / market
- 상한가: limit_up 배열(각 항목: name, reason)
- 섹터: sectors 사전 + sector_order 배열

변경 포인트
- 뉴스 개수: scripts/make_briefing.py 의 MAX_HEADLINES_PER_CAT
- 섹터 편집: data/sectors.json
