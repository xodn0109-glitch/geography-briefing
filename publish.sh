#!/usr/bin/env bash
# 지리 뉴스 브리핑 아카이브 — 사이트 발행(빌드→커밋→푸시) 원자적 실행.
# SKILL.md 9단계에서 호출한다. 매일 브리핑을 보낸 뒤 반드시 실행되어야 한다.
#
# 사용법:  bash publish.sh [YYYY-MM-DD]
#   날짜 인자를 주면 커밋 메시지에 쓰고, 생략하면 오늘 날짜를 쓴다.
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

# 1) 빌드 — data/*.json → index.html
if ! python3 build.py; then
  echo "PUBLISH: build.py 실패"
  exit 1
fi

# 2) 스테이징. 변경이 없으면 커밋 없이 성공 종료.
git add -A
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
  echo "PUBLISH: 완료 (${DATE})"
  git log --oneline -1
  exit 0
fi

echo "PUBLISH: git push 1차 실패 — gh auth setup-git 후 재시도"
gh auth setup-git 2>/dev/null || true
if git push; then
  echo "PUBLISH: 완료 (${DATE}, 재시도 성공)"
  git log --oneline -1
  exit 0
fi

echo "PUBLISH: git push 최종 실패 — 커밋은 로컬에 남음(다음 실행이 자동 포함해 발행)"
exit 2
