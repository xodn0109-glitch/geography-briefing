#!/usr/bin/env python3
"""제목·💬 단언 하드 게이트 — publish.sh가 빌드 직전에 호출한다.

■ 왜 있나 (2026-08-07 실제 사고)
    제목 "콜로라도강, 나누기로 한 물이 강에 없다"
    요약 "...올해 파월호로 든 물은 7월 기준 350만에 그칠 것으로 추정된다"
    물이 **없는** 게 아니라 나눈 양만큼 **흐르지 않는** 것이었다. 즉 제목이 원문과
    어긋난 게 아니라 **두 줄 아래 자기 요약문과 모순**이었다 — 원문을 다시 펴 볼
    필요조차 없이 자기 안에서 잡히는 오류다.

    SKILL에는 이미 '★ 제목 재료 불변식'이 있었지만 적용 범위가 **수치·기간·비율**
    뿐이었다. 이 제목에는 숫자가 하나도 없어서 게이트를 그냥 통과했다. 문제는
    숫자가 아니라 **서술어**였다. 그래서 서술어까지 코드로 막는다.

■ 차단(BLOCK, exit 1) — 판단이 0%인 것만. 과거 전수에 돌려 오탐 0을 확인한 뒤 올렸다.
    · 모순형: 제목이 존재를 부정하는데, 요약·본문에는 '있긴 있고 적다'는 양(量)
      진술("350만에 그칠", "3곳만 남았")이 있다 → 제목이 자기 텍스트와 충돌
    · 연도(4자리)·퍼센트·온도가 제목에 있는데 요약·본문에 없다 → 지어낸 숫자
      (SKILL 제목 재료 불변식의 코드화. 실제 사고 계열: 원문에 없는 기간이 제목에 샌 건)
    · **💬(talk)의 기간 표현**('N년 뒤/먼저/간/째/만의/앞서/전에')이 기준 문서에
      직접 없고 연도 산술로도 나오지 않으면 차단 (2026-08-12 신설, 실측: 과거 6건 중
      4건 차단·전부 정당·오탐 0). SKILL 제목 규칙은 제목·오늘의 한 줄·💬 모두를
      구속하는데 코드는 제목만 보고 있었고, 그 구멍으로 실제 두 건이 나갔다 —
      8/02 "8일마다 찍힌 위성 기록이 40년 뒤"(기준 문서는 1984~2013),
      8/12 "대만은 그 길을 45년 먼저 갔고"(기준 문서는 1980년 출범).
      💬는 해석이 자유롭지만 **그 안의 숫자는 여전히 사실**이라서 재료가 필요하다.

■ 경고(WARN, 차단하지 않음) — **오탐률을 실측해서 차단에서 내렸다**
    · 부정 어휘 무근거(오탐 5/6): "국경이 사라졌다" ← 본문 "철거됐다·없어진 것",
      "런던의 사라진 하늘" ← "하늘을 못 보게 됐다". 한국어는 같은 뜻을 다른 낱말로
      쓰므로 '제목 낱말이 본문에 그대로 있어야 한다'는 조건은 정당한 제목을 잡는다.
    · 기간 표현 무근거(오탐 2/3): "한 해 300일"(연간의 뜻), "닷새 전"←"5일 전".
    · **💬의 기간 아닌 숫자**(오탐 8/10): 수업 활동 제안의 임의 수치("반경 500m 안에
      몇 개인지 세어보는 활동"), 한국 배경 통계("도시화율 90%", "합계출산율 0.7"),
      낱말로 쓰인 숫자("기관이 0곳"←"한 곳도 없었다"), 허용된 산술("4년 뒤"←2030-2026).
      기간 표현만 좁혀 잡으면 오탐이 0이 되므로 차단은 그쪽에만 걸었다.
    · 어감: 긴 관형절(~기로 한/~라고 밝힌) + 물리적 부정형(없다/말랐다)은 층이
      어긋나 덜컹거린다. 이번 사고 제목의 어색함이 여기서 왔다. 문장 품질은
      코드로 판정할 수 없다 — 경고까지가 코드의 몫이다.

    ⚠️ 경고를 차단으로 올리려면 **먼저 과거 전수에 돌려 오탐을 재라**. 오탐이 잦은
    게이트는 7시 자동 실행을 근거 없이 세우고, 결국 게이트를 우회하게 만든다.
    측정 없이 올리지 마라(eval/run_title_eval.py 가 이 경계선을 지킨다).

    python3 check_titles.py            # 검사 (차단 사유 있으면 exit 1)
    python3 check_titles.py --strict   # 경고까지 차단으로 취급 (규칙 손볼 때만)
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
STRICT = "--strict" in sys.argv

# ── 제목: 존재·완전 부정 ────────────────────────────────────────────────
NEG_TITLE = re.compile(r"없다|없었다|없는|사라졌|사라진|말랐|말라붙|바닥났|고갈|"
                       r"끊겼|멈췄|제로|전멸|멸종")
# '없'의 관용 결합은 부정 단언이 아니다
IDIOM = re.compile(r"어쩔 수 없|끊임없|다름없|틀림없|어김없|하는 수 없|말할 것도 없|더없")
# 요약·본문: '있긴 있는데 적다'는 양 진술 — 존재 부정과 정면 충돌하는 형태
QTY_ONLY = re.compile(r"\d[\d,\.]*\s*(?:만|억|천|%|퍼센트)?[가-힣]*\s*(?:에 )?"
                      r"(?:그친|그칠|그쳤|불과|남았|남은|밑돌|미치지 못)")

# ── 제목의 숫자: 요약·본문에 없으면 지어낸 것 ───────────────────────────
YEAR = re.compile(r"(?<!\d)(?:1[6-9]\d\d|20[0-4]\d)년")
PCT = re.compile(r"\d[\d\.]*\s*%")
DEG = re.compile(r"\d[\d\.]*\s*도(?![시로구군민])")
DURATION = re.compile(r"하루|이틀|사흘|나흘|닷새|엿새|열흘|보름|한 달|두 달|석 달|넉 달|반년")
# 💬의 기간 표현 — 'N년 뒤/먼저/간/째/만의/앞서/전에'
TALK_SPAN = re.compile(r"(\d[\d,\.]*)\s*년\s*(뒤|먼저|간|째|만의|앞서|전에)")
YEAR4 = re.compile(r"(?:19\d\d|20[0-4]\d)년")
TRANS = os.path.join(HERE, "..", "translations")
# 'N년치·N년간·N개월' — 자료 기간을 부풀린 제목. 2026-08-02 실제 사고가 이 형태였다.
SPAN = re.compile(r"(\d[\d,\.]*)\s*(년치|년간|년\s*동안|개월)")
# 본문의 연도 범위 — 'N년치'의 근거로 산술 대조한다(1984~2013년 → 29~30년)
YRANGE = re.compile(r"(\d{4})\s*[~–—-]\s*(\d{4})\s*년|(\d{4})년\s*(?:부터|에서)\s*(\d{4})년")

# ── 어감: 긴 관형절 + 물리적 부정형 ─────────────────────────────────────
CLUNKY = (re.compile(r"기로 한|라고 밝힌|하겠다는|한다는"),
          re.compile(r"없다|말랐다|멈췄다|끊겼다|사라졌다"))


def norm(s):
    return s.replace(",", "").replace(" ", "")


def reference_doc(date, idx, a):
    """그 기사의 **기준 문서**(SKILL 공용 개념 ①) — 💬 검사의 근거.

    해외=확정 번역문 / 국내=보관 원문이 translations/YYYY-MM-DD/N-슬러그.md 에 있다.
    2026-08-11 이전 회차에는 이 폴더가 없으므로 요약+본문으로 우아하게 강등한다.
    """
    base = article_text(a)
    d = os.path.join(TRANS, date)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.startswith(f"{idx}-"):
                base += " " + open(os.path.join(d, f), encoding="utf-8").read()
    return base


def check_talk(talk, ref, pub_year):
    """💬의 숫자 검사 — 기간 표현은 차단, 나머지는 경고."""
    blocks, warns = [], []
    if not talk:
        return blocks, warns
    nref = norm(ref)
    years = sorted({int(y[:-1]) for y in YEAR4.findall(ref)})
    diffs = {abs(b - a) for a in years + [pub_year] for b in years + [pub_year]}
    for num, unit in TALK_SPAN.findall(talk):
        n = num.replace(",", "")
        if n + "년" in nref:
            continue                                   # 기준 문서에 직접 있음
        if n.isdigit() and int(n) in diffs:
            continue                                   # 기준 문서 연도 산술로 나옴
        blocks.append(f"💬의 기간 '{num}년 {unit}' 이 기준 문서에 없고 연도 산술로도 안 나옴"
                      f" (기준 문서 연도: {years or '없음'})")
    span_toks = {m.group(0) for m in TALK_SPAN.finditer(talk)}
    rest = TALK_SPAN.sub(" ", talk)
    for tok in sorted(set(re.findall(r"\d[\d,\.]*", rest))):
        if norm(tok) not in nref:
            warns.append(f"💬의 숫자 '{tok}' 이 기준 문서에 없음 — 수업 활동 예시·산술이면 무해")
    return blocks, warns


def article_text(a):
    """제목을 검증할 기준 텍스트 = 요약 + 본문. **💬(talk)는 넣지 않는다.**

    talk은 편집자의 해석이라 제미나이 대조를 지나가지 않은 문장이다. 기준에 넣으면
    검증되지 않은 문장끼리 서로를 보증하게 된다. 실제로 그렇게 새어 나갔다:
    2026-08-02 제목 '40년치'가 본문 근거 없이 통과했는데, 유일한 '40년'이
    talk("위성 기록이 40년 뒤 타임머신이 됐습니다")에 있었기 때문이다.
    """
    body = " ".join(s.get("p", "") for s in (a.get("body") or []))
    return f"{a.get('summary', '')} {body}"


def check(title, text):
    """(차단 사유, 경고 사유) 반환. 게이트와 eval이 같은 함수를 쓴다."""
    blocks, warns = [], []
    bare = IDIOM.sub("", title)
    n_title, n_text = norm(title), norm(text)

    if NEG_TITLE.search(bare):
        m = QTY_ONLY.search(text)
        if m:
            blocks.append(f"모순형 — 제목은 존재를 부정하는데 본문은 '{m.group(0)}'")
        elif not NEG_TITLE.search(text):
            warns.append("부정 어휘의 근거가 요약·본문에 안 보임 (다른 낱말로 쓰였을 수 있음)")

    for label, rx in (("연도", YEAR), ("비율", PCT), ("온도", DEG)):
        for tok in sorted(set(rx.findall(title) if label != "연도" else YEAR.findall(title))):
            if norm(tok) not in n_text:
                blocks.append(f"{label} '{tok}' 이 요약·본문에 없음 — 제목 재료 불변식 위반")

    # N년치·N년간·N개월 — 근거는 ① 같은 수의 'N년/N개월' 또는 ② 본문 연도 범위와의 산술 일치
    lens = set()
    for a_, b_, c_, d_ in YRANGE.findall(text):
        s_, e_ = (a_, b_) if a_ else (c_, d_)
        lens |= {int(e_) - int(s_), int(e_) - int(s_) + 1}
    for num, unit in SPAN.findall(title):
        n_ = num.replace(",", "")
        base = "개월" if unit == "개월" else "년"
        if n_ + base in n_text:
            continue
        if base == "년" and n_.isdigit() and any(abs(int(n_) - L) <= 1 for L in lens):
            continue
        blocks.append(f"기간 '{num}{unit}' 의 근거가 요약·본문에 없음 — 자료 기간 부풀리기")

    for tok in sorted(set(DURATION.findall(title))):
        if tok not in text:
            warns.append(f"기간 '{tok}' 이 요약·본문에 없음 — 검색 스니펫에서 샜을 수 있음")

    if CLUNKY[0].search(n_title) and CLUNKY[1].search(n_title):
        warns.append("어감 — 긴 관형절 뒤에 물리적 부정형. 서술어를 관형절과 같은 층으로")

    return blocks, warns


def main():
    docs = {p: json.load(open(p, encoding="utf-8"))
            for p in sorted(glob.glob(os.path.join(DATA, "*.json")))}
    n_art, blocks, warns = 0, [], []
    for p, d in docs.items():
        date = os.path.basename(p)[:10]
        pub_year = int(date[:4]) if date[:4].isdigit() else 2026
        for idx, a in enumerate(d.get("articles", []), 1):
            n_art += 1
            b, w = check(a["title"], article_text(a))
            tb, tw = check_talk(a.get("talk", ""), reference_doc(date, idx, a), pub_year)
            b += tb
            w += tw
            blocks += [f"{a['id']}\n        제목: {a['title']}\n        {x}" for x in b]
            warns += [f"{a['id']} — {x}\n        제목: {a['title']}" for x in w]

    print(f"제목 게이트 — 기사 {n_art}건 검사")
    if warns:
        print(f"  [경고] {len(warns)}건 (차단 아님 — 오탐률 실측 후 경고로 둔 항목)")
        for w in warns:
            print("    ⚠ " + w)
    if STRICT:
        blocks += warns

    if blocks:
        print(f"  [차단] {len(blocks)}건 — 발행할 수 없다")
        for b in blocks:
            print("    ✗ " + b)
        sys.exit(1)
    print("  통과 ✅ (자기 요약과 모순 없음 · 제목의 연도·비율·온도가 본문에 실재)")


if __name__ == "__main__":
    main()
