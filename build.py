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

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "index.html")

def load_days():
    days = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True):
        with open(path, encoding="utf-8") as f:
            days.append(json.load(f))
    # 날짜 내림차순
    days.sort(key=lambda d: d.get("date", ""), reverse=True)
    return days


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{y}. {int(m)}. {int(d)}."


def build():
    days = load_days()

    # 통계
    total_articles = sum(len(d["articles"]) for d in days)
    cats = []
    for d in days:
        for a in d["articles"]:
            if a["category"] not in cats:
                cats.append(a["category"])

    payload = json.dumps({"days": days}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # </script> 방어

    tpl = HTML_TEMPLATE
    tpl = tpl.replace("__DATA__", payload)
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

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(tpl)
    print(f"built {OUT}  ({len(days)} days, {total_articles} articles)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지리 뉴스 브리핑 아카이브 — 깊이 읽기</title>
<style>
  :root {
    --bg: #fbfbfd;
    --surface: #ffffff;
    --surface-2: #f5f5f7;
    --ink: #1d1d1f;
    --ink-soft: #515154;
    --ink-faint: #86868b;
    --line: #e6e6eb;
    --accent: #1f7a5a;
    --accent-soft: #e9f4ee;
    --accent-ink: #146145;
    --talk-bg: #f5f5f7;
    --talk-line: #1f7a5a;
    --talk-ink: #1d1d1f;
    --glass: rgba(251,251,253,.72);
    --shadow: 0 1px 3px rgba(0,0,0,.04), 0 10px 30px rgba(0,0,0,.06);
    --maxw: 800px;
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #000000;
      --surface: #1c1c1e;
      --surface-2: #2c2c2e;
      --ink: #f5f5f7;
      --ink-soft: #a1a1a6;
      --ink-faint: #8e8e93;
      --line: #38383a;
      --accent: #4cd6a0;
      --accent-soft: #14342a;
      --accent-ink: #7fe3bd;
      --talk-bg: #1c1c1e;
      --talk-line: #4cd6a0;
      --talk-ink: #f5f5f7;
      --glass: rgba(0,0,0,.6);
      --shadow: 0 1px 3px rgba(0,0,0,.5), 0 10px 30px rgba(0,0,0,.4);
    }
  }
  :root[data-theme="light"] {
    --bg:#fbfbfd; --surface:#fff; --surface-2:#f5f5f7; --ink:#1d1d1f; --ink-soft:#515154;
    --ink-faint:#86868b; --line:#e6e6eb; --accent:#1f7a5a; --accent-soft:#e9f4ee; --accent-ink:#146145;
    --talk-bg:#f5f5f7; --talk-line:#1f7a5a; --talk-ink:#1d1d1f; --glass:rgba(251,251,253,.72);
    --shadow:0 1px 3px rgba(0,0,0,.04), 0 10px 30px rgba(0,0,0,.06);
  }
  :root[data-theme="dark"] {
    --bg:#000; --surface:#1c1c1e; --surface-2:#2c2c2e; --ink:#f5f5f7; --ink-soft:#a1a1a6;
    --ink-faint:#8e8e93; --line:#38383a; --accent:#4cd6a0; --accent-soft:#14342a; --accent-ink:#7fe3bd;
    --talk-bg:#1c1c1e; --talk-line:#4cd6a0; --talk-ink:#f5f5f7; --glass:rgba(0,0,0,.6);
    --shadow:0 1px 3px rgba(0,0,0,.5), 0 10px 30px rgba(0,0,0,.4);
  }

  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Pretendard",
                 "Noto Sans KR", "Malgun Gothic", sans-serif;
    line-height: 1.72;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: var(--maxw); margin: 0 auto; padding: 0 20px; }

  header.top .wrap { padding-top: 72px; padding-bottom: 40px; }
  .brand { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
  h1 { font-size: clamp(2.1rem, 5.5vw, 3rem); line-height: 1.06; letter-spacing: -.025em; margin: 0; font-weight: 700; }
  .pin { color: var(--accent); }
  .tagline { margin: 18px 0 0; color: var(--ink-soft); font-size: 1.16rem; line-height: 1.5;
             letter-spacing: -.01em; max-width: 30rem; font-weight: 400; }
  .stat { margin-top: 22px; font-size: .82rem; color: var(--ink-faint); letter-spacing: .01em; }
  .stat b { color: var(--accent-ink); font-weight: 700; }

  .mapnav .wrap { padding: 18px 20px 6px; }
  .map-card { background: var(--surface); border: 1px solid var(--line); border-radius: 22px;
              padding: 18px 22px 14px; box-shadow: var(--shadow); }
  .map-datebar { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 8px; }
  .map-datebar button { font: inherit; font-size: .82rem; border: 1px solid var(--line); background: var(--surface);
                        color: var(--ink-soft); border-radius: 980px; padding: 4px 13px; cursor: pointer;
                        transition: border-color .15s var(--ease-out), color .15s var(--ease-out), transform .16s var(--ease-out); }
  .map-datebar button:active:not(:disabled) { transform: scale(0.94); }
  .map-datebar button:hover:not(:disabled) { border-color: var(--accent); color: var(--ink); }
  .map-datebar button:disabled { opacity: .3; cursor: default; }
  #map-date { font-weight: 700; font-size: .95rem; font-variant-numeric: tabular-nums; min-width: 11ch; text-align: center; }
  #navmap { width: 100%; height: auto; display: block; }
  #navmap .land { fill: var(--surface-2); stroke: var(--line); stroke-width: .6; }
  .newsdot { fill: var(--accent); stroke: var(--surface); stroke-width: 1.8; pointer-events: none; }
  .newsdot-hit { fill: transparent; cursor: pointer; }
  .newsdot-hit:hover { fill: var(--accent); opacity: .18; }
  .map-hint { margin: 6px 0 0; font-size: .77rem; color: var(--ink-faint); text-align: center; }
  .card.flash { animation: flashcard 1.2s var(--ease-out); }
  @keyframes flashcard { 0% { box-shadow: 0 0 0 3px var(--accent); } 100% { box-shadow: var(--shadow); } }

  .filters { position: sticky; top: 0; z-index: 5; background: var(--glass);
             -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px);
             border-bottom: 1px solid var(--line); }
  .filters .wrap { display: flex; gap: 8px; flex-wrap: wrap; padding-top: 14px; padding-bottom: 14px; }
  .chip {
    font: inherit; font-size: .85rem; cursor: pointer;
    border: 1px solid transparent; background: var(--surface-2); color: var(--ink-soft);
    padding: 7px 15px; border-radius: 980px; white-space: nowrap;
    transition: background-color .15s var(--ease-out), color .15s var(--ease-out), transform .16s var(--ease-out);
  }
  .chip:active { transform: scale(0.96); }
  .chip:hover { color: var(--ink); }
  .chip.on { background: var(--accent); color: #fff; font-weight: 600; }
  @media (prefers-color-scheme: dark){ .chip.on { color: #0f130c; } }
  :root[data-theme="dark"] .chip.on { color:#0f130c; }
  .chip .n { opacity: .6; margin-left: 5px; font-variant-numeric: tabular-nums; }

  main .wrap { padding-top: 28px; padding-bottom: 80px; }

  .theme { margin-bottom: 56px; }
  .theme-head { font-size: 1.6rem; font-weight: 700; letter-spacing: -.02em; margin: 0 0 22px;
                display: flex; align-items: baseline; gap: 10px; }
  .theme-n { font-size: 1rem; font-weight: 400; color: var(--ink-faint); letter-spacing: 0; }
  .theme-n { font-size: .82rem; color: var(--ink-faint); font-weight: 600; margin-left: 9px; }

  .card {
    background: var(--surface); border: 1px solid var(--line); border-radius: 20px;
    padding: 26px 28px 22px; margin-bottom: 18px; box-shadow: var(--shadow);
  }
  .meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .badge { font-size: .74rem; font-weight: 700; padding: 3px 9px; border-radius: 7px;
           background: var(--accent-soft); color: var(--accent-ink); letter-spacing: .02em; }
  .badge.region { background: var(--surface-2); color: var(--ink-faint); font-weight: 600; }
  .badge.date { background: var(--accent-soft); color: var(--accent-ink); font-weight: 700; font-variant-numeric: tabular-nums; }
  .journal { font-size: .76rem; color: var(--ink-faint); margin-left: auto; text-align: right;
             font-variant-numeric: tabular-nums; }
  h3.title { font-size: 1.32rem; line-height: 1.32; margin: 4px 0 10px; letter-spacing: -.018em; font-weight: 700; }
  .who { margin: 12px 0 0; font-size: .82rem; color: var(--ink-faint); }

  .deep { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 14px; }
  .deep-body { position: relative; transition: none; }
  .deep[data-collapsed="1"] .deep-body {
    max-height: 10.5em; overflow: hidden;
    -webkit-mask-image: linear-gradient(to bottom, #000 62%, transparent 100%);
            mask-image: linear-gradient(to bottom, #000 62%, transparent 100%);
  }
  .deep[data-fits="1"] .deep-body { max-height: none; -webkit-mask-image: none; mask-image: none; }
  .deep[data-fits="1"] .deep-toggle { display: none; }
  .deep-toggle {
    margin-top: 8px; cursor: pointer; color: var(--accent-ink); font-weight: 600;
    font-size: .85rem; background: none; border: none; padding: 4px 0; font-family: inherit;
    line-height: 1.5;
  }
  .deep-toggle .tw { color: var(--accent); font-weight: 700; }
  .deep-toggle:hover { text-decoration: underline; }
  .section { margin: 14px 0 0; }
  .section:first-child { margin-top: 0; }
  .section h4 { margin: 0 0 3px; font-size: .82rem; color: var(--accent); letter-spacing: .03em;
                text-transform: none; font-weight: 700; }
  .section p { margin: 0; color: var(--ink-soft); font-size: .97rem; }

  .talk { margin-top: 18px; background: var(--talk-bg); border-left: 3px solid var(--talk-line);
          border-radius: 4px 14px 14px 4px; padding: 13px 16px; color: var(--talk-ink); font-size: .95rem; }
  .talk b { font-weight: 700; }

  .curric { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .curric-label { font-size: .74rem; font-weight: 700; color: #fff; background: var(--accent);
                  padding: 4px 10px; border-radius: 980px; letter-spacing: .02em; }
  :root[data-theme="dark"] .curric-label { color: #0f130c; }
  @media (prefers-color-scheme: dark){ .curric-label { color: #0f130c; } }
  .curric-item { font-size: .8rem; color: var(--ink-soft); background: var(--accent-soft);
                 padding: 4px 11px; border-radius: 980px; }
  .curric-item b { color: var(--accent-ink); font-weight: 700; font-variant-numeric: tabular-nums; }

  .foot { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 16px; }
  .tags { display: flex; gap: 6px; flex-wrap: wrap; }
  .tag { font-size: .74rem; color: var(--ink-faint); background: var(--surface-2);
         padding: 3px 10px; border-radius: 980px; }
  a.src { margin-left: auto; font-size: .84rem; font-weight: 600; color: var(--accent-ink);
          text-decoration: none; border: 1px solid var(--line); padding: 7px 15px; border-radius: 980px;
          white-space: nowrap;
          transition: border-color .15s var(--ease-out), background-color .15s var(--ease-out), transform .16s var(--ease-out); }
  a.src:hover { border-color: var(--accent); background: var(--accent-soft); }
  a.src:active { transform: scale(0.96); }

  .empty { text-align: center; color: var(--ink-faint); padding: 60px 0; }

  @media (prefers-reduced-motion: reduce) {
    .chip:active, a.src:active, .map-datebar button:active:not(:disabled) { transform: none; }
  }
  @media (prefers-reduced-transparency: reduce) {
    .filters { background: var(--bg); -webkit-backdrop-filter: none; backdrop-filter: none; }
  }

  footer.bot { border-top: 1px solid var(--line); color: var(--ink-faint); font-size: .8rem; }
  footer.bot .wrap { padding: 24px 20px 48px; }
  footer.bot p { margin: 4px 0; }
</style>
</head>
<body>
<header class="top">
  <div class="wrap">
    <div class="brand">
      <h1><span class="pin">📍</span> 지리 뉴스 브리핑 아카이브</h1>
    </div>
    <p class="tagline">매일 아침 텔레그램으로 나가는 지리 브리핑의 <b>깊이 읽기</b> 판. 짧은 요약에서 잘려나간
      방법론·수치·배경을 원문에서 다시 살려, 분야별로 정리했습니다.</p>
    <p class="stat"><b>__TOTAL__</b>건 · <b>__DAYS__</b>일치 · <b>__CATCOUNT__</b>개 분야 · 최신 __LATEST__</p>
  </div>
</header>

<section class="mapnav">
  <div class="wrap">
    <div class="map-card">
      <div class="map-datebar">
        <button id="map-prev" type="button" aria-label="이전 날짜">◀</button>
        <span id="map-date"></span>
        <button id="map-next" type="button" aria-label="다음 날짜">▶</button>
      </div>
      <svg id="navmap" viewBox="0 0 1000 400" role="img" aria-label="기사 위치 세계지도">
        <path class="land" d="__WORLDPATH__"/>
      </svg>
      <p class="map-hint">📍 그날의 뉴스가 일어난 곳 — 점을 누르면 해당 기사로 이동합니다 (전 지구 단위 연구는 표시되지 않음)</p>
    </div>
  </div>
</section>

<nav class="filters">
  <div class="wrap" id="chips"></div>
</nav>

<main>
  <div class="wrap" id="feed"></div>
</main>

<footer class="bot">
  <div class="wrap">
    <p>이 사이트는 매일 아침 브리핑 봇이 생성합니다. 본문의 사실 진술은 각 기사 원문에서 확인한 것이며, 💬 이야깃거리는 편집자의 해석입니다.</p>
    <p>각 카드의 ‘펼쳐보기’를 누르면 본문 전체가 열리고, 오른쪽 아래 ‘매체명 →’ 버튼으로 원문을 열 수 있습니다.</p>
  </div>
</footer>

<script>
const DATA = __DATA__;
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// 분야별 카운트
const catCount = {};
DATA.days.forEach(d => d.articles.forEach(a => { catCount[a.category] = (catCount[a.category]||0)+1; }));
let active = "전체";
// 분야 표시 순서(지리학 분과 체계: 자연 → 인문 → 정치지리 → 지도·GIS 도구 → 교육). 목록에 없는 분야는 뒤에 자동 추가.
// 필터 칩과 본문 섹션이 반드시 같은 순서를 쓰도록 여기서 한 번만 정한다.
const CAT_ORDER = ["지형학","기후학","도시지리학","경제지리학","지역지리학","문화지리학","역사지리학","인구지리학","지정학·국제","지도학","GIS","지리교육"];
const cats = CAT_ORDER.filter(c => c in catCount)
  .concat(Object.keys(catCount).filter(c => !CAT_ORDER.includes(c)));

function chipsHtml() {
  const all = `<button class="chip on" data-cat="전체">전체<span class="n">${DATA.days.reduce((s,d)=>s+d.articles.length,0)}</span></button>`;
  return all + cats.map(c =>
    `<button class="chip" data-cat="${esc(c)}">${esc(c)}<span class="n">${catCount[c]}</span></button>`
  ).join("");
}

function cardHtml(a) {
  const sections = (a.body||[]).map(s =>
    `<div class="section"><h4>${esc(s.h)}</h4><p>${esc(s.p)}</p></div>`).join("");
  const deep = sections
    ? `<div class="deep" data-collapsed="1"><div class="deep-body">${sections}</div>` +
      `<button class="deep-toggle" type="button"><span class="tw">⌄</span> 펼쳐보기</button></div>`
    : "";
  const tags = (a.tags||[]).map(t => `<span class="tag">#${esc(t)}</span>`).join("");
  const who = a.researchers ? `<p class="who">${esc(a.researchers)}</p>` : "";
  const curric = (a.curriculum||[]).length
    ? `<div class="curric"><span class="curric-label">🎓 교육과정 연계</span>` +
      a.curriculum.map(c => `<span class="curric-item"><b>${esc(c.code)}</b> ${esc(c.gloss)}</span>`).join("") +
      `</div>`
    : "";
  const dp = (a._date||"").split("-");
  const dl = dp.length===3 ? `${+dp[1]}.${+dp[2]}` : "";
  return `<article class="card" id="${esc(a.id||"")}" data-cat="${esc(a.category)}">
    <div class="meta">
      ${dl ? `<span class="badge date">${dl}</span>` : ""}
      <span class="badge region">${esc(a.region)}</span>
      <span class="journal">${esc(a.journal||"")}</span>
    </div>
    <h3 class="title">${esc(a.title)}</h3>
    ${who}
    ${deep}
    ${curric}
    <div class="talk"><b>💬</b> ${esc(a.talk)}</div>
    <div class="foot">
      <div class="tags">${tags}</div>
      <a class="src" href="${esc(a.source.url)}" target="_blank" rel="noopener">${esc(a.source.name)} →</a>
    </div>
  </article>`;
}

let firstRender = true;  // 최초 로드는 페이드 없이, 이후 필터 전환만 페이드
function render() {
  const feed = document.getElementById("feed");
  // 모든 기사에 날짜를 붙여 평탄화한 뒤 분야별로 묶는다
  const all = [];
  DATA.days.forEach(d => d.articles.forEach(a => all.push(Object.assign({_date: d.date}, a))));
  let html = "";
  cats.forEach(cat => {
    if (active !== "전체" && active !== cat) return;
    const arts = all.filter(a => a.category === cat)
                    .sort((x, y) => y._date.localeCompare(x._date));  // 분야 안에서 최신순
    if (!arts.length) return;
    html += `<section class="theme">
      <h2 class="theme-head">${esc(cat)}<span class="theme-n">${arts.length}건</span></h2>
      ${arts.map(cardHtml).join("")}
    </section>`;
  });
  feed.innerHTML = html || `<p class="empty">이 분야의 기사가 아직 없습니다.</p>`;
  // 분야 필터 전환 시 카드가 뚝 바뀌지 않게 옅은 페이드인(불투명도만 — GPU·스크롤 안전·reduced-motion 친화). 최초 로드는 제외.
  if (!firstRender && feed.animate) {
    feed.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "cubic-bezier(0.23, 1, 0.32, 1)" });
  }
  firstRender = false;
  // 본문이 짧아 클램프 안에 다 들어가면 페이드·버튼을 없앤다.
  // 반드시 레이아웃(클램프 적용) 이후에 측정해야 한다 — rAF로 다음 프레임에 실행.
  requestAnimationFrame(() => feed.querySelectorAll(".deep").forEach(deep => {
    const body = deep.querySelector(".deep-body");
    if (body.scrollHeight <= body.clientHeight + 4) deep.setAttribute("data-fits", "1");
  }));
}

document.getElementById("chips").innerHTML = chipsHtml();
document.getElementById("chips").addEventListener("click", e => {
  const b = e.target.closest(".chip"); if (!b) return;
  active = b.dataset.cat;
  document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c===b));
  render();
});
document.getElementById("feed").addEventListener("click", e => {
  const btn = e.target.closest(".deep-toggle"); if (!btn) return;
  const deep = btn.closest(".deep");
  const collapsed = deep.getAttribute("data-collapsed") === "1";
  deep.setAttribute("data-collapsed", collapsed ? "0" : "1");
  btn.innerHTML = collapsed
    ? `<span class="tw">⌃</span> 접기`
    : `<span class="tw">⌄</span> 펼쳐보기`;
});
render();

// --- 세계지도 내비게이터 ---
// 기사 geo:{lat,lon,label}를 equirectangular 투영으로 점 찍기.
// 투영 상수는 world_land_path.txt 생성 스크립트와 반드시 동일해야 한다: lat [-60,84] → 1000×400.
function goToArticle(id){
  if (active !== "전체") {
    active = "전체";
    document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c.dataset.cat === "전체"));
    render();  // 동기 렌더 — 프레임 대기 불필요
  }
  const el = document.getElementById(id);
  if (!el) return;
  const before = window.scrollY;
  el.scrollIntoView({behavior: "smooth", block: "start"});
  // 백그라운드 탭 등 렌더 프레임이 멈춘 환경에선 smooth가 진행되지 않는다 — 350ms 안에 안 움직였으면 즉시 점프
  setTimeout(() => {
    if (Math.abs(window.scrollY - before) < 4) el.scrollIntoView({block: "start"});
  }, 350);
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1800);
}
(function(){
  const svg = document.getElementById("navmap");
  if (!svg || !DATA.days.length) return;
  const W = 1000, TOP = 84, BOT = -60, H = 400;
  const px = lon => (lon + 180) * (W / 360);
  const py = lat => (TOP - Math.max(BOT, Math.min(TOP, lat))) * (H / (TOP - BOT));
  const label = document.getElementById("map-date");
  const btnPrev = document.getElementById("map-prev");   // 과거로
  const btnNext = document.getElementById("map-next");   // 최신으로
  let idx = 0;  // DATA.days 인덱스 (0 = 최신 날짜)

  const fmt = iso => { const [y,m,d] = iso.split("-"); return `${y}. ${+m}. ${+d}.`; };

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
    label.textContent = `${fmt(day.date)} · ${n}곳`;
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
