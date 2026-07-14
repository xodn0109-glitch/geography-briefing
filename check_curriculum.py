#!/usr/bin/env python3
"""교육과정 매칭 하드 게이트 — publish.sh가 빌드 직전에 호출한다.

SKILL(프롬프트)의 규칙을 '모델이 지켜주길 바라는' 대신, 여기서 **코드가 막는다**.
실제로 SKILL이 '화산→지오투어리즘'을 대표 오판으로 명시해 둔 상태에서도 그 오판이
발생했다(2026-07-14 감사). 지시문은 강제력이 없다 — 그래서 이 파일이 있다.

    python3 check_curriculum.py          # 검사만 (위반 시 exit 1)
    python3 check_curriculum.py --fix    # 안전한 것만 자동 교정 후 재검사

■ 차단(BLOCK, exit 1) — 사이트를 '틀리게' 만드는 것들
    · 날조 코드: curriculum_ref.json에 없는 코드 (환각 — 가장 위험)
    · 제외 대상: 초등(4사·6사)·일반사회(9사(일사)) 등
    · 기사당 3개 이상 (SKILL: 중·고 합계 0~2개)
    · gloss 길이 8~20자 위반
■ 자동 교정(--fix) — 판단이 필요 없는 순수 기계적 정규화
    · 한 기사 안의 코드 중복 제거
    · gloss 표준화: 어휘집(curriculum_gloss.json)의 코드당 표준 gloss로 통일.
      처음 쓰이는 코드는 길이 검사를 통과하면 어휘집에 등록되어 이후의 기준이 된다.

의미 판단('이 해설과 진짜 통하는가')은 코드로 잡을 수 없다 — 그건 eval/의 몫이다.
"""
import json, glob, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REF = os.path.join(HERE, "..", "curriculum_ref.json")
LEX = os.path.join(HERE, "..", "curriculum_gloss.json")

FIX = "--fix" in sys.argv
EXCLUDED = re.compile(r"^[46]사|일사")   # 초등·일반사회 — 지리 영역 아님

# 성취기준 원본(코드 실재성 판정용). 없으면 실재성 검사만 건너뛴다(우아한 강등).
valid = None
if os.path.exists(REF):
    ref = json.load(open(REF, encoding="utf-8"))
    valid = {s["code"] for stds in ref["subjects"].values() for s in stds}

lex = json.load(open(LEX, encoding="utf-8")) if os.path.exists(LEX) else {}
lex_before = dict(lex)

blocks, fixes = [], []
docs = {}
for p in sorted(glob.glob(os.path.join(DATA, "*.json"))):
    docs[p] = json.load(open(p, encoding="utf-8"))

for p, d in docs.items():
    for a in d.get("articles", []):
        cur = a.get("curriculum")
        if cur is None:
            blocks.append(f"{a['id']}: curriculum 키 없음")
            continue

        # [FIX] 코드 중복 제거
        seen, deduped = set(), []
        for c in cur:
            if c["code"] in seen:
                fixes.append(f"{a['id']}: 중복 코드 {c['code']} 제거")
                continue
            seen.add(c["code"])
            deduped.append(c)
        if len(deduped) != len(cur):
            a["curriculum"] = cur = deduped

        # [BLOCK] 기사당 최대 2개 — 어느 것을 버릴지는 판단이라 자동 교정하지 않는다
        if len(cur) > 2:
            codes = ", ".join(c["code"] for c in cur)
            blocks.append(f"{a['id']}: 연결 {len(cur)}개 (최대 2개) — {codes}")

        for c in cur:
            code, gloss = c.get("code", ""), c.get("gloss", "")

            if valid is not None and code not in valid:
                blocks.append(f"{a['id']}: 날조 코드 '{code}' — curriculum_ref.json에 없음 ⚠️")
                continue
            if EXCLUDED.search(code):
                blocks.append(f"{a['id']}: 제외 대상 코드 '{code}' (초등·일반사회)")
                continue

            # [FIX] gloss 표준화 — 코드당 하나
            if code in lex:
                if gloss != lex[code]:
                    fixes.append(f"{a['id']}: {code} gloss '{gloss}' → '{lex[code]}'")
                    c["gloss"] = lex[code]
            else:
                if not (8 <= len(gloss) <= 20):
                    blocks.append(f"{a['id']}: {code} gloss {len(gloss)}자 (8~20자) — '{gloss}'")
                    continue
                lex[code] = gloss          # 신규 코드 → 어휘집에 등록(이후의 표준이 됨)
                fixes.append(f"{a['id']}: {code} 신규 gloss 어휘집 등록 — '{gloss}'")

            g = c["gloss"]
            if not (8 <= len(g) <= 20):
                blocks.append(f"{a['id']}: {code} gloss {len(g)}자 (8~20자) — '{g}'")

if FIX and fixes:
    for p, d in docs.items():
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if lex != lex_before:
        with open(LEX, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(lex.items())), f, ensure_ascii=False, indent=2)
            f.write("\n")

n_art = sum(len(d.get("articles", [])) for d in docs.values())
n_link = sum(len(a.get("curriculum") or []) for d in docs.values() for a in d.get("articles", []))
print(f"교육과정 게이트 — 기사 {n_art}건 · 연결 {n_link}개 · 코드 {len(lex)}종"
      + ("" if valid is not None else "  (⚠ curriculum_ref.json 없음 — 코드 실재성 검사 생략)"))

if fixes:
    tag = "자동 교정" if FIX else "교정 필요(--fix 로 해결 가능)"
    print(f"  [{tag}] {len(fixes)}건")
    for f_ in fixes:
        print("    · " + f_)
    if not FIX:
        blocks.extend(fixes)

if blocks:
    print(f"  [차단] {len(blocks)}건 — 발행할 수 없다")
    for b in blocks:
        print("    ✗ " + b)
    sys.exit(1)

print("  통과 ✅ (날조 없음 · 기사당 ≤2 · 제외대상 없음 · gloss 코드당 하나·8~20자)")
