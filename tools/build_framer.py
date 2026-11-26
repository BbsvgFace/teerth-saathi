"""Build framer/TeerthSaathiCaseStudy.tsx (a Framer code component) from site/index.html.

- The page's own top nav is removed: the Framer site's Navigation Bar and footer take over.
- CSS is scoped to .tsj-in (page content) and .tsj-ov (timer, contents menu, image viewer, confetti),
  which is mounted on <body> so position:fixed is never trapped by a Framer wrapper.
- The purple aura becomes a sticky layer inside the component instead of a fixed one.
- Width media queries become container queries on the component, vw becomes cqw.
- The page script runs inside init(root, ov, onCanvas) with shimmed globals so it is cleaned up on unmount.
- Asset paths point at the GitHub repo through jsDelivr, pinned to a commit.

Usage: python3 tools/build_framer.py <commit-sha>
"""
import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHA = sys.argv[1] if len(sys.argv) > 1 else "main"
BASE = f"https://cdn.jsdelivr.net/gh/BbsvgFace/teerth-saathi@{SHA}/site/assets/"

src = (REPO / "site/index.html").read_text()

def swap_assets(s):
    return re.sub(r"assets/([\w.-]+\.(?:png|jpe?g|webp|mp4|svg))", lambda m: BASE + m.group(1), s)

# ---------------- CSS ----------------
css = src.split("<style>", 1)[1].split("</style>", 1)[0]
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

def parse(s):
    out, i, n = [], 0, len(s)
    while i < n:
        while i < n and s[i] in " \n\t\r":
            i += 1
        if i >= n:
            break
        j = i
        while j < n and s[j] not in "{;":
            j += 1
        head = s[i:j].strip()
        if j < n and s[j] == ";":
            out.append(("at", head, None)); i = j + 1; continue
        depth, k = 0, j
        while k < n:
            if s[k] == "{": depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0: break
            k += 1
        body = s[j + 1:k]
        out.append(("at" if head.startswith("@") else "rule", head, body))
        i = k + 1
    return out

def split_sel(sel):
    parts, depth, cur = [], 0, ""
    for ch in sel:
        if ch in "([": depth += 1
        if ch in ")]": depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]

P = {"both": ":is(.tsj-in,.tsj-ov)", "in": ".tsj-in", "ov": ".tsj-ov"}

def scope_one(sel, mode):
    p = P[mode]
    if sel in (":root", "html", "body"):
        return p
    if sel.startswith("html ") or sel.startswith("body "):
        return p + " " + sel.split(" ", 1)[1]
    return p + " " + sel

def scope(sel, mode):
    parts = [s for s in split_sel(sel) if not s.startswith(".topnav")]
    return ",".join(dict.fromkeys(scope_one(s, mode) for s in parts))

def vw(body):
    return re.sub(r"(\d*\.?\d+)vw", r"\1cqw", body)

def rules(items, mode):
    o = []
    for k, h, b in items:
        if k != "rule":
            continue
        s = scope(h, mode)
        if s:
            o.append(s + "{" + vw(b) + "}")
    return "".join(o)

out = []
for kind, head, body in parse(css):
    if kind == "rule":
        r = rules([(kind, head, body)], "both")
        if r: out.append(r)
    elif head.startswith("@media") and re.search(r"(min|max)-width", head):
        inner = parse(body)
        cond = head[len("@media"):].strip()
        a, o = rules(inner, "in"), rules(inner, "ov")
        if a: out.append("@container tsj " + cond + "{" + a + "}")
        if o: out.append("@media " + cond + "{" + o + "}")
    elif head.startswith("@media"):
        out.append(head + "{" + rules(parse(body), "both") + "}")
    else:
        out.append(head + ("{" + body + "}" if body is not None else ";"))

extra = (
    ".tsj-in .sr-only{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}"
    ".tsj-in{position:relative;width:100%;overflow-x:clip;isolation:isolate;text-align:left}"
    ".tsj-ov{position:static;height:0;background:none}"
    ".tsj-in .aura-wrap{position:absolute;inset:0;z-index:-1;pointer-events:none}"
    ".tsj-in .aura-wrap .aura{position:sticky;top:0;inset:auto;width:100%;height:100vh;z-index:auto}"
    ".tsj-ov #confetti{position:fixed;inset:0;pointer-events:none;z-index:200}"
)
# the site's title block sits above the component, so the hero starts closer to the top
extra_end = ".tsj-in .hero.hero{padding-top:56px}"
CSS = swap_assets(extra + "".join(out) + extra_end)
CSS = re.sub(r"\s*\n\s*", "", CSS)

# ---------------- HTML ----------------
body = src.split("<body>", 1)[1].split("<script>", 1)[0]
body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
body = re.sub(r'<nav class="topnav".*?</nav>', "", body, count=1, flags=re.S)
body = re.sub(r'(<div class="aura".*?</div>)', r'<div class="aura-wrap" aria-hidden="true">\1</div>', body, count=1, flags=re.S)
cut = body.index('<div class="timer" id="timer"')
OV = body[cut:].strip()
body = body[:cut]
body = body.replace('<h1 class="reveal">Teerth Saathi</h1>', '<h1 class="sr-only">Teerth Saathi</h1>', 1)
assert 'class="sr-only">Teerth Saathi' in body, "hero h1 not found"
body = re.sub(r">\s+<", "> <", body).strip()
OV = re.sub(r">\s+<", "> <", OV)
HTML = swap_assets(body)
OV_HTML = swap_assets(OV)

# ---------------- JS ----------------
js = src.split("<script>", 1)[1].split("</script>", 1)[0].strip()
assert js.startswith("(function(){") and js.endswith("})();"), "unexpected script wrapper"
js = js[len("(function(){"):-len("})();")]
def rep(old, new):
    global js
    assert old in js, "missing: " + old[:60]
    js = js.replace(old, new, 1)
rep("const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];", "")
rep("const tb=$('#topbar'); const ist=$('#ist');", "")
rep("function tick(){ if(ist) ist.textContent=new Date().toLocaleTimeString('en-GB',{timeZone:'Asia/Kolkata',hour12:false}); }", "")
rep("tick(); setInterval(tick,1000);", "")
rep("tb.classList.toggle('scrolled',y>10);", "")
rep("document.body.appendChild(c)", "ov.appendChild(c)")
js = swap_assets(js)

PRE = r"""
    const ac = new AbortController()
    const dead = { v: false }
    const obs: any[] = []
    const ivs: any[] = []
    const W: any = window
    const D: any = window.document
    const sig = (o?: any) => (typeof o === "object" && o ? { ...o, signal: ac.signal } : { capture: !!o, signal: ac.signal })
    const addEventListener = (t: string, f: any, o?: any) => W.addEventListener(t, f, sig(o))
    const requestAnimationFrame = (f: any) => (dead.v ? 0 : W.requestAnimationFrame((t: number) => { if (!dead.v) f(t) }))
    const setTimeout = (f: any, ms?: number) => W.setTimeout(() => { if (!dead.v) f() }, ms)
    const clearTimeout = (id: any) => W.clearTimeout(id)
    const setInterval = (f: any, ms?: number) => { const id = W.setInterval(() => { if (!dead.v) f() }, ms); ivs.push(id); return id }
    const clearInterval = (id: any) => W.clearInterval(id)
    class IntersectionObserver extends W.IntersectionObserver { constructor(cb: any, o?: any) { super(cb, o); obs.push(this) } }
    class ResizeObserver extends W.ResizeObserver { constructor(cb: any) { super(cb); obs.push(this) } }
    const document: any = {
        // the timer runs 48h -> 0 over the case study itself, not the whole Framer page
        documentElement: { get scrollHeight() { return root.getBoundingClientRect().bottom + W.scrollY }, classList: root.classList, style: root.style },
        body: D.body,
        readyState: "complete",
        createElement: (t: string) => D.createElement(t),
        addEventListener: (t: string, f: any, o?: any) => D.addEventListener(t, f, sig(o)),
        get hidden() { return D.hidden },
        get activeElement() { return D.activeElement },
    }
    const $ = (s: string, r?: any): any => (r ? r.querySelector(s) : root.querySelector(s) || ov.querySelector(s))
    const $$ = (s: string, r?: any): any[] => (r ? [...r.querySelectorAll(s)] : [...root.querySelectorAll(s), ...ov.querySelectorAll(s)])
    const BASE = "__BASE__"
    W.R = (x: string) => (typeof x === "string" && x.startsWith("assets/") ? BASE + x.slice(7) : x)
    // in-page anchors (contents menu, jump buttons): smooth scroll without touching Framer's router
    const jump = (e: any) => {
        const a = e.target.closest && e.target.closest('a[href^="#"]')
        if (!a) return
        const t = root.querySelector(a.getAttribute("href"))
        if (!t) return
        e.preventDefault()
        W.scrollTo({ top: t.getBoundingClientRect().top + W.scrollY - 24, behavior: "smooth" })
    }
    root.addEventListener("click", jump, { signal: ac.signal })
    ov.addEventListener("click", jump, { signal: ac.signal })
    root.querySelectorAll("video").forEach((v: any) => { v.muted = true; v.defaultMuted = true })
    if (onCanvas) root.querySelectorAll(".reveal").forEach((el: any) => el.classList.add("in"))
""".replace("__BASE__", BASE)

POST = r"""
    return () => {
        dead.v = true
        ac.abort()
        obs.forEach((o) => o.disconnect())
        ivs.forEach((id) => W.clearInterval(id))
        D.body.style.overflow = ""
    }
"""

FONT_URL = "https://fonts.googleapis.com/css2?family=Figtree:ital,wght@0,400;0,500;0,600;1,400&family=Google+Sans+Flex:wght@400..700&family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600&display=swap"

tsx = f"""// @ts-nocheck
// Teerth Saathi case study (Salesforce Hackathon, IIT Kanpur).
// Generated by tools/build_framer.py from site/index.html in github.com/BbsvgFace/teerth-saathi.
// Edit the site and rebuild, or edit the strings below directly in Framer.
import {{ useEffect, useRef }} from "react"
import {{ RenderTarget }} from "framer"

const FONT_URL: string = {json.dumps(FONT_URL)}
const CSS: string = {json.dumps(CSS, ensure_ascii=False)}
const HTML: string = {json.dumps(HTML, ensure_ascii=False)}
const OV_HTML: string = {json.dumps(OV_HTML, ensure_ascii=False)}

function init(root: HTMLElement, ov: HTMLElement, onCanvas: boolean): () => void {{
{PRE}
    try {{
{js}
    }} catch (err) {{
        console.error("[TeerthSaathi]", err)
    }}
{POST}
}}

/**
 * @framerIntrinsicWidth 1200
 * @framerSupportedLayoutWidth any-prefer-fixed
 * @framerSupportedLayoutHeight auto
 */
export default function TeerthSaathiCaseStudy(props: {{ style?: React.CSSProperties }}) {{
    const ref = useRef<HTMLDivElement>(null)

    useEffect(() => {{
        const root = ref.current
        if (!root) return
        const ov = document.createElement("div")
        ov.className = "tsj-ov"
        ov.innerHTML = OV_HTML
        document.body.appendChild(ov)
        const dispose = init(root, ov, RenderTarget.current() === RenderTarget.canvas)
        return () => {{ dispose(); ov.remove() }}
    }}, [])

    return (
        <div style={{{{ ...props.style, width: "100%", containerType: "inline-size", containerName: "tsj" }} as React.CSSProperties}}>
            <link rel="preconnect" href="https://fonts.googleapis.com" />
            <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
            <link rel="stylesheet" href={{FONT_URL}} />
            <style dangerouslySetInnerHTML={{{{ __html: CSS }}}} />
            <div ref={{ref}} className="tsj-in" dangerouslySetInnerHTML={{{{ __html: HTML }}}} />
        </div>
    )
}}
"""
dst = REPO / "framer/TeerthSaathiCaseStudy.tsx"
dst.parent.mkdir(exist_ok=True)
dst.write_text(tsx)
(REPO / "framer/parts.json").write_text(json.dumps({"CSS": CSS, "HTML": HTML, "OV": OV_HTML, "JS": js, "PRE": PRE, "POST": POST, "FONT": FONT_URL}))
print("tsx bytes", len(tsx), "css", len(CSS), "html", len(HTML), "ov", len(OV_HTML), "js", len(js))
