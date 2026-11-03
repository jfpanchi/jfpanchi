#!/usr/bin/env python3
"""Genera los SVG del README en blanco y negro.

Toma algunos detalles de jefferson-panchi.vercel.app (bordes gruesos, sombras
sólidas, marco de selección, cursor con etiqueta, chips en fuente mono) pero
mantiene la paleta monocroma del perfil de GitHub.

Cada gráfico se genera en versión clara y oscura (assets/*-light.svg y
assets/*-dark.svg). Las fuentes se incrustan recortadas a los caracteres
usados, así GitHub las muestra aunque no pueda cargar fuentes externas.

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

# Blanco y negro. En modo oscuro todo se invierte.
THEMES = {
    "light": {"bg": "#ffffff", "fg": "#000000", "muted": "#57606a", "shadow": "#000000", "soft": "#d0d7de"},
    "dark": {"bg": "#000000", "fg": "#ffffff", "muted": "#9198a1", "shadow": "#ffffff", "soft": "#3d444d"},
}

# --- Fuentes -----------------------------------------------------------------
FONT_SPECS = {
    "display": ("bricolage.woff2", 800),
    "sansbold": ("inter.woff2", 700),
    "body": ("inter.woff2", 400),
    "mono": ("jbmono.woff2", 500),
    "monobold": ("jbmono.woff2", 700),
}
_font_cache = {}


def font(key):
    if key not in _font_cache:
        file, weight = FONT_SPECS[key]
        f = TTFont(FONTS / file)
        _font_cache[key] = instancer.instantiateVariableFont(f, {"wght": weight})
    return _font_cache[key]


def text_width(key, text, size):
    f = font(key)
    cmap, hmtx = f.getBestCmap(), f["hmtx"]
    total = sum(hmtx[cmap.get(ord(c)) or cmap[ord("?")]][0] for c in text)
    return total * size / f["head"].unitsPerEm


def font_face(key, chars):
    """@font-face con la fuente recortada a `chars`, en base64."""
    buf = io.BytesIO()
    font(key).save(buf)
    buf.seek(0)
    sub = TTFont(buf)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern"]
    opts.name_IDs = []
    s = subset.Subsetter(opts)
    s.populate(text="".join(sorted(set(chars))) + " ")
    s.subset(sub)
    out = io.BytesIO()
    sub.flavor = "woff2"
    # Fecha fija: así regenerar no cambia los SVG si nada cambió
    sub.recalcTimestamp = False
    sub["head"].modified = sub["head"].created
    sub.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{data}) format('woff2');}}"


class Svg:
    """Acumula elementos y el texto usado por cada fuente."""

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts, self.css, self.chars = [], [], {}

    def add(self, s):
        self.parts.append(s)

    def use(self, key, s):
        self.chars.setdefault(key, set()).update(s)

    def text(self, x, y, s, key, size, fill, extra=""):
        self.use(key, s)
        self.add(
            f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{key}" '
            f'font-size="{size}" fill="{fill}" {extra}>{escape(s)}</text>'
        )

    def render(self):
        faces = "".join(font_face(k, v) for k, v in self.chars.items())
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
            f"<title>{escape(self.title)}</title><style>{faces}{''.join(self.css)}</style>"
            + "".join(self.parts) + "</svg>\n"
        )


def write(name, theme, svg):
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}-{theme}.svg"
    path.write_text(svg.render(), encoding="utf-8")
    print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size // 1024} KB)")


# --- Piezas reutilizables ----------------------------------------------------
def block(svg, x, y, w, h, r, t, fill=None, sw=2.5, off=6, extra="", shadow=None):
    """Rectángulo con borde grueso y sombra sólida desplazada."""
    svg.add(
        f'<g {extra}><rect x="{x + off}" y="{y + off}" width="{w:.1f}" height="{h}" rx="{r}" fill="{shadow or t["shadow"]}"/>'
        f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{r}" fill="{fill or t["bg"]}" '
        f'stroke="{t["fg"]}" stroke-width="{sw}"/></g>'
    )


def selection(svg, x, y, w, h, t):
    """Marco de selección con tiradores en las esquinas."""
    hs = 9
    svg.add(
        f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" fill="none" stroke="{t["muted"]}" '
        f'stroke-width="1.5" stroke-dasharray="6 5"/>'
    )
    for hx, hy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
        svg.add(
            f'<rect x="{hx - hs / 2:.1f}" y="{hy - hs / 2}" width="{hs}" height="{hs}" '
            f'fill="{t["bg"]}" stroke="{t["fg"]}" stroke-width="1.5"/>'
        )


def pill(svg, x, y, label, t, dot=False):
    size, pad, h = 12.5, 14, 28
    dot_w = 14 if dot else 0
    w = text_width("mono", label, size) + pad * 2 + dot_w
    svg.add(
        f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
        f'fill="{t["bg"]}" stroke="{t["fg"]}" stroke-width="1.6"/>'
    )
    if dot:
        svg.add(f'<circle class="pulse" cx="{x + pad + 3.5:.1f}" cy="{y + h / 2}" r="4" fill="{t["fg"]}"/>')
    svg.text(x + pad + dot_w, y + h / 2 + size * 0.36, label, "mono", size, t["fg"])
    return w


def icon_path(name):
    raw = (ICONS / f"{name}.svg").read_text()
    return re.search(r'<path d="([^"]+)"', raw).group(1)


# Iconos de trazo (estilo lucide).
SHIELD = "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"
CHECK = "m9 12 2 2 4-4"
HEART = "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"
CODE = ["m16 18 6-6-6-6", "m8 6-6 6 6 6"]
EXTERNAL = ["M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"]
CURSOR = "M0 0 L0 21 L5.5 16 L9.5 24.5 L13 23 L9 14.5 L16 14.5 Z"


def stroke_icon(paths, x, y, size, color):
    ds = "".join(f'<path d="{d}"/>' for d in paths)
    return (
        f'<g transform="translate({x} {y}) scale({size / 24})" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{ds}</g>'
    )


def icon_tile(svg, x, y, paths, t):
    block(svg, x, y, 52, 52, 12, t, off=4)
    svg.add(stroke_icon(paths, x + 14, y + 14, 24, t["fg"]))


REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"

# --- Cabecera ----------------------------------------------------------------
ROLES = ["Full Stack Developer", "Cybersecurity Enthusiast", "Creative by Nature"]


def build_header(theme):
    t = THEMES[theme]
    W, H = 900, 262
    svg = Svg(W, H, "Jefferson Panchi — Full Stack Developer, Cybersecurity Enthusiast, Creative by Nature")

    # Nombre centrado dentro del marco de selección
    size, name = 76, "Jefferson Panchi"
    nw = text_width("display", name, size)
    bx, by, bw, bh = (W - nw) / 2 - 22, 52, nw + 44, 110
    selection(svg, bx, by, bw, bh, t)
    svg.text(bx + 22, by + 82, name, "display", size, t["fg"], 'letter-spacing="-1.5"')

    # Pastilla invertida con los roles escritos letra a letra
    rs = 17
    cw = text_width("mono", "M", rs)  # monoespaciada: todas iguales
    longest = max(len(r) for r in ROLES)
    pw, ph = cw * (longest + 1) + 40, 46
    px, py = (W - pw) / 2, 196
    block(svg, px, py, pw, ph, 12, t, fill=t["fg"], off=5, shadow=t["muted"])
    svg.add(f'<clipPath id="pc"><rect x="{px}" y="{py}" width="{pw:.1f}" height="{ph}" rx="12"/></clipPath>')
    slot = 4  # segundos por rol
    total = slot * len(ROLES)
    show = 100 / len(ROLES)
    svg.css.append(
        f"@keyframes show{{0%,{show:.2f}%{{opacity:1}}{show + 0.01:.2f}%,100%{{opacity:0}}}}"
        f".role{{opacity:0;animation:show {total}s infinite}}"
        f"@keyframes blink{{0%,50%{{opacity:1}}50.1%,100%{{opacity:0}}}}"
        f".caret{{animation:blink 1s infinite}}"
        f"@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}.pulse{{animation:pulse 2s infinite}}"
    )
    tx, ty = px + 20, py + ph / 2 + rs * 0.36
    svg.add('<g clip-path="url(#pc)">')
    for i, role in enumerate(ROLES):
        n = len(role)
        typed = show * 0.45  # parte del turno que dura la escritura
        svg.css.append(
            f"@keyframes type{i}{{0%{{transform:translateX(0);animation-timing-function:steps({n},end)}}"
            f"{typed:.2f}%,100%{{transform:translateX({n * cw:.2f}px)}}}}"
            f".type{i}{{animation:type{i} {total}s infinite;animation-delay:{i * slot}s}}"
        )
        svg.add(f'<g class="role" style="animation-delay:{i * slot}s">')
        svg.text(tx, ty, role, "mono", rs, t["bg"])
        # Tapa que se desplaza para "escribir" el texto, con el cursor delante
        svg.add(
            f'<g class="type{i}"><rect x="{tx:.1f}" y="{py + 4}" width="{pw:.1f}" height="{ph - 8}" fill="{t["fg"]}"/>'
            f'<rect class="caret" x="{tx + 1:.1f}" y="{py + 12}" width="{cw * 0.55:.1f}" height="{ph - 24}" fill="{t["bg"]}"/></g>'
        )
        svg.add("</g>")
    svg.add("</g>")

    # Pastillas arriba del nombre
    w1 = text_width("mono", "Software Engineer", 12.5) + 42
    w2 = text_width("mono", "@jfpanchi", 12.5) + 28
    x0 = (W - (w1 + 10 + w2)) / 2
    pill(svg, x0, 8, "Software Engineer", t, dot=True)
    pill(svg, x0 + w1 + 10, 8, "@jfpanchi", t)

    # Iconos a los lados (seguro, código, humano)
    icon_tile(svg, 40, 70, [SHIELD, CHECK], t)
    icon_tile(svg, 96, 168, CODE, t)
    icon_tile(svg, W - 100, 92, [HEART], t)

    # Cursor flotante con etiqueta
    svg.css.append(
        "@keyframes float{0%,100%{transform:translate(0,0)}50%{transform:translate(-12px,8px)}}"
        ".cursor{animation:float 6s ease-in-out infinite}"
    )
    gx, gy = bx + bw - 14, by + bh - 10
    lw = text_width("sansbold", "jfpanchi", 13) + 22
    svg.use("sansbold", "jfpanchi")
    svg.add(
        f'<g class="cursor"><g transform="translate({gx:.1f} {gy})">'
        f'<path d="{CURSOR}" fill="{t["fg"]}" stroke="{t["bg"]}" stroke-width="1.6" stroke-linejoin="round"/>'
        f'<rect x="14" y="22" width="{lw:.1f}" height="26" rx="13" fill="{t["fg"]}"/>'
        f'<text x="25" y="39.5" font-family="sansbold" font-size="13" fill="{t["bg"]}">jfpanchi</text></g></g>'
    )
    svg.css.append(REDUCED)
    write("header", theme, svg)


# --- Títulos de sección ------------------------------------------------------
SECTIONS = {
    "about": ("01", "About Me"),
    "toolbox": ("02", "My Toolbox"),
    "learning": ("03", "Currently Learning"),
    "stats": ("04", "GitHub Stats"),
    "connect": ("05", "Let's Connect!"),
}


def build_title(name, theme):
    t = THEMES[theme]
    num, label = SECTIONS[name]
    size = 28
    nw = text_width("monobold", num, 13) + 18
    tw = text_width("display", label, size)
    w, h = nw + tw + 44, 52
    svg = Svg(int(w + 16), 70, label)
    block(svg, 4, 6, w, h, 10, t, off=5)
    # Número de sección en una pastilla invertida
    svg.add(f'<rect x="16" y="{6 + (h - 24) / 2}" width="{nw:.1f}" height="24" rx="6" fill="{t["fg"]}"/>')
    svg.text(25, 6 + h / 2 + 4.7, num, "monobold", 13, t["bg"])
    svg.text(16 + nw + 12, 6 + h / 2 + size * 0.34, label, "display", size, t["fg"], 'letter-spacing="-0.5"')
    write(f"title-{name}", theme, svg)


# --- Caja de herramientas ----------------------------------------------------
TOOLBOX = [
    ("Languages", [("JavaScript", "javascript"), ("TypeScript", "typescript"), ("PHP", "php")]),
    ("Frontend", [
        ("HTML5", "html5"), ("CSS3", "css3"), ("Tailwind", "tailwindcss"), ("React", "react"),
        ("Redux", "redux"), ("Zustand", None), ("React Query", "reactquery"),
        ("shadcn/ui", "shadcnui"), ("Radix", "radixui"), ("Next.js", "nextdotjs"),
    ]),
    ("Backend", [("Node.js", "nodedotjs"), ("Laravel", "laravel"), ("Express", "express"), ("MySQL", "mysql"), ("MongoDB", "mongodb")]),
    ("CMS", [("WordPress", "wordpress")]),
]
LEARNING = [("React Native", "react"), ("Expo", "expo")]
CHIP_FS, CHIP_H, ICON = 13.5, 34, 18


def chip_width(label):
    return text_width("mono", label, CHIP_FS) + 26 + ICON + 8


def chip(svg, x, y, label, icon, t, dashed=False):
    w = chip_width(label)
    if dashed:
        svg.add(
            f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{CHIP_H}" rx="9" fill="{t["bg"]}" '
            f'stroke="{t["fg"]}" stroke-width="1.8" stroke-dasharray="5 4"/>'
        )
    else:
        block(svg, x, y, w, CHIP_H, 9, t, sw=1.8, off=3)
    ix, iy = x + 13, y + (CHIP_H - ICON) / 2
    if icon:
        svg.add(f'<path transform="translate({ix} {iy}) scale({ICON / 24})" d="{icon_path(icon)}" fill="{t["fg"]}"/>')
    else:  # Zustand no tiene icono oficial: una "Z" en recuadro
        svg.add(f'<rect x="{ix + 1}" y="{iy + 1}" width="{ICON - 2}" height="{ICON - 2}" rx="4" fill="{t["fg"]}"/>')
        svg.text(ix + (ICON - text_width("monobold", "Z", 12)) / 2, y + CHIP_H / 2 + 4.3, "Z", "monobold", 12, t["bg"])
    svg.text(ix + ICON + 8, y + CHIP_H / 2 + CHIP_FS * 0.36, label, "mono", CHIP_FS, t["fg"])
    return w


def build_toolbox(theme):
    t = THEMES[theme]
    W, gap, row_h, left = 900, 12, 46, 190
    layout, y = [], 34
    for cat, items in TOOLBOX:
        rows, x = [[]], left
        for label, icon in items:
            w = chip_width(label)
            if x + w > W - 50 and rows[-1]:
                rows.append([])
                x = left
            rows[-1].append((x, label, icon))
            x += w + gap
        layout.append((cat, y, rows))
        y += len(rows) * row_h + 24
    H = int(y + 14)
    svg = Svg(W, H, "My toolbox: " + ", ".join(l for _, it in TOOLBOX for l, _ in it))
    block(svg, 4, 4, W - 16, H - 16, 18, t, off=8)
    for i, (cat, y0, rows) in enumerate(layout):
        if i:
            svg.add(f'<line x1="30" y1="{y0 - 13}" x2="{W - 42}" y2="{y0 - 13}" stroke="{t["soft"]}" stroke-width="1.5"/>')
        label = cat.upper()
        svg.text(32, y0 + 22, "> ", "monobold", 13, t["muted"])
        svg.text(32 + text_width("monobold", "> ", 13), y0 + 22, label, "monobold", 13, t["fg"], 'letter-spacing="1"')
        for r, row in enumerate(rows):
            for x, lbl, icon in row:
                chip(svg, x, y0 + r * row_h, lbl, icon, t)
    write("toolbox", theme, svg)


def build_learning(theme):
    t = THEMES[theme]
    widths = [chip_width(l) for l, _ in LEARNING]
    W = int(6 + sum(widths) + 14 * (len(widths) - 1) + 6)
    svg = Svg(W, 56, "Currently learning: " + ", ".join(l for l, _ in LEARNING))
    x = 6
    for label, icon in LEARNING:
        x += chip(svg, x, 10, label, icon, t, dashed=True) + 14
    write("learning", theme, svg)


# --- Botón del portafolio ----------------------------------------------------
def build_button(theme):
    t = THEMES[theme]
    label, fs = "Visit my portfolio", 18
    tw = text_width("sansbold", label, fs)
    w, h = tw + 80, 56
    svg = Svg(int(w + 20), int(h + 20), "Visit my portfolio — jefferson-panchi.vercel.app")
    # Botón invertido: la sombra va en gris para que no se funda con el relleno
    block(svg, 6, 6, w, h, 12, t, fill=t["fg"], off=6, shadow=t["muted"])
    svg.text(31, 6 + h / 2 + fs * 0.36, label, "sansbold", fs, t["bg"])
    svg.add(stroke_icon(EXTERNAL, 31 + tw + 12, 6 + h / 2 - 9, 18, t["bg"]))
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
