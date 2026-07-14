#!/usr/bin/env bash
# 지리 뉴스 브리핑 아카이브 — 사이트 발행(빌드→커밋→푸시) 원자적 실행.
# SKILL.md 9단계에서 호출한다. 매일 브리핑을 보낸 뒤 반드시 실행되어야 한다.
#
# 사용법:  bash publish.sh [커밋 메시지 접미사]
#   인자는 "brief: " 뒤에 그대로 붙는 자유 문구다(보통 YYYY-MM-DD). 생략하면 오늘 날짜.
#
# 설계 원칙:
#   - git add -A 로 '밀린 날짜 파일'까지 함께 쓸어 담는다 → 이전 회차가 푸시를
#     놓쳤어도 이번 실행이 자동으로 따라잡는다(self-healing).
#   - 변경이 없으면 조용히 성공 종료(빈 커밋을 만들지 않는다).
#   - 푸시가 인증으로 막히면 gh 자격증명 설정 후 1회 재시도.
#   - 최종 실패해도 커밋은 로컬에 남아 다음 실행이 포함해 발행한다.
#
# 종료 코드:  0=완료 또는 변경없음 / 1=빌드·커밋 실패 / 2=푸시 실패(커밋은 보존)
# 마지막 출력 줄의 'PUBLISH:' 마커로 결과를 판별하라.

set -uo pipefail
cd "$(dirname "$0")" || { echo "PUBLISH: 사이트 폴더 진입 실패"; exit 1; }

DATE="${1:-$(date +%Y-%m-%d)}"

# 0) 데이터 존재 확인 — data/가 비면 빈 아카이브를 발행해 버리므로 중단.
if ! ls data/*.json >/dev/null 2>&1; then
  echo "PUBLISH: data/ 비어있음 — 발행 중단"
  exit 1
fi

# 0.5) 교육과정 매칭 하드 게이트 — 규칙 위반이면 발행 자체를 막는다.
#      SKILL(프롬프트)의 규칙은 강제력이 없다: '화산→지오투어리즘'을 대표 오판으로 명시해 둔
#      상태에서도 그 오판이 실제로 발생했다(2026-07-14 감사). 그래서 여기서 코드가 막는다.
#      --fix 는 판단이 필요 없는 것(gloss 표준화·중복 제거)만 교정하고, 나머지(날조 코드·
#      기사당 3개 이상·gloss 길이)는 차단한다. 의미 판단은 eval/ 의 몫이다.
if ! python3 check_curriculum.py --fix; then
  echo "PUBLISH: 교육과정 검증 실패 — 발행 중단 (위 ✗ 항목을 고친 뒤 다시 실행)"
  exit 1
fi

# 1) 빌드 — data/*.json → index.html
if ! python3 build.py; then
  echo "PUBLISH: build.py 실패"
  exit 1
fi

# 2) 스테이징. add 실패(동시 실행 index.lock 등)가 '변경 없음' 오판으로 이어지지 않게 반드시 검사.
if ! git add -A; then
  echo "PUBLISH: git add 실패 (동시 실행 충돌 가능성 — 다음 회차가 자동 수습)"
  exit 1
fi
if git diff --cached --quiet; then
  echo "PUBLISH: 변경 없음 (이미 최신, 커밋 생략)"
  exit 0
fi

# 3) 커밋
if ! git commit -m "brief: ${DATE}"; then
  echo "PUBLISH: git commit 실패"
  exit 1
fi

# 4) 푸시 (1차 실패 시 gh 자격증명 설정 후 1회 재시도)
if git push; then
  git log --oneline -1
  echo "PUBLISH: 완료 (${DATE})"
  exit 0
fi

echo "git push 1차 실패 — 원격 동기화(rebase)·인증 재설정 후 재시도"
git pull --rebase --autostash 2>/dev/null || true
gh auth setup-git 2>/dev/null || true
if git push; then
  git log --oneline -1
  echo "PUBLISH: 완료 (${DATE}, 재시도 성공)"
  exit 0
fi

echo "PUBLISH: git push 최종 실패 — 커밋은 로컬에 남음(다음 실행이 자동 포함해 발행)"
exit 2
