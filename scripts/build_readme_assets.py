#!/usr/bin/env python3
"""Genera los SVG del README con el estilo de jefferson-panchi.vercel.app.

Cada gráfico se genera en versión clara y oscura (assets/*-light.svg y
assets/*-dark.svg). Las fuentes se incrustan en el SVG recortadas solo a los
caracteres usados, así GitHub las muestra aunque no pueda cargar fuentes
externas.

Uso:
    pip install fonttools brotli
    python3 scripts/build_readme_assets.py
"""

import base64
import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "scripts" / "fonts"
ICONS = ROOT / "scripts" / "icons"
OUT = ROOT / "assets"

# --- Paleta (tokens copiados de la hoja de estilos del sitio) ---------------
ACCENTS = {
    "mint": "#7ee0c3",
    "yellow": "#ffd25c",
    "pink": "#ff9ec7",
    "lilac": "#b9a7f5",
    "select": "#9c8cf0",
    "coral": "#ff8a7a",
    "green": "#3fcf9c",
    "sticker_ink": "#17171c",
}
THEMES = {
    "light": {
        "surface": "#ffffff",
        "surface2": "#f4efe4",
        "ink": "#17171c",
        "muted": "#3f3d4a",
        "line": "#17171c",
        "shadow": "#17171c",
    },
    "dark": {
        "surface": "#1a1a22",
        "surface2": "#23232d",
        "ink": "#f5f3ff",
        "muted": "#cfccde",
        "line": "#f5f3ff",
        "shadow": "#838bc5",
    },
}

# --- Fuentes -----------------------------------------------------------------
FONT_SPECS = {
    "display": ("bricolage.woff2", 800, "Bricolage Grotesque"),
    "sans": ("inter.woff2", 600, "Inter"),
    "sansbold": ("inter.woff2", 700, "Inter"),
    "body": ("inter.woff2", 400, "Inter"),
    "mono": ("jbmono.woff2", 500, "JetBrains Mono"),
    "monobold": ("jbmono.woff2", 700, "JetBrains Mono"),
}
_font_cache = {}


def font(key):
    if key not in _font_cache:
        file, weight, _ = FONT_SPECS[key]
        f = TTFont(FONTS / file)
        f = instancer.instantiateVariableFont(f, {"wght": weight})
        _font_cache[key] = f
    return _font_cache[key]


def text_width(key, text, size):
    f = font(key)
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    upm = f["head"].unitsPerEm
    total = 0
    for ch in text:
        glyph = cmap.get(ord(ch)) or cmap.get(ord("?"))
        total += hmtx[glyph][0]
    return total * size / upm


def font_face(key, chars):
    """@font-face con la fuente recortada a `chars`, en base64."""
    f = font(key)
    buf = io.BytesIO()
    f.save(buf)
    buf.seek(0)
    sub = TTFont(buf)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt"]
    opts.name_IDs = []
    s = subset.Subsetter(opts)
    s.populate(text="".join(sorted(set(chars))) + " ")
    s.subset(sub)
    out = io.BytesIO()
    sub.flavor = "woff2"
    sub.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return (
        f"@font-face{{font-family:'{key}';"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
    )


class Svg:
    """Pequeño ayudante que acumula elementos y el texto usado por fuente."""

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts = []
        self.chars = {}
        self.css = []

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, key, size, fill, extra=""):
        self.chars.setdefault(key, set()).update(s)
        self.add(
            f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{key}" '
            f'font-size="{size}" fill="{fill}" {extra}>{escape(s)}</text>'
        )

    def render(self):
        faces = "".join(font_face(k, v) for k, v in self.chars.items())
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
            f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" '
            f'aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title>"
            f"<style>{faces}{''.join(self.css)}</style>"
            + "".join(self.parts)
            + "</svg>\n"
        )


def write(name, theme, svg):
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}-{theme}.svg"
    path.write_text(svg.render(), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")


# --- Piezas reutilizables ----------------------------------------------------
def card(svg, x, y, w, h, r, fill, stroke, shadow, sw=2.5, off=6, extra=""):
    """Rectángulo con borde grueso y sombra dura desplazada (neo-brutalista)."""
    svg.add(
        f'<g {extra}><rect x="{x + off}" y="{y + off}" width="{w}" height="{h}" '
        f'rx="{r}" fill="{shadow}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/></g>'
    )


def selection(svg, x, y, w, h, extra=""):
    """Marco de selección lila con tiradores, como en el sitio."""
    c = ACCENTS["select"]
    hs = 9
    handles = "".join(
        f'<rect x="{hx - hs / 2}" y="{hy - hs / 2}" width="{hs}" height="{hs}" '
        f'fill="#ffffff" stroke="{c}" stroke-width="1.5"/>'
        for hx, hy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h))
    )
    svg.add(
        f'<g {extra}><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
        f'stroke="{c}" stroke-width="1.5"/>{handles}</g>'
    )


def pill(svg, x, y, label, t, key="mono", size=12.5, fill=None, dot=None, extra=""):
    pad = 14
    tw = text_width(key, label, size)
    dot_w = 14 if dot else 0
    w = tw + pad * 2 + dot_w
    h = 28
    svg.add(f"<g {extra}>")
    svg.add(
        f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
        f'fill="{fill or t["surface"]}" stroke="{t["line"]}" stroke-width="1.6"/>'
    )
    if dot:
        svg.add(
            f'<circle cx="{x + pad + 3.5}" cy="{y + h / 2}" r="4" fill="{dot}" '
            f'stroke="{ACCENTS["sticker_ink"]}" stroke-width="1"/>'
        )
    svg.add("</g>")
    svg.text(
        x + pad + dot_w, y + h / 2 + size * 0.36, label, key, size,
        t["ink"] if not fill else ACCENTS["sticker_ink"], extra,
    )
    return w


def icon_path(name):
    raw = (ICONS / f"{name}.svg").read_text()
    return re.search(r'<path d="([^"]+)"', raw).group(1)


# Iconos de trazo (estilo lucide) para las pegatinas.
SHIELD = "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"
CHECK = "m9 12 2 2 4-4"
HEART = "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"
SPARKLES = "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"
EXTERNAL = ["M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"]
CURSOR = "M0 0 L0 21 L5.5 16 L9.5 24.5 L13 23 L9 14.5 L16 14.5 Z"


def stroke_icon(paths, x, y, size, color):
    s = size / 24
    ds = "".join(f'<path d="{d}"/>' for d in paths)
    return (
        f'<g transform="translate({x} {y}) scale({s})" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ds}</g>'
    )


def sticker(svg, x, y, w, h, color, inner, t, rot):
    cx, cy = x + w / 2, y + h / 2
    card(
        svg, x, y, w, h, 14, color, ACCENTS["sticker_ink"], t["shadow"],
        sw=2.5, off=4, extra=f'transform="rotate({rot} {cx} {cy})"',
    )
    svg.add(f'<g transform="rotate({rot} {cx} {cy})">{inner}</g>')


# --- Cabecera ----------------------------------------------------------------
ROLES = ["Full Stack Developer", "Cybersecurity Enthusiast", "Creative by Nature"]


def build_header(theme):
    t = THEMES[theme]
    W, H = 900, 420
    svg = Svg(W, H, "Jefferson Panchi — Software Engineer: Full Stack Developer, Cybersecurity Enthusiast, Creative by Nature")
    ink = ACCENTS["sticker_ink"]

    # Ventana del navegador
    card(svg, 4, 4, W - 18, H - 18, 24, t["surface"], t["line"], t["shadow"], off=8)
    bar_y = 70
    svg.add(f'<line x1="5.3" y1="{bar_y}" x2="{W - 15.3}" y2="{bar_y}" stroke="{t["line"]}" stroke-width="2.5"/>')
    for i, c in enumerate((ACCENTS["coral"], ACCENTS["yellow"], ACCENTS["mint"])):
        svg.add(f'<circle cx="{34 + i * 22}" cy="40" r="6.5" fill="{c}" stroke="{ink}" stroke-width="1.5"/>')

    # Pestañas
    tab_x, tab_w, tab_top = 120, 132, 24
    svg.add(
        f'<path d="M{tab_x} {bar_y} V{tab_top + 12} Q{tab_x} {tab_top} {tab_x + 12} {tab_top} '
        f'H{tab_x + tab_w - 12} Q{tab_x + tab_w} {tab_top} {tab_x + tab_w} {tab_top + 12} V{bar_y}" '
        f'fill="{t["surface"]}" stroke="{t["line"]}" stroke-width="2.5"/>'
    )
    svg.add(f'<line x1="{tab_x + 1.3}" y1="{bar_y}" x2="{tab_x + tab_w - 1.3}" y2="{bar_y}" stroke="{t["surface"]}" stroke-width="3"/>')
    label = "README.md"
    svg.text(tab_x + (tab_w - text_width("sansbold", label, 15)) / 2, 53, label, "sansbold", 15, t["ink"])
    x = tab_x + tab_w + 26
    for name in ("about", "toolbox", "stats"):
        svg.text(x, 53, name, "sans", 15, t["muted"])
        x += text_width("sans", name, 15) + 34

    # Pastillas superiores
    px, py = 52, 102
    w = pill(svg, px, py, "Software Engineer", t, dot=ACCENTS["green"])
    pill(svg, px + w + 10, py, "@jfpanchi", t)

    # Nombre dentro del marco de selección
    size = 70
    l1, l2 = "Jefferson", "Panchi"
    nw = max(text_width("display", l1, size), text_width("display", l2, size))
    bx, by, bw, bh = 46, 146, nw + 36, 162
    rot = f'transform="rotate(-2 {bx + bw / 2} {by + bh / 2})"'
    selection(svg, bx, by, bw, bh, rot)
    svg.text(bx + 18, by + 72, l1, "display", size, t["ink"], f'letter-spacing="-1.5" {rot}')
    svg.text(bx + 18, by + 146, l2, "display", size, t["ink"], f'letter-spacing="-1.5" {rot}')

    # Pegatina menta con los roles (animados)
    rsize = 15
    rw = max(text_width("sansbold", r, rsize) for r in ROLES) + 32
    rx, ry, rh = bx + bw - rw + 40, by + bh - 6, 38
    rrot = f'transform="rotate(1.5 {rx + rw / 2} {ry + rh / 2})"'
    card(svg, rx, ry, rw, rh, 9, ACCENTS["mint"], ink, t["shadow"], sw=2, off=4, extra=rrot)
    n = len(ROLES)
    dur = 3 * n
    step = 100 / n
    svg.css.append(
        f"@keyframes role{{0%{{opacity:0;transform:translateY(6px)}}"
        f"{step * 0.12:.1f}%{{opacity:1;transform:translateY(0)}}"
        f"{step * 0.88:.1f}%{{opacity:1;transform:translateY(0)}}"
        f"{step:.1f}%,100%{{opacity:0;transform:translateY(-6px)}}}}"
        f".role{{opacity:0;animation:role {dur}s infinite}}"
        f"@media (prefers-reduced-motion:reduce){{.role{{animation:none}}.role:first-child{{opacity:1}}}}"
    )
    svg.add(f"<g {rrot}><g>")
    for i, r in enumerate(ROLES):
        tw = text_width("sansbold", r, rsize)
        svg.chars.setdefault("sansbold", set()).update(r)
        svg.add(
            f'<text class="role" style="animation-delay:{i * 3}s" x="{rx + (rw - tw) / 2:.1f}" '
            f'y="{ry + rh / 2 + rsize * 0.36:.1f}" font-family="sansbold" font-size="{rsize}" '
            f'fill="{ink}">{escape(r)}</text>'
        )
    svg.add("</g></g>")

    # Frase con resaltado lila
    fy = 372
    pre, hl, post = "Creating ", "secure & reliable", " user experiences."
    fs = 19
    svg.text(52, fy, pre, "body", fs, t["muted"])
    hx = 52 + text_width("body", pre, fs)
    hw = text_width("sansbold", hl, fs) + 20
    hrot = f'transform="rotate(-1.5 {hx + hw / 2} {fy - 6})"'
    card(svg, hx, fy - 25, hw, 34, 8, ACCENTS["lilac"], ink, t["shadow"], sw=1.8, off=3, extra=hrot)
    svg.text(hx + 10, fy, hl, "sansbold", fs, ink, hrot)
    svg.text(hx + hw + 6, fy, post, "body", fs, t["muted"])

    # Tarjeta de código a la derecha
    cx, cy, cw, ch = 584, 128, 252, 168
    crot = f'transform="rotate(3 {cx + cw / 2} {cy + ch / 2})"'
    selection(svg, cx - 16, cy - 16, cw + 30, ch + 30, f'transform="rotate(-1.5 {cx + cw / 2} {cy + ch / 2})"')
    card(svg, cx, cy, cw, ch, 18, t["surface2"], t["line"], t["shadow"], off=6, extra=crot)
    lines = [
        [("const ", "monobold", ACCENTS["select"]), ("jefferson = {", "mono", t["ink"])],
        [("  role: ", "mono", t["ink"]), ('"Full Stack"', "mono", t["muted"]), (",", "mono", t["ink"])],
        [("  focus: ", "mono", t["ink"]), ('"Security"', "mono", t["muted"]), (",", "mono", t["ink"])],
        [("  nature: ", "mono", t["ink"]), ('"Creative"', "mono", t["muted"]), (",", "mono", t["ink"])],
        [("};", "mono", t["ink"])],
    ]
    ms = 14
    for i, segs in enumerate(lines):
        x = cx + 22
        for s, key, color in segs:
            svg.text(x, cy + 44 + i * 26, s, key, ms, color, crot)
            x += text_width(key, s, ms)

    # Pegatinas alrededor de la tarjeta
    sticker(svg, 548, 96, 62, 62, ACCENTS["mint"],
            stroke_icon([SHIELD, CHECK], 548 + 17, 96 + 17, 28, ink), t, -8)
    pill(svg, 528, 168, "secure", t, extra='transform="rotate(-6 560 182)"')
    sticker(svg, 800, 86, 62, 44, ACCENTS["yellow"], "", t, 8)
    cw2 = text_width("monobold", "</>", 17)
    svg.text(800 + (62 - cw2) / 2, 86 + 28, "</>", "monobold", 17, ink, 'transform="rotate(8 831 108)"')
    sticker(svg, 806, 266, 62, 62, ACCENTS["pink"],
            stroke_icon([HEART], 806 + 17, 266 + 18, 28, ink), t, 7)
    pill(svg, 764, 338, "human", t, extra='transform="rotate(-4 800 352)"')
    sticker(svg, 560, 286, 58, 58, ACCENTS["yellow"],
            stroke_icon([SPARKLES], 560 + 15, 286 + 15, 28, ink), t, -6)
    pill(svg, 540, 354, "creative", t, extra='transform="rotate(5 576 368)"')

    # Cursor flotante con etiqueta
    svg.css.append(
        "@keyframes float{0%,100%{transform:translate(0,0)}50%{transform:translate(-14px,10px)}}"
        ".cursor{animation:float 6s ease-in-out infinite}"
        "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}"
    )
    gx, gy = 486, 214
    svg.add(f'<g class="cursor"><g transform="translate({gx} {gy})">'
            f'<path d="{CURSOR}" fill="{ACCENTS["lilac"]}" stroke="{ink}" stroke-width="1.6" stroke-linejoin="round"/>')
    lw = text_width("sansbold", "jfpanchi", 13) + 22
    svg.add(f'<rect x="14" y="22" width="{lw:.1f}" height="26" rx="13" fill="{ACCENTS["lilac"]}" stroke="{ink}" stroke-width="1.6"/></g></g>')
    svg.chars.setdefault("sansbold", set()).update("jfpanchi")
    svg.add(f'<g class="cursor"><text x="{gx + 25}" y="{gy + 39.5}" font-family="sansbold" font-size="13" fill="{ink}">jfpanchi</text></g>')

    write("header", theme, svg)


# --- Títulos de sección (pegatinas como "Proyectos" en el sitio) -------------
SECTIONS = {
    "about": ("About Me", "lilac", -2),
    "toolbox": ("My Toolbox", "yellow", 1.5),
    "learning": ("Currently Learning", "mint", -1.5),
    "stats": ("GitHub Stats", "pink", 2),
    "connect": ("Let's Connect!", "coral", -2),
}


def build_title(name, theme):
    t = THEMES[theme]
    label, color, rot = SECTIONS[name]
    size = 30
    tw = text_width("display", label, size)
    w, h = tw + 36, 54
    W, H = int(w + 30), 80
    svg = Svg(W, H, label)
    x, y = 10, 12
    r = f'transform="rotate({rot} {x + w / 2} {y + h / 2})"'
    card(svg, x, y, w, h, 12, ACCENTS[color], ACCENTS["sticker_ink"], t["shadow"], off=5, extra=r)
    svg.text(x + 18, y + h / 2 + size * 0.34, label, "display", size, ACCENTS["sticker_ink"], f'letter-spacing="-0.5" {r}')
    write(f"title-{name}", theme, svg)


# --- Caja de herramientas ----------------------------------------------------
TOOLBOX = [
    ("Languages", "lilac", [("JavaScript", "javascript"), ("TypeScript", "typescript"), ("PHP", "php")]),
    ("Frontend", "yellow", [
        ("HTML5", "html5"), ("CSS3", "css3"), ("Tailwind", "tailwindcss"), ("React", "react"),
        ("Redux", "redux"), ("Zustand", None), ("React Query", "reactquery"),
        ("shadcn/ui", "shadcnui"), ("Radix", "radixui"), ("Next.js", "nextdotjs"),
    ]),
    ("Backend", "mint", [("Node.js", "nodedotjs"), ("Laravel", "laravel"), ("Express", "express"), ("MySQL", "mysql"), ("MongoDB", "mongodb")]),
    ("CMS", "pink", [("WordPress", "wordpress")]),
]
LEARNING = [("React Native", "react"), ("Expo", "expo")]


def chip(svg, x, y, label, icon, t, fill, text_color):
    fs = 13.5
    h = 34
    iw = 18 if icon is not False else 0
    w = text_width("mono", label, fs) + 26 + (iw + 8 if iw else 0)
    card(svg, x, y, w, h, 9, fill, t["line"], t["shadow"], sw=1.8, off=3)
    tx = x + 13
    if iw:
        if icon:
            s = iw / 24
            svg.add(f'<path transform="translate({tx} {y + (h - iw) / 2}) scale({s})" d="{icon_path(icon)}" fill="{text_color}"/>')
        else:  # sin icono oficial: una "Z" en recuadro
            svg.add(f'<rect x="{tx + 1}" y="{y + (h - iw) / 2 + 1}" width="{iw - 2}" height="{iw - 2}" rx="4" fill="{text_color}"/>')
            zw = text_width("monobold", "Z", 12)
            svg.text(tx + (iw - zw) / 2, y + h / 2 + 4.3, "Z", "monobold", 12, fill)
        tx += iw + 8
    svg.text(tx, y + h / 2 + fs * 0.36, label, "mono", fs, text_color)
    return w


def build_toolbox(theme):
    t = THEMES[theme]
    W = 900
    label_w = 150
    gap = 12
    row_h = 46
    # Distribuye las pastillas en filas
    layout = []
    y = 36
    max_x = W - 52
    for cat, color, items in TOOLBOX:
        rows = [[]]
        x = 40 + label_w
        for label, icon in items:
            w = text_width("mono", label, 13.5) + 26 + 26
            if x + w > max_x and rows[-1]:
                rows.append([])
                x = 40 + label_w
            rows[-1].append((x, label, icon))
            x += w + gap
        layout.append((cat, color, y, rows))
        y += len(rows) * row_h + 22
    H = int(y + 18)
    svg = Svg(W, H, "My toolbox: " + ", ".join(l for _, _, it in TOOLBOX for l, _ in it))
    card(svg, 4, 4, W - 16, H - 16, 22, t["surface"], t["line"], t["shadow"], off=8)
    for i, (cat, color, y0, rows) in enumerate(layout):
        if i:
            svg.add(f'<line x1="28" y1="{y0 - 12}" x2="{W - 40}" y2="{y0 - 12}" stroke="{t["line"]}" stroke-width="1.5" stroke-dasharray="2 6" stroke-linecap="round" opacity=".45"/>')
        lw = text_width("monobold", cat.upper(), 12) + 22
        svg.add(f'<rect x="32" y="{y0 + 5}" width="{lw:.1f}" height="26" rx="6" fill="{ACCENTS[color]}" stroke="{ACCENTS["sticker_ink"]}" stroke-width="1.6"/>')
        svg.text(43, y0 + 22.5, cat.upper(), "monobold", 12, ACCENTS["sticker_ink"], 'letter-spacing="0.5"')
        for r, row in enumerate(rows):
            for x, label, icon in row:
                chip(svg, x, y0 + r * row_h, label, icon, t, t["surface2"], t["ink"])
    write("toolbox", theme, svg)


def build_learning(theme):
    t = THEMES[theme]
    x = 10
    widths = [text_width("mono", l, 13.5) + 52 for l, _ in LEARNING]
    W = int(10 + sum(widths) + 14 * len(widths) + 120)
    H = 60
    svg = Svg(W, H, "Currently learning: " + ", ".join(l for l, _ in LEARNING))
    for label, icon in LEARNING:
        x += chip(svg, x, 12, label, icon, t, ACCENTS["mint"], ACCENTS["sticker_ink"]) + 14
    # Indicador "en progreso" animado
    svg.css.append(
        "@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}"
        ".dot{animation:blink 1.4s infinite}.dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}"
        "@media (prefers-reduced-motion:reduce){.dot{animation:none}}"
    )
    svg.add("<g>" + "".join(
        f'<circle class="dot" cx="{x + 8 + i * 14}" cy="29" r="4.5" fill="{t["ink"]}"/>' for i in range(3)
    ) + "</g>")
    write("learning", theme, svg)


# --- Botón del portafolio ----------------------------------------------------
def build_button(theme):
    t = THEMES[theme]
    label = "Visit my portfolio"
    fs = 18
    tw = text_width("sansbold", label, fs)
    w, h = tw + 30 + 30 + 10, 56
    W, H = int(w + 20), int(h + 20)
    svg = Svg(W, H, "Visit my portfolio — jefferson-panchi.vercel.app")
    ink = ACCENTS["sticker_ink"]
    card(svg, 6, 6, w, h, 14, ACCENTS["yellow"], ink, t["shadow"], off=6)
    svg.text(6 + 25, 6 + h / 2 + fs * 0.36, label, "sansbold", fs, ink)
    svg.add(stroke_icon(EXTERNAL, 6 + 25 + tw + 12, 6 + h / 2 - 9, 18, ink))
    write("portfolio", theme, svg)


def main():
    for theme in THEMES:
        print(f"[{theme}]")
        build_header(theme)
        for name in SECTIONS:
            build_title(name, theme)
        build_toolbox(theme)
        build_learning(theme)
        build_button(theme)


if __name__ == "__main__":
    main()
