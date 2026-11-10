"""
Generates the two system diagrams (architecture, workflow) from one layout
spec, in two forms:
  * Claude Design canvas artboards (<canvas_root>/project/*.dc.html), where
    each card and arrow is a separate, editable element;
  * standalone HTML pages that are printed to vector PDF with headless
    Chrome for the LaTeX paper (no screenshots, no raster).

Usage: python make_diagrams.py <canvas_root>
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

INK = "#1f2328"
MUTED = "#57606a"
LINE = "#57606a"
CARD = "background: #ffffff; border: 1.5px solid #8c959f; border-radius: 10px"
ACCENT = "background: #eef4ff; border: 1.5px solid #3b6fd8; border-radius: 10px"
STORE = "background: #fff6e8; border: 1.5px solid #c9822b; border-radius: 10px"
BAND = "background: #f6f8fa; border: 1px dashed #afb8c1; border-radius: 14px"
FONT = "font-family: Arial, Helvetica, sans-serif"


class Diagram:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.bands, self.arrows, self.cards, self.labels = [], [], [], []
        self.n = 0

    def band(self, x, y, w, h, label):
        self.bands.append(f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; box-sizing: border-box; {BAND}"></div>')
        self.labels.append(f'<div style="position: absolute; left: {x + 16}px; top: {y + 12}px; font-size: 14px; line-height: 18px; font-weight: 700; letter-spacing: 0.04em; color: {MUTED}">{label}</div>')

    def card(self, x, y, w, h, html, style=CARD):
        self.cards.append(
            f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; box-sizing: border-box; padding: 8px; '
            f'display: flex; align-items: center; justify-content: center; text-align: center; font-size: 16px; line-height: 21px; color: {INK}; {style}">'
            f'<span>{html}</span></div>')

    def text(self, x, y, w, html, size=13):
        self.labels.append(f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; text-align: center; font-size: {size}px; line-height: 16px; color: {MUTED}">{html}</div>')

    def _svg(self, left, top, sw, sh, d, head, dashed):
        self.n += 1
        dash = "; stroke-dasharray: 6 6" if dashed else ""
        defs = (f'<defs><marker id="dc-arrow-head-filled-{self.n}" orient="auto" markerWidth="5" markerHeight="5" refX="2" refY="2" overflow="visible">'
                f'<path d="M0 0 L4 2 L0 4 Z" fill="{LINE}" stroke="none" style="stroke: none; fill: {LINE}; fill: context-stroke"/></marker></defs>') if head else ""
        me = f' marker-end="url(#dc-arrow-head-filled-{self.n})"' if head else ""
        self.arrows.append(
            f'<svg width="{sw}" height="{sh}" viewBox="0 0 {sw} {sh}" preserveAspectRatio="none" style="position: absolute; left: {left}px; top: {top}px; '
            f'width: {sw}px; height: {sh}px; overflow: visible; fill: none; stroke: {LINE}; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round{dash}">'
            f'{defs}<path d="{d}"{me}></path></svg>')

    def hz(self, x1, x2, y, head=True, dashed=False):
        """Horizontal segment from x1 to tip x2 (either direction)."""
        n = abs(x2 - x1)
        hh = 4 if head else 0
        if x2 > x1:
            self._svg(x1, y - 4, n, 8, f"M 0 4 L {n - hh} 4", head, dashed)
        else:
            self._svg(x2, y - 4, n, 8, f"M {n} 4 L {hh} 4", head, dashed)

    def vt(self, x, y1, y2, head=True, dashed=False):
        n = abs(y2 - y1)
        hh = 4 if head else 0
        if y2 > y1:
            self._svg(x - 4, y1, 8, n, f"M 4 0 L 4 {n - hh}", head, dashed)
        else:
            self._svg(x - 4, y2, 8, n, f"M 4 {n} L 4 {hh}", head, dashed)

    def host(self):
        title = f'<div style="position: absolute; left: 64px; top: 28px; font-size: 24px; line-height: 30px; font-weight: 700; color: {INK}">{self.title}</div>'
        body = "\n".join(self.bands + self.arrows + self.cards + self.labels)
        return (f'<div style="position: relative; width: {self.w}px; height: {self.h}px; background: #ffffff; {FONT}">\n'
                f'{title}\n{body}\n</div>')


def architecture():
    d = Diagram(1824, 912, "Unified ChangeGuard + CodeOrigin platform")
    d.band(920, 88, 816, 264, "CHANGEGUARD STACK: PULL-REQUEST ANALYSIS")
    d.band(920, 416, 816, 256, "CODEORIGIN STACK: HISTORY-AWARE QUESTION ANSWERING")
    d.card(64, 200, 176, 88, "<b>Developer</b><br>web browser")
    d.card(64, 440, 176, 88, "<b>Team</b><br>Discord server")
    d.card(320, 200, 224, 88, "<b>Merged dashboard</b><br>React + Vite &#183; :5173")
    d.card(320, 440, 224, 88, "<b>Discord bot</b><br>/analyze /why /tests /ci")
    d.card(624, 276, 240, 96, "<b>Platform bridge</b><br>FastAPI &#183; SQLite &#183; SSE<br>:8300", ACCENT)
    d.card(944, 168, 208, 96, "<b>API gateway</b><br>:8100")
    d.card(1232, 168, 208, 96, "<b>Orchestrator</b><br>risk workflow")
    d.card(1520, 136, 192, 160, "<b>Services</b><br>git &#183; code analysis<br>RAG &#183; embedding<br>LLM &#183; test generation<br>data")
    d.card(944, 496, 208, 96, "<b>Gateway</b><br>:8200 &#183; rate limit, G7")
    d.card(1232, 496, 208, 96, "<b>Orchestrator</b><br>guardrails G1&#8211;G10", ACCENT)
    d.card(1520, 464, 192, 160, "<b>Services</b><br>ingest (git + GitHub)<br>hybrid RAG<br>LLM &#183; eval")
    d.card(624, 760, 240, 88, "<b>Prometheus &#183; Grafana</b><br>scrape CodeOrigin /metrics", CARD)
    d.card(944, 760, 208, 88, "<b>GitHub</b><br>REST API + git", STORE)
    d.card(1232, 760, 208, 88, "<b>ChromaDB</b><br>one store per stack", STORE)
    d.card(1520, 760, 192, 88, "<b>Shared Ollama</b><br>RTX 3060, 6 GB", STORE)
    d.hz(240, 319, 244)
    d.hz(240, 319, 484)
    d.hz(544, 584, 244, head=False)
    d.vt(584, 244, 300, head=False)
    d.hz(584, 623, 300)
    d.hz(544, 584, 484, head=False)
    d.vt(584, 348, 484, head=False)
    d.hz(584, 623, 348)
    d.hz(864, 904, 324, head=False)
    d.vt(904, 216, 544, head=False)
    d.hz(904, 943, 216)
    d.hz(904, 943, 544)
    d.hz(1152, 1231, 216)
    d.hz(1440, 1519, 216)
    d.hz(1152, 1231, 544)
    d.hz(1440, 1519, 544)
    d.vt(1048, 592, 759)
    d.vt(1336, 592, 759)
    d.vt(1616, 624, 759)
    d.hz(1712, 1768, 216, head=False)
    d.vt(1768, 216, 804, head=False)
    d.hz(1768, 1713, 804)
    d.text(256, 216, 48, "HTTP")
    d.text(256, 456, 48, "HTTP")
    d.text(1060, 668, 64, "ingest")
    d.text(1348, 668, 64, "search")
    d.text(1628, 680, 64, "generate")
    return d


def workflow():
    d = Diagram(1836, 664, "Pull-request analysis and history-aware question answering")
    d.band(48, 88, 1740, 224, "CHANGEGUARD: ONE PULL REQUEST")
    d.band(48, 368, 1740, 240, "CODEORIGIN: ONE “WHY” QUESTION")
    col = lambda i: 64 + i * 252
    W, H = 196, 104
    top, bot = 160, 440
    toprow = ["<b>1. PR opened</b><br>dashboard or /analyze", "<b>2. Diff + metadata</b><br>git-service",
              "<b>3. Risk signal</b><br>import graph, missing tests", "<b>4. Retrieve code</b><br>AST chunks, top-5",
              "<b>5. Explain risk</b><br>LLM, cited files", "<b>6. Tests + CI</b><br>on request, pytest",
              "<b>7. Decision</b><br>approve or request changes"]
    botrow = ["<b>1. Question</b><br>web or /why", "<b>2. Safety</b><br>G10 input check",
              "<b>3. Hybrid retrieval</b><br>vector + BM25, RRF,<br>k&nbsp;=&nbsp;8", "<b>4. Gates</b><br>G1 on-topic, G2 history",
              "<b>5. Build context</b><br>links, G5, 6000 chars", "<b>6. Generate</b><br>local LLM, temp 0",
              "<b>7. Check output</b><br>G3 citations, G4<br>grounding, G6 redaction"]
    for i, lab in enumerate(toprow):
        d.card(col(i), top, W, H, lab, ACCENT if i in (2, 4) else CARD)
    for i, lab in enumerate(botrow):
        d.card(col(i), bot, W, H, lab, ACCENT if i in (3, 6) else CARD)
    for i in range(6):
        d.hz(col(i) + W, col(i + 1) - 1, top + H // 2)
        d.hz(col(i) + W, col(i + 1) - 1, bot + H // 2)
    d.vt(col(4) + W // 2, bot, top + H + 1, dashed=True)
    d.text(col(4) + W // 2 + 12, 336, 200, "per-file history (bridge)")
    return d


def write_pdf(d, name):
    html = os.path.join(HERE, f"_{name}.html")
    with open(html, "w", encoding="utf-8") as fh:
        fh.write(f'<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:{d.w}px {d.h}px;margin:0}}'
                 f'html,body{{margin:0;padding:0}}</style></head><body>{d.host()}</body></html>')
    pdf = os.path.join(HERE, f"{name}.pdf")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", "file:///" + html.replace("\\", "/")], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html)


def write_artboard(d, root, fname, title):
    src = (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>{title}</title>\n'
           f'<script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n<style>\nbody{{margin:0}}\n'
           f'a{{color:#57606a}}a:hover{{color:#1f2328}}\n</style>\n</helmet>\n{d.host()}\n</x-dc>\n'
           f'<script type="text/x-dc" data-dc-script data-props=\'{{"$preview":{{"width":{d.w},"height":{d.h}}}}}\'>\n'
           f'class Component extends DCLogic {{\nrenderVals() {{\nreturn {{}};\n}}\n}}\n</script>\n</body>\n</html>\n')
    with open(os.path.join(root, "project", fname), "w", encoding="utf-8") as fh:
        fh.write(src)


if __name__ == "__main__":
    root = sys.argv[1]
    os.makedirs(os.path.join(root, "project"), exist_ok=True)
    a, w = architecture(), workflow()
    write_pdf(a, "architecture")
    write_pdf(w, "workflow")
    write_artboard(a, root, "Main.dc.html", "Architecture")
    write_artboard(w, root, "Workflow.dc.html", "Workflow")
    canvas = {"v": 3, "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
              "title": "IDT paper figures", "launch": {"view": "canvas"}, "pages": [],
              "boards": {"Main.dc.html": {"x": 0, "y": 0, "w": a.w, "h": a.h, "title": "Fig. 1 Architecture"},
                         "Workflow.dc.html": {"x": 0, "y": a.h + 120, "w": w.w, "h": w.h, "title": "Fig. 2 Workflow"}},
              "order": ["Main.dc.html", "Workflow.dc.html"], "notes": {}, "designSystems": []}
    with open(os.path.join(root, "project", "canvas.json"), "w", encoding="utf-8") as fh:
        json.dump(canvas, fh, indent=1)
    print("ok")
