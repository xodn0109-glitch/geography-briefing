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
import argparse
import datetime as dt
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REF = os.path.join(HERE, "..", "curriculum_ref.json")
LEX = os.path.join(HERE, "..", "curriculum_gloss.json")

EXCLUDED = re.compile(r"^[46]사|일사")   # 초등·일반사회 — 지리 영역 아님


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result

def load_reference(ref_path=REF, lex_path=LEX):
    """Load the two fail-closed curriculum authorities."""

    missing = [path for path in (ref_path, lex_path) if not os.path.exists(path)]
    if missing:
        raise RuntimeError(
            "정본 파일 누락: " + ", ".join(os.path.basename(path) for path in missing)
        )
    try:
        with open(ref_path, encoding="utf-8") as handle:
            reference = json.load(handle, object_pairs_hook=strict_object)
        valid = {
            standard["code"]
            for standards in reference["subjects"].values()
            for standard in standards
        }
        with open(lex_path, encoding="utf-8") as handle:
            lexicon = json.load(handle, object_pairs_hook=strict_object)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError(f"정본 파일 읽기 실패({type(exc).__name__})") from exc
    if not isinstance(lexicon, dict):
        raise RuntimeError("gloss 정본은 JSON 객체여야 함")
    return valid, lexicon


def check_documents(documents, valid, lexicon, *, fix=False):
    """Return the exact BLOCK/fix result used before send and before publish."""

    lex = dict(lexicon)
    blocks, fixes = [], []
    for document in documents.values():
        articles = document.get("articles", []) if isinstance(document, dict) else []
        for article in articles:
            if not isinstance(article, dict):
                blocks.append("기사 객체 형식 오류")
                continue
            article_id = str(article.get("id", "기사 id 없음"))
            curriculum = article.get("curriculum")
            if not isinstance(curriculum, list):
                blocks.append(f"{article_id}: curriculum 키 또는 배열 형식 오류")
                continue

            seen, deduped = set(), []
            for link in curriculum:
                if not isinstance(link, dict):
                    blocks.append(f"{article_id}: curriculum 항목 형식 오류")
                    continue
                code = link.get("code", "")
                if code in seen:
                    fixes.append(f"{article_id}: 중복 코드 {code} 제거")
                    continue
                seen.add(code)
                deduped.append(link)
            if len(deduped) != len(curriculum):
                article["curriculum"] = curriculum = deduped

            if len(curriculum) > 2:
                codes = ", ".join(str(link.get("code", "")) for link in curriculum)
                blocks.append(f"{article_id}: 연결 {len(curriculum)}개 (최대 2개) — {codes}")

            for link in curriculum:
                code, gloss = link.get("code", ""), link.get("gloss", "")
                if code not in valid:
                    blocks.append(
                        f"{article_id}: 날조 코드 '{code}' — curriculum_ref.json에 없음"
                    )
                    continue
                if EXCLUDED.search(code):
                    blocks.append(f"{article_id}: 제외 대상 코드 '{code}' (초등·일반사회)")
                    continue
                if code in lex:
                    if gloss != lex[code]:
                        fixes.append(
                            f"{article_id}: {code} gloss '{gloss}' → '{lex[code]}'"
                        )
                        link["gloss"] = lex[code]
                else:
                    if not isinstance(gloss, str) or not 8 <= len(gloss) <= 20:
                        blocks.append(
                            f"{article_id}: {code} gloss 길이 8~20자 위반"
                        )
                        continue
                    lex[code] = gloss
                    fixes.append(
                        f"{article_id}: {code} 신규 gloss 어휘집 등록 필요 — '{gloss}'"
                    )
                normalized_gloss = link.get("gloss", "")
                if not isinstance(normalized_gloss, str) or not 8 <= len(normalized_gloss) <= 20:
                    blocks.append(f"{article_id}: {code} gloss 길이 8~20자 위반")

    if fixes and not fix:
        blocks.extend(fixes)
    article_count = sum(
        len(document.get("articles", []))
        for document in documents.values()
        if isinstance(document, dict) and isinstance(document.get("articles"), list)
    )
    link_count = sum(
        len(article.get("curriculum") or [])
        for document in documents.values()
        if isinstance(document, dict)
        for article in document.get("articles", [])
        if isinstance(article, dict)
    )
    return {
        "ok": not blocks,
        "blocks": blocks,
        "fixes": fixes,
        "documents": documents,
        "lexicon": lex,
        "articles": article_count,
        "links": link_count,
    }


def check_document(document, ref_path=REF, lex_path=LEX):
    valid, lexicon = load_reference(ref_path, lex_path)
    return check_documents({"current": document}, valid, lexicon, fix=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--exclude-date", help="exclude one YYYY-MM-DD recovery target")
    args = parser.parse_args()
    if args.exclude_date is not None:
        try:
            excluded_date = dt.date.fromisoformat(args.exclude_date).isoformat()
        except ValueError:
            parser.error("--exclude-date must be YYYY-MM-DD")
        if excluded_date != args.exclude_date:
            parser.error("--exclude-date must be YYYY-MM-DD")
    else:
        excluded_date = None
    try:
        valid, lexicon = load_reference()
        documents = {}
        for path in sorted(glob.glob(os.path.join(DATA, "*.json"))):
            if excluded_date is not None and os.path.basename(path) == f"{excluded_date}.json":
                continue
            with open(path, encoding="utf-8") as handle:
                documents[path] = json.load(handle, object_pairs_hook=strict_object)
        result = check_documents(documents, valid, lexicon, fix=args.fix)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"교육과정 게이트 — 검사 자료를 읽을 수 없음({exc})")
        return 1

    if args.fix and result["fixes"]:
        for path, document in result["documents"].items():
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        if result["lexicon"] != lexicon:
            with open(LEX, "w", encoding="utf-8") as handle:
                json.dump(
                    dict(sorted(result["lexicon"].items())),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")

    print(
        f"교육과정 게이트 — 기사 {result['articles']}건 · 연결 {result['links']}개 "
        f"· 코드 {len(result['lexicon'])}종"
    )
    if result["fixes"]:
        tag = "자동 교정" if args.fix else "교정 필요(--fix 로 해결 가능)"
        print(f"  [{tag}] {len(result['fixes'])}건")
        for message in result["fixes"]:
            print("    · " + message)
    if result["blocks"]:
        print(f"  [차단] {len(result['blocks'])}건 — 발행할 수 없다")
        for message in result["blocks"]:
            print("    ✗ " + message)
        return 1
    print("  통과 ✅ (날조 없음 · 기사당 ≤2 · 제외대상 없음 · gloss 코드당 하나·8~20자)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
