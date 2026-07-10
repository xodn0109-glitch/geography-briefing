# 지리 브리핑 아카이브

매일 아침 텔레그램으로 발송되는 지리 브리핑의 **깊이 읽기(long-form)** 판입니다.
짧은 요약에서 잘려나간 방법론·수치·배경을 원문에서 다시 살려 분야별로 정리합니다.

**사이트:** https://xodn0109-glitch.github.io/geography-briefing

## 구조

- `data/YYYY-MM-DD.json` — 하루 한 파일. 기사별 분야·요약·본문(소제목별)·연구진·저널·이야깃거리·태그·원문 URL.
- `build.py` — `data/*.json`을 모두 읽어 자기완결형 `index.html` 한 장을 생성. 표준 라이브러리만 사용.
- `index.html` — 생성물. 분야 필터·날짜별 그룹·펼치기·다크모드.

## 갱신

브리핑 봇이 매일 그날치 JSON을 `data/`에 쓰고 아래를 실행하면 사이트가 갱신됩니다.

```
python3 build.py
git add -A && git commit -m "brief: YYYY-MM-DD" && git push
```

GitHub Pages가 push를 감지해 자동 재배포합니다.
