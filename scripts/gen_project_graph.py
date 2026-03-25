#!/usr/bin/env python3
"""Generate an interactive, zoomable HTML graph of how every project file connects.

Doubles as a context file: open `project-graph.html` in any browser (or hand it to an AI)
to see the full data-lifecycle flow ingestion → data lake → dbt transform → ML → app → docs.

Edges extracted (real, not guessed):
  * dbt:    ref('x') / source('a','b')  in transform/models/**.sql        → model→model
  * TS/TSX: relative `import ... from './x'` in app/src/**                 → module→module
  * Python: `from pkg.mod import ...` / `import pkg.mod` in ml|ingestion|scripts
  * Layer flow: synthetic edges between the six lifecycle stages (dashed)

No build step, no server. Output is a single self-contained .html (D3 from CDN with a
graceful offline message).

Usage: python scripts/gen_project_graph.py [-o project-graph.html]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── layer definitions (order = lifecycle; colour = legend) ──────────────────────
LAYERS = [
    ("ingestion", "#60a5fa", "Ingestion FastF1/OpenF1 → Bronze Parquet"),
    ("data", "#38bdf8", "Data lake medallion Parquet"),
    ("transform", "#34d399", "Transform dbt staging → marts"),
    ("ml", "#fbbf24", "ML XGBoost + ONNX"),
    ("app", "#f472b6", "App React + DuckDB-Wasm"),
    ("scripts", "#a78bfa", "Scripts reference generators"),
    ("docs", "#cbd5e1", "Docs Docusaurus"),
]
LAYER_COLOR = {name: color for name, color, _ in LAYERS}
LAYER_INDEX = {name: i for i, (name, _, _) in enumerate(LAYERS)}

REF_RE = re.compile(r"ref\(\s*'([a-zA-Z0-9_]+)'\s*\)")
SOURCE_RE = re.compile(r"source\(\s*'([a-zA-Z0-9_]+)'\s*,\s*'([a-zA-Z0-9_]+)'\s*\)")
TS_IMPORT_RE = re.compile(r"""(?:from|import)\s+['"](\.[^'"]+)['"]""")
PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+((?:ml|ingestion|scripts)[\w.]*)\s+import|import\s+((?:ml|ingestion|scripts)[\w.]*))",
    re.M,
)

SKIP_PARTS = {"node_modules", "__pycache__", "dbt_packages", "target", ".venv", "dist", "build", ".docusaurus"}


def layer_of(rel: str) -> str | None:
    top = rel.split("/", 1)[0]
    if top in LAYER_COLOR:
        return top
    return None


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("\\", "/")


def skip(p: Path) -> bool:
    return any(part in SKIP_PARTS for part in p.parts)


def describe(rel_path: str, kind: str) -> str:
    """A short, human one-liner for the hover tooltip."""
    name = Path(rel_path).name
    stem = Path(rel_path).stem
    if kind == "source":
        return f"Bronze source table '{stem.replace('source:', '')}' (raw ingested Parquet)"
    if kind == "dbt_model":
        if "/staging/" in rel_path or stem.startswith("stg_"):
            return "dbt staging model cleans & types one Bronze source"
        if "/intermediate/" in rel_path or stem.startswith("int_"):
            return "dbt intermediate model physics / decomposition step"
        if "/marts/" in rel_path or stem.startswith(("fct_", "dim_")):
            return "dbt mart gold feature table consumed by ML & app"
        if "/reference/" in rel_path:
            return "dbt reference model slowly-changing dimension data"
        return "dbt model"
    if kind == "py":
        if rel_path.startswith("ml/"):
            return "ML pipeline module (XGBoost / ONNX / features)"
        if rel_path.startswith("ingestion/"):
            return "Ingestion module FastF1/OpenF1 → Bronze Parquet"
        if rel_path.startswith("scripts/"):
            return "Build script reference-doc generator / CI tooling"
        return "Python module"
    if kind == "ts":
        if "/features/" in rel_path:
            return "App feature a page + its data transform & methodology"
        if "/ui/charts/" in rel_path:
            return "Chart primitive reusable D3/Recharts visual"
        if "/ui/" in rel_path:
            return "UI component layout / feedback / theming"
        if "/data/" in rel_path:
            return "Data layer DuckDB-Wasm client & query hooks"
        if "/ml/" in rel_path:
            return "In-browser ONNX inference module"
        if "/routes/" in rel_path:
            return "Route wires a URL to a feature page"
        if "/state/" in rel_path:
            return "App state React context (filters / theme)"
        return "App module (React + TypeScript)"
    return name


def collect():
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(rel_path: str, kind: str):
        if rel_path not in nodes:
            lyr = layer_of(rel_path) or "docs"
            nodes[rel_path] = {
                "id": rel_path,
                "label": Path(rel_path).name,
                "layer": lyr,
                "kind": kind,
                "deg": 0,
                "desc": describe(rel_path, kind),
            }

    # index dbt models by stem → rel path (models live in transform/models/**)
    sql_files = [p for p in (ROOT / "transform" / "models").rglob("*.sql") if not skip(p)]
    model_by_stem = {p.stem: rel(p) for p in sql_files}

    # ── dbt edges ──
    for p in sql_files:
        src = rel(p)
        add_node(src, "dbt_model")
        text = p.read_text(encoding="utf-8", errors="ignore")
        for stem in REF_RE.findall(text):
            tgt = model_by_stem.get(stem)
            if tgt and tgt != src:
                add_node(tgt, "dbt_model")
                edges.append({"source": src, "target": tgt, "type": "ref"})
        for _src_name, tbl in SOURCE_RE.findall(text):
            seed = f"source:{tbl}"
            add_node(seed, "source")
            nodes[seed]["layer"] = "ingestion"
            edges.append({"source": src, "target": seed, "type": "source"})

    # ── TS / TSX edges (app/src) ──
    ts_files = [p for p in (ROOT / "app" / "src").rglob("*") if p.suffix in {".ts", ".tsx"} and not skip(p)]
    ts_set = {rel(p) for p in ts_files}
    for p in ts_files:
        src = rel(p)
        add_node(src, "ts")
        text = p.read_text(encoding="utf-8", errors="ignore")
        for imp in TS_IMPORT_RE.findall(text):
            resolved = (p.parent / imp).resolve()
            cand = None
            for ext in ("", ".ts", ".tsx", ".d.ts", "/index.ts", "/index.tsx"):
                test = Path(str(resolved) + ext)
                if test.exists() and test.is_file():
                    cand = rel(test)
                    break
            if cand and cand in ts_set and cand != src:
                add_node(cand, "ts")
                edges.append({"source": src, "target": cand, "type": "import"})

    # ── Python edges (ml / ingestion / scripts) ──
    py_files = [
        p
        for base in ("ml", "ingestion", "scripts")
        for p in (ROOT / base).rglob("*.py")
        if not skip(p)
    ]
    mod_to_rel: dict[str, str] = {}
    for p in py_files:
        r = rel(p)
        mod = r[:-3].replace("/", ".")
        mod_to_rel[mod] = r
        mod_to_rel[mod.removesuffix(".__init__")] = r
    for p in py_files:
        src = rel(p)
        add_node(src, "py")
        text = p.read_text(encoding="utf-8", errors="ignore")
        for a, b in PY_IMPORT_RE.findall(text):
            mod = a or b
            tgt = mod_to_rel.get(mod) or mod_to_rel.get(mod.rsplit(".", 1)[0])
            if tgt and tgt != src:
                add_node(tgt, "py")
                edges.append({"source": src, "target": tgt, "type": "import"})

    # degree
    for e in edges:
        if e["source"] in nodes:
            nodes[e["source"]]["deg"] += 1
        if e["target"] in nodes:
            nodes[e["target"]]["deg"] += 1

    return list(nodes.values()), edges


def build_html(nodes, edges) -> str:
    payload = json.dumps({"nodes": nodes, "links": edges})
    legend = json.dumps([{"name": n, "color": c, "desc": d} for n, c, d in LAYERS])
    counts = {}
    for n in nodes:
        counts[n["layer"]] = counts.get(n["layer"], 0) + 1
    summary = " · ".join(f"{counts.get(name,0)} {name}" for name, _, _ in LAYERS if counts.get(name))
    return HTML_TEMPLATE.replace("__DATA__", payload).replace("__LEGEND__", legend).replace(
        "__SUMMARY__", f"{len(nodes)} files · {len(edges)} dependencies · {summary}"
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Off The Pace Project Dependency Graph</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html,body { margin:0; height:100%; background:#070a13; color:#e2e8f0;
    font:14px/1.5 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    overflow: hidden; }
  
  /* scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.08); border-radius: 99px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.18); }

  #app { display:flex; height:100vh; background:#070a13; position: relative; }
  
  #side {
    width: 320px;
    flex: 0 0 320px;
    padding: 24px 20px;
    display: flex;
    flex-direction: column;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(10, 15, 30, 0.75);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    z-index: 10;
    height: 100%;
  }
  .side-top { flex:0 0 auto; }
  .side-content { flex:1 1 auto; overflow-y:auto; margin-bottom: 20px; padding-right: 4px; }
  
  .back-btn {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.02);
    color: #94a3b8;
    text-decoration: none;
    font-weight: 500;
    font-size: 13px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    justify-content: center;
  }
  .back-btn:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.15);
    color: #f1f5f9;
  }
  .back-btn svg {
    transition: transform 0.2s ease;
  }
  .back-btn:hover svg {
    transform: translateX(-2px);
  }

  #side h1 {
    font-size: 18px;
    font-weight: 700;
    margin: 0 0 4px;
    letter-spacing: .5px;
    background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  #side .sub { color:#64748b; font-size:11.5px; margin-bottom:18px; font-weight: 500; }
  #search {
    width: 100%;
    padding: 10px 14px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(7, 10, 19, 0.6);
    color: #e2e8f0;
    margin-bottom: 18px;
    font-family: inherit;
    font-size: 13px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  #search:focus {
    outline: none;
    border-color: rgba(56, 189, 248, 0.5);
    box-shadow: 0 0 12px rgba(56, 189, 248, 0.15);
  }
  
  .legend-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12.5px;
    transition: background 0.15s ease;
  }
  .legend-item:hover { background: rgba(255, 255, 255, 0.04); }
  .legend-item.off { opacity:.3; }
  .dot { width:10px; height:10px; border-radius:50%; flex:0 0 10px; }
  .legend-item .desc { color:#64748b; font-size:11px; margin-top: 1px; }
  
  #info {
    margin-top: 20px;
    padding: 14px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    background: rgba(7, 10, 19, 0.4);
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.5;
  }
  #info h3 { margin:0 0 4px; font-size:13.5px; font-weight:600; color:#f1f5f9; word-break:break-all; }
  #info .path { color:#38bdf8; font-size:11.5px; word-break:break-all; opacity: 0.85; }
  
  #graph { flex:1; position:relative; overflow: hidden; background: radial-gradient(circle at center, #0c1122 0%, #070a13 100%); }
  #graph svg { width:100%; height:100%; display:block; cursor:grab; }
  #graph svg:active { cursor:grabbing; }
  .hint { position:absolute; left:20px; bottom:18px; color:#475569; font-size:11px; letter-spacing: 0.3px; }
  
  /* Nodes & glow effects */
  .node circle { stroke:#070a13; stroke-width:1.5px; cursor:pointer; transition: stroke-width 0.2s, stroke 0.2s; }
  .node circle:hover { filter: url(#glow); stroke: #ffffff; stroke-width: 2px; }
  .node.focused-node circle { filter: url(#glow); stroke: #ffffff; stroke-width: 2.2px; }
  
  .node text { fill:#f8fafc; font-size:10px; font-weight:600; pointer-events:none; opacity:0;
    paint-order:stroke; stroke:#070a13; stroke-width:3.5px; stroke-linejoin:round;
    transition:opacity .15s ease; }
  .node.lbl text, .node.hover-lbl text { opacity:1; }
  .node.dim text { opacity:0 !important; }
  
  /* Laser connections */
  line.link { stroke:rgba(51, 65, 85, 0.35); stroke-width:1px; transition: stroke 0.2s, stroke-width 0.2s; }
  line.link.src {
    stroke: #fbbf24;
    stroke-width: 2px;
    stroke-dasharray: 6 6;
    animation: laser-flow 1.2s linear infinite;
  }
  @keyframes laser-flow {
    to { stroke-dashoffset: -12; }
  }
  line.link.dim { stroke-opacity:.02; }
  .node.dim { opacity:.15; }
  
  .offline { padding:40px; max-width:600px; margin:60px auto; text-align:center; color:#94a3b8; }
  code { background:rgba(255, 255, 255, 0.04); padding:2px 6px; border-radius:4px; color:#38bdf8; font-size: 12px; }
  
  /* Right panel */
  #detail {
    width: 340px;
    flex: 0 0 340px;
    padding: 24px 20px;
    overflow: auto;
    border-left: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(10, 15, 30, 0.75);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    z-index: 10;
    display: none;
  }
  #detail.open { display:block; }
  #detail .close { float:right; cursor:pointer; color:#64748b; font-size:20px; line-height:1;
    border:none; background:none; transition: color 0.15s; }
  #detail .close:hover { color:#f1f5f9; }
  #detail h2 { font-size:15px; margin:0 0 4px; word-break:break-all; font-weight: 600; color: #f8fafc; }
  #detail .fpath { color:#38bdf8; font-size:11.5px; word-break:break-all; margin-bottom:12px; opacity: 0.85; }
  #detail .meta { color:#64748b; font-size:12px; margin-bottom:16px; font-weight: 500; }
  #detail .grp-title { font-size:10.5px; font-weight:600; text-transform:uppercase; letter-spacing:1px;
    margin:18px 0 8px; }
  #detail .grp-out { color:#fbbf24; }
  #detail .grp-in { color:#38bdf8; }
  
  #detail .link-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
    word-break: break-all;
    border: 1px solid transparent;
    transition: all 0.15s ease;
    margin-bottom: 4px;
    background: rgba(255, 255, 255, 0.02);
  }
  #detail .link-row:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.08);
    transform: translateX(2px);
  }
  #detail .link-row .dot { width:8px; height:8px; flex:0 0 8px; }
  #detail .link-row .nm { color:#e2e8f0; font-weight: 500; }
  #detail .link-row .dir { color:#64748b; font-size:10.5px; }
  #detail .none { color:#475569; font-style:italic; font-size:12px; padding-left: 8px; }
  
  /* Tooltip */
  #tip {
    position: fixed;
    z-index: 50;
    pointer-events: none;
    max-width: 280px;
    padding: 12px 14px;
    background: rgba(10, 15, 30, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity .15s ease, transform .15s ease;
  }
  #tip.show { opacity:1; transform:translateY(0); }
  #tip .t-name { font-size:13px; font-weight:600; color:#f1f5f9; word-break:break-all; margin-bottom:4px; }
  #tip .t-layer { display:inline-block; font-size:10px; font-weight:600; padding:2px 8px;
    border-radius:999px; margin-bottom:8px; text-transform: uppercase; letter-spacing: 0.5px; }
  #tip .t-desc { font-size:12px; color:#94a3b8; line-height:1.45; }
  #tip .t-deg { margin-top:8px; font-size:11px; color:#475569; font-weight: 500; }
</style>
</head>
<body>
<div id="app">
  <aside id="side">
    <div class="side-top">
      <h1>Off The Pace</h1>
      <div class="sub">__SUMMARY__</div>
      <input id="search" placeholder="filter files… (e.g. fct_, waterfall)"/>
    </div>
    <div class="side-content">
      <div id="legend"></div>
      <div id="info"><em>Click a node to inspect its dependencies. Scroll to zoom, drag to pan.</em></div>
    </div>
    <a href="/" class="back-btn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
      Back to Docs
    </a>
  </aside>
  <div id="graph">
    <svg>
      <defs>
        <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    </svg>
    <div class="hint">scroll = zoom · drag background = pan · drag node = pin · click = focus neighbours</div>
  </div>
  <aside id="detail"></aside>
</div>
<div id="tip"></div>
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script>
const DATA = __DATA__;
const LEGEND = __LEGEND__;
const COLOR = Object.fromEntries(LEGEND.map(l => [l.name, l.color]));
const hidden = new Set();
let node, link, sim, label;

// ── DATA PREP must run BEFORE draw(), because d3.forceLink mutates
//    link.source/target from id-strings into node objects. ───────────────────
const byId = new Map(DATA.nodes.map(n => [n.id, n]));
const eid = e => (typeof e === "object" ? e.id : e);

// drop dangling links, then snapshot adjacency from the original string ids
const idset = new Set(DATA.nodes.map(n => n.id));
DATA.links = DATA.links.filter(l => idset.has(eid(l.source)) && idset.has(eid(l.target)));

const OUT = new Map(), INC = new Map();
DATA.nodes.forEach(n => { OUT.set(n.id, new Set()); INC.set(n.id, new Set()); });
DATA.links.forEach(l => {
  const s = eid(l.source), t = eid(l.target);
  OUT.get(s).add(t);
  INC.get(t).add(s);
});

if (typeof d3 === "undefined") {
  document.getElementById("graph").innerHTML =
    '<div class="offline">This graph needs D3.js. You appear to be offline and the CDN '
    + '(<code>cdn.jsdelivr.net/npm/d3@7</code>) could not load. Reconnect once and reload '
    + 'the data itself is embedded in this file.</div>';
} else {
  renderLegend();
  draw();
}

function renderLegend(){
  const box = d3.select("#legend");
  LEGEND.forEach(l => {
    const row = box.append("div").attr("class","legend-item")
      .on("click", () => {
        if (hidden.has(l.name)) hidden.delete(l.name); else hidden.add(l.name);
        row.classed("off", hidden.has(l.name));
        applyFilter();
      });
    row.append("span").attr("class","dot").style("background", l.color);
    const t = row.append("div");
    t.append("div").text(l.name);
    t.append("div").attr("class","desc").text(l.desc.replace(/^[^—]*— /,""));
  });
}

function draw(){
  const svg = d3.select("#graph svg");
  const W = svg.node().clientWidth, H = svg.node().clientHeight;
  const g = svg.append("g");
  svg.call(d3.zoom().scaleExtent([0.1, 6]).on("zoom", e => g.attr("transform", e.transform)));

  link = g.append("g").selectAll("line").data(DATA.links).join("line")
    .attr("class", d => "link " + d.type);

  node = g.append("g").selectAll("g").data(DATA.nodes).join("g")
    .attr("class","node")
    .call(d3.drag()
      .on("start", (e,d)=>{ if(!e.active) sim.alphaTarget(.3).restart(); d.fx=d.x; d.fy=d.y; })
      .on("drag",  (e,d)=>{ d.fx=e.x; d.fy=e.y; })
      .on("end",   (e,d)=>{ if(!e.active) sim.alphaTarget(0); }));

  node.append("circle")
    .attr("r", d => 4 + Math.min(d.deg, 14) * 0.9)
    .attr("fill", d => COLOR[d.layer] || "#888")
    .on("click", (e,d)=>focus(d))
    .on("mouseover", function(e,d){ showInfo(d); showTip(e,d);
        d3.select(this.parentNode).classed("hover-lbl", true); })
    .on("mousemove", (e)=>moveTip(e))
    .on("mouseout", function(){ hideTip();
        d3.select(this.parentNode).classed("hover-lbl", false); });
  label = node.append("text")
    .attr("text-anchor", "middle")
    .attr("dy", d => (4 + Math.min(d.deg, 14) * 0.9) + 12)
    .text(d => d.label);

  sim = d3.forceSimulation(DATA.nodes)
    .force("link", d3.forceLink(DATA.links).id(d=>d.id).distance(90).strength(.35))
    .force("charge", d3.forceManyBody().strength(-340).distanceMax(720))
    .force("x", d3.forceX(d => (LEGEND.findIndex(l=>l.name===d.layer)+1)/(LEGEND.length+1)*W).strength(.09))
    .force("y", d3.forceY(H/2).strength(.03))
    .force("collide", d3.forceCollide(d => 10 + Math.min(d.deg,14)*0.9 + 8).strength(.9))
    .on("tick", ticked);

  function ticked(){
    link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
        .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    node.attr("transform", d=>`translate(${d.x},${d.y})`);
  }
  // show labels only when zoomed in
  svg.on("wheel.lbl", () => {
    const k = d3.zoomTransform(svg.node()).k;
    node.classed("lbl", k > 1.8);
  });
}

function neighbours(d){
  return new Set([d.id, ...(OUT.get(d.id)||[]), ...(INC.get(d.id)||[])]);
}

// ── styled hover tooltip ────────────────────────────────────────────────────
const tipEl = document.getElementById("tip");
function showTip(e, d){
  const c = COLOR[d.layer] || "#888";
  tipEl.innerHTML =
      `<div class="t-name">${d.label}</div>`
    + `<div class="t-layer" style="background:${c}22;color:${c};border:1px solid ${c}55">${d.layer}</div>`
    + `<div class="t-desc">${d.desc || ""}</div>`
    + `<div class="t-deg">${d.deg} connection${d.deg===1?"":"s"} · click to inspect</div>`;
  tipEl.classList.add("show");
  moveTip(e);
}
function moveTip(e){
  const pad = 14, w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + w > innerWidth)  x = e.clientX-w-pad;
  if (y + h > innerHeight) y = e.clientY-h-pad;
  tipEl.style.left = x + "px";
  tipEl.style.top  = y + "px";
}
function hideTip(){ tipEl.classList.remove("show"); }

function focus(d){
  const nb = neighbours(d);
  node.classed("dim", n => !nb.has(n.id))
      .classed("lbl", n => nb.has(n.id))
      .classed("focused-node", n => n.id === d.id);
  link.classed("dim", l => !(eid(l.source)===d.id || eid(l.target)===d.id))
      .classed("src", l => eid(l.source)===d.id || eid(l.target)===d.id);
  showInfo(d);
  openDetail(d);
}

// left panel: lightweight hover preview only
function showInfo(d){
  const out = (OUT.get(d.id)||new Set()).size;
  const inc = (INC.get(d.id)||new Set()).size;
  d3.select("#info").html(
    `<h3>${d.label}</h3><div class="path">${d.id}</div>`
    + `<div style="margin-top:6px;color:#94a3b8">layer: <b style="color:${COLOR[d.layer]}">${d.layer}</b> · `
    + `${out} out · ${inc} in</div>`
    + `<div style="margin-top:8px;color:#64748b;font-size:11.5px">Click for the full linked-file list →</div>`
  );
}

// right sidebar: full clickable linked-file list, spawned on click
function row(id, dir){
  const n = byId.get(id);
  const color = n ? (COLOR[n.layer] || "#888") : "#888";
  const name = n ? n.label : id;
  return `<div class="link-row" data-id="${id}">`
    + `<span class="dot" style="background:${color};border-radius:50%"></span>`
    + `<span class="nm">${name}<span class="dir"> · ${id}</span></span></div>`;
}

function openDetail(d){
  const out = [...(OUT.get(d.id)||[])].sort();
  const inc = [...(INC.get(d.id)||[])].sort();
  const panel = document.getElementById("detail");
  panel.innerHTML =
      `<button class="close" title="close">×</button>`
    + `<h2>${d.label}</h2><div class="fpath">${d.id}</div>`
    + `<div class="meta">layer <b style="color:${COLOR[d.layer]}">${d.layer}</b>`
    + ` · ${out.length} dependency(ies) · ${inc.length} dependent(s)</div>`
    + `<div class="grp-title grp-out">depends on → (${out.length})</div>`
    + (out.length ? out.map(x=>row(x,"out")).join("") : `<div class="none">nothing this is a leaf</div>`)
    + `<div class="grp-title grp-in">← used by (${inc.length})</div>`
    + (inc.length ? inc.map(x=>row(x,"in")).join("") : `<div class="none">nothing this is an entry point / root</div>`);
  panel.classList.add("open");
  // close button
  panel.querySelector(".close").onclick = closeDetail;
  // clicking a listed file re-focuses the graph on it
  panel.querySelectorAll(".link-row").forEach(r => {
    r.onclick = () => { const t = byId.get(r.dataset.id); if (t) focus(t); };
  });
}

function closeDetail(){
  const panel = document.getElementById("detail");
  panel.classList.remove("open");
  panel.innerHTML = "";
  node.classed("dim",false).classed("lbl",false).classed("focused-node",false);
  link.classed("dim",false).classed("src",false);
}

function applyFilter(){
  const q = (document.getElementById("search").value || "").toLowerCase();
  node.style("display", d => (hidden.has(d.layer) || (q && !d.id.toLowerCase().includes(q))) ? "none" : null);
  link.style("display", l =>
    (hidden.has(l.source.layer) || hidden.has(l.target.layer)
      || (q && !(l.source.id.toLowerCase().includes(q) || l.target.id.toLowerCase().includes(q)))) ? "none" : null);
}
document.getElementById("search").addEventListener("input", applyFilter);
// reset focus + close the right sidebar on background click
d3.select("#graph svg").on("click", function(e){
  if (e.target.tagName === "svg") closeDetail();
});
</script>
</body>
</html>
"""


def main(argv):
    out = ROOT / "project-graph.html"
    if "-o" in argv:
        out = Path(argv[argv.index("-o") + 1])
    nodes, edges = collect()
    html = build_html(nodes, edges)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}  ({len(nodes)} nodes, {len(edges)} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
