# KR Morning Briefing (뉴스 + 증시 요약)

이 리포는 매일 아침(한국 시간) 다음 내용을 담은 `briefing.json`을 자동 생성합니다.
- 뉴스: 경제/정치/연예/증시 카테고리별 상위 기사 (Google News RSS, 키 없음)
- 상한가: 전일 기준 '상한가' 관련 뉴스로 종목/이슈 추출(휴리스틱)
- 섹터 추천: data/sectors.json의 섹터/종목 리스트

주의
- 상한가 종목/이유는 뉴스 기반 추정이라 100% 정확하진 않습니다. 필요 시 증권사 API로 개선 가능.
- 주말엔 last_trading_day가 금요일로 표기됩니다.

## 사용법
1) 이 구조로 파일 생성 후 커밋
2) Actions 탭에서 워크플로 Enable → Run workflow 수동 실행(또는 스케줄 자동)
3) 리포 루트에 briefing.json 생성 → Raw 링크를 아이폰 단축어에서 사용
   - 예: https://raw.githubusercontent.com/계정/리포명/main/briefing.json

## 단축어 팁
- URL → URL 콘텐츠 가져오기(응답: JSON) → 입력에서 사전 가져오기
- 뉴스: news.economy/politics/entertainment/market 사용
- 상한가: limit_up 배열(각 항목: name, reason)
- 섹터: sectors 사전 + sector_order 배열

## 변경 포인트
- 뉴스 개수: scripts/make_briefing.py의 MAX_HEADLINES_PER_CAT
- 섹터: data/sectors.json 수정
