#!/usr/bin/env bash
# 지리 뉴스 브리핑 아카이브 — 사이트 발행(빌드→커밋→푸시) 원자적 실행.
# SKILL.md 8절에서 호출한다. 매일 브리핑을 보낸 뒤 반드시 실행되어야 한다.
#
# 사용법:  bash publish.sh [YYYY-MM-DD]
#   인자는 검증·커밋에 함께 쓰는 브리핑 날짜다. 생략하면 로컬 오늘 날짜.
#
# 설계 원칙:
#   - 공개 allowlist만 stage하되 모든 추적·현재 날짜 JSON을 포함해 이전 회차가
#     놓친 데이터도 자동으로 따라잡는다(self-healing).
#   - 과거 data 삭제와 upstream 이후 각 커밋의 비공개 경로를 거부한다.
#   - 새 변경이 없어도 push를 실행해 이전 회차의 미전송 로컬 커밋을 복구한다.
#   - origin의 현재 추적 브랜치 하나만 명시적 refspec으로 push한다.
#   - 푸시가 인증으로 막히면 gh 자격증명 설정 후 1회 재시도.
#   - 최종 실패해도 커밋은 로컬에 남아 다음 실행이 포함해 발행한다.
#
# 종료 코드:  0=완료 또는 변경없음 / 1=빌드·커밋 실패 / 2=푸시 실패(커밋은 보존)
# 마지막 출력 줄의 'PUBLISH:' 마커로 결과를 판별하라.

set -uo pipefail
export GIT_NO_REPLACE_OBJECTS=1
export PYTHONDONTWRITEBYTECODE=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)" || {
  echo "PUBLISH: 사이트 폴더 확인 실패"
  exit 1
}
SCRIPT_PATH="${SCRIPT_DIR}/$(basename "$0")"
if [[ "${GEOGRAPHY_PUBLICATION_LOCK_HELD:-}" != "1" ]]; then
  exec python3 "${SCRIPT_DIR}/../.agents/skills/daily-geography-briefing/scripts/publication_lock.py" -- \
    env GEOGRAPHY_PUBLICATION_LOCK_HELD=1 bash "$SCRIPT_PATH" "$@"
fi
cd "$SCRIPT_DIR" || { echo "PUBLISH: 사이트 폴더 진입 실패"; exit 1; }

DATE="${1:-$(date +%Y-%m-%d)}"

validate_public_path() {
  local changed_path="$1"
  local scope="$2"
  if [[ "$changed_path" =~ ^data/[0-9]{4}-[0-9]{2}-[0-9]{2}\.json$ ]]; then
    return 0
  fi
  case "$changed_path" in
    .gitignore|README.md|build.py|check_curriculum.py|check_titles.py|index.html|publish.sh|world_land_path.txt)
      return 0
      ;;
    *)
      echo "PUBLISH: 공개 allowlist 밖의 ${scope} 경로가 있어 발행 중단"
      return 1
      ;;
  esac
}

validate_staged_paths() {
  local changed_path
  local -a pipeline_status
  git diff --cached --name-only -z --diff-filter=ACDMRTUXB | while IFS= read -r -d '' changed_path; do
    validate_public_path "$changed_path" "staged" || exit 1
  done
  pipeline_status=("${PIPESTATUS[@]}")
  if [[ "${pipeline_status[0]}" -ne 0 ]]; then
    echo "PUBLISH: staged 경로 확인 실패"
    return 1
  fi
  if [[ "${pipeline_status[1]}" -ne 0 ]]; then
    return 1
  fi
  git diff --cached --quiet --diff-filter=D -- 'data/*.json'
  local deletion_status=$?
  if [[ "$deletion_status" -eq 1 ]]; then
    echo "PUBLISH: 과거 data 삭제가 staged되어 발행 중단"
    return 1
  fi
  if [[ "$deletion_status" -ne 0 ]]; then
    echo "PUBLISH: staged data 삭제 여부 확인 실패"
    return 1
  fi
  return 0
}

validate_untracked_paths() {
  local untracked_path
  local -a pipeline_status
  git ls-files --others --exclude-standard -z | while IFS= read -r -d '' untracked_path; do
    validate_public_path "$untracked_path" "untracked" || exit 1
  done
  pipeline_status=("${PIPESTATUS[@]}")
  if [[ "${pipeline_status[0]}" -ne 0 ]]; then
    echo "PUBLISH: untracked 경로 확인 실패"
    return 1
  fi
  [[ "${pipeline_status[1]}" -eq 0 ]]
}

validate_no_tracked_data_deletions() {
  local deleted_data
  if ! deleted_data="$(git ls-files --deleted -- 'data/*.json')"; then
    echo "PUBLISH: 추적 data 삭제 여부 확인 실패"
    return 1
  fi
  if [[ -n "$deleted_data" ]]; then
    echo "PUBLISH: 과거 data 파일이 작업 폴더에서 삭제되어 발행 중단"
    return 1
  fi
  return 0
}

validate_data_path_for_run() {
  local data_path="$1"
  local context="$2"
  local data_date
  if [[ ! "$data_path" =~ ^data/([0-9]{4}-[0-9]{2}-[0-9]{2})\.json$ ]]; then
    echo "PUBLISH: ${context} data 파일명이 엄격한 날짜 형식이 아니어서 발행 중단"
    return 1
  fi
  data_date="${BASH_REMATCH[1]}"
  if [[ "$data_date" > "$DATE" ]]; then
    echo "PUBLISH: 실행 날짜보다 미래인 ${context} data 변경이 있어 발행 중단"
    return 1
  fi
  if ! python3 -B "${SCRIPT_DIR}/../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py" \
    --date "$data_date" --require-current-policy-for-date >/dev/null; then
    echo "PUBLISH: ${context} data의 현재 정책 발행 영수증 검증 실패"
    return 1
  fi
  return 0
}

validate_pending_data_date() {
  local data_path
  local -a pipeline_status
  git diff --name-only -z -- 'data/*.json' | while IFS= read -r -d '' data_path; do
    validate_data_path_for_run "$data_path" "unstaged" || exit 1
  done
  pipeline_status=("${PIPESTATUS[@]}")
  [[ "${pipeline_status[0]}" -eq 0 && "${pipeline_status[1]}" -eq 0 ]] || return 1
  git diff --cached --name-only -z -- 'data/*.json' | while IFS= read -r -d '' data_path; do
    validate_data_path_for_run "$data_path" "staged" || exit 1
  done
  pipeline_status=("${PIPESTATUS[@]}")
  [[ "${pipeline_status[0]}" -eq 0 && "${pipeline_status[1]}" -eq 0 ]] || return 1
  git ls-files --others --exclude-standard -z -- 'data/*.json' | while IFS= read -r -d '' data_path; do
    validate_data_path_for_run "$data_path" "untracked" || exit 1
  done
  pipeline_status=("${PIPESTATUS[@]}")
  [[ "${pipeline_status[0]}" -eq 0 && "${pipeline_status[1]}" -eq 0 ]]
}

validate_ahead_commit() {
  local commit="$1"
  local validated_head="$2"
  local upstream_commit="$3"
  local changed_path deleted_data
  local -a pipeline_status
  git diff-tree --root -m --no-commit-id --no-renames --name-only -r -z "$commit" | while IFS= read -r -d '' changed_path; do
    validate_public_path "$changed_path" "local-ahead commit" || exit 1
    if [[ "$changed_path" == data/*.json ]]; then
      validate_data_path_for_run "$changed_path" "local-ahead commit" || exit 1
    fi
  done
  pipeline_status=("${PIPESTATUS[@]}")
  if [[ "${pipeline_status[0]}" -ne 0 ]]; then
    echo "PUBLISH: local-ahead commit 경로 확인 실패"
    return 1
  fi
  if [[ "${pipeline_status[1]}" -ne 0 ]]; then
    return 1
  fi
  if ! deleted_data="$(git diff-tree --root -m --no-commit-id --no-renames \
    --diff-filter=D --name-only -r "$commit" -- 'data/*.json')"; then
    echo "PUBLISH: local-ahead commit data 삭제 여부 확인 실패"
    return 1
  fi
  if [[ -n "$deleted_data" ]]; then
    echo "PUBLISH: local-ahead commit에 과거 data 삭제가 있어 발행 중단"
    return 1
  fi
  # 작업 폴더가 아니라 이 커밋 자체의 공개 data blob과 index.html을 검사한다.
  # 그래야 뒤 커밋에서 되돌린 비공개 데이터나 임의 index가 push 이력에 섞이지 않는다.
  if ! python3 -B "${SCRIPT_DIR}/../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py" \
    --date "$DATE" --site-dir "$SCRIPT_DIR" --site-commit "$commit" \
    --site-head "$validated_head" --site-upstream "$upstream_commit" >/dev/null; then
    echo "PUBLISH: local-ahead commit blob/index 스냅샷 검증 실패"
    return 1
  fi
  return 0
}

validate_local_ahead_paths() {
  local upstream="$1"
  local validated_head="$2"
  local commits commit saw_head=0
  validate_git_object_view || return 1
  if ! commits="$(git rev-list "${upstream}..${validated_head}")"; then
    echo "PUBLISH: local-ahead commit 목록 확인 실패"
    return 1
  fi
  if [[ -z "$commits" ]]; then
    if [[ "$upstream" == "$validated_head" ]]; then
      validate_git_object_view
      return $?
    fi
    echo "PUBLISH: 서로 다른 고정 commit 사이의 검증 목록이 비어 발행 중단"
    return 1
  fi
  while IFS= read -r commit; do
    if [[ ! "$commit" =~ ^[0-9a-fA-F]{40,64}$ ]]; then
      echo "PUBLISH: local-ahead commit 식별자 확인 실패"
      return 1
    fi
    [[ "$commit" == "$validated_head" ]] && saw_head=1
    validate_ahead_commit "$commit" "$validated_head" "$upstream" || return 1
  done <<< "$commits"
  if [[ "$saw_head" -ne 1 ]]; then
    echo "PUBLISH: 고정 HEAD가 검증 목록에 없어 발행 중단"
    return 1
  fi
  validate_git_object_view
}

validate_git_object_view() {
  local replace_refs graft_path
  if ! replace_refs="$(git for-each-ref --format='%(refname)' refs/replace)"; then
    echo "PUBLISH: Git 대체 객체 상태 확인 실패"
    return 1
  fi
  if [[ -n "$replace_refs" ]]; then
    echo "PUBLISH: Git replace ref가 있어 발행 중단"
    return 1
  fi
  if ! graft_path="$(git rev-parse --git-path info/grafts)"; then
    echo "PUBLISH: Git graft 상태 확인 실패"
    return 1
  fi
  if [[ -f "$graft_path" && -s "$graft_path" ]]; then
    echo "PUBLISH: Git graft가 있어 발행 중단"
    return 1
  fi
  return 0
}

resolve_tracked_upstream() {
  local upstream branch
  if ! python3 "${SCRIPT_DIR}/../.agents/skills/daily-geography-briefing/scripts/validate_site_origin.py" \
    --site-dir "$SCRIPT_DIR" >/dev/null; then
    echo "PUBLISH: origin fetch/push URL이 정본 저장소가 아니어서 발행 중단"
    return 1
  fi
  if ! upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}')"; then
    echo "PUBLISH: 현재 브랜치 upstream 확인 실패"
    return 1
  fi
  if [[ ! "$upstream" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*/.+$ ]]; then
    echo "PUBLISH: 현재 브랜치 upstream 형식 확인 실패"
    return 1
  fi
  UPSTREAM_REMOTE="${upstream%%/*}"
  branch="${upstream#*/}"
  if [[ "$UPSTREAM_REMOTE" != "origin" ]]; then
    echo "PUBLISH: 현재 브랜치 upstream이 origin이 아니어서 발행 중단"
    return 1
  fi
  UPSTREAM_MERGE_REF="refs/heads/${branch}"
  if ! git check-ref-format "$UPSTREAM_MERGE_REF" >/dev/null 2>&1; then
    echo "PUBLISH: upstream 브랜치 ref 형식 확인 실패"
    return 1
  fi
  if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
    echo "PUBLISH: upstream 원격 확인 실패"
    return 1
  fi
  UPSTREAM_REV="$upstream"
  return 0
}

push_tracked_upstream() {
  local current_head
  if ! current_head="$(git rev-parse --verify 'HEAD^{commit}')"; then
    echo "PUBLISH: push 직전 HEAD 확인 실패"
    return 1
  fi
  if [[ "$current_head" != "$VALIDATED_HEAD" ]]; then
    echo "PUBLISH: 검증 뒤 HEAD가 바뀌어 push 중단"
    return 1
  fi
  git push --no-follow-tags "$UPSTREAM_REMOTE" \
    "${VALIDATED_HEAD}:$UPSTREAM_MERGE_REF"
}

pin_publication_commits() {
  if ! VALIDATED_HEAD="$(git rev-parse --verify 'HEAD^{commit}')" || \
    ! VALIDATED_UPSTREAM="$(git rev-parse --verify "${UPSTREAM_REV}^{commit}")"; then
    echo "PUBLISH: 검증할 commit 고정 실패"
    return 1
  fi
  if [[ ! "$VALIDATED_HEAD" =~ ^[0-9a-fA-F]{40,64}$ ]] || \
    [[ ! "$VALIDATED_UPSTREAM" =~ ^[0-9a-fA-F]{40,64}$ ]]; then
    echo "PUBLISH: 검증할 commit 형식 확인 실패"
    return 1
  fi
  return 0
}

stage_public_site() {
  local -a public_paths
  local tracked_path current_path
  public_paths=(
    .gitignore README.md build.py check_curriculum.py check_titles.py
    index.html publish.sh world_land_path.txt
  )
  while IFS= read -r tracked_path; do
    [[ -n "$tracked_path" ]] && public_paths+=("$tracked_path")
  done < <(git ls-files -- 'data/*.json')
  for current_path in data/*.json; do
    [[ -e "$current_path" ]] || continue
    if [[ ! "$current_path" =~ ^data/[0-9]{4}-[0-9]{2}-[0-9]{2}\.json$ ]]; then
      echo "PUBLISH: 날짜 형식 밖의 data 파일이 있어 발행 중단"
      return 1
    fi
    public_paths+=("$current_path")
  done
  git add -A -- "${public_paths[@]}" || return 1
  validate_staged_paths && validate_pending_data_date
}

# 0) 데이터 존재 확인 — data/가 비면 빈 아카이브를 발행해 버리므로 중단.
if ! validate_git_object_view; then
  exit 1
fi
if ! ls data/*.json >/dev/null 2>&1; then
  echo "PUBLISH: data/ 비어있음 — 발행 중단"
  exit 1
fi

# 0.4) 발송 판본 결합 하드 게이트 — 2026-08-24 이후 날짜 데이터는 검증된
#      LIVE 산출물, 확정 Telegram 발송 기록과 결합된 발행 영수증이 있어야 한다.
if ! python3 ../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py \
  --date "$DATE" --require-current-policy-for-date; then
  echo "PUBLISH: 발행 영수증 검증 실패 — 발행 중단"
  exit 1
fi

# 0.5) 교육과정 매칭 하드 게이트 — 규칙 위반이면 발행 자체를 막는다.
#      SKILL(프롬프트)의 규칙은 강제력이 없다: '화산→지오투어리즘'을 대표 오판으로 명시해 둔
#      상태에서도 그 오판이 실제로 발생했다(2026-07-14 감사). 그래서 여기서 코드가 막는다.
#      발행 단계에서는 어떤 JSON도 고치지 않고 읽기 전용으로 검사한다. 의미 판단은
#      eval/ 의 몫이며, 교정이 필요하면 다시 finalize한 판본으로 돌아간다.
if ! python3 check_curriculum.py; then
  echo "PUBLISH: 교육과정 검증 실패 — 발행 중단 (위 ✗ 항목을 고친 뒤 다시 실행)"
  exit 1
fi

# 0.6) 제목 단언 하드 게이트 — 제목이 자기 요약문과 모순되면 발행을 막는다.
#      2026-08-07 실제 사고: 제목 "물이 강에 없다" + 요약 "350만에 그칠 것으로 추정된다".
#      SKILL의 제목 불변식이 '수치·기간·비율'만 보고 있어 숫자 없는 이 제목은 그냥 통과했다.
#      차단은 판단이 0%인 것만 한다(과거 164건 전수 오탐 0건 실측). 문장 품질·어감은
#      경고까지만 — 코드로 판정할 수 없다.
if ! python3 check_titles.py; then
  echo "PUBLISH: 제목 검증 실패 — 발행 중단 (제목을 요약에 맞게 낮추고 다시 실행)"
  exit 1
fi

# 0.9) 빌드 직전 전수 재검증 — 앞선 게이트나 외부 작업이 데이터를 바꿨으면 차단.
if ! python3 ../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py \
  --date "$DATE" --require-current-policy-for-date; then
  echo "PUBLISH: 빌드 직전 발행 영수증 재검증 실패 — 발행 중단"
  exit 1
fi

# 1) 빌드 — data/*.json → index.html
if ! python3 build.py; then
  echo "PUBLISH: build.py 실패"
  exit 1
fi

# 2) 공개 allowlist만 스테이징. 사전 staged·untracked 경로와 과거 data 삭제도
#    같은 fail-closed 게이트로 검사한다.
if ! validate_staged_paths || ! validate_untracked_paths || \
  ! validate_no_tracked_data_deletions || ! validate_pending_data_date || \
  ! stage_public_site; then
  echo "PUBLISH: git add 실패 (동시 실행 충돌 가능성 — 다음 회차가 자동 수습)"
  exit 1
fi

# 2.1) 스테이징 직후 전수 재검증 — 검증된 JSON과 다른 판본의 커밋을 차단.
if ! python3 ../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py \
  --date "$DATE" --require-current-policy-for-date; then
  echo "PUBLISH: 스테이징 직후 발행 영수증 재검증 실패 — 발행 중단"
  exit 1
fi
# 3) 변경분만 새로 커밋한다. 변경이 없어도 여기서 종료하지 않는다. 이전 회차의
#    로컬 미푸시 커밋이 남았을 수 있으므로 아래 push까지 반드시 진행한다.
NEW_COMMIT=0
git diff --cached --quiet
DIFF_STATUS=$?
if [[ "$DIFF_STATUS" -eq 1 ]]; then
  if ! git commit -m "brief: ${DATE}"; then
    echo "PUBLISH: git commit 실패"
    exit 1
  fi
  NEW_COMMIT=1
elif [[ "$DIFF_STATUS" -ne 0 ]]; then
  echo "PUBLISH: 스테이징 변경 확인 실패"
  exit 1
else
  echo "새로 커밋할 변경 없음 — 기존 로컬 커밋의 원격 동기화 확인"
fi

if ! resolve_tracked_upstream || ! pin_publication_commits; then
  echo "PUBLISH: upstream 결합 실패 — 발행 중단"
  exit 1
fi
LOCAL_AHEAD_BEFORE_PUSH="$(git rev-list --count "${VALIDATED_UPSTREAM}..${VALIDATED_HEAD}" 2>/dev/null || true)"
if ! validate_local_ahead_paths "$VALIDATED_UPSTREAM" "$VALIDATED_HEAD"; then
  echo "PUBLISH: 미전송 로컬 커밋 공개 경로 검증 실패 — 발행 중단"
  exit 1
fi

# 4) 푸시 (1차 실패 시 gh 자격증명 설정 후 1회 재시도)
if push_tracked_upstream; then
  if [[ "$NEW_COMMIT" -eq 0 && "$LOCAL_AHEAD_BEFORE_PUSH" =~ ^[1-9][0-9]*$ ]]; then
    echo "PUBLISH: 밀린 커밋 전송 완료 (${DATE})"
  elif [[ "$NEW_COMMIT" -eq 0 ]]; then
    echo "PUBLISH: 변경 없음 (원격 동기화 확인 완료)"
  else
    echo "PUBLISH: 완료 (${DATE})"
  fi
  exit 0
fi

echo "git push 1차 실패 — 원격 동기화(rebase)·인증 재설정 후 재시도"
gh auth setup-git 2>/dev/null || true
if ! git pull --rebase --autostash 2>/dev/null; then
  echo "PUBLISH: 원격 동기화 실패 — 상태 확인 전 재푸시하지 않음(커밋은 로컬에 보존)"
  exit 2
fi
# 원격 변경이 들어온 뒤에는 앞선 검증·빌드 결과를 재사용하지 않는다.
if ! python3 ../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py \
  --date "$DATE" --require-current-policy-for-date; then
  echo "PUBLISH: 원격 동기화 뒤 발행 영수증 검증 실패 — 커밋은 로컬에 보존"
  exit 2
fi
if ! python3 check_curriculum.py || ! python3 check_titles.py || ! python3 build.py; then
  echo "PUBLISH: 원격 동기화 뒤 재검증·재빌드 실패 — 커밋은 로컬에 보존"
  exit 2
fi
if ! validate_staged_paths || ! validate_untracked_paths || \
  ! validate_no_tracked_data_deletions || ! validate_pending_data_date || \
  ! stage_public_site; then
  echo "PUBLISH: 원격 동기화 뒤 git add 실패 — 커밋은 로컬에 보존"
  exit 2
fi
if ! python3 ../.agents/skills/daily-geography-briefing/scripts/verify_finalized_artifacts.py \
  --date "$DATE" --require-current-policy-for-date; then
  echo "PUBLISH: 원격 동기화 뒤 스테이징 검증 실패 — 커밋은 로컬에 보존"
  exit 2
fi
git diff --cached --quiet
REBUILD_DIFF_STATUS=$?
if [[ "$REBUILD_DIFF_STATUS" -eq 1 ]]; then
  if ! git commit -m "brief: ${DATE} (동기화 후 재빌드)"; then
    echo "PUBLISH: 원격 동기화 뒤 재빌드 커밋 실패 — 기존 커밋은 로컬에 보존"
    exit 2
  fi
elif [[ "$REBUILD_DIFF_STATUS" -ne 0 ]]; then
  echo "PUBLISH: 원격 동기화 뒤 스테이징 변경 확인 실패 — 커밋은 로컬에 보존"
  exit 2
fi
if ! resolve_tracked_upstream || ! pin_publication_commits || \
  ! validate_local_ahead_paths "$VALIDATED_UPSTREAM" "$VALIDATED_HEAD"; then
  echo "PUBLISH: 원격 동기화 뒤 미전송 커밋 공개 경로 검증 실패 — 커밋은 로컬에 보존"
  exit 2
fi
if push_tracked_upstream; then
  echo "PUBLISH: 완료 (${DATE}, 재시도 성공)"
  exit 0
fi

echo "PUBLISH: git push 최종 실패 — 커밋은 로컬에 남음(다음 실행이 자동 포함해 발행)"
exit 2
