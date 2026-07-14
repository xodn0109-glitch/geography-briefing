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
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "index.html")

def load_days():
    days = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            day = json.load(f)
        # 렌더에 쓰는 필드만 담는다 — 봇이 남긴 잔여 필드(intro·weekday 등)가 payload에 실리지 않게.
        days.append({"date": day.get("date", ""), "articles": day.get("articles", [])})
    # 날짜 내림차순 — 지도 내비게이터의 idx=0=최신 가정이 이 정렬에 의존한다.
    days.sort(key=lambda d: d["date"], reverse=True)
    return days


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{y}. {int(m)}. {int(d)}."


def build():
    days = load_days()

    # 통계
    total_articles = sum(len(d["articles"]) for d in days)
    cats = {a["category"] for d in days for a in d["articles"]}

    # < 전체를 이스케이프해 </script>·<!-- 등 파서 이탈을 원천 차단(JSON 문자열 안에서만 등장 가능).
    payload = json.dumps({"days": days}, ensure_ascii=False).replace("<", "\\u003c")

    tpl = HTML_TEMPLATE
    tpl = tpl.replace("__TOTAL__", str(total_articles))
    tpl = tpl.replace("__DAYS__", str(len(days)))
    tpl = tpl.replace("__CATCOUNT__", str(len(cats)))
    tpl = tpl.replace("__LATEST__", fmt_date(days[0]["date"]) if days else "")

    # 세계지도 내비게이터 육지 윤곽 (Natural Earth 110m, 퍼블릭 도메인 → SVG path 사전 변환본)
    wp_file = os.path.join(HERE, "world_land_path.txt")
    world_path = ""
    if os.path.exists(wp_file):
        with open(wp_file, encoding="utf-8") as f:
            world_path = f.read().strip()
    tpl = tpl.replace("__WORLDPATH__", world_path)

    # 교육과정 성취기준 전문(빌드 시 ../curriculum_ref.json 참조 — 실제 사용된 코드만 심어 클릭 시 노출).
    # 참조 파일이 없으면 빈 객체 → 배지는 그대로 보이되 펼침만 비활성(우아한 강등).
    curr = {}
    ref_file = os.path.join(HERE, "..", "curriculum_ref.json")
    if os.path.exists(ref_file):
        with open(ref_file, encoding="utf-8") as f:
            ref = json.load(f)
        flat = {}
        for stds in ref.get("subjects", {}).values():
            for s in stds:
                flat[s["code"]] = s
        used = set()
        for d in days:
            for a in d["articles"]:
                for c in (a.get("curriculum") or []):
                    used.add(c["code"])
        for code in used:
            s = flat.get(code)
            if not s:
                continue
            # 해설은 원문에서 코드를 떼며 남은 선행 조사(에서는/은/는…)를 제거해 자연스럽게.
            ex = re.sub(r"^(에서는|에서|은|는|이|가|을|를|와|과)\s+", "", (s.get("explain") or "").strip())
            curr[code] = {"text": s.get("text", ""), "explain": ex}
    tpl = tpl.replace("__CURRICULUM__", json.dumps(curr, ensure_ascii=False).replace("<", "\\u003c"))
    # 기사 본문(payload)은 자유 텍스트라 다른 플레이스홀더 토큰을 담을 수 있다 — 반드시 맨 마지막에 치환.
    tpl = tpl.replace("__DATA__", payload)

    # 임시 파일에 쓴 뒤 원자 교체 — 부분 쓰기 상태의 index.html이 남지 않게.
    tmp_out = OUT + ".tmp"
    with open(tmp_out, "w", encoding="utf-8") as f:
        f.write(tpl)
    os.replace(tmp_out, OUT)
    print(f"built {OUT}  ({len(days)} days, {total_articles} articles)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지리 뉴스 브리핑 아카이브 — 깊이 읽기</title>
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
    --yellow: #ffce00;
    --glass: rgba(245,245,247,.82);
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
    --maxw: 940px;
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
  .wrap { max-width: var(--maxw); margin: 0 auto; padding: 0 22px; }

  /* 상단 다크 바 */
  .topnav { position: sticky; top: 0; z-index: 30; background: #000; height: 44px;
            display: flex; align-items: center; }
  .topnav .wrap { width: 100%; display: flex; align-items: center; justify-content: space-between; }
  .tn-brand { color: #f5f5f7; font-size: 13px; font-weight: 600; letter-spacing: -.02em; }
  .tn-stat { color: #86868b; font-size: 12px; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }

  /* 히어로 */
  .hero { background: var(--surface); padding: 40px 22px 36px; }
  .hero-inner { max-width: 720px; margin: 0 auto; text-align: center; }
  .brand { display: flex; align-items: center; justify-content: center; gap: clamp(12px, 1.6vw, 18px); }
  .frame { width: clamp(29px, 4.7vw, 44px); height: clamp(42px, 6.8vw, 63px);
           border: clamp(4px, 0.65vw, 6px) solid var(--yellow); border-radius: 2px; flex: none; }
  h1 { font-size: clamp(34px, 6vw, 56px); font-weight: 600; line-height: 1.06;
       letter-spacing: -.03em; color: var(--ink); margin: 0; }
  .tagline { font-size: clamp(19px, 2.6vw, 26px); font-weight: 400; line-height: 1.32;
             letter-spacing: -.008em; color: var(--ink); margin: 24px auto 0; max-width: 34rem; }
  .stat { font-size: 14px; color: var(--ink-faint); letter-spacing: -.01em; margin: 28px 0 0;
          font-variant-numeric: tabular-nums; }

  /* 지도 */
  .mapnav { background: var(--surface); padding: 8px 22px 56px; }
  .map-inner { max-width: var(--maxw); margin: 0 auto; }
  .map-datebar { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 16px; }
  .map-datebar button { font: inherit; font-size: 13px; border: 1px solid #d2d2d7; background: #fff;
                        color: var(--ink); border-radius: 980px; width: 32px; height: 32px; cursor: pointer;
                        transition: border-color .15s var(--ease-out), transform .16s var(--ease-out); }
  .map-datebar button:hover:not(:disabled) { border-color: var(--accent); }
  .map-datebar button:active:not(:disabled) { transform: scale(0.92); }
  .map-datebar button:disabled { opacity: .3; cursor: default; }
  #map-date { color: var(--ink); font-size: 15px; font-weight: 600; letter-spacing: -.01em;
              font-variant-numeric: tabular-nums; min-width: 14ch; text-align: center; }
  #navmap { width: 100%; height: auto; display: block; }
  #navmap .land, #navmap use { fill: #e8e8ed; stroke: #d2d2d7; stroke-width: .6; }
  .newsdot { fill: var(--accent); stroke: #fff; stroke-width: 1.8; pointer-events: none; }
  .newsdot-hit { fill: transparent; cursor: pointer; }
  .newsdot-hit:hover { fill: var(--accent); opacity: .22; }
  .map-hint { margin: 14px 0 0; font-size: 13px; color: var(--ink-faint); text-align: center; letter-spacing: -.01em; }

  /* 필터 */
  .filters { position: sticky; top: 44px; z-index: 20; background: var(--glass);
             -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
             border-bottom: 1px solid var(--line); }
  .filters .wrap { display: flex; flex-direction: column; gap: 10px; padding-top: 12px; padding-bottom: 12px; }
  .searchbar { position: relative; width: 100%; }
  .searchbar .s-icon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%);
                       width: 16px; height: 16px; color: var(--ink-faint); pointer-events: none; }
  .searchbar input { width: 100%; font: inherit; font-size: 15px; line-height: 1.2;
                     padding: 11px 42px 11px 40px; border: 1px solid var(--line); border-radius: 980px;
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
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  mark { background: #fff3b0; color: inherit; border-radius: 3px; padding: 0 1px; }
  .chip { font: inherit; font-size: 14px; cursor: pointer; border: 1px solid var(--line);
          background: #fff; color: var(--ink-soft); padding: 8px 15px; border-radius: 980px;
          white-space: nowrap; letter-spacing: -.01em;
          transition: background-color .15s var(--ease-out), color .15s var(--ease-out), transform .16s var(--ease-out); }
  .chip:active { transform: scale(0.96); }
  .chip.on { background: var(--accent); color: #fff; font-weight: 600; border-color: transparent; }
  .chip .n { opacity: .55; margin-left: 6px; font-variant-numeric: tabular-nums; }

  /* 피드 */
  main .wrap { padding-top: 40px; padding-bottom: 100px; }
  .theme { margin-bottom: 60px; }
  .theme-head { font-size: clamp(24px, 3vw, 32px); font-weight: 600; letter-spacing: -.02em;
                color: var(--ink); margin: 0 0 22px; display: flex; align-items: baseline; gap: 10px; }
  .theme-n { font-size: 14px; font-weight: 600; color: var(--ink-faint); letter-spacing: 0;
             white-space: nowrap; flex: none; }

  .card { background: var(--surface); border: 1px solid var(--line); border-radius: 18px;
          padding: 26px 28px; margin-bottom: 18px; transition: box-shadow .4s var(--ease-out); }
  .card.flash { box-shadow: 0 0 0 3px var(--accent); border-color: transparent; }
  .meta { display: flex; align-items: baseline; gap: 9px; flex-wrap: wrap; margin-bottom: 2px; }
  .m-date { font-size: 14px; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
  .m-region { font-size: 13px; color: var(--ink-faint); letter-spacing: -.01em; }
  .m-journal { margin-left: auto; font-size: 13px; color: var(--ink-faint); text-align: right; letter-spacing: -.01em; }
  h3.title { font-size: clamp(20px, 2.4vw, 24px); font-weight: 600; line-height: 1.28;
             letter-spacing: -.02em; color: var(--ink); margin: 8px 0 0; }
  .who { margin: 10px 0 0; font-size: 13px; color: var(--ink-faint); line-height: 1.5; letter-spacing: -.01em; }
  .summary { margin: 16px 0 0; font-size: 17px; line-height: 1.6; color: var(--ink-soft); letter-spacing: -.01em; }

  .deep-toggle { margin-top: 14px; cursor: pointer; color: var(--accent); font-weight: 600; font-size: 15px;
                 background: none; border: none; padding: 4px 0; font-family: inherit; letter-spacing: -.01em;
                 transition: transform .16s var(--ease-out); }
  .deep-toggle:active { transform: scale(0.97); }
  .deep { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 6px; }
  .deep[hidden] { display: none; }
  .sec { margin-top: 16px; }
  .sec-h { font-size: 14px; font-weight: 600; color: var(--ink); letter-spacing: -.01em; }
  .sec-p { margin: 5px 0 0; font-size: 16px; line-height: 1.66; color: var(--ink-soft); letter-spacing: -.01em; }

  .talk { margin-top: 18px; background: #fafafc; border: 1px solid #f0f0f0; border-radius: 12px; padding: 15px 18px; }
  .talk-label { font-size: 12px; font-weight: 600; color: var(--ink-faint); letter-spacing: .02em; margin-bottom: 6px; }
  .talk-body { font-size: 16px; line-height: 1.6; color: var(--ink); letter-spacing: -.01em; }

  .curric-block { margin-top: 18px; }
  .curric-label { font-size: 12px; font-weight: 600; color: var(--ink-faint); letter-spacing: .02em; margin-bottom: 9px; }
  .curric { display: flex; flex-wrap: wrap; gap: 8px; }
  .curric-item { font: inherit; font-size: 13px; cursor: pointer; background: #fff; border: 1px solid var(--line);
                 padding: 6px 13px; border-radius: 980px; color: var(--ink-soft); letter-spacing: -.01em;
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

  .foot { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 20px; }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { font-size: 13px; color: var(--ink-faint); background: var(--surface-2); padding: 3px 10px;
         border-radius: 980px; letter-spacing: -.01em; }
  a.src { margin-left: auto; font-size: 14px; font-weight: 600; color: var(--accent); text-decoration: none;
          border: 1px solid var(--accent); border-radius: 980px; padding: 8px 16px; white-space: nowrap;
          letter-spacing: -.01em;
          transition: background-color .15s var(--ease-out), transform .16s var(--ease-out); }
  a.src:hover { background: var(--surface-2); text-decoration: none; }
  a.src:active { transform: scale(0.96); }

  .empty { text-align: center; color: var(--ink-faint); padding: 80px 0; font-size: 15px; letter-spacing: -.01em; }

  footer.bot { background: var(--page); border-top: 1px solid var(--line); }
  footer.bot .wrap { padding: 48px 22px 60px; }
  footer.bot p { margin: 5px 0; font-size: 12px; line-height: 1.7; color: #7a7a7a; letter-spacing: -.01em; }

  @media (prefers-reduced-motion: reduce) {
    .chip:active, a.src:active, .curric-item:active, .deep-toggle:active,
    .map-datebar button:active:not(:disabled) { transform: none; }
  }
</style>
</head>
<body>
<div class="topnav">
  <div class="wrap">
    <span class="tn-brand">Powered by TW.graphy</span>
    <span class="tn-stat">__TOTAL__건 · __DAYS__일</span>
  </div>
</div>

<header class="hero">
  <div class="hero-inner">
    <div class="brand">
      <span class="frame"></span>
      <h1>지리 뉴스 브리핑 아카이브</h1>
    </div>
    <p class="tagline">매일 아침 보내드리는 텔레그램 요약본의 조금 더 긴 내용을 이 사이트에서 확인할 수 있습니다.</p>
    <p class="stat">__TOTAL__건 · __DAYS__일치 · __CATCOUNT__개 분야 · 최신 __LATEST__</p>
  </div>
</header>

<section class="mapnav">
  <div class="map-inner">
    <div class="map-datebar">
      <button id="map-prev" type="button" aria-label="이전 날짜">◀</button>
      <span id="map-date" aria-live="polite"></span>
      <button id="map-next" type="button" aria-label="다음 날짜">▶</button>
    </div>
    <svg id="navmap" viewBox="417 0 1000 400" role="img" aria-label="기사 위치 세계지도 (태평양 중심)">
      <path id="land-path" class="land" d="__WORLDPATH__"/>
      <use href="#land-path" x="1000"/>
      <use href="#land-path" x="-1000"/>
    </svg>
    <p class="map-hint">그날의 뉴스가 일어난 곳 — 점을 누르면 해당 기사로 이동합니다 (전 지구 단위 연구는 표시되지 않음)</p>
  </div>
</section>

<nav class="filters">
  <div class="wrap">
    <div class="searchbar">
      <svg class="s-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>
      <input id="q" type="search" autocomplete="off" placeholder="키워드로 검색 — 화산, 도시, 인구, 기후…" aria-label="기사 키워드 검색">
      <button id="q-clear" class="s-clear" type="button" aria-label="검색어 지우기">×</button>
    </div>
    <div class="chips" id="chips"></div>
  </div>
</nav>

<main>
  <div class="wrap" id="feed"></div>
</main>

<footer class="bot">
  <div class="wrap">
    <p>이 사이트는 매일 아침 브리핑 봇이 생성합니다. 본문의 사실 진술은 각 기사 원문에서 확인한 것이며, 이야깃거리는 편집자의 해석입니다.</p>
    <p>각 카드의 ‘본문 자세히’를 눌러 전체를 열고, ‘매체명 →’으로 원문을 확인하세요.</p>
  </div>
</footer>

<script>
const DATA = __DATA__;
const CURR = __CURRICULUM__;   // {code: {text(본문), explain(해설)}} — 실제 사용된 성취기준만
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const safeUrl = u => /^https?:\/\//i.test(String(u)) ? String(u) : "";
const fmtDate = iso => { const p = String(iso).split("-"); return `${p[0]}. ${+p[1]}. ${+p[2]}.`; };

// 분야별 카운트
const catCount = {};
DATA.days.forEach(d => d.articles.forEach(a => { catCount[a.category] = (catCount[a.category]||0)+1; }));
let active = "전체";
let query = "";  // 검색어. 비어 있으면 기존 날짜/분야 뷰, 채워지면 검색 모드.
// 분야 표시 순서(지리학 분과 체계: 자연 → 인문 → 정치지리 → 지도·GIS 도구 → 교육). 목록에 없는 분야는 뒤에 자동 추가.
// 필터 칩과 본문 섹션이 반드시 같은 순서를 쓰도록 여기서 한 번만 정한다.
const CAT_ORDER = ["지형학","기후학","도시지리학","경제지리학","지역지리학","문화지리학","역사지리학","인구지리학","지정학·국제","지도학","GIS","지리교육"];
const cats = CAT_ORDER.filter(c => c in catCount)
  .concat(Object.keys(catCount).filter(c => !CAT_ORDER.includes(c)));

function chipsHtml() {
  const total = Object.values(catCount).reduce((s,n)=>s+n,0);
  const all = `<button class="chip on" data-cat="전체">전체<span class="n">${total}</span></button>`;
  return all + cats.map(c =>
    `<button class="chip" data-cat="${esc(c)}">${esc(c)}<span class="n">${catCount[c]}</span></button>`
  ).join("");
}

// 검색 대상 텍스트를 한 번 만들어 원본 기사에 캐시(제목·요약·본문·이야깃거리·태그·지역·연구진·매체·분야·교육과정).
function searchText(a){
  if (a._hay !== undefined) return a._hay;
  const parts = [a.title, a.summary, a.talk, a.region, a.researchers, a.journal, a.category];
  (a.body||[]).forEach(s => { parts.push(s.h, s.p); });
  (a.tags||[]).forEach(t => parts.push(t));
  (a.curriculum||[]).forEach(c => { parts.push(c.code, c.gloss); });
  a._hay = parts.filter(Boolean).join(" ").toLowerCase();
  return a._hay;
}
function articleMatches(a, tokens){
  const hay = searchText(a);
  return tokens.every(t => hay.includes(t));   // 모든 토큰(AND) 포함
}
// 검색어 강조: 원문을 매칭 조각 단위로 잘라 각 조각을 개별 esc → HTML 엔티티가 쪼개질 일이 없음.
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

function cardHtml(a, tokens) {
  const dp = (a._date||"").split("-");
  const dl = dp.length===3 ? `${+dp[1]}.${+dp[2]}` : "";
  const who = a.researchers ? `<p class="who">${esc(a.researchers)}</p>` : "";
  const summary = a.summary ? `<p class="summary">${hl(a.summary, tokens)}</p>` : "";
  const sections = (a.body||[]).map(s =>
    `<div class="sec"><div class="sec-h">${esc(s.h)}</div><p class="sec-p">${esc(s.p)}</p></div>`).join("");
  const deep = sections
    ? `<button class="deep-toggle" type="button" aria-expanded="false">본문 자세히 ⌄</button>` +
      `<div class="deep" hidden>${sections}</div>`
    : "";
  const talk = a.talk
    ? `<div class="talk"><div class="talk-label">이야깃거리</div><div class="talk-body">${esc(a.talk)}</div></div>`
    : "";
  const curric = (a.curriculum||[]).length
    ? `<div class="curric-block"><div class="curric-label">교육과정 연계</div><div class="curric">` +
      a.curriculum.map(c => `<button class="curric-item" type="button" aria-expanded="false" data-code="${esc(c.code)}"><b>${esc(c.code)}</b> ${esc(c.gloss)}</button>`).join("") +
      `</div><div class="curric-detail"></div></div>`
    : "";
  const tags = (a.tags||[]).map(t => `<span class="tag">#${esc(t)}</span>`).join("");
  const src = a.source && safeUrl(a.source.url)
    ? `<a class="src" href="${esc(safeUrl(a.source.url))}" target="_blank" rel="noopener">${esc(a.source.name)} →</a>`
    : "";
  return `<article class="card" id="${esc(a.id||"")}" data-cat="${esc(a.category)}">
    <div class="meta">
      <span class="m-date">${dl}</span>
      <span class="m-region">${esc(a.region)}</span>
      <span class="m-journal">${esc(a.journal||"")}</span>
    </div>
    <h3 class="title">${hl(a.title, tokens)}</h3>
    ${who}
    ${summary}
    ${deep}
    ${talk}
    ${curric}
    <div class="foot"><div class="tags">${tags}</div>${src}</div>
  </article>`;
}

let firstRender = true;  // 최초 로드는 페이드 없이, 이후 필터 전환만 페이드
function render() {
  const feed = document.getElementById("feed");
  let out = "";
  const q = query.trim().toLowerCase();
  const tokens = q ? q.split(/\s+/) : [];
  if (tokens.length) {
    // 검색 모드: (활성 분야가 있으면 그 안에서) 모든 날짜의 매칭 기사를 최신순 평탄 리스트로.
    const arts = [];
    DATA.days.forEach(d => d.articles.forEach(a => {
      if ((active === "전체" || a.category === active) && articleMatches(a, tokens))
        arts.push(Object.assign({_date: d.date}, a));
    }));
    arts.sort((x, y) => y._date.localeCompare(x._date));
    const head = active === "전체" ? "검색 결과" : `검색 결과 · ${esc(active)}`;
    if (arts.length) {
      out = `<section class="theme">
        <h2 class="theme-head">${head}<span class="theme-n">${arts.length}건</span></h2>
        ${arts.map(a => cardHtml(a, tokens)).join("")}
      </section>`;
    }
    feed.innerHTML = out || `<p class="empty">‘${esc(query.trim())}’에 대한 결과가 없습니다.</p>`;
    if (!firstRender && feed.animate) {
      feed.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
    }
    firstRender = false;
    return;
  }
  if (active === "전체") {
    // 기본 뷰: 날짜별 섹션(최신일 먼저). DATA.days는 build에서 이미 최신순.
    // 하루 안에서는 JSON에 담긴 순서(해외 먼저 → 국내) 그대로 둔다.
    DATA.days.forEach(d => {
      if (!d.articles.length) return;
      const arts = d.articles.map(a => Object.assign({_date: d.date}, a));
      out += `<section class="theme">
        <h2 class="theme-head">${esc(fmtDate(d.date))}<span class="theme-n">${arts.length}건</span></h2>
        ${arts.map(a => cardHtml(a)).join("")}
      </section>`;
    });
  } else {
    // 특정 분야 선택: 모든 날짜에서 그 분야만 모아 최신순 평탄 리스트로.
    const arts = [];
    DATA.days.forEach(d => d.articles.forEach(a => {
      if (a.category === active) arts.push(Object.assign({_date: d.date}, a));
    }));
    arts.sort((x, y) => y._date.localeCompare(x._date));
    if (arts.length) {
      out = `<section class="theme">
        <h2 class="theme-head">${esc(active)}<span class="theme-n">${arts.length}건</span></h2>
        ${arts.map(a => cardHtml(a)).join("")}
      </section>`;
    }
  }
  feed.innerHTML = out || `<p class="empty">이 분야의 기사가 아직 없습니다.</p>`;
  // 필터 전환 시 카드가 뚝 바뀌지 않게 옅은 페이드인(불투명도만). 최초 로드는 제외.
  if (!firstRender && feed.animate) {
    feed.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
  }
  firstRender = false;
}

document.getElementById("chips").innerHTML = chipsHtml();
document.getElementById("chips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  active = b.dataset.cat;
  document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c===b));
  render();
});
// 검색 입력
const qInput = document.getElementById("q");
const qClear = document.getElementById("q-clear");
function applyQuery(v){
  query = v;
  qClear.classList.toggle("show", query.trim().length > 0);
  render();
}
qInput.addEventListener("input", () => applyQuery(qInput.value));
qInput.addEventListener("keydown", e => { if (e.key === "Escape") { qInput.value = ""; applyQuery(""); } });
qClear.addEventListener("click", () => { qInput.value = ""; applyQuery(""); qInput.focus(); });
// 본문 자세히 펼치기/접기
document.getElementById("feed").addEventListener("click", e => {
  const btn = e.target.closest(".deep-toggle"); if (!btn) return;
  const deep = btn.nextElementSibling;
  const open = !deep.hidden;
  deep.hidden = open;
  btn.setAttribute("aria-expanded", String(!open));
  btn.textContent = open ? "본문 자세히 ⌄" : "접기 ⌃";
});
// 교육과정 배지 클릭 → 성취기준 본문+해설 전문 펼치기(같은 배지 다시 누르면 접기).
document.getElementById("feed").addEventListener("click", e => {
  const item = e.target.closest(".curric-item"); if (!item) return;
  const code = item.getAttribute("data-code");
  const info = CURR[code]; if (!info) return;
  const row = item.closest(".curric");
  const detail = row.nextElementSibling;
  const same = detail.classList.contains("open") && detail.getAttribute("data-code") === code;
  row.querySelectorAll(".curric-item").forEach(b => { b.classList.remove("active"); b.setAttribute("aria-expanded", "false"); });
  if (same) { detail.classList.remove("open"); detail.removeAttribute("data-code"); return; }
  detail.setAttribute("data-code", code);
  detail.innerHTML = `<div class="cd-code">${esc(code)}</div><div class="cd-text">${esc(info.text)}</div>` +
    (info.explain ? `<div class="cd-explain"><span class="cd-label">해설</span>${esc(info.explain)}</div>` : "");
  detail.classList.add("open"); item.classList.add("active"); item.setAttribute("aria-expanded", "true");
  if (detail.animate) detail.animate([{opacity:0},{opacity:1}], {duration:180, easing:"cubic-bezier(0.23,1,0.32,1)"});
});
render();

// --- 세계지도 내비게이터 ---
// 기사 geo:{lat,lon,label}를 equirectangular 투영으로 점 찍기.
// 투영 상수는 world_land_path.txt 생성 스크립트와 반드시 동일해야 한다: lat [-60,84] → 1000×400.
function goToArticle(id){
  // 지도에서 특정 기사로 갈 때는 검색·분야 필터를 풀어 대상 카드가 반드시 존재하게 한다.
  let needRender = false;
  if (query) { query = ""; qInput.value = ""; qClear.classList.remove("show"); needRender = true; }
  if (active !== "전체") {
    active = "전체";
    document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c.dataset.cat === "전체"));
    needRender = true;
  }
  if (needRender) render();  // 동기 렌더 — 프레임 대기 불필요
  const el = document.getElementById(id);
  if (!el) return;
  // sticky 스택 = topnav(44px) + 필터바 실측 높이 — 카드 상단이 바 뒤에 숨지 않게 보정.
  const bar = document.querySelector(".filters");
  const stick = 44 + (bar ? bar.offsetHeight : 12);
  const y = el.getBoundingClientRect().top + window.scrollY - (stick + 12);
  window.scrollTo({ top: y, behavior: "smooth" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1800);
}
(function(){
  const svg = document.getElementById("navmap");
  if (!svg || !DATA.days.length) return;
  const W = 1000, TOP = 84, BOT = -60, H = 400;
  // 태평양 중심(중심 경도 150°E): 창을 오른쪽으로 옮겨(viewBox minX=417) 한국·아시아·태평양을 가운데로.
  // 육지 그림은 <use>로 한 벌 더 이어 붙여 뒀고, 점이 창 왼쪽(MINX) 밖이면 지도 폭(W)만큼 감아 복제본 위에 얹는다.
  // MINX는 SVG viewBox의 minX와 반드시 같은 값이어야 육지와 점이 정렬된다.
  const MINX = 417;
  const px = lon => { const x = (lon + 180) * (W / 360); return x < MINX ? x + W : x; };
  const py = lat => (TOP - Math.max(BOT, Math.min(TOP, lat))) * (H / (TOP - BOT));
  const label = document.getElementById("map-date");
  const btnPrev = document.getElementById("map-prev");   // 과거로
  const btnNext = document.getElementById("map-next");   // 최신으로
  let idx = 0;  // DATA.days 인덱스 (0 = 최신 날짜)

  function draw(){
    svg.querySelectorAll("circle").forEach(c => c.remove());   // 육지 path는 유지
    const day = DATA.days[idx];
    const placed = [];
    let n = 0;
    day.articles.forEach(a => {
      const g = a.geo;
      if (!g || typeof g.lat !== "number" || typeof g.lon !== "number") return;
      let x = px(g.lon), y = py(g.lat), k = 1;
      // 겹침 방지: 기존 점과 10px 이내면 나선형으로 밀어낸다
      while (placed.some(p => (p.x-x)**2 + (p.y-y)**2 < 100) && k <= 12) {
        const ang = k * 2.4;
        x = px(g.lon) + Math.cos(ang) * 7 * Math.ceil(k/3);
        y = py(g.lat) + Math.sin(ang) * 7 * Math.ceil(k/3);
        k++;
      }
      placed.push({x, y});
      const mk = (r, cls) => {
        const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        c.setAttribute("cx", x.toFixed(1)); c.setAttribute("cy", y.toFixed(1));
        c.setAttribute("r", r); c.setAttribute("class", cls);
        c.setAttribute("data-id", a.id);
        const tip = document.createElementNS("http://www.w3.org/2000/svg", "title");
        tip.textContent = (g.label ? g.label + " — " : "") + a.title;
        c.appendChild(tip);
        svg.appendChild(c);
      };
      mk(7, "newsdot");        // 보이는 점
      mk(15, "newsdot-hit");   // 투명 히트 영역(터치·클릭용)
      n++;
    });
    label.textContent = `${fmtDate(day.date)} · ${n}곳`;
    btnPrev.disabled = (idx >= DATA.days.length - 1);
    btnNext.disabled = (idx <= 0);
  }

  btnPrev.addEventListener("click", () => { if (idx < DATA.days.length - 1) { idx++; draw(); } });
  btnNext.addEventListener("click", () => { if (idx > 0) { idx--; draw(); } });
  // 이벤트 위임: svg 하나에만 리스너 (개별 circle 리스너보다 견고)
  svg.addEventListener("click", e => {
    const c = e.target.closest("[data-id]");
    if (c) goToArticle(c.getAttribute("data-id"));
  });
  draw();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
