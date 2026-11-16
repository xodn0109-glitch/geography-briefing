#!/usr/bin/env python3
"""
지리 뉴스 브리핑 아카이브 사이트 빌더.

site/data/*.json (하루 한 파일)을 모두 읽어 자기완결형 index.html 한 장을 생성한다.
매일 봇이 그날치 JSON을 data/에 떨궈 놓고 이 스크립트를 실행하면 사이트가 갱신된다.

    python3 build.py

의존성 없음(표준 라이브러리만). 결과물은 site/index.html.
"""
import json
import os
import glob
import html
import re
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "index.html")
WORLD_PATH_SAFE = re.compile(r"[MmZzLlHhVvCcSsQqTtAaEe0-9+.,\- \t\r\n]+\Z")
WORLD_PATH_MAX_BYTES = 2_000_000

PUBLIC_SCALAR_FIELDS = (
    "id", "region", "target_country", "category", "title", "journal",
    "researchers", "summary", "talk",
    "topic_key",
)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def load_json_strict(handle):
    return json.load(handle, object_pairs_hook=strict_object)


def safe_world_path(raw):
    """Return an attribute-safe SVG path or fail closed on mutable markup."""

    if not isinstance(raw, str):
        raise ValueError("world land path must be text")
    value = raw.strip()
    if not value:
        return ""
    if len(value.encode("utf-8")) > WORLD_PATH_MAX_BYTES:
        raise ValueError("world land path is too large")
    if WORLD_PATH_SAFE.fullmatch(value) is None:
        raise ValueError("world land path contains unsafe characters")
    return html.escape(value, quote=True)


def public_article(article):
    """Copy only the documented public schema, including nested allowlists."""

    if not isinstance(article, dict):
        return None
    result = {
        field: article[field]
        for field in PUBLIC_SCALAR_FIELDS
        if field in article
    }
    source = article.get("source")
    result["source"] = (
        {
            field: source[field]
            for field in (
                "name", "url", "date", "language", "doi", "canonical_kind"
            )
            if field in source
        }
        if isinstance(source, dict)
        else None
    )
    body = article.get("body")
    result["body"] = [
        {field: section[field] for field in ("h", "p") if field in section}
        for section in body
        if isinstance(section, dict)
    ] if isinstance(body, list) else []
    tags = article.get("tags")
    result["tags"] = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
    curriculum = article.get("curriculum")
    result["curriculum"] = [
        {field: link[field] for field in ("code", "gloss") if field in link}
        for link in curriculum
        if isinstance(link, dict)
    ] if isinstance(curriculum, list) else []
    geo = article.get("geo")
    result["geo"] = (
        {field: geo[field] for field in ("lat", "lon", "label") if field in geo}
        if isinstance(geo, dict)
        else None
    )
    references = article.get('references')
    if isinstance(references, list):
        result['references'] = [
            {field: ref[field] for field in
             ('id','author','date','title','url','kind','short_label','apa') if field in ref}
            for ref in references if isinstance(ref, dict)]
    return result

def load_days(data_dir=DATA_DIR):
    days = []
    for path in sorted(glob.glob(os.path.join(os.fspath(data_dir), "*.json"))):
        with open(path, encoding="utf-8") as f:
            day = load_json_strict(f)
        # 검증 우회나 과거 파일의 잔여 메모가 있어도 공개 payload에는 명시된
        # 필드만 넣는다. 중첩 객체도 동일한 allowlist로 다시 만든다.
        raw_articles = day.get("articles", [])
        articles = [
            cleaned
            for cleaned in (public_article(article) for article in raw_articles)
            if cleaned is not None
        ] if isinstance(raw_articles, list) else []
        fmt = day.get("format")
        days.append({
            "date": day.get("date", ""),
            "format": fmt if isinstance(fmt, str) else "",
            "articles": articles,
        })
    # 날짜 내림차순: 화면의 날짜 이동(0번이 최신)이 이 정렬에 의존한다.
    days.sort(key=lambda d: d["date"], reverse=True)
    return days


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{y}. {int(m)}. {int(d)}."


# 2026-11-04 사용자 요청: '성취기준별' 보기의 과목과 순서. (참조 파일의 과목명, 화면 표시명)
# 중학교는 사회1·사회2를 나누지 않고 '중학교 사회' 하나로 보여준다.
SUBJECT_ORDER = (
    ("중학교 사회(지리 영역)", "중학교 사회"),
    ("통합사회1", "통합사회1"),
    ("통합사회2", "통합사회2"),
    ("한국지리 탐구", "한국지리 탐구"),
    ("세계시민과 지리", "세계시민과 지리"),
    ("여행지리", "여행지리"),
    ("기후변화와 지속가능한 세계", "기후변화와 지속가능한 세계"),
    ("도시의 미래 탐구", "도시의 미래 탐구"),
)


def build(
    *,
    data_dir=DATA_DIR,
    out=OUT,
    world_path_file=None,
    curriculum_ref_file=None,
    quiet=False,
):
    data_dir = os.fspath(data_dir)
    out = os.fspath(out)
    world_path_file = os.fspath(
        world_path_file or os.path.join(HERE, "world_land_path.txt")
    )
    curriculum_ref_file = os.fspath(
        curriculum_ref_file or os.path.join(HERE, "..", "curriculum_ref.json")
    )
    days = load_days(data_dir)

    total_articles = sum(len(d["articles"]) for d in days)

    # < 전체를 이스케이프해 </script>·<!-- 등 파서 이탈을 원천 차단(JSON 문자열 안에서만 등장 가능).
    payload = json.dumps({"days": days}, ensure_ascii=False).replace("<", "\\u003c")

    tpl = HTML_TEMPLATE
    tpl = tpl.replace("__LATEST__", fmt_date(days[0]["date"]) if days else "")

    # 세계지도 내비게이터 육지 윤곽 (Natural Earth 110m, 퍼블릭 도메인 → SVG path 사전 변환본)
    world_path = ""
    if os.path.exists(world_path_file):
        with open(world_path_file, encoding="utf-8") as f:
            world_path = safe_world_path(f.read())
    tpl = tpl.replace("__WORLDPATH__", world_path)

    # 교육과정 성취기준 전문(빌드 시 ../curriculum_ref.json 참조). 2026-11-04부터 '성취기준별' 보기가
    # 기사가 아직 없는 성취기준도 보여주므로 참조 파일의 모든 성취기준을 심는다.
    # 참조 파일이 없으면 빈 객체 → 배지는 그대로 보이되 펼침만 비활성(우아한 강등).
    curr = {}
    subjects = []
    if os.path.exists(curriculum_ref_file):
        with open(curriculum_ref_file, encoding="utf-8") as f:
            ref = load_json_strict(f)
        gloss_file = os.path.join(os.path.dirname(curriculum_ref_file), "curriculum_gloss.json")
        gloss = {}
        if os.path.exists(gloss_file):
            with open(gloss_file, encoding="utf-8") as f:
                gloss = load_json_strict(f)
        ref_subjects = ref.get("subjects", {})
        flat = {}
        for stds in ref_subjects.values():
            for s in stds:
                flat[s["code"]] = s
        used = set()
        for d in days:
            for a in d["articles"]:
                for c in (a.get("curriculum") or []):
                    used.add(c["code"])
        # 출력 바이트가 PYTHONHASHSEED와 무관하도록 교육과정 삽입 순서를 고정한다.
        for code in sorted(set(flat) | used):
            s = flat.get(code)
            if not s:
                continue
            # 해설은 원문에서 코드를 떼며 남은 선행 조사(에서는/은/는…)를 제거해 자연스럽게.
            ex = re.sub(r"^(에서는|에서|은|는|이|가|을|를|와|과)\s+", "", (s.get("explain") or "").strip())
            row = {"text": s.get("text", ""), "explain": ex}
            if isinstance(gloss.get(code), str):
                row["gloss"] = gloss[code]
            curr[code] = row
        # '성취기준별' 보기의 과목 순서(사용자 지정). 참조 파일에 없는 과목은 건너뛰고,
        # 목록 밖의 새 과목은 뒤에 붙인다.
        ordered = [name for name, _ in SUBJECT_ORDER if name in ref_subjects]
        ordered += [name for name in ref_subjects if name not in dict(SUBJECT_ORDER)]
        labels = dict(SUBJECT_ORDER)
        for name in ordered:
            subjects.append({
                "name": labels.get(name, name),
                "codes": [s["code"] for s in ref_subjects[name]],
            })
    tpl = tpl.replace("__CURRICULUM__", json.dumps(curr, ensure_ascii=False).replace("<", "\\u003c"))
    tpl = tpl.replace("__SUBJECTS__", json.dumps(subjects, ensure_ascii=False).replace("<", "\\u003c"))
    # 기사 본문(payload)은 자유 텍스트라 다른 플레이스홀더 토큰을 담을 수 있다 — 반드시 맨 마지막에 치환.
    tpl = tpl.replace("__DATA__", payload)

    # 임시 파일에 쓴 뒤 원자 교체 — 부분 쓰기 상태의 index.html이 남지 않게.
    tmp_out = out + ".tmp"
    with open(tmp_out, "w", encoding="utf-8") as f:
        f.write(tpl)
    os.replace(tmp_out, out)
    if not quiet:
        print(f"built {out}  ({len(days)} days, {total_articles} articles)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<!-- slop-gate: off (확정·발송된 브리핑 데이터를 글자 그대로 싣는 생성물) -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지리 뉴스 브리핑 아카이브</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>
  :root {
    --page: #f5f5f7;
    --surface: #ffffff;
    --surface-2: #f5f5f7;
    --ink: #1d1d1f;
    --ink-soft: #333333;
    --ink-faint: #86868b;
    --line: #e0e0e0;
    --accent: #0066cc;
    --accent-dark: #0055ad;
    --yellow: #ffce00;
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
    --maxw: 860px;
  }

  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--page);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Pretendard Variable", Inter,
                 "Apple SD Gothic Neo", "Noto Sans KR", system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  button { font: inherit; }
  .wrap { max-width: var(--maxw); margin: 0 auto; padding: 0 20px; }
  [hidden] { display: none !important; }

  /* 상단 바 */
  .topnav { position: sticky; top: 0; z-index: 30; background: #000; height: 44px;
            display: flex; align-items: center; }
  .topnav .wrap { width: 100%; display: flex; align-items: center; justify-content: space-between; }
  .tn-brand { color: #f5f5f7; font-size: 13px; font-weight: 600; letter-spacing: -.02em; }
  .tn-stat { color: #86868b; font-size: 12px; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }

  /* 머리글: 제목과 구독 단추만 */
  .hero { background: var(--surface); padding: 32px 20px 22px; }
  .hero-inner { max-width: 720px; margin: 0 auto; text-align: center; }
  .brand { display: flex; align-items: center; justify-content: center; gap: clamp(10px, 1.4vw, 16px); }
  .frame { width: clamp(24px, 3.6vw, 34px); height: clamp(35px, 5.2vw, 49px);
           border: clamp(4px, 0.55vw, 5px) solid var(--yellow); border-radius: 2px; flex: none; }
  h1 { font-size: clamp(28px, 4.6vw, 44px); font-weight: 600; line-height: 1.08;
       letter-spacing: -.03em; color: var(--ink); margin: 0; word-break: keep-all; }
  .tagline { font-size: clamp(16px, 2vw, 19px); line-height: 1.45; color: var(--ink-soft);
             margin: 14px auto 0; max-width: 32rem; word-break: keep-all; letter-spacing: -.01em; }
  .subscribe { display: inline-flex; align-items: center; gap: 8px; margin: 18px 0 0;
               background: var(--accent); color: #fff; font-size: 14px; font-weight: 600;
               padding: 10px 19px; border-radius: 980px; text-decoration: none;
               letter-spacing: -.01em; white-space: nowrap;
               transition: background-color .15s var(--ease-out), transform .16s var(--ease-out); }
  .subscribe:hover { background: var(--accent-dark); text-decoration: none; }
  .subscribe:active { transform: scale(0.97); }
  .subscribe svg { width: 16px; height: 16px; flex: none; }

  /* 보기 전환 */
  .viewbar { background: var(--surface); border-bottom: 1px solid var(--line); }
  .viewbar .wrap { display: flex; justify-content: center; padding-top: 4px; padding-bottom: 16px; }
  .viewtabs { display: inline-flex; gap: 2px; padding: 3px; background: #e8e8ed; border-radius: 980px; }
  .viewtabs button { font-size: 14px; border: none; background: transparent; cursor: pointer;
                     color: var(--ink-soft); padding: 7px 18px; border-radius: 980px; letter-spacing: -.01em;
                     transition: background-color .15s var(--ease-out), transform .16s var(--ease-out); }
  .viewtabs button:active { transform: scale(0.96); }
  .viewtabs button.on { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,.08); }

  /* 날짜별 보기: 날짜 막대 + 지도 */
  .dayhead { background: var(--surface); padding: 22px 20px 26px; }
  .dayhead-inner { max-width: var(--maxw); margin: 0 auto; }
  .daybar { display: flex; align-items: center; justify-content: center; gap: 14px; }
  .daybar .nav { font-size: 14px; border: 1px solid #d2d2d7; background: #fff; color: var(--ink);
                 border-radius: 980px; width: 36px; height: 36px; cursor: pointer; flex: none;
                 transition: border-color .15s var(--ease-out), transform .16s var(--ease-out); }
  .daybar .nav:hover:not(:disabled) { border-color: var(--accent); }
  .daybar .nav:active:not(:disabled) { transform: scale(0.92); }
  .daybar .nav:disabled { opacity: .3; cursor: default; }
  .day-title { text-align: center; min-width: 13ch; }
  .day-label { margin: 0; font-size: clamp(20px, 3vw, 26px); font-weight: 700; letter-spacing: -.02em;
               font-variant-numeric: tabular-nums; }
  .day-sub { margin: 3px 0 0; font-size: 13px; color: var(--ink-faint); letter-spacing: -.01em; }
  .day-latest { display: block; margin: 10px auto 0; font-size: 13px; font-weight: 600; color: var(--accent);
                background: none; border: none; cursor: pointer; padding: 4px 8px; }
  #navmap { width: 100%; height: auto; display: block; margin-top: 18px; }
  #navmap .land, #navmap use { fill: #e8e8ed; stroke: #d2d2d7; stroke-width: .6; }
  .mk { cursor: pointer; outline: none; }
  .mk-dot { fill: var(--accent); stroke: #fff; }
  .mk:hover .mk-dot, .mk:focus-visible .mk-dot { fill: var(--accent-dark); }
  .mk-num { fill: #fff; font-weight: 700; pointer-events: none; }
  .mk-label { fill: var(--ink); font-weight: 600; paint-order: stroke; stroke: #fff; stroke-linejoin: round;
              pointer-events: none; letter-spacing: -.02em; }
  .map-hint { margin: 12px 0 0; font-size: 13px; color: var(--ink-faint); text-align: center; letter-spacing: -.01em; }

  main .wrap.day-body { padding-top: 26px; padding-bottom: 20px; }
  .era-note { margin: 0 0 18px; padding: 13px 16px; background: #fff8d6; border-radius: 12px;
              font-size: 14px; line-height: 1.6; color: var(--ink-soft); letter-spacing: -.01em; }

  /* 카드 */
  .card { background: var(--surface); border: 1px solid var(--line); border-radius: 18px;
          padding: 24px 26px; margin-bottom: 16px; transition: box-shadow .4s var(--ease-out); }
  .card.flash { box-shadow: 0 0 0 3px var(--accent); border-color: transparent; }
  .meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .m-num { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px;
           border-radius: 50%; background: var(--accent); color: #fff; font-size: 12px; font-weight: 700;
           font-variant-numeric: tabular-nums; flex: none; }
  .m-date { font-size: 13px; font-weight: 600; color: var(--accent); background: none; border: none;
            padding: 0; cursor: pointer; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
  .m-date:hover { text-decoration: underline; }
  .m-region { font-size: 13px; font-weight: 600; color: var(--ink-soft); letter-spacing: -.01em; }
  .m-journal { margin-left: auto; font-size: 13px; color: var(--ink-faint); text-align: right; letter-spacing: -.01em; }
  h3.title { font-size: clamp(19px, 2.3vw, 23px); font-weight: 600; line-height: 1.32;
             letter-spacing: -.02em; color: var(--ink); margin: 10px 0 0; word-break: keep-all; }
  .who { margin: 8px 0 0; font-size: 13px; color: var(--ink-faint); line-height: 1.5; letter-spacing: -.01em; }
  .summary { margin: 14px 0 0; font-size: 17px; line-height: 1.65; color: var(--ink-soft); letter-spacing: -.01em; }
  mark { background: #fff3b0; color: inherit; border-radius: 3px; padding: 0 1px; }

  .deep-toggle { margin-top: 12px; cursor: pointer; color: var(--accent); font-weight: 600; font-size: 15px;
                 background: none; border: none; padding: 4px 0; letter-spacing: -.01em;
                 transition: transform .16s var(--ease-out); }
  .deep-toggle:active { transform: scale(0.97); }
  .deep { margin-top: 12px; border-top: 1px solid var(--line); padding-top: 4px; }
  .sec { margin-top: 16px; }
  .sec-h { font-size: 15px; font-weight: 700; color: var(--ink); letter-spacing: -.01em; }
  .sec-p { margin: 5px 0 0; font-size: 16px; line-height: 1.7; color: var(--ink-soft); letter-spacing: -.01em; }
  .refs { margin: 6px 0 0; padding-left: 20px; font-size: 13px; line-height: 1.6; color: var(--ink-faint); }
  .refs li { margin-top: 4px; word-break: break-all; }

  .talk { margin-top: 18px; background: #fafafc; border: 1px solid #f0f0f0; border-radius: 12px; padding: 15px 18px; }
  .talk-label { font-size: 12px; font-weight: 600; color: var(--ink-faint); letter-spacing: .02em; margin-bottom: 6px; }
  .talk-body { font-size: 16px; line-height: 1.6; color: var(--ink); letter-spacing: -.01em; }

  .curric-block { margin-top: 16px; }
  .curric-label { font-size: 12px; font-weight: 600; color: var(--ink-faint); letter-spacing: .02em; margin-bottom: 8px; }
  .curric { display: flex; flex-wrap: wrap; gap: 8px; }
  .curric-item { font-size: 13px; cursor: pointer; background: #fff; border: 1px solid var(--line);
                 padding: 6px 13px; border-radius: 980px; color: var(--ink-soft); letter-spacing: -.01em; text-align: left;
                 transition: border-color .15s var(--ease-out), transform .16s var(--ease-out); }
  .curric-item b { color: var(--accent); font-weight: 600; font-variant-numeric: tabular-nums; }
  .curric-item:active { transform: scale(0.96); }
  .curric-item.active { border: 2px solid var(--accent); padding: 5px 12px; }
  .curric-detail { display: none; margin-top: 11px; background: var(--surface-2); border-radius: 11px; padding: 15px 17px; }
  .curric-detail.open { display: block; }
  .cd-code { font-size: 13px; font-weight: 600; color: var(--accent); letter-spacing: .01em;
             margin-bottom: 6px; font-variant-numeric: tabular-nums; }
  .cd-text { font-size: 16px; line-height: 1.6; color: var(--ink); font-weight: 500; letter-spacing: -.01em; }
  .cd-explain { margin-top: 11px; font-size: 14px; line-height: 1.66; color: #7a7a7a; letter-spacing: -.01em; }
  .cd-label { display: inline-block; font-size: 11px; font-weight: 600; color: #fff; background: var(--ink-faint);
              padding: 1px 8px; border-radius: 980px; margin-right: 7px; vertical-align: middle; }
  .cd-more { display: inline-block; margin-top: 12px; font-size: 14px; font-weight: 600; letter-spacing: -.01em; }

  .foot { display: flex; justify-content: flex-end; margin-top: 18px; }
  a.src { font-size: 14px; font-weight: 600; color: var(--accent); text-decoration: none;
          border: 1px solid var(--accent); border-radius: 980px; padding: 8px 16px; white-space: nowrap;
          letter-spacing: -.01em;
          transition: background-color .15s var(--ease-out), transform .16s var(--ease-out); }
  a.src:hover { background: var(--surface-2); text-decoration: none; }
  a.src:active { transform: scale(0.96); }

  /* 지난 브리핑 목록 */
  .archive { margin-top: 40px; padding-top: 30px; border-top: 1px solid var(--line); }
  .sec-title { font-size: clamp(20px, 2.6vw, 24px); font-weight: 700; letter-spacing: -.02em; margin: 0 0 6px; }
  .sec-hint { margin: 0 0 18px; font-size: 14px; color: var(--ink-faint); letter-spacing: -.01em; }
  .arch-month { font-size: 13px; font-weight: 700; color: var(--ink-faint); letter-spacing: .01em; margin: 22px 0 8px; }
  .arch-row { display: flex; gap: 14px; width: 100%; text-align: left; background: var(--surface);
              border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; margin-bottom: 8px;
              cursor: pointer; color: var(--ink); transition: border-color .15s var(--ease-out); }
  .arch-row:hover { border-color: var(--accent); }
  .arch-row.on { border: 2px solid var(--accent); padding: 11px 15px; }
  .arch-date { flex: none; min-width: 6.5ch; font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums;
               letter-spacing: -.01em; padding-top: 1px; }
  .arch-titles { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
  .arch-t { font-size: 15px; line-height: 1.45; color: var(--ink-soft); letter-spacing: -.01em; word-break: keep-all; }
  .arch-t em { font-style: normal; font-size: 12px; font-weight: 600; color: var(--ink-faint); margin-right: 6px; }
  details.arch-old { margin-top: 26px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; }
  details.arch-old summary { cursor: pointer; padding: 14px 16px; font-size: 15px; font-weight: 600; letter-spacing: -.01em; }
  .arch-old-body { padding: 0 16px 16px; }
  .arch-old-body .arch-month:first-child { margin-top: 4px; }
  .arch-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .arch-chip { font-size: 13px; border: 1px solid var(--line); background: #fff; color: var(--ink-soft);
               border-radius: 980px; padding: 5px 11px; cursor: pointer; font-variant-numeric: tabular-nums; }
  .arch-chip span { color: var(--ink-faint); margin-left: 3px; }
  .arch-chip:hover { border-color: var(--accent); }
  .arch-chip.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .arch-chip.on span { color: #fff; opacity: .8; }
  .arch-special { margin-top: 26px; }
  .arch-special a { display: block; font-size: 15px; line-height: 1.5; margin-top: 6px; letter-spacing: -.01em; }

  /* 성취기준별 보기 */
  .view-pad { padding-top: 30px; padding-bottom: 60px; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; }
  .chip { font-size: 14px; cursor: pointer; border: 1px solid var(--line);
          background: #fff; color: var(--ink-soft); padding: 8px 15px; border-radius: 980px;
          white-space: nowrap; letter-spacing: -.01em;
          transition: background-color .15s var(--ease-out), color .15s var(--ease-out), transform .16s var(--ease-out); }
  .chip:active { transform: scale(0.96); }
  .chip.on { background: var(--accent); color: #fff; font-weight: 600; border-color: transparent; }
  .chip .n { opacity: .55; margin-left: 6px; font-variant-numeric: tabular-nums; }
  .theme-head { font-size: clamp(22px, 2.8vw, 28px); font-weight: 600; letter-spacing: -.02em;
                color: var(--ink); margin: 0 0 18px; display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .theme-n { font-size: 14px; font-weight: 600; color: var(--ink-faint); letter-spacing: 0; }
  .std-hint { margin: -6px 0 20px; font-size: 14px; line-height: 1.6; color: var(--ink-faint); letter-spacing: -.01em; }
  .std { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; margin-bottom: 10px; }
  .std-row { display: flex; align-items: baseline; gap: 12px; width: 100%; padding: 15px 20px; text-align: left;
             background: none; border: none; cursor: pointer; color: var(--ink); }
  .std-code { flex: none; min-width: 10.5ch; font-size: 13px; font-weight: 600; color: var(--accent);
              font-variant-numeric: tabular-nums; letter-spacing: .01em; }
  .std-gloss { flex: 1; min-width: 0; font-size: 16px; line-height: 1.45; letter-spacing: -.01em; word-break: keep-all; }
  .std-n { flex: none; font-size: 13px; font-weight: 600; color: #fff; background: var(--accent);
           border-radius: 980px; padding: 2px 10px; font-variant-numeric: tabular-nums; }
  .std-row .chev { flex: none; color: var(--ink-faint); font-size: 13px; transition: transform .2s var(--ease-out); }
  .std.open .std-row .chev { transform: rotate(180deg); }
  .std.none .std-code, .std.none .std-gloss { color: var(--ink-faint); }
  .std.none .std-n { background: var(--surface-2); color: var(--ink-faint); }
  .std-body { padding: 0 20px 20px; }
  .std-full { background: var(--surface-2); border-radius: 11px; padding: 15px 17px; margin-bottom: 18px; }
  .std-body .card { padding: 22px 22px; border-radius: 14px; }
  .std-empty { margin: 0; font-size: 14px; color: var(--ink-faint); letter-spacing: -.01em; }

  /* 검색 보기 */
  .searchbar { position: relative; width: 100%; margin-bottom: 22px; }
  .searchbar .s-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
                       width: 16px; height: 16px; color: var(--ink-faint); pointer-events: none; }
  .searchbar input { width: 100%; font: inherit; font-size: 16px; line-height: 1.2;
                     padding: 12px 42px 12px 40px; border: 1px solid var(--line); border-radius: 980px;
                     background: #fff; color: var(--ink); letter-spacing: -.01em;
                     -webkit-appearance: none; appearance: none; }
  .searchbar input::-webkit-search-cancel-button { -webkit-appearance: none; display: none; }
  .searchbar input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,102,204,.12); }
  .searchbar input::placeholder { color: var(--ink-faint); }
  .s-clear { position: absolute; right: 7px; top: 50%; transform: translateY(-50%); border: none;
             background: var(--surface-2); cursor: pointer; color: var(--ink-faint); font-size: 17px;
             line-height: 1; width: 28px; height: 28px; border-radius: 50%; padding: 0;
             display: none; align-items: center; justify-content: center; }
  .s-clear:hover { color: var(--ink); }
  .s-clear.show { display: inline-flex; }

  .empty { text-align: center; color: var(--ink-faint); padding: 60px 0; font-size: 15px; letter-spacing: -.01em; }

  footer.bot { background: var(--page); border-top: 1px solid var(--line); margin-top: 40px; }
  footer.bot .wrap { padding: 40px 20px 56px; }
  footer.bot p { margin: 5px 0; font-size: 12px; line-height: 1.7; color: #7a7a7a; letter-spacing: -.01em; }
  .foot-sub { font-size: 13px; margin-top: 14px !important; }
  .foot-sub a { font-weight: 600; }

  @media (prefers-reduced-motion: reduce) {
    .chip:active, a.src:active, .curric-item:active, .deep-toggle:active, .subscribe:active,
    .daybar .nav:active:not(:disabled), .viewtabs button:active { transform: none; }
    .std-row .chev { transition: none; }
  }

  @media (max-width: 640px) {
    .wrap { padding: 0 14px; }
    .hero { padding: 24px 16px 16px; }
    /* 좁은 화면에서 제목 끝 글자만 다음 줄로 떨어지지 않게 글자 크기를 화면 폭에 맞춘다. */
    h1 { font-size: min(28px, calc((100vw - 75px) / 10.2)); }
    .viewtabs button { padding: 7px 14px; }
    .dayhead { padding: 18px 8px 20px; }
    .card { padding: 20px 18px; border-radius: 16px; }
    .summary { font-size: 16px; }
    .arch-row { gap: 10px; padding: 11px 13px; }
    .arch-row.on { padding: 10px 12px; }
    .std-row { flex-wrap: wrap; padding: 14px 16px; gap: 4px 10px; }
    .std-gloss { flex-basis: 100%; order: 3; }
    .std-n { margin-left: auto; }
    .std-body { padding: 0 12px 14px; }
    .std-body .card { padding: 18px 16px; }
  }
</style>
</head>
<body>
<div class="topnav">
  <div class="wrap">
    <span class="tn-brand">Powered by TW.graphy</span>
    <span class="tn-stat">최신 __LATEST__</span>
  </div>
</div>

<header class="hero">
  <div class="hero-inner">
    <div class="brand">
      <span class="frame"></span>
      <h1>지리 뉴스 브리핑 아카이브</h1>
    </div>
    <p class="tagline">매일 아침 보내드리는 텔레그램 요약본의 조금 더 긴 내용을 이 사이트에서 확인할 수 있습니다.</p>
    <a class="subscribe" href="https://t.me/geo_news_brief" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.9 4.3 19 20.1c-.2 1-.8 1.2-1.6.7l-4.4-3.2-2.1 2c-.2.2-.4.4-.9.4l.3-4.5 8.2-7.4c.4-.3-.1-.5-.6-.2L6.8 13.2 2.4 11.8c-1-.3-1-1 .2-1.4l17.1-6.6c.8-.3 1.5.2 1.2 1.5z"/></svg>
      매일 아침 텔레그램으로 받기
    </a>
  </div>
</header>

<nav class="viewbar" aria-label="보기 방식">
  <div class="wrap">
    <div class="viewtabs" id="viewtabs" role="tablist">
      <button type="button" role="tab" data-view="day" class="on" aria-selected="true">날짜별</button>
      <button type="button" role="tab" data-view="curr" aria-selected="false">성취기준별</button>
      <button type="button" role="tab" data-view="search" aria-selected="false">검색</button>
    </div>
  </div>
</nav>

<main>
  <section id="view-day" aria-labelledby="day-label">
    <div class="dayhead">
      <div class="dayhead-inner">
        <div class="daybar">
          <button class="nav" id="day-prev" type="button" aria-label="이전 날짜">◀</button>
          <div class="day-title">
            <h2 class="day-label" id="day-label" aria-live="polite"></h2>
            <p class="day-sub" id="day-sub"></p>
          </div>
          <button class="nav" id="day-next" type="button" aria-label="다음 날짜">▶</button>
        </div>
        <button class="day-latest" id="day-latest" type="button" hidden>최신 브리핑으로 돌아가기</button>
        <svg id="navmap" viewBox="417 0 1000 400" role="img" aria-label="이날 브리핑의 위치를 표시한 세계지도(태평양 중심)">
          <path id="land-path" class="land" d="__WORLDPATH__"/>
          <use href="#land-path" x="1000"/>
          <use href="#land-path" x="-1000"/>
        </svg>
        <p class="map-hint" id="map-note"></p>
      </div>
    </div>
    <div class="wrap day-body">
      <div id="day-cards"></div>
      <section class="archive" aria-labelledby="archive-title">
        <h2 class="sec-title" id="archive-title">지난 브리핑</h2>
        <p class="sec-hint">날짜를 누르면 그날의 지도와 브리핑이 위에 열립니다.</p>
        <div id="archive"></div>
      </section>
    </div>
  </section>

  <section id="view-curr" hidden>
    <div class="wrap view-pad">
      <div class="chips" id="subj-chips"></div>
      <div id="curr"></div>
    </div>
  </section>

  <section id="view-search" hidden>
    <div class="wrap view-pad">
      <div class="searchbar">
        <svg class="s-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
        <input id="q" type="search" autocomplete="off" placeholder="낱말로 찾기 (예: 화산, 도시, 인구, 기후)" aria-label="모든 날짜의 브리핑에서 찾기">
        <button id="q-clear" class="s-clear" type="button" aria-label="검색어 지우기">×</button>
      </div>
      <div id="results"></div>
    </div>
  </section>
</main>

<footer class="bot">
  <div class="wrap">
    <p>이 사이트는 매일 아침 브리핑 봇이 만듭니다. 본문의 사실 진술은 각 기사 원문과 참고문헌에서 확인한 것입니다.</p>
    <p>날짜별 보기에서는 ◀ ▶ 단추로 날짜를 넘기거나 ‘지난 브리핑’에서 날짜를 고릅니다. 카드의 ‘본문 자세히’를 누르면 전체 해설과 참고문헌이 열립니다.</p>
    <p>‘성취기준별’ 보기에서는 중학교 사회·통합사회·지리 선택 과목의 성취기준마다 연결된 브리핑을 모아 볼 수 있습니다.</p>
    <p class="foot-sub">매일 아침 짧은 요약으로 받아 보시려면 <a href="https://t.me/geo_news_brief" target="_blank" rel="noopener">텔레그램 채널(@geo_news_brief)을 구독</a>하세요.</p>
  </div>
</footer>

<script>
const DATA = __DATA__;
const CURR = __CURRICULUM__;   // {code: {text, explain, gloss?}}: 참조 파일의 모든 성취기준
const SUBJECTS = __SUBJECTS__; // [{name, codes:[...]}]: '성취기준별' 보기의 과목 순서
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const safeUrl = u => /^https?:\/\//i.test(String(u)) ? String(u) : "";
const WEEK = ["일","월","화","수","목","금","토"];
const parts = iso => String(iso).split("-").map(Number);
const weekday = iso => { const p = parts(iso); return WEEK[new Date(Date.UTC(p[0], p[1]-1, p[2])).getUTCDay()]; };
const fmtDate = iso => { const p = parts(iso); return `${p[0]}. ${p[1]}. ${p[2]}.`; };
const fmtDay = iso => `${fmtDate(iso)} (${weekday(iso)})`;
const shortDate = iso => { const p = parts(iso); return `${p[1]}. ${p[2]}.`; };

// 기사가 있는 날만, 최신순(build.py가 이미 내림차순으로 정렬).
const DAYS = DATA.days.filter(d => d.articles.length);
const isDeep = d => d.format === "daily_deep";
const FIRST_DEEP = DAYS.slice().reverse().find(isDeep);
const dayIndex = date => DAYS.findIndex(d => d.date === date);
const withDate = (a, date) => Object.assign({_date: date}, a);

let cur = 0;          // DAYS 인덱스(0 = 최신)
let view = "day";     // "day" | "curr" | "search"
let subj = 0;         // SUBJECTS 인덱스
let openStd = null;   // 펼친 성취기준 코드(한 번에 하나)
let query = "";
let oldOpen = false;  // 이전 형식 목록 펼침 상태

// 성취기준마다 연결된 기사(최신순)
const STD_ARTS = {};
DAYS.forEach(d => d.articles.forEach(a => (a.curriculum||[]).forEach(c => {
  (STD_ARTS[c.code] = STD_ARTS[c.code] || []).push(withDate(a, d.date));
})));
const stdGloss = code => {
  const fromArt = (STD_ARTS[code]||[]).map(a => (a.curriculum||[]).find(c => c.code === code)).find(c => c && c.gloss);
  if (fromArt) return fromArt.gloss;
  const info = CURR[code] || {};
  return info.gloss || info.text || "";
};
const subjCount = s => s.codes.reduce((n, c) => n + (STD_ARTS[c]||[]).length, 0);

// 검색 대상 문자열(제목·요약·본문·이야깃거리·태그·지역·연구진·매체·교육과정)을 기사마다 한 번 만든다.
function searchText(a){
  if (a._hay !== undefined) return a._hay;
  const ps = [a.title, a.summary, a.talk, a.region, a.researchers, a.journal, a.category];
  (a.body||[]).forEach(s => { ps.push(s.h, s.p); });
  (a.tags||[]).forEach(t => ps.push(t));
  (a.curriculum||[]).forEach(c => { ps.push(c.code, c.gloss); });
  a._hay = ps.filter(Boolean).join(" ").toLowerCase();
  return a._hay;
}
// 검색어 강조: 매칭 조각 단위로 잘라 각 조각을 따로 이스케이프한다.
function hl(text, tokens){
  const raw = text == null ? "" : String(text);
  if (!tokens || !tokens.length) return esc(raw);
  const pats = tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).filter(Boolean);
  if (!pats.length) return esc(raw);
  const re = new RegExp("(" + pats.join("|") + ")", "gi");
  let out = "", last = 0, m;
  while ((m = re.exec(raw)) !== null){
    out += esc(raw.slice(last, m.index)) + "<mark>" + esc(m[0]) + "</mark>";
    last = m.index + m[0].length;
    if (m.index === re.lastIndex) re.lastIndex++;
  }
  return out + esc(raw.slice(last));
}

// opts: {num: 지도 번호, anchor: 날짜별 보기의 카드(지도에서 이동할 id), tokens, open, dated: 날짜 표시}
function cardHtml(a, opts) {
  opts = opts || {};
  const tokens = opts.tokens || null;
  const num = opts.num ? `<span class="m-num" aria-label="지도 ${opts.num}번">${opts.num}</span>` : "";
  const date = opts.dated && a._date
    ? `<button class="m-date" type="button" data-goto="${esc(a._date)}" title="이날 브리핑 보기">${esc(fmtDate(a._date))}</button>` : "";
  const who = a.researchers ? `<p class="who">${esc(a.researchers)}</p>` : "";
  const summary = a.summary ? `<p class="summary">${hl(a.summary, tokens)}</p>` : "";
  const sections = (a.body||[]).map(s =>
    `<div class="sec"><div class="sec-h">${esc(s.h)}</div><p class="sec-p">${esc(s.p)}</p></div>`).join("");
  const references = (a.references||[]).length
    ? `<div class="sec"><div class="sec-h">참고문헌</div><ol class="refs">` +
      a.references.map(r => `<li>${esc(r.apa||"")} ${safeUrl(r.url) ? `<a href="${esc(safeUrl(r.url))}" target="_blank" rel="noopener">${esc(r.url)}</a>` : ""}</li>`).join("") + `</ol></div>`
    : "";
  const deep = sections
    ? (opts.open
      ? `<button class="deep-toggle" type="button" aria-expanded="true">접기 ⌃</button><div class="deep">${sections}${references}</div>`
      : `<button class="deep-toggle" type="button" aria-expanded="false">본문 자세히 ⌄</button><div class="deep" hidden>${sections}${references}</div>`)
    : "";
  const talk = a.talk
    ? `<div class="talk"><div class="talk-label">이야깃거리</div><div class="talk-body">${esc(a.talk)}</div></div>` : "";
  const curric = (a.curriculum||[]).length
    ? `<div class="curric-block"><div class="curric-label">교육과정 연계</div><div class="curric">` +
      a.curriculum.map(c => `<button class="curric-item" type="button" aria-expanded="false" data-code="${esc(c.code)}"><b>${esc(c.code)}</b> ${esc(c.gloss)}</button>`).join("") +
      `</div><div class="curric-detail"></div></div>` : "";
  const src = a.source && safeUrl(a.source.url)
    ? `<div class="foot"><a class="src" href="${esc(safeUrl(a.source.url))}" target="_blank" rel="noopener">${esc(a.source.name)} 원문 →</a></div>` : "";
  const idAttr = opts.anchor ? ` id="a-${esc(a.id||"")}"` : "";
  return `<article class="card"${idAttr}>
    <div class="meta">${num}${date}<span class="m-region">${esc(a.region||"")}</span><span class="m-journal">${esc(a.journal||"")}</span></div>
    <h3 class="title">${hl(a.title, tokens)}</h3>
    ${who}${summary}${deep}${talk}${curric}${src}
  </article>`;
}

// --- 세계지도 ---
// 투영 상수는 world_land_path.txt를 만든 스크립트와 같아야 한다: 위도 [-60, 84] → 1000×400.
// 태평양 중심(viewBox minX=417). 창 왼쪽 밖의 점은 지도 폭(W)만큼 옮겨 복제본 위에 둔다.
const svg = document.getElementById("navmap");
const NS = "http://www.w3.org/2000/svg";
const W = 1000, H = 400, TOP = 84, BOT = -60, MINX = 417;
const px = lon => { const x = (lon + 180) * (W / 360); return x < MINX ? x + W : x; };
const py = lat => (TOP - Math.max(BOT, Math.min(TOP, lat))) * (H / (TOP - BOT));
const layer = document.createElementNS(NS, "g");
svg.appendChild(layer);
function svgEl(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  Object.keys(attrs).forEach(k => e.setAttribute(k, attrs[k]));
  if (text !== undefined) e.textContent = text;
  return e;
}
const hasGeo = a => !!(a.geo && typeof a.geo.lat === "number" && typeof a.geo.lon === "number");
function drawMap(d) {
  layer.replaceChildren();
  // 위치가 기록되지 않은 날은 빈 지도 대신 안내 문장만 남긴다.
  const located = d.articles.some(hasGeo);
  svg.toggleAttribute("hidden", !located);
  // 화면에서 늘 같은 크기로 보이도록 표식 크기를 지도 폭에 맞춘다(지도 단위 / CSS 픽셀).
  const k = W / Math.max(svg.clientWidth || W, 1);
  const r = 11 * k, gap = 2.3 * r;
  const placed = [];
  let n = 0;
  d.articles.forEach((a, i) => {
    if (!hasGeo(a)) return;
    const g = a.geo;
    let x = px(g.lon), y = py(g.lat), t = 1;
    while (placed.some(p => (p.x-x)**2 + (p.y-y)**2 < gap*gap) && t <= 12) {
      const ang = t * 2.4, step = gap * Math.ceil(t/3);
      x = px(g.lon) + Math.cos(ang) * step; y = py(g.lat) + Math.sin(ang) * step; t++;
    }
    placed.push({x, y});
    const label = g.label || "";
    const grp = svgEl("g", {class: "mk", "data-id": a.id, tabindex: "0", role: "button",
      "aria-label": `${i+1}번 ${label} ${a.title}`});
    grp.appendChild(svgEl("title", {}, (label ? label + ": " : "") + a.title));
    grp.appendChild(svgEl("circle", {class: "mk-dot", cx: x.toFixed(1), cy: y.toFixed(1), r: r.toFixed(2), "stroke-width": (2*k).toFixed(2)}));
    grp.appendChild(svgEl("text", {class: "mk-num", x: x.toFixed(1), y: y.toFixed(1), dy: ".36em",
      "text-anchor": "middle", "font-size": (12*k).toFixed(2)}, String(i+1)));
    if (label) {
      const fs = 13 * k, width = label.length * fs * 0.98, off = r + 5*k;
      const right = x + off + width <= MINX + W - 6*k;
      grp.appendChild(svgEl("text", {class: "mk-label", x: (right ? x + off : x - off).toFixed(1), y: y.toFixed(1),
        dy: ".36em", "text-anchor": right ? "start" : "end", "font-size": fs.toFixed(2),
        "stroke-width": (3.5*k).toFixed(2)}, label));
    }
    layer.appendChild(grp);
    n++;
  });
  document.getElementById("map-note").textContent = n
    ? "지도의 번호를 누르면 아래 같은 번호의 브리핑으로 이동합니다."
    : "이날 브리핑에는 지도 위치가 기록되어 있지 않습니다.";
}
function goToCard(id) {
  const el = document.getElementById("a-" + id);
  if (!el) return;
  const y = el.getBoundingClientRect().top + window.scrollY - (44 + 12);
  window.scrollTo({ top: y, behavior: "smooth" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1800);
}
svg.addEventListener("click", e => { const m = e.target.closest(".mk"); if (m) goToCard(m.getAttribute("data-id")); });
svg.addEventListener("keydown", e => {
  const m = e.target.closest(".mk");
  if (m && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); goToCard(m.getAttribute("data-id")); }
});
let resizeFrame = 0;
window.addEventListener("resize", () => {
  if (view !== "day" || !DAYS.length) return;
  cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => drawMap(DAYS[cur]));
});

// --- 날짜별 보기 ---
function setHash(h) {
  const url = location.pathname + location.search + (h ? "#" + h : "");
  try { history.replaceState(null, "", url); } catch (e) {}
}
function byMonth(list, rowFn) {
  let out = "", month = "";
  list.forEach(d => {
    const m = d.date.slice(0, 7);
    if (m !== month) {
      if (month) out += "</div>";
      month = m;
      const p = parts(d.date);
      out += `<h3 class="arch-month">${p[0]}년 ${p[1]}월</h3><div class="arch-group">`;
    }
    out += rowFn(d);
  });
  return out + (month ? "</div>" : "");
}
function renderArchive() {
  const sel = DAYS[cur] ? DAYS[cur].date : "";
  const deep = DAYS.filter(isDeep), old = DAYS.filter(d => !isDeep(d));
  let out = byMonth(deep, d => `<button class="arch-row${d.date === sel ? " on" : ""}" type="button" data-goto="${esc(d.date)}">
      <span class="arch-date">${esc(shortDate(d.date))} ${esc(weekday(d.date))}</span>
      <span class="arch-titles">${d.articles.map(a => `<span class="arch-t"><em>${esc(a.region||"")}</em>${esc(a.title)}</span>`).join("")}</span>
    </button>`);
  if (old.length) {
    const opened = oldOpen || old.some(d => d.date === sel);
    const chips = byMonth(old, d => `<button class="arch-chip${d.date === sel ? " on" : ""}" type="button" data-goto="${esc(d.date)}">${parts(d.date)[2]}일<span>${d.articles.length}건</span></button>`)
      .replace(/<div class="arch-group">/g, `<div class="arch-chips">`);
    out += `<details class="arch-old"${opened ? " open" : ""}>
      <summary>이전 형식 브리핑 · ${esc(fmtDate(old[old.length-1].date))} ~ ${esc(fmtDate(old[0].date))} · ${old.length}일</summary>
      <div class="arch-old-body">${chips}</div></details>`;
  }
  out += `<div class="arch-special"><h3 class="arch-month">특별 심층 글 (2026. 10. 10.)</h3>
    <a href="deep/nepal-flood-2026.html">네팔 홍수 참사: 발생 배경과 피해, 남겨진 과제</a>
    <a href="deep/europe-heat-2026.html">2026년 여름 유럽 폭염: 기록적 고온과 지역별 피해의 차이</a></div>`;
  document.getElementById("archive").innerHTML = out;
}
function renderDay() {
  const d = DAYS[cur];
  if (!d) { document.getElementById("day-cards").innerHTML = `<p class="empty">아직 발행된 브리핑이 없습니다.</p>`; return; }
  document.getElementById("day-label").textContent = fmtDay(d.date);
  const regions = d.articles.map(a => a.region).filter(Boolean);
  document.getElementById("day-sub").textContent = isDeep(d)
    ? `${regions.join("·")} 심층 브리핑 ${d.articles.length}건` : `브리핑 ${d.articles.length}건`;
  document.getElementById("day-prev").disabled = cur >= DAYS.length - 1;
  document.getElementById("day-next").disabled = cur <= 0;
  document.getElementById("day-latest").hidden = cur === 0;
  drawMap(d);
  let html = "";
  if (!isDeep(d) && FIRST_DEEP) {
    html += `<p class="era-note">이전 형식의 브리핑입니다. ${esc(fmtDate(FIRST_DEEP.date))}부터는 국내·해외 심층 브리핑을 하루 2건씩 싣고 있습니다.</p>`;
  }
  html += d.articles.map((a, i) => cardHtml(withDate(a, d.date), {num: hasGeo(a) ? i + 1 : 0, anchor: true})).join("");
  document.getElementById("day-cards").innerHTML = html;
  renderArchive();
  setHash(cur === 0 ? "" : "d=" + d.date);
}
function selectDay(i, scroll) {
  if (i < 0 || i >= DAYS.length) return;
  cur = i;
  if (view !== "day") setView("day"); else renderDay();
  if (scroll) {
    const y = document.getElementById("view-day").getBoundingClientRect().top + window.scrollY - 44;
    window.scrollTo({ top: y, behavior: "smooth" });
  }
}
document.getElementById("day-prev").addEventListener("click", () => selectDay(cur + 1));
document.getElementById("day-next").addEventListener("click", () => selectDay(cur - 1));
document.getElementById("day-latest").addEventListener("click", () => selectDay(0));
document.getElementById("archive").addEventListener("toggle", e => {
  if (e.target.matches("details.arch-old")) oldOpen = e.target.open;
}, true);

// --- 성취기준별 보기 ---
function stdFullHtml(code) {
  const info = CURR[code]; if (!info) return "";
  return `<div class="cd-code">${esc(code)}</div><div class="cd-text">${esc(info.text)}</div>` +
    (info.explain ? `<div class="cd-explain"><span class="cd-label">해설</span>${esc(info.explain)}</div>` : "");
}
function renderCurr() {
  document.getElementById("subj-chips").innerHTML = SUBJECTS.map((s, i) =>
    `<button class="chip${i === subj ? " on" : ""}" type="button" data-subj="${i}">${esc(s.name)}<span class="n">${subjCount(s)}</span></button>`).join("");
  const s = SUBJECTS[subj];
  const box = document.getElementById("curr");
  if (!s) { box.innerHTML = `<p class="empty">교육과정 자료를 불러오지 못했습니다.</p>`; return; }
  const rows = s.codes.map(code => {
    const arts = STD_ARTS[code] || [];
    const isOpen = openStd === code;
    const body = isOpen
      ? `<div class="std-body"><div class="std-full">${stdFullHtml(code)}</div>` +
        (arts.length ? arts.map(a => cardHtml(a, {open: true, dated: true})).join("")
                     : `<p class="std-empty">아직 이 성취기준에 연결된 브리핑이 없습니다.</p>`) + `</div>`
      : "";
    return `<section class="std${arts.length ? "" : " none"}${isOpen ? " open" : ""}" id="std-${esc(code)}">
      <button class="std-row" type="button" data-std="${esc(code)}" aria-expanded="${isOpen}">
        <span class="std-code">${esc(code)}</span>
        <span class="std-gloss">${esc(stdGloss(code))}</span>
        <span class="std-n">${arts.length}건</span>
        <span class="chev" aria-hidden="true">⌄</span>
      </button>${body}
    </section>`;
  }).join("");
  const linked = s.codes.filter(c => (STD_ARTS[c]||[]).length).length;
  box.innerHTML = `<h2 class="theme-head">${esc(s.name)}<span class="theme-n">성취기준 ${s.codes.length}개 · 브리핑 연결 ${linked}개</span></h2>
    <p class="std-hint">성취기준을 누르면 본문·해설과 연결된 브리핑이 열립니다. 연결된 브리핑이 없는 성취기준은 흐리게 표시됩니다.</p>
    ${rows}`;
}
function openStandard(code, scroll) {
  const i = SUBJECTS.findIndex(s => s.codes.includes(code));
  if (i < 0) return false;
  subj = i; openStd = code;
  setView("curr"); setHash("std=" + encodeURIComponent(code));
  if (scroll) {
    const el = document.getElementById("std-" + code);
    if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 56, behavior: "smooth" });
  }
  return true;
}
document.getElementById("subj-chips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  subj = +b.dataset.subj; openStd = null; setHash(""); renderCurr();
});

// --- 검색 보기 ---
const qInput = document.getElementById("q");
const qClear = document.getElementById("q-clear");
function renderSearch() {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const box = document.getElementById("results");
  qClear.classList.toggle("show", tokens.length > 0);
  if (!tokens.length) { box.innerHTML = `<p class="empty">모든 날짜의 브리핑에서 찾습니다.</p>`; return; }
  const arts = [];
  DAYS.forEach(d => d.articles.forEach(a => {
    if (tokens.every(t => searchText(a).includes(t))) arts.push(withDate(a, d.date));
  }));
  box.innerHTML = arts.length
    ? `<h2 class="theme-head">검색 결과<span class="theme-n">${arts.length}건</span></h2>` +
      arts.map(a => cardHtml(a, {tokens, dated: true})).join("")
    : `<p class="empty">‘${esc(query.trim())}’에 대한 결과가 없습니다.</p>`;
}
qInput.addEventListener("input", () => { query = qInput.value; renderSearch(); });
qInput.addEventListener("keydown", e => { if (e.key === "Escape") { qInput.value = ""; query = ""; renderSearch(); } });
qClear.addEventListener("click", () => { qInput.value = ""; query = ""; renderSearch(); qInput.focus(); });

// --- 보기 전환 ---
function setView(v) {
  view = v;
  document.querySelectorAll("#viewtabs button").forEach(b => {
    const on = b.dataset.view === v;
    b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on));
  });
  document.getElementById("view-day").hidden = v !== "day";
  document.getElementById("view-curr").hidden = v !== "curr";
  document.getElementById("view-search").hidden = v !== "search";
  if (v === "day") renderDay();
  else if (v === "curr") renderCurr();
  else { renderSearch(); setHash(""); }
}
document.getElementById("viewtabs").addEventListener("click", e => {
  const b = e.target.closest("button[data-view]"); if (!b || b.dataset.view === view) return;
  if (b.dataset.view !== "curr") openStd = null;
  if (b.dataset.view === "curr") setHash("");
  setView(b.dataset.view);
  if (view === "search") qInput.focus();
});

// 카드 안의 단추들(세 보기 공통)
document.querySelector("main").addEventListener("click", e => {
  const go = e.target.closest("[data-goto]");
  if (go) { selectDay(dayIndex(go.getAttribute("data-goto")), true); return; }
  const toggle = e.target.closest(".deep-toggle");
  if (toggle) {
    const deep = toggle.nextElementSibling, open = !deep.hidden;
    deep.hidden = open;
    toggle.setAttribute("aria-expanded", String(!open));
    toggle.textContent = open ? "본문 자세히 ⌄" : "접기 ⌃";
    return;
  }
  const item = e.target.closest(".curric-item");
  if (item) {
    const code = item.getAttribute("data-code");
    if (!CURR[code]) return;
    const row = item.closest(".curric"), detail = row.nextElementSibling;
    const same = detail.classList.contains("open") && detail.getAttribute("data-code") === code;
    row.querySelectorAll(".curric-item").forEach(b => { b.classList.remove("active"); b.setAttribute("aria-expanded", "false"); });
    if (same) { detail.classList.remove("open"); detail.removeAttribute("data-code"); return; }
    detail.setAttribute("data-code", code);
    const n = (STD_ARTS[code]||[]).length;
    const more = SUBJECTS.some(s => s.codes.includes(code)) && !(view === "curr" && openStd === code)
      ? `<a class="cd-more" href="#std=${encodeURIComponent(code)}" data-std-link="${esc(code)}">이 성취기준 브리핑 ${n}건 모두 보기 →</a>` : "";
    detail.innerHTML = stdFullHtml(code) + more;
    detail.classList.add("open"); item.classList.add("active"); item.setAttribute("aria-expanded", "true");
    return;
  }
  const link = e.target.closest("[data-std-link]");
  if (link) { e.preventDefault(); openStandard(link.getAttribute("data-std-link"), true); return; }
  const stdRow = e.target.closest(".std-row");
  if (stdRow) {
    const code = stdRow.getAttribute("data-std");
    openStd = openStd === code ? null : code;
    setHash(openStd ? "std=" + encodeURIComponent(openStd) : "");
    renderCurr();
    if (openStd) {
      const el = document.getElementById("std-" + code);
      if (el && el.getBoundingClientRect().top < 44) el.scrollIntoView({ block: "start" });
    }
  }
});

// 주소의 #d=YYYY-MM-DD(날짜), #std=코드(성취기준)로 바로 연다.
function openFromHash(scroll) {
  const h = location.hash.slice(1);
  let m = /^std=(.+)$/.exec(h);
  if (m && openStandard(decodeURIComponent(m[1]), scroll)) return;
  m = /^d=(\d{4}-\d{2}-\d{2})$/.exec(h);
  const i = m ? dayIndex(m[1]) : -1;
  cur = i >= 0 ? i : 0;
  setView("day");
}
window.addEventListener("hashchange", () => openFromHash(true));
openFromHash(false);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=DATA_DIR)
    parser.add_argument("--output", default=OUT)
    parser.add_argument(
        "--world-path", default=os.path.join(HERE, "world_land_path.txt")
    )
    parser.add_argument(
        "--curriculum-ref", default=os.path.join(HERE, "..", "curriculum_ref.json")
    )
    args = parser.parse_args()
    build(
        data_dir=args.data_dir,
        out=args.output,
        world_path_file=args.world_path,
        curriculum_ref_file=args.curriculum_ref,
    )
