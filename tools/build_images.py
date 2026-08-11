#!/usr/bin/env python3
"""Build the site's illustrations.

Every picture on the site is a flat, layered SVG drawn in the brand palette —
a relief-print reading of the places Fako Journeys actually goes. This script
is the source: it writes each scene into ../images/. The site itself does not
need it; nothing here runs at deploy time.

    python3 tools/build_images.py

Scenes are composed 3:2 and centre-weighted, because the page crops them to
3/4, 4/5, 5/4 and 1/1 with object-fit: cover. Keep the subject inside
x = 400..1200 and it survives every crop.
"""

import math
import os
import random

W, H = 1600, 1067
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images")

# ---- palette ------------------------------------------------------------------
# The five brand tokens, and nothing else. Every other colour in the file is one
# of these mixed towards another, which is what keeps 27 drawings looking like
# one set.
PAPER = (0xF7, 0xF2, 0xE7)
BASALT = (0x1C, 0x2A, 0x25)
LATERITE = (0xBE, 0x55, 0x27)
INK = (0x1F, 0x21, 0x1C)
MUTED = (0x6E, 0x71, 0x66)


def mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hexc(c):
    return "#%02X%02X%02X" % c


def tone(t, warm=0.0, base=PAPER):
    """Atmospheric depth: t=0 is the far haze, t=1 the nearest ground.

    Past 0.72 the ramp keeps going past basalt towards ink, because a relief
    print needs a genuinely dark register to silhouette against — a scale that
    stops at #1C2A25 turns every foreground into the same mid-grey.
    """
    c = mix(base, BASALT, min(1.0, t))
    if t > 0.72:
        c = mix(c, (0x0B, 0x0E, 0x0C), (t - 0.72) / 0.28 * 0.6)
    if warm:
        c = mix(c, LATERITE, warm)
    return hexc(c)


def pale(t, warm=0.0):
    return hexc(mix(PAPER, mix(BASALT, LATERITE, warm), t))


# ---- svg plumbing -------------------------------------------------------------


class Scene:
    def __init__(self, name, title, seed=0):
        self.name = name
        self.title = title
        self.rnd = random.Random(seed if seed else sum(map(ord, name)))
        self.defs = []
        self.body = []

    def add(self, s):
        self.body.append(s)

    def define(self, s):
        self.defs.append(s)

    def render(self):
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-label="%s">\n'
            "<title>%s</title>\n<defs>\n%s\n</defs>\n%s\n</svg>\n"
            % (
                W,
                H,
                W,
                H,
                esc(self.title),
                esc(self.title),
                "\n".join(self.defs),
                "\n".join(self.body),
            )
        )


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def pts(points):
    return " ".join("%.1f,%.1f" % (x, y) for x, y in points)


# ---- ground and sky -----------------------------------------------------------


def sky(s, top, bottom, name=None):
    gid = "sky_%s" % (name or s.name.replace("-", "_"))
    s.define(
        '<linearGradient id="%s" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
        "</linearGradient>" % (gid, top, bottom)
    )
    s.add('<rect width="%d" height="%d" fill="url(#%s)"/>' % (W, H, gid))


def sun(s, cx, cy, r, color, glow=None, rings=3):
    if glow:
        for i in range(rings, 0, -1):
            s.add(
                '<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s" opacity="%.3f"/>'
                % (cx, cy, r * (1 + i * 0.85), glow, 0.055 + 0.02 * (rings - i))
            )
    s.add('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="%s"/>' % (cx, cy, r, color))


def band(s, y0, y1, color, opacity=1.0):
    s.add(
        '<rect x="0" y="%.1f" width="%d" height="%.1f" fill="%s" opacity="%.3f"/>'
        % (y0, W, y1 - y0, color, opacity)
    )


def ridge(s, y, amp, color, seed=None, roughness=0.55, steps=13, x0=-40, x1=W + 40, opacity=1.0):
    """A soft rolling ridge filled to the bottom of the frame."""
    rnd = random.Random(seed) if seed is not None else s.rnd
    p = []
    n = steps
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        wave = math.sin(i * 0.9 + rnd.random() * 0.4) * amp
        p.append((x, y + wave * roughness + rnd.uniform(-amp * 0.22, amp * 0.22)))
    d = "M %.1f,%.1f " % p[0]
    for i in range(1, len(p)):
        px, py = p[i - 1]
        x, yy = p[i]
        d += "C %.1f,%.1f %.1f,%.1f %.1f,%.1f " % (px + (x - px) / 2, py, px + (x - px) / 2, yy, x, yy)
    d += "L %d,%d L %d,%d Z" % (x1, H + 10, x0, H + 10)
    s.add('<path d="%s" fill="%s" opacity="%.3f"/>' % (d, color, opacity))


def peaks(s, points, color, opacity=1.0):
    """An angular skyline: explicit points, closed to the bottom of the frame."""
    p = list(points)
    p = [(-40, p[0][1])] + p + [(W + 40, p[-1][1]), (W + 40, H + 10), (-40, H + 10)]
    s.add('<polygon points="%s" fill="%s" opacity="%.3f"/>' % (pts(p), color, opacity))


def cone(s, cx, base_y, height, half, color, notch=0.0, opacity=1.0):
    """A volcanic cone — Fako's own shape, used at every scale."""
    top = base_y - height
    p = [(cx - half, base_y), (cx - half * 0.30, top + height * 0.10), (cx - half * 0.10, top)]
    if notch:
        p += [(cx, top + height * notch), (cx + half * 0.10, top)]
    else:
        p += [(cx + half * 0.08, top)]
    p += [(cx + half * 0.34, top + height * 0.11), (cx + half, base_y)]
    s.add('<polygon points="%s" fill="%s" opacity="%.3f"/>' % (pts(p), color, opacity))


def water(s, y0, y1, color, glint=None, seed=1, rows=9, cx=None):
    band(s, y0, y1, color)
    if glint:
        rnd = random.Random(seed)
        for i in range(rows):
            y = y0 + (y1 - y0) * (i + 0.5) / rows
            w = 60 + rnd.random() * 260
            x = (cx if cx else W / 2) - w / 2 + rnd.uniform(-420, 420)
            s.add(
                '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s" opacity="%.2f" rx="3"/>'
                % (x, y, w, 3 + rnd.random() * 3, glint, 0.10 + rnd.random() * 0.28)
            )


def surf(s, y, color, seed=2, count=7):
    rnd = random.Random(seed)
    for i in range(count):
        yy = y - i * 16 - rnd.uniform(0, 8)
        w = W * (0.5 + rnd.random() * 0.6)
        x = W / 2 - w / 2 + rnd.uniform(-160, 160)
        s.add(
            '<path d="M %.0f,%.0f q %.0f,%.0f %.0f,0" fill="none" stroke="%s" '
            'stroke-width="%.1f" opacity="%.2f" stroke-linecap="round"/>'
            % (x, yy, w / 2, -10 - rnd.random() * 14, w, color, 3 + rnd.random() * 4, 0.22 + rnd.random() * 0.4)
        )


def hatch(s, x, y, w, h, color, gap=9, angle=0, opacity=0.18, width=2.0):
    gid = "h%d" % (abs(hash((x, y, w, h, color, gap, angle))) % 100000)
    s.define(
        '<pattern id="%s" width="%d" height="%d" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(%d)"><line x1="0" y1="0" x2="0" y2="%d" '
        'stroke="%s" stroke-width="%.1f"/></pattern>' % (gid, gap, gap, angle, gap, color, width)
    )
    s.add(
        '<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="url(#%s)" opacity="%.2f"/>'
        % (x, y, w, h, gid, opacity)
    )


def grain(s, opacity=0.30):
    """Riso-ish tooth over the whole frame — it is what stops the flats looking like clip art."""
    gid = "grain_%s" % s.name.replace("-", "_").replace(".", "_")
    rnd = random.Random(7)
    dots = "".join(
        '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>'
        % (rnd.uniform(0, 90), rnd.uniform(0, 90), 0.7 + rnd.random() * 1.1, hexc(BASALT))
        for _ in range(150)
    )
    s.define('<pattern id="%s" width="90" height="90" patternUnits="userSpaceOnUse">%s</pattern>' % (gid, dots))
    s.add('<rect width="%d" height="%d" fill="url(#%s)" opacity="%.2f"/>' % (W, H, gid, opacity))
    s.add(
        '<rect width="%d" height="%d" fill="none" stroke="%s" stroke-width="0" />' % (W, H, hexc(INK))
    )


def vignette(s, strength=0.20):
    gid = "vig_%s" % s.name.replace("-", "_").replace(".", "_")
    s.define(
        '<radialGradient id="%s" cx="0.5" cy="0.48" r="0.78">'
        '<stop offset="0.55" stop-color="%s" stop-opacity="0"/>'
        '<stop offset="1" stop-color="%s" stop-opacity="%.2f"/></radialGradient>'
        % (gid, hexc(BASALT), hexc(BASALT), strength)
    )
    s.add('<rect width="%d" height="%d" fill="url(#%s)"/>' % (W, H, gid))


# ---- vegetation ---------------------------------------------------------------


def broadleaf(s, x, base, h, color, seed=0):
    rnd = random.Random(seed or int(x + base))
    w = h * (0.62 + rnd.random() * 0.3)
    s.add(
        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
        % (x - h * 0.035, base - h * 0.45, max(2.0, h * 0.07), h * 0.45, color)
    )
    cy = base - h * 0.62
    for i in range(5):
        s.add(
            '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
            % (
                x + rnd.uniform(-w * 0.34, w * 0.34),
                cy + rnd.uniform(-h * 0.16, h * 0.12),
                w * (0.30 + rnd.random() * 0.22),
                h * (0.16 + rnd.random() * 0.12),
                color,
            )
        )


def palm(s, x, base, h, color, lean=0.0):
    s.add(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" '
        'fill="none" stroke-linecap="round"/>'
        % (x, base, h * 0.10 + lean * h * 0.2, -h * 0.5, h * 0.16 + lean * h * 0.35, -h, color, max(2.5, h * 0.045))
    )
    tx, ty = x + h * 0.16 + lean * h * 0.35, base - h
    for a in (-168, -128, -90, -52, -12, 20, 200):
        r = math.radians(a)
        ex, ey = tx + math.cos(r) * h * 0.44, ty + math.sin(r) * h * 0.30
        s.add(
            '<path d="M %.1f,%.1f Q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" '
            'fill="none" stroke-linecap="round"/>'
            % (tx, ty, (tx + ex) / 2, (ty + ey) / 2 - h * 0.16, ex, ey, color, max(2.0, h * 0.038))
        )


def acacia(s, x, base, h, color):
    s.add(
        '<path d="M %.1f,%.1f L %.1f,%.1f M %.1f,%.1f l %.1f,%.1f M %.1f,%.1f l %.1f,%.1f" '
        'stroke="%s" stroke-width="%.1f" fill="none" stroke-linecap="round"/>'
        % (
            x, base, x, base - h * 0.55,
            x, base - h * 0.5, -h * 0.20, -h * 0.18,
            x, base - h * 0.5, h * 0.20, -h * 0.18,
            color, max(2.0, h * 0.05),
        )
    )
    s.add(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,0 q %.1f,%.1f %.1f,0 Z" fill="%s"/>'
        % (
            x - h * 0.52, base - h * 0.70,
            h * 0.26, -h * 0.26, h * 0.52,
            h * 0.26, h * 0.02, h * 0.52,
            color,
        )
    )
    s.add(
        '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
        % (x, base - h * 0.74, h * 0.50, h * 0.11, color)
    )


def canopy(s, y, color, seed=3, count=26, scale=1.0, x0=-40, x1=W + 40, jitter=26):
    rnd = random.Random(seed)
    for i in range(count):
        x = x0 + (x1 - x0) * i / max(1, count - 1) + rnd.uniform(-jitter, jitter)
        r = (34 + rnd.random() * 40) * scale
        s.add(
            '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
            % (x, y + rnd.uniform(-14, 12) * scale, r, r * (0.62 + rnd.random() * 0.3), color)
        )
    s.add(
        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
        % (x0, y, x1 - x0, H - y + 10, color)
    )


def grass(s, y, color, seed=4, count=90, h=22, x0=0, x1=W):
    rnd = random.Random(seed)
    for _ in range(count):
        x = rnd.uniform(x0, x1)
        hh = h * (0.5 + rnd.random())
        s.add(
            '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" '
            'fill="none" opacity="%.2f" stroke-linecap="round"/>'
            % (x, y + rnd.uniform(-6, 10), rnd.uniform(-6, 6), -hh * 0.6, rnd.uniform(-10, 10), -hh,
               color, 1.4 + rnd.random() * 1.6, 0.35 + rnd.random() * 0.45)
        )


# ---- figures ------------------------------------------------------------------


def figure(s, x, base, h, color, pack=False, facing=1, stride=0.30, arm=0.5, hat=False, pole=False):
    """A walker. Small, silhouetted, never detailed enough to pretend to be a photograph."""
    g = []
    head_r = h * 0.082
    head_y = base - h * 0.905
    g.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, head_y, head_r, color))
    if hat:
        g.append(
            '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,0 Z" fill="%s"/>'
            % (x - head_r * 1.35, head_y - head_r * 0.40, head_r * 1.35, -head_r * 1.9, head_r * 2.7, color)
        )
    sh_y = base - h * 0.80
    hip_y = base - h * 0.46
    g.append(
        '<polygon points="%s" fill="%s"/>'
        % (pts([(x - h * 0.088, sh_y), (x + h * 0.088, sh_y), (x + h * 0.070, hip_y), (x - h * 0.070, hip_y)]), color)
    )
    if pack:
        g.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>'
            % (x - facing * h * 0.155, sh_y - h * 0.03, h * 0.11, h * 0.30, h * 0.03, color)
        )
    lg = h * 0.46
    for d in (-1, 1):
        fx = x + d * lg * stride * 0.5
        g.append(
            '<path d="M %.1f,%.1f L %.1f,%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>'
            % (x, hip_y - h * 0.02, fx, base, color, h * 0.062)
        )
    ax = x + facing * h * 0.09 * arm
    g.append(
        '<path d="M %.1f,%.1f L %.1f,%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>'
        % (x - facing * h * 0.02, sh_y + h * 0.02, ax, base - h * 0.50, color, h * 0.05)
    )
    if pole:
        g.append(
            '<path d="M %.1f,%.1f L %.1f,%.1f" stroke="%s" stroke-width="%.1f" stroke-linecap="round" opacity="0.85"/>'
            % (ax, base - h * 0.52, ax + facing * h * 0.06, base + h * 0.02, color, h * 0.022)
        )
    s.add("<g>%s</g>" % "".join(g))


def figure_line(s, x0, base_y, count, h, color, gap=44, drop=0.0, seed=5, facing=1):
    rnd = random.Random(seed)
    for i in range(count):
        x = x0 + i * gap + rnd.uniform(-6, 6)
        y = base_y + i * drop
        figure(
            s, x, y, h * (0.94 + rnd.random() * 0.12), color,
            pack=(i % 2 == 0), facing=facing, stride=0.24 + rnd.random() * 0.22,
            pole=(i % 3 == 0), hat=(i % 4 == 1),
        )


def elephant(s, x, base, h, color, facing=-1):
    """h is shoulder height. Legs are long and separated — at thumbnail size a
    short-legged elephant is just a dark blob."""
    body_top = base - h
    g = []
    for d in (-0.34, -0.16, 0.20, 0.38):
        g.append(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>'
            % (x + d * h, base - h * 0.52, h * 0.14, h * 0.52, h * 0.03, color)
        )
    g.append(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,0 l 0,%.1f q %.1f,%.1f %.1f,0 Z" fill="%s"/>'
        % (x - h * 0.50, base - h * 0.46, h * 0.50, -h * 0.62, h * 1.00, h * 0.20,
           -h * 0.50, h * 0.14, -h * 1.00, color)
    )
    hx = x + facing * h * 0.60
    g.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s"/>'
             % (hx, base - h * 0.80, h * 0.22, h * 0.24, color))
    # ear
    g.append('<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f q %.1f,%.1f %.1f,%.1f Z" fill="%s"/>'
             % (hx - facing * h * 0.10, base - h * 1.00, -facing * h * 0.34, h * 0.06,
                -facing * h * 0.24, h * 0.40, facing * h * 0.16, h * 0.06, facing * h * 0.08, -h * 0.46, color))
    # trunk
    g.append(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" '
        'fill="none" stroke-linecap="round"/>'
        % (hx + facing * h * 0.16, base - h * 0.78, facing * h * 0.20, -h * 0.06,
           facing * h * 0.14, h * 0.66, color, h * 0.095)
    )
    # tusk
    g.append(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" '
        'fill="none" stroke-linecap="round" opacity="0.55"/>'
        % (hx + facing * h * 0.08, base - h * 0.70, facing * h * 0.14, h * 0.12,
           facing * h * 0.22, h * 0.16, hexc(PAPER), h * 0.045)
    )
    g.append(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,%.1f" stroke="%s" stroke-width="%.1f" fill="none" stroke-linecap="round"/>'
        % (x - facing * h * 0.50, base - h * 0.92, -facing * h * 0.12, h * 0.14,
           -facing * h * 0.02, h * 0.30, color, h * 0.035)
    )
    s.add("<g>%s</g>" % "".join(g))


def bird(s, x, y, w, color, opacity=0.55):
    s.add(
        '<path d="M %.1f,%.1f q %.1f,%.1f %.1f,0 q %.1f,%.1f %.1f,0" fill="none" stroke="%s" '
        'stroke-width="%.1f" opacity="%.2f" stroke-linecap="round"/>'
        % (x - w, y, w * 0.5, -w * 0.55, w, w * 0.5, w * 0.55, w, color, max(1.6, w * 0.10), opacity)
    )


def birds(s, cx, cy, n, color, seed=6, spread=260):
    rnd = random.Random(seed)
    for _ in range(n):
        bird(s, cx + rnd.uniform(-spread, spread), cy + rnd.uniform(-spread * 0.35, spread * 0.35),
             8 + rnd.random() * 10, color, 0.3 + rnd.random() * 0.35)


# ---- built things -------------------------------------------------------------


def hut(s, x, base, w, h, wall, roof, conical=True, door=None):
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x - w / 2, base - h, w, h, wall))
    if conical:
        s.add(
            '<polygon points="%s" fill="%s"/>'
            % (pts([(x - w * 0.66, base - h), (x, base - h - h * 0.95), (x + w * 0.66, base - h)]), roof)
        )
    else:
        s.add(
            '<polygon points="%s" fill="%s"/>'
            % (pts([(x - w * 0.60, base - h), (x - w * 0.42, base - h - h * 0.42),
                    (x + w * 0.42, base - h - h * 0.42), (x + w * 0.60, base - h)]), roof)
        )
    if door:
        s.add(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
            % (x - w * 0.12, base - h * 0.55, w * 0.24, h * 0.55, door)
        )


def shopfront(s, x, base, w, h, wall, trim, sign=None, awning=None, panes=3):
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x, base - h, w, h, wall))
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x, base - h, w, h * 0.07, trim))
    gw = w / (panes + 0.6)
    for i in range(panes):
        s.add(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.9"/>'
            % (x + w * 0.06 + i * gw * 1.05, base - h * 0.62, gw * 0.82, h * 0.40, trim)
        )
    if sign:
        s.add(
            '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
            % (x + w * 0.10, base - h * 0.92, w * 0.80, h * 0.17, sign)
        )
    if awning:
        s.add(
            '<polygon points="%s" fill="%s"/>'
            % (pts([(x, base - h * 0.70), (x + w, base - h * 0.70),
                    (x + w * 0.92, base - h * 0.46), (x + w * 0.08, base - h * 0.46)]), awning)
        )


def vehicle(s, x, base, w, color, glass, facing=1, roofrack=True):
    """A long-wheelbase 4x4 in profile — the thing every one of these circuits runs on."""
    wr = w * 0.085                       # wheel radius
    body_h = w * 0.20
    body_y = base - wr * 1.35 - body_h
    cab_h = w * 0.16
    cab_y = body_y - cab_h
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>'
          % (x - w / 2, body_y, w, body_h + wr * 0.6, w * 0.02, color))
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>'
          % (x - w * 0.40, cab_y, w * 0.78, cab_h + w * 0.02, w * 0.02, color))
    for gx, gw in ((-0.355, 0.30), (-0.035, 0.20), (0.185, 0.18)):
        s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.8"/>'
              % (x + gx * w, cab_y + cab_h * 0.16, gw * w, cab_h * 0.64, glass))
    if roofrack:
        s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s"/>'
              % (x - w * 0.42, cab_y - w * 0.055, w * 0.82, w * 0.05, w * 0.012, color))
        for i in range(5):
            s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" opacity="0.55"/>'
                  % (x - w * 0.40 + i * w * 0.19, cab_y - w * 0.05, w * 0.012, w * 0.05, glass))
    for d in (-0.315, 0.315):
        s.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x + d * w, base - wr, wr, color))
        s.add('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" opacity="0.45"/>'
              % (x + d * w, base - wr, wr * 0.42, glass))


def post(s, x, base, h, color, w=6):
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x - w / 2, base - h, w, h, color))


def signboard(s, x, base, w, h, post_h, frame, face, rules=3):
    post(s, x - w * 0.32, base, post_h, frame, 8)
    post(s, x + w * 0.32, base, post_h, frame, 8)
    y = base - post_h
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (x - w / 2, y, w, h, face))
    s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s" stroke-width="5"/>'
          % (x - w / 2, y, w, h, frame))
    for i in range(rules):
        s.add('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="%s" opacity="0.8"/>'
              % (x - w * 0.36, y + h * (0.24 + i * 0.22), w * (0.72 if i else 0.5), frame))


# =================================================================================
#  Scenes
# =================================================================================

SCENES = {}


def scene(name, title):
    def deco(fn):
        SCENES[name] = (fn, title)
        return fn

    return deco


# ---- Mount Cameroon ------------------------------------------------------------


@scene("mount-ascent-walkers", "Walkers on the open upper slopes of Mount Cameroon above the tree line")
def _(s):
    sky(s, pale(0.10, 0.05), pale(0.28, 0.30))
    sun(s, 1180, 300, 54, pale(0.06, 0.55), glow=hexc(LATERITE))
    band(s, 470, 500, pale(0.20, 0.18), 0.5)
    ridge(s, 520, 40, tone(0.20, 0.10), seed=11)
    ridge(s, 610, 52, tone(0.34, 0.06), seed=12)
    canopy(s, 720, tone(0.46), seed=13, count=22, scale=0.9)
    peaks(s, [(200, 760), (520, 700), (900, 742), (1300, 690), (1600, 730)], tone(0.60, 0.05))
    peaks(s, [(0, 940), (330, 860), (700, 880), (1100, 830), (1600, 900)], tone(0.78, 0.04))
    hatch(s, 0, 830, W, H - 830, hexc(PAPER), gap=11, angle=-18, opacity=0.10)
    grass(s, 980, tone(0.55, 0.10), seed=14, count=70, h=26)
    figure_line(s, 560, 900, 5, 150, tone(0.94), gap=92, drop=-16, seed=15, facing=1)
    figure(s, 1080, 858, 138, tone(0.90), pack=True, facing=1, pole=True, hat=True)
    birds(s, 420, 250, 4, tone(0.45), seed=16)
    vignette(s, 0.18)
    grain(s, 0.26)


@scene("mount-dawn-cinder", "The upper cinder slopes of Mount Cameroon at dawn with the Atlantic far below")
def _(s):
    sky(s, pale(0.34, 0.12), pale(0.10, 0.62))
    sun(s, 1080, 470, 66, pale(0.02, 0.78), glow=hexc(LATERITE), rings=4)
    band(s, 470, 486, pale(0.26, 0.55), 0.55)
    water(s, 486, 560, tone(0.30, 0.16), glint=pale(0.05, 0.35), seed=21, rows=6, cx=1080)
    band(s, 552, 600, tone(0.24, 0.22), 0.7)
    ridge(s, 600, 34, tone(0.42, 0.16), seed=22)
    peaks(s, [(120, 700), (430, 628), (760, 668), (1120, 610), (1600, 656)], tone(0.58, 0.12))
    peaks(s, [(0, 880), (300, 782), (620, 812), (1000, 748), (1380, 800), (1600, 860)], tone(0.80, 0.06))
    peaks(s, [(0, 1010), (420, 930), (860, 960), (1240, 900), (1600, 970)], tone(0.94))
    hatch(s, 0, 890, W, H - 890, hexc(LATERITE), gap=14, angle=-24, opacity=0.10)
    figure(s, 690, 1000, 190, tone(0.98), pack=True, facing=1, pole=True)
    figure(s, 830, 972, 176, tone(0.98), pack=True, facing=1, hat=True)
    vignette(s, 0.26)
    grain(s, 0.28)


@scene("mount-summit-grass", "Walkers crossing the grass slopes below the summit huts on Mount Cameroon")
def _(s):
    sky(s, pale(0.12, 0.02), pale(0.24, 0.14))
    band(s, 300, 420, pale(0.16, 0.04), 0.55)
    cone(s, 1180, 620, 330, 420, tone(0.30, 0.05), notch=0.05)
    ridge(s, 640, 46, tone(0.40, 0.03), seed=31)
    ridge(s, 740, 40, tone(0.52, 0.05), seed=32)
    band(s, 812, H, tone(0.64, 0.10))
    hatch(s, 0, 812, W, H - 812, hexc(PAPER), gap=10, angle=-14, opacity=0.14)
    grass(s, 880, tone(0.50, 0.16), seed=33, count=110, h=30)
    hut(s, 1235, 812, 96, 46, tone(0.80), hexc(LATERITE), conical=False, door=tone(0.95))
    hut(s, 1330, 806, 70, 36, tone(0.84), tone(0.70, 0.25), conical=False)
    figure_line(s, 480, 930, 4, 168, tone(0.92), gap=104, drop=-14, seed=34)
    grass(s, 1030, tone(0.62, 0.14), seed=35, count=60, h=40)
    vignette(s, 0.16)
    grain(s, 0.26)


@scene("mount-dry-season", "Dry-season light on the open upper slopes of Mount Cameroon")
def _(s):
    sky(s, pale(0.06, 0.03), pale(0.22, 0.22))
    sun(s, 520, 250, 46, pale(0.04, 0.5), glow=hexc(LATERITE))
    ridge(s, 560, 30, tone(0.18, 0.08), seed=41)
    ridge(s, 660, 44, tone(0.30, 0.06), seed=42)
    peaks(s, [(150, 800), (560, 726), (980, 764), (1340, 706), (1600, 750)], tone(0.52, 0.08))
    peaks(s, [(0, 960), (380, 880), (820, 906), (1220, 852), (1600, 916)], tone(0.76, 0.10))
    hatch(s, 0, 850, W, H - 850, hexc(PAPER), gap=9, angle=-20, opacity=0.16)
    grass(s, 1000, tone(0.66, 0.18), seed=43, count=120, h=34)
    # a cairn on the near shoulder, and two walkers a long way off
    for i, (x, y, r) in enumerate([(560, 1010, 46), (566, 962, 36), (572, 924, 27), (576, 896, 19)]):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s"/>' % (x, y, r, r * 0.62, tone(0.94, 0.04)))
    figure(s, 1090, 900, 74, tone(0.86), pack=True, facing=1)
    figure(s, 1140, 896, 70, tone(0.86), facing=1, hat=True)
    birds(s, 1180, 330, 5, tone(0.44), seed=44)
    vignette(s, 0.14)
    grain(s, 0.24)


@scene("mount-guide-portrait", "A mountain guide on the upper slopes at first light")
def _(s):
    sky(s, pale(0.26, 0.14), pale(0.08, 0.42))
    sun(s, 430, 360, 58, pale(0.02, 0.7), glow=hexc(LATERITE), rings=4)
    ridge(s, 560, 36, tone(0.26, 0.14), seed=51)
    ridge(s, 690, 44, tone(0.42, 0.10), seed=52)
    peaks(s, [(0, 900), (340, 820), (760, 856), (1180, 800), (1600, 860)], tone(0.62, 0.08))
    hatch(s, 0, 800, W, H - 800, hexc(LATERITE), gap=12, angle=-22, opacity=0.10)
    band(s, 980, H, tone(0.82, 0.05))
    # the guide — the same walker vocabulary as every other scene, just close up
    figure(s, 780, 1050, 430, tone(0.96), pack=True, facing=1, stride=0.20, arm=0.7, hat=True, pole=True)
    # a second, further down the slope
    figure(s, 1090, 962, 250, tone(0.86), pack=True, facing=1, stride=0.26)
    vignette(s, 0.22)
    grain(s, 0.28)


@scene("mount-lava-flow", "Lava flow country on the lower flank of Mount Cameroon near the coast")
def _(s):
    sky(s, pale(0.06, 0.08), pale(0.24, 0.30))
    cone(s, 700, 600, 400, 580, tone(0.30, 0.06), notch=0.04)
    ridge(s, 620, 24, tone(0.40, 0.04), seed=61)
    water(s, 656, 730, tone(0.42, 0.14), glint=pale(0.05, 0.28), seed=62, rows=6)
    # the shore, then the flow: black lava fingers reaching the water
    band(s, 700, H, tone(0.52, 0.22))
    hatch(s, 0, 700, W, H - 700, hexc(PAPER), gap=12, angle=-8, opacity=0.12)
    # the flow reads as stacked lobes, not fingers: black rock spilling downhill
    # in overlapping tongues, each one a little darker than the last
    lobes = [
        (0.72, 720, [(-60, 60), (240, 20), (620, 46), (1020, 14), (1400, 52), (1660, 20)]),
        (0.82, 800, [(-60, 40), (300, 74), (700, 30), (1080, 70), (1480, 26), (1660, 58)]),
        (0.90, 890, [(-60, 66), (260, 22), (640, 72), (1060, 28), (1420, 74), (1660, 34)]),
        (0.97, 990, [(-60, 26), (340, 66), (780, 22), (1180, 62), (1660, 30)]),
    ]
    for t, y, ctrl in lobes:
        d = "M %d,%d " % (ctrl[0][0], y + ctrl[0][1])
        for i in range(1, len(ctrl)):
            px, po = ctrl[i - 1]
            cx_, co = ctrl[i]
            d += "C %.0f,%.0f %.0f,%.0f %.0f,%.0f " % (
                px + (cx_ - px) * 0.4, y + po - 34, px + (cx_ - px) * 0.6, y + co + 30, cx_, y + co)
        d += "L %d,%d L %d,%d Z" % (W + 60, H + 10, -60, H + 10)
        s.add('<path d="%s" fill="%s"/>' % (d, tone(t, 0.05)))
    hatch(s, 0, 700, W, H - 700, hexc(PAPER), gap=15, angle=-72, opacity=0.07)
    for x, y in [(380, 906), (1010, 966), (1280, 886), (700, 1020)]:
        s.add('<ellipse cx="%d" cy="%d" rx="86" ry="22" fill="%s" opacity="0.30"/>' % (x, y, tone(0.55, 0.36)))
    # young growth taking hold in the cracks
    for x, b, h in [(330, 880, 96), (1260, 940, 110), (700, 1010, 120), (1520, 900, 90)]:
        broadleaf(s, x, b, h, tone(0.66, 0.10), seed=x)
    for i, (cy, r) in enumerate([(196, 46), (150, 34), (112, 24)]):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s" opacity="%.2f"/>'
              % (706 + i * 26, cy, r, r * 0.72, pale(0.20), 0.42 - i * 0.10))
    vignette(s, 0.20)
    grain(s, 0.26)


@scene("mount-trailhead-dawn", "Guides and porters gathered at a trailhead registration point in Buea at dawn")
def _(s):
    sky(s, pale(0.30, 0.16), pale(0.08, 0.40))
    sun(s, 1260, 330, 48, pale(0.02, 0.72), glow=hexc(LATERITE))
    cone(s, 520, 640, 300, 380, tone(0.26, 0.08), notch=0.05)
    ridge(s, 660, 30, tone(0.36, 0.06), seed=71)
    canopy(s, 760, tone(0.50, 0.03), seed=72, count=20, scale=0.8)
    band(s, 860, H, tone(0.66, 0.14))
    hatch(s, 0, 860, W, H - 860, hexc(LATERITE), gap=10, angle=0, opacity=0.10)
    # registration shelter
    s.add('<rect x="980" y="700" width="330" height="164" fill="%s"/>' % tone(0.78))
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(950, 700), (1145, 636), (1340, 700)]), tone(0.62, 0.30)))
    s.add('<rect x="1030" y="746" width="100" height="80" fill="%s" opacity="0.8"/>' % pale(0.18, 0.2))
    signboard(s, 1420, 860, 170, 110, 120, tone(0.86), pale(0.10, 0.10))
    figure(s, 1090, 860, 150, tone(0.92), facing=-1, stride=0.06, arm=0.2)
    figure_line(s, 470, 900, 4, 156, tone(0.94), gap=86, seed=73, facing=1)
    figure(s, 840, 906, 162, tone(0.92), pack=True, facing=-1, stride=0.10, hat=True)
    # packs on the ground
    for x, y, w in [(690, 930, 62), (760, 946, 54)]:
        s.add('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="%s"/>'
              % (x, y, w, int(w * 1.1), tone(0.86)))
    vignette(s, 0.22)
    grain(s, 0.28)


@scene("mount-wet-cloud", "Cloud and rain sitting on the rainforest above Buea in the wet season")
def _(s):
    sky(s, pale(0.20, 0.02), pale(0.06, 0.03))
    for i, y in enumerate([170, 250, 330, 410]):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s" opacity="%.2f"/>'
              % (740 + (i - 1) * 130, y, 700 - i * 70, 84 - i * 10, hexc(PAPER), 0.62 - i * 0.08))
    ridge(s, 470, 24, tone(0.30), seed=81)
    band(s, 450, 560, hexc(PAPER), 0.42)
    ridge(s, 590, 32, tone(0.46), seed=82)
    band(s, 560, 690, hexc(PAPER), 0.34)
    ridge(s, 700, 30, tone(0.60), seed=85)
    band(s, 680, 780, hexc(PAPER), 0.22)
    canopy(s, 790, tone(0.74), seed=83, count=24, scale=1.0)
    canopy(s, 930, tone(0.90), seed=84, count=18, scale=1.35)
    for x, b, h in [(250, 1010, 230), (1330, 1050, 250), (800, 1067, 270)]:
        broadleaf(s, x, b, h, tone(0.97), seed=x)
    rnd = random.Random(9)
    for _ in range(170):
        x, y = rnd.uniform(0, W), rnd.uniform(80, 940)
        ln = 30 + rnd.random() * 40
        s.add('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="1.8" opacity="%.2f"/>'
              % (x, y, x - ln * 0.22, y + ln, hexc(PAPER), 0.16 + rnd.random() * 0.26))
    vignette(s, 0.22)
    grain(s, 0.28)


@scene("mount-trail-repair", "Villagers and guides working on a repaired section of mountain trail")
def _(s):
    sky(s, pale(0.10, 0.03), pale(0.24, 0.16))
    ridge(s, 470, 34, tone(0.22, 0.06), seed=91)
    canopy(s, 600, tone(0.40), seed=92, count=20, scale=0.85)
    band(s, 700, H, tone(0.58, 0.12))
    # the trail: a laterite ribbon climbing away
    s.add('<path d="M 520,1067 q 120,-260 300,-330 q 130,-52 210,-64 L 1090,700 q -120,24 -250,84 '
          'q -200,92 -300,283 Z" fill="%s"/>' % pale(0.34, 0.62))
    hatch(s, 400, 700, 800, 367, hexc(LATERITE), gap=11, angle=-58, opacity=0.16)
    # stepped stonework
    for i in range(7):
        y = 1010 - i * 46
        w = 250 - i * 26
        x = 700 + i * 22
        s.add('<rect x="%.0f" y="%.0f" width="%.0f" height="14" rx="4" fill="%s" opacity="0.85"/>'
              % (x - w / 2, y, w, tone(0.74, 0.05)))
    figure(s, 640, 960, 158, tone(0.92), facing=1, stride=0.10, arm=0.9, pole=True)
    figure(s, 900, 880, 140, tone(0.90), facing=-1, stride=0.12, arm=0.8, hat=True)
    figure(s, 1080, 820, 124, tone(0.88), facing=-1, stride=0.06, arm=0.3, pack=True)
    grass(s, 780, tone(0.48, 0.10), seed=93, count=60, h=26, x0=1150, x1=1600)
    grass(s, 900, tone(0.52, 0.12), seed=94, count=60, h=30, x0=0, x1=520)
    vignette(s, 0.18)
    grain(s, 0.26)


# ---- the coast -----------------------------------------------------------------


@scene("coast-lobe-falls", "The Lobé falls pouring over rock directly into the Atlantic near Kribi")
def _(s):
    sky(s, pale(0.08, 0.06), pale(0.22, 0.24))
    band(s, 424, 446, pale(0.16, 0.12), 0.6)
    water(s, 446, 620, tone(0.30, 0.12), glint=pale(0.04, 0.22), seed=101, rows=5)
    # forest walls closing in from both sides
    canopy(s, 430, tone(0.62), seed=102, count=14, scale=1.0, x0=-40, x1=430)
    canopy(s, 440, tone(0.62), seed=103, count=14, scale=1.0, x0=1180, x1=W + 40)
    s.add('<rect x="-40" y="430" width="470" height="330" fill="%s"/>' % tone(0.62))
    s.add('<rect x="1180" y="440" width="460" height="320" fill="%s"/>' % tone(0.62))
    # the rock shelf the river runs off, and the dark gaps between the tongues
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(360, 596), (1250, 588), (1290, 800), (330, 806)]), tone(0.86, 0.06)))
    hatch(s, 330, 588, 960, 220, hexc(PAPER), gap=13, angle=-80, opacity=0.10)
    # water arriving over the lip, then dropping in separate tongues
    band(s, 560, 600, pale(0.05), 0.9)
    for x0, w in [(392, 150), (582, 200), (824, 120), (976, 210)]:
        s.add('<path d="M %d,594 h %d l %d,196 q %d,20 %d,0 l %d,-196 Z" fill="%s"/>'
              % (x0, w, 16, -w * 0.18, -(w + 32), 16, pale(0.03)))
        hatch(s, x0 - 6, 594, w + 30, 196, hexc(BASALT), gap=11, angle=4, opacity=0.14)
    # foam pool
    water(s, 780, H, tone(0.48, 0.08), glint=pale(0.06), seed=105, rows=9)
    for x0, w in [(392, 150), (582, 200), (824, 120), (976, 210)]:
        s.add('<ellipse cx="%.0f" cy="798" rx="%.0f" ry="22" fill="%s" opacity="0.55"/>'
              % (x0 + w / 2, w * 0.60, pale(0.03)))
    surf(s, 900, pale(0.02), seed=104, count=9)
    for x, b, h in [(150, 780, 340), (1470, 800, 380)]:
        palm(s, x, b, h, tone(0.94), lean=0.22 if x < 800 else -0.22)
    birds(s, 1180, 280, 4, tone(0.44), seed=106)
    vignette(s, 0.20)
    grain(s, 0.26)


@scene("coast-black-sand-dusk", "Surf breaking on volcanic black sand at dusk on the Cameroon coast")
def _(s):
    sky(s, pale(0.36, 0.20), pale(0.06, 0.66))
    sun(s, 780, 430, 74, pale(0.02, 0.85), glow=hexc(LATERITE), rings=4)
    band(s, 455, 470, pale(0.24, 0.5), 0.6)
    water(s, 470, 720, tone(0.44, 0.16), glint=pale(0.06, 0.55), seed=111, rows=9, cx=780)
    # sun path on the water
    s.add('<polygon points="%s" fill="%s" opacity="0.30"/>'
          % (pts([(736, 470), (824, 470), (960, 760), (600, 760)]), pale(0.02, 0.8)))
    surf(s, 790, pale(0.04, 0.10), seed=112, count=9)
    band(s, 800, H, tone(0.88, 0.04))
    hatch(s, 0, 800, W, H - 800, hexc(LATERITE), gap=8, angle=-6, opacity=0.10)
    # wet sand reflecting the last of the light
    s.add('<path d="M 0,820 q 400,40 800,10 q 400,-30 800,20 L 1600,900 L 0,900 Z" fill="%s" opacity="0.5"/>'
          % pale(0.10, 0.45))
    palm(s, 210, 1010, 380, tone(0.96), lean=0.24)
    palm(s, 1430, 1050, 420, tone(0.96), lean=-0.20)
    birds(s, 1180, 320, 5, tone(0.55, 0.2), seed=113)
    vignette(s, 0.28)
    grain(s, 0.28)


@scene("douala-office-street", "A quiet office street in the Bonapriso quarter of Douala")
def _(s):
    sky(s, pale(0.08, 0.02), pale(0.20, 0.10))
    band(s, 0, 520, pale(0.12, 0.03), 0.4)
    # far buildings
    for x, w, h, t in [(60, 220, 300, 0.30), (300, 180, 250, 0.36), (1240, 240, 330, 0.32), (1480, 200, 280, 0.38)]:
        s.add('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x, 620 - h, w, h + 40, tone(t)))
    canopy(s, 560, tone(0.44), seed=121, count=10, scale=1.1, x0=380, x1=1240)
    # the street itself, receding
    band(s, 620, H, tone(0.60, 0.10))
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(740, 640), (880, 640), (1240, 1067), (330, 1067)]), tone(0.74, 0.14)))
    for i in range(5):
        y = 700 + i * i * 16 + i * 40
        s.add('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s" opacity="0.55"/>'
              % (790 - i * 12, y, 30 + i * 14, 8 + i * 3, pale(0.12)))
    # low office frontages, one each side
    shopfront(s, 250, 900, 430, 300, tone(0.72), tone(0.34, 0.05), sign=hexc(LATERITE), panes=3)
    shopfront(s, 1010, 830, 380, 230, tone(0.66), tone(0.30, 0.04), sign=tone(0.50, 0.30), panes=3)
    for x, b, h in [(620, 960, 300), (1330, 1000, 340)]:
        broadleaf(s, x, b, h, tone(0.82), seed=x)
    figure(s, 900, 940, 130, tone(0.86), facing=-1)
    vehicle(s, 1180, 1010, 240, tone(0.86), tone(0.48), roofrack=False)
    vignette(s, 0.20)
    grain(s, 0.26)


# ---- rainforest ----------------------------------------------------------------


@scene("forest-canopy-bridge", "A canopy suspension bridge crossing a river inside dense rainforest")
def _(s):
    sky(s, pale(0.20, 0.02), pale(0.34, 0.04))
    band(s, 0, 420, pale(0.16), 0.5)
    canopy(s, 330, tone(0.30), seed=131, count=18, scale=1.1)
    s.add('<rect x="-40" y="330" width="%d" height="200" fill="%s"/>' % (W + 80, tone(0.30)))
    # light shafts
    for x, w in [(520, 90), (760, 130), (1020, 80)]:
        s.add('<polygon points="%s" fill="%s" opacity="0.16"/>'
              % (pts([(x, 300), (x + w, 300), (x + w * 2.4, 1067), (x - w * 1.2, 1067)]), pale(0.02, 0.25)))
    # river below
    water(s, 800, H, tone(0.52, 0.04), glint=pale(0.14), seed=132, rows=7)
    canopy(s, 620, tone(0.58), seed=133, count=20, scale=1.2)
    s.add('<rect x="-40" y="620" width="%d" height="220" fill="%s"/>' % (W + 80, tone(0.58)))
    # trunks
    for x, w in [(180, 46), (1400, 54), (1150, 30), (420, 26)]:
        s.add('<rect x="%d" y="180" width="%d" height="890" fill="%s"/>' % (x, w, tone(0.86)))
    # the bridge
    col = tone(0.80)
    s.add('<path d="M 120,600 Q 800,760 1500,600" stroke="%s" stroke-width="9" fill="none"/>' % col)
    s.add('<path d="M 120,660 Q 800,822 1500,660" stroke="%s" stroke-width="14" fill="none"/>' % col)
    for i in range(23):
        t = i / 22
        x = 120 + (1500 - 120) * t
        y0 = 600 + (760 - 600) * (4 * t * (1 - t)) * 1.0
        y1 = 660 + (822 - 660) * (4 * t * (1 - t)) * 1.0
        s.add('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="%s" stroke-width="5" opacity="0.9"/>'
              % (x, y0, x, y1, col))
    figure(s, 800, 764, 128, tone(0.95), facing=1, pack=True, stride=0.20)
    figure(s, 930, 758, 120, tone(0.95), facing=1, stride=0.18, hat=True)
    vignette(s, 0.30)
    grain(s, 0.28)


@scene("forest-guide-tree", "A forest guide pointing out a tree species inside dense rainforest")
def _(s):
    sky(s, pale(0.22, 0.02), pale(0.34, 0.03))
    canopy(s, 200, tone(0.30), seed=141, count=16, scale=1.4)
    canopy(s, 400, tone(0.42), seed=142, count=18, scale=1.2)
    # one shaft of light coming through the gap, which is all you ever get down here
    s.add('<polygon points="%s" fill="%s" opacity="0.20"/>'
          % (pts([(430, 300), (520, 300), (700, 1067), (330, 1067)]), pale(0.02, 0.18)))
    canopy(s, 560, tone(0.56), seed=143, count=20, scale=1.0)
    # far trunks, thinning with depth
    for x, w, t in [(190, 30, 0.62), (1500, 34, 0.62), (660, 20, 0.58), (1260, 24, 0.60)]:
        s.add('<rect x="%d" y="300" width="%d" height="770" fill="%s"/>' % (x, w, tone(t)))
    # the tree in question: a buttressed hardwood, centre-right, lit down one edge
    t = tone(0.86)
    s.add('<path d="M 924,120 L 1014,120 L 1046,700 L 890,700 Z" fill="%s"/>' % t)
    s.add('<path d="M 938,214 C 892,190 846,150 806,86 l 30,-14 C 878,132 918,168 960,190 Z" fill="%s"/>' % t)
    s.add('<path d="M 1006,168 C 1058,146 1102,110 1140,56 l 28,20 C 1130,134 1082,176 1024,200 Z" fill="%s"/>' % t)
    s.add('<path d="M 1002,268 C 1046,254 1084,232 1120,196 l 22,20 C 1104,256 1058,286 1010,300 Z" fill="%s"/>' % t)
    s.add('<path d="M 890,700 C 884,830 840,930 726,1010 L 890,1010 Z" fill="%s"/>' % t)
    s.add('<path d="M 1046,700 C 1054,830 1100,930 1214,1010 L 1046,1010 Z" fill="%s"/>' % t)
    s.add('<path d="M 968,700 C 966,820 950,920 906,1010 L 1004,1010 Z" fill="%s"/>' % t)
    s.add('<path d="M 924,120 L 948,120 L 946,700 L 890,700 Z" fill="%s" opacity="0.26"/>' % hexc(PAPER))
    s.add('<path d="M 1004,700 C 1010,830 1050,930 1150,1010 L 1214,1010 C 1100,930 1054,830 1046,700 Z" '
          'fill="%s" opacity="0.30"/>' % hexc(BASALT))
    hatch(s, 890, 120, 156, 890, hexc(BASALT), gap=14, angle=0, opacity=0.14)
    # lianas
    for x0, x1, y in [(1046, 1300, 460), (890, 640, 380), (1046, 1180, 300)]:
        s.add('<path d="M %d,%d Q %d,%d %d,%d" stroke="%s" stroke-width="6" fill="none" opacity="0.7"/>'
              % (x0, y, (x0 + x1) / 2, y + 130, x1, y - 40, tone(0.70)))
    band(s, 960, H, tone(0.72))
    canopy(s, 1000, tone(0.84), seed=144, count=16, scale=0.8)
    figure(s, 660, 1030, 330, tone(0.97), facing=1, stride=0.14, arm=1.9, hat=True)
    figure(s, 470, 1040, 306, tone(0.93), facing=1, stride=0.08, arm=0.2, pack=True)
    figure(s, 330, 1030, 292, tone(0.90), facing=1, stride=0.10, arm=0.3)
    vignette(s, 0.30)
    grain(s, 0.28)


# ---- the Sahel and the north ---------------------------------------------------


@scene("waza-elephants", "Elephants at a dry-season waterhole in flat acacia savanna in northern Cameroon")
def _(s):
    sky(s, pale(0.06, 0.12), pale(0.20, 0.40))
    sun(s, 1210, 260, 62, pale(0.02, 0.62), glow=hexc(LATERITE), rings=4)
    band(s, 520, 545, pale(0.20, 0.30), 0.6)
    ridge(s, 560, 12, tone(0.24, 0.20), seed=151, roughness=0.3)
    band(s, 580, H, tone(0.42, 0.30))
    for x, b, h in [(140, 600, 190), (330, 606, 150), (1350, 604, 170), (1520, 598, 140), (760, 592, 120)]:
        acacia(s, x, b, h, tone(0.56, 0.10))
    # the waterhole, shrinking
    s.add('<ellipse cx="820" cy="880" rx="520" ry="150" fill="%s"/>' % tone(0.30, 0.14))
    s.add('<ellipse cx="820" cy="880" rx="520" ry="150" fill="none" stroke="%s" stroke-width="16" opacity="0.5"/>'
          % tone(0.60, 0.24))
    s.add('<ellipse cx="820" cy="886" rx="430" ry="112" fill="%s"/>' % tone(0.44, 0.06))
    water(s, 790, 900, tone(0.44, 0.06), glint=pale(0.08, 0.2), seed=152, rows=4, cx=820)
    hatch(s, 0, 600, W, 290, hexc(LATERITE), gap=14, angle=-4, opacity=0.10)
    elephant(s, 700, 764, 128, tone(0.84), facing=1)
    elephant(s, 940, 778, 150, tone(0.90), facing=-1)
    elephant(s, 1200, 758, 104, tone(0.74), facing=-1)
    elephant(s, 430, 752, 92, tone(0.70), facing=1)
    grass(s, 1010, tone(0.60, 0.22), seed=153, count=90, h=40)
    # one close enough to see the tusks on
    elephant(s, 620, 1055, 250, tone(0.97), facing=1)
    elephant(s, 1180, 1000, 176, tone(0.93), facing=-1)
    birds(s, 420, 330, 5, tone(0.36), seed=154)
    vignette(s, 0.18)
    grain(s, 0.26)


@scene("savanna-waterhole", "A shrinking waterhole in dry savanna under a hard dry-season sun")
def _(s):
    sky(s, pale(0.04, 0.10), pale(0.18, 0.44))
    sun(s, 800, 220, 70, pale(0.01, 0.55), glow=hexc(LATERITE), rings=5)
    band(s, 540, 566, pale(0.18, 0.34), 0.55)
    band(s, 566, H, tone(0.40, 0.34))
    for x, b, h in [(200, 590, 160), (1420, 586, 150), (1120, 582, 120), (420, 578, 100)]:
        acacia(s, x, b, h, tone(0.54, 0.12))
    s.add('<ellipse cx="800" cy="840" rx="470" ry="140" fill="%s"/>' % tone(0.56, 0.26))
    s.add('<ellipse cx="800" cy="850" rx="360" ry="102" fill="%s"/>' % tone(0.36, 0.16))
    water(s, 790, 900, tone(0.36, 0.12), glint=pale(0.06, 0.25), seed=161, rows=4, cx=800)
    # cracked mud at the margin
    rnd = random.Random(17)
    for _ in range(26):
        x, y = rnd.uniform(240, 1360), rnd.uniform(920, 1050)
        s.add('<path d="M %.0f,%.0f l %.0f,%.0f l %.0f,%.0f" stroke="%s" stroke-width="2.4" '
              'fill="none" opacity="0.35"/>'
              % (x, y, rnd.uniform(-60, 60), rnd.uniform(-14, 14), rnd.uniform(-50, 50), rnd.uniform(-12, 12),
                 tone(0.72, 0.16)))
    hatch(s, 0, 566, W, 300, hexc(LATERITE), gap=15, angle=-3, opacity=0.10)
    for x, y, h in [(556, 792, 88), (1084, 786, 76), (760, 776, 62)]:
        elephant(s, x, y, h, tone(0.68), facing=1 if x < 800 else -1)
    grass(s, 1000, tone(0.58, 0.24), seed=162, count=80, h=34)
    birds(s, 1200, 380, 4, tone(0.34), seed=163)
    vignette(s, 0.16)
    grain(s, 0.26)


@scene("benue-river", "A wide brown river with gallery forest along the bank in savanna country")
def _(s):
    sky(s, pale(0.04, 0.06), pale(0.20, 0.28))
    band(s, 470, 492, pale(0.16, 0.20), 0.5)
    canopy(s, 500, tone(0.58, 0.02), seed=171, count=26, scale=0.75)
    s.add('<rect x="-40" y="500" width="%d" height="100" fill="%s"/>' % (W + 80, tone(0.58, 0.02)))
    band(s, 580, 610, tone(0.72, 0.16))
    water(s, 604, 950, tone(0.60, 0.26), glint=pale(0.20, 0.30), seed=172, rows=14)
    # sandbanks — the bright note in a brown river
    s.add('<path d="M -40,700 L 700,706 C 840,730 700,766 470,772 C 240,778 40,760 -40,742 Z" fill="%s"/>'
          % pale(0.42, 0.62))
    s.add('<path d="M 1640,806 L 900,822 C 760,846 900,884 1130,890 C 1360,896 1560,872 1640,850 Z" fill="%s"/>'
          % pale(0.46, 0.64))
    s.add('<path d="M 420,940 C 700,918 1080,930 1300,956 L 1640,962 L 1640,1010 L 300,1010 Z" fill="%s"/>'
          % pale(0.50, 0.66))
    hatch(s, 0, 700, 760, 80, hexc(LATERITE), gap=11, angle=-6, opacity=0.14)
    band(s, 948, H, tone(0.76, 0.22))
    hatch(s, 0, 950, W, H - 950, hexc(BASALT), gap=12, angle=-4, opacity=0.10)
    grass(s, 1010, tone(0.72, 0.22), seed=173, count=80, h=44)
    for x, b, h in [(240, 1010, 220), (1380, 1020, 210)]:
        acacia(s, x, b, h, tone(0.94, 0.04))
    # a pirogue working across, which is what tells you the brown band is water
    s.add('<path d="M 640,790 q 150,-16 300,0 q -30,34 -150,34 q -120,0 -150,-34 Z" fill="%s"/>' % tone(0.92))
    s.add('<rect x="770" y="716" width="16" height="80" fill="%s"/>' % tone(0.92))
    figure(s, 778, 792, 108, tone(0.94), facing=1, stride=0.06, arm=1.5)
    s.add('<path d="M 806,700 L 872,806" stroke="%s" stroke-width="7" stroke-linecap="round"/>' % tone(0.92))
    s.add('<ellipse cx="790" cy="822" rx="150" ry="10" fill="%s" opacity="0.35"/>' % tone(0.80, 0.20))
    birds(s, 1140, 300, 6, tone(0.36), seed=174, spread=300)
    vignette(s, 0.18)
    grain(s, 0.26)


@scene("mandara-spires", "Volcanic rock spires rising out of dry farmland in the Mandara mountains")
def _(s):
    sky(s, pale(0.05, 0.08), pale(0.20, 0.34))
    sun(s, 350, 240, 44, pale(0.02, 0.6), glow=hexc(LATERITE))
    ridge(s, 620, 22, tone(0.22, 0.16), seed=181, roughness=0.4)
    # the spires themselves
    spires = [(560, 640, 330, 70), (700, 660, 430, 96), (880, 650, 300, 78), (1010, 668, 220, 60),
              (1180, 656, 360, 88), (1330, 672, 200, 54)]
    for i, (cx, base, h, half) in enumerate(spires):
        t = 0.50 + (i % 3) * 0.10
        p = [(cx - half, base), (cx - half * 0.7, base - h * 0.55), (cx - half * 0.25, base - h),
             (cx + half * 0.2, base - h * 0.92), (cx + half * 0.62, base - h * 0.45), (cx + half, base)]
        s.add('<polygon points="%s" fill="%s"/>' % (pts(p), tone(t, 0.12)))
        s.add('<polygon points="%s" fill="%s" opacity="0.28"/>'
              % (pts([(cx - half * 0.25, base - h), (cx + half * 0.2, base - h * 0.92),
                      (cx + half, base), (cx + half * 0.3, base)]), hexc(BASALT)))
    band(s, 660, H, tone(0.40, 0.30))
    # terraced fields
    for i in range(7):
        y = 720 + i * 50
        s.add('<path d="M -40,%d q 400,%d 820,%d q 420,%d 860,%d L 1640,%d L -40,%d Z" '
              'fill="%s" opacity="0.55"/>'
              % (y, -26 - i * 2, -6, 16, 8, y + 26, y + 26, tone(0.34 + i * 0.055, 0.22)))
    hatch(s, 0, 700, W, H - 700, hexc(LATERITE), gap=10, angle=-8, opacity=0.12)
    for x, b in [(300, 900), (1420, 960)]:
        acacia(s, x, b, 150, tone(0.78, 0.06))
    hut(s, 520, 1000, 110, 60, tone(0.72, 0.10), tone(0.60, 0.34))
    hut(s, 640, 1020, 90, 50, tone(0.74, 0.10), tone(0.62, 0.34))
    vignette(s, 0.18)
    grain(s, 0.26)


@scene("north-market-street", "A guide talking with a market trader beside a vehicle in a northern town")
def _(s):
    sky(s, pale(0.05, 0.09), pale(0.20, 0.32))
    band(s, 0, 480, pale(0.10, 0.06), 0.4)
    ridge(s, 500, 18, tone(0.22, 0.18), seed=191, roughness=0.35)
    # low town wall and buildings
    for x, w, h, t in [(0, 300, 200, 0.34), (280, 240, 260, 0.40), (1180, 280, 230, 0.36), (1420, 220, 280, 0.42)]:
        s.add('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x, 620 - h, w, h + 60, tone(t, 0.14)))
    band(s, 640, H, tone(0.52, 0.28))
    hatch(s, 0, 640, W, H - 640, hexc(LATERITE), gap=9, angle=-3, opacity=0.14)
    # awnings over stalls
    for i, x in enumerate([420, 700, 980]):
        s.add('<polygon points="%s" fill="%s"/>'
              % (pts([(x, 560), (x + 250, 560), (x + 230, 640), (x + 20, 640)]),
                 [hexc(LATERITE), tone(0.56, 0.30), tone(0.44, 0.44)][i % 3]))
        post(s, x + 24, 780, 220, tone(0.72), 7)
        post(s, x + 226, 780, 220, tone(0.72), 7)
        s.add('<rect x="%d" y="700" width="200" height="80" fill="%s" opacity="0.85"/>' % (x + 26, tone(0.62, 0.10)))
    vehicle(s, 1230, 980, 340, tone(0.88), tone(0.50), roofrack=True)
    figure(s, 760, 990, 200, tone(0.92), facing=1, stride=0.10, arm=1.2, hat=True)
    figure(s, 920, 986, 196, tone(0.88), facing=-1, stride=0.08, arm=0.9)
    figure(s, 400, 950, 150, tone(0.78), facing=-1)
    vignette(s, 0.20)
    grain(s, 0.26)


@scene("north-craft-stalls", "Leather and craft stalls under awnings in a northern Cameroonian market")
def _(s):
    sky(s, pale(0.06, 0.10), pale(0.22, 0.30))
    band(s, 0, 420, pale(0.12, 0.06), 0.45)
    for x, w, h, t in [(60, 260, 240, 0.32), (1300, 280, 260, 0.34)]:
        s.add('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>' % (x, 560 - h, w, h + 80, tone(t, 0.14)))
    band(s, 620, H, tone(0.50, 0.30))
    hatch(s, 0, 620, W, H - 620, hexc(LATERITE), gap=10, angle=-2, opacity=0.14)
    # a run of awnings receding
    cols = [hexc(LATERITE), tone(0.50, 0.34), tone(0.36, 0.46), tone(0.62, 0.20)]
    for i, x in enumerate([180, 520, 860, 1200]):
        w = 330
        s.add('<polygon points="%s" fill="%s"/>'
              % (pts([(x, 470 + i * 8), (x + w, 470 + i * 8), (x + w - 18, 570 + i * 8), (x + 18, 570 + i * 8)]),
                 cols[i % 4]))
        post(s, x + 26, 860, 300, tone(0.74), 8)
        post(s, x + w - 26, 860, 300, tone(0.74), 8)
        s.add('<rect x="%.0f" y="%.0f" width="%.0f" height="90" fill="%s"/>' % (x + 30, 770, w - 60, tone(0.70, 0.06)))
        # goods hanging from the frame
        rnd = random.Random(200 + i)
        for j in range(6):
            gx = x + 46 + j * (w - 92) / 5
            gh = 60 + rnd.random() * 60
            s.add('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" rx="8" fill="%s" opacity="0.9"/>'
                  % (gx, 580 + i * 8, 34, gh, tone(0.44 + rnd.random() * 0.34, 0.30)))
    figure(s, 700, 1010, 180, tone(0.92), facing=1, stride=0.12)
    figure(s, 1060, 1020, 190, tone(0.88), facing=-1, stride=0.10, hat=True)
    vignette(s, 0.22)
    grain(s, 0.26)


@scene("park-permit-post", "A guide checking a permit book at a national park entry post")
def _(s):
    sky(s, pale(0.07, 0.05), pale(0.22, 0.20))
    ridge(s, 500, 26, tone(0.24, 0.10), seed=201)
    canopy(s, 600, tone(0.40, 0.02), seed=202, count=20, scale=0.9)
    band(s, 700, H, tone(0.56, 0.20))
    hatch(s, 0, 700, W, H - 700, hexc(LATERITE), gap=10, angle=-3, opacity=0.14)
    # the barrier and the post hut
    s.add('<rect x="120" y="640" width="360" height="200" fill="%s"/>' % tone(0.70))
    s.add('<polygon points="%s" fill="%s"/>' % (pts([(90, 640), (300, 570), (510, 640)]), tone(0.58, 0.30)))
    s.add('<rect x="180" y="690" width="110" height="90" fill="%s" opacity="0.85"/>' % pale(0.16, 0.12))
    post(s, 620, 840, 190, tone(0.84), 12)
    s.add('<rect x="620" y="700" width="620" height="18" rx="9" fill="%s"/>' % tone(0.86))
    for i in range(6):
        s.add('<rect x="%d" y="700" width="52" height="18" fill="%s"/>' % (660 + i * 100, hexc(LATERITE)))
    post(s, 1240, 840, 120, tone(0.84), 12)
    signboard(s, 1400, 900, 200, 130, 150, tone(0.86), pale(0.10, 0.08))
    figure(s, 830, 940, 230, tone(0.94), facing=1, stride=0.06, arm=1.4, hat=True)
    # the book itself, held out
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(878, 806), (952, 790), (956, 830), (880, 846)]), pale(0.05)))
    figure(s, 1030, 950, 224, tone(0.90), facing=-1, stride=0.08, arm=1.1, pack=True)
    grass(s, 1010, tone(0.62, 0.16), seed=203, count=60, h=30, x0=0, x1=560)
    vignette(s, 0.20)
    grain(s, 0.26)


# ---- the highlands -------------------------------------------------------------


@scene("highlands-october", "Green highland country under clearing October skies in the Bamenda highlands")
def _(s):
    sky(s, pale(0.16, 0.03), pale(0.06, 0.06))
    for i, (cx, cy, rx) in enumerate([(420, 250, 300), (900, 200, 360), (1300, 280, 260)]):
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s" opacity="0.75"/>'
              % (cx, cy, rx, rx * 0.28, hexc(PAPER)))
        s.add('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="%s" opacity="0.55"/>'
              % (cx + 60, cy + 40, rx * 0.7, rx * 0.20, pale(0.14)))
    band(s, 430, 470, pale(0.12, 0.02), 0.5)
    ridge(s, 480, 40, tone(0.24, 0.02), seed=211)
    ridge(s, 590, 48, tone(0.42), seed=212)
    ridge(s, 700, 54, tone(0.60), seed=213)
    ridge(s, 840, 46, tone(0.78), seed=214)
    hatch(s, 0, 700, W, H - 700, hexc(PAPER), gap=11, angle=-16, opacity=0.10)
    # a red road threading the ridges
    s.add('<path d="M 1600,736 C 1360,762 1180,820 1040,896 C 900,972 800,1010 610,1067 '
          'L 400,1067 C 640,986 810,930 940,850 C 1120,770 1330,738 1600,712 Z" fill="%s"/>'
          % pale(0.62, 0.88))
    s.add('<path d="M 1600,724 C 1330,750 1120,782 940,862 C 810,942 640,996 400,1067 l 90,0 '
          'C 720,984 860,930 980,856 C 1160,780 1360,752 1600,730 Z" fill="%s" opacity="0.18"/>'
          % hexc(BASALT))
    band(s, 970, H, tone(0.92))
    grass(s, 1020, tone(0.72), seed=215, count=110, h=36)
    for x, b, h in [(230, 1000, 200), (1400, 1030, 220)]:
        broadleaf(s, x, b, h, tone(0.98), seed=x)
    birds(s, 700, 330, 4, tone(0.34), seed=216)
    vignette(s, 0.16)
    grain(s, 0.26)


@scene("laterite-road", "A 4x4 on a red laterite road running between forest and highland farmland")
def _(s):
    sky(s, pale(0.08, 0.04), pale(0.22, 0.16))
    ridge(s, 470, 34, tone(0.20, 0.04), seed=221)
    ridge(s, 560, 40, tone(0.32, 0.02), seed=222)
    canopy(s, 640, tone(0.46), seed=223, count=22, scale=0.9)
    band(s, 720, H, tone(0.58, 0.06))
    # the road: laterite red, running from the horizon to the bottom edge
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(742, 700), (858, 700), (1300, 1067), (280, 1067)]), pale(0.66, 0.92)))
    s.add('<polygon points="%s" fill="%s" opacity="0.22"/>'
          % (pts([(742, 700), (764, 700), (500, 1067), (280, 1067)]), hexc(BASALT)))
    s.add('<polygon points="%s" fill="%s" opacity="0.16"/>'
          % (pts([(836, 700), (858, 700), (1300, 1067), (1080, 1067)]), hexc(BASALT)))
    hatch(s, 280, 700, 1020, 367, hexc(BASALT), gap=16, angle=-70, opacity=0.07)
    # verge crops on the right, forest wall on the left
    canopy(s, 780, tone(0.72), seed=224, count=10, scale=1.4, x0=-40, x1=400)
    for i in range(6):
        y = 800 + i * 44
        s.add('<path d="M 1150,%d q 260,-20 500,6" stroke="%s" stroke-width="%d" fill="none" opacity="0.5"/>'
              % (y, tone(0.56, 0.10), 10 + i * 2))
    grass(s, 900, tone(0.62, 0.06), seed=225, count=50, h=30, x0=1140, x1=1600)
    vehicle(s, 800, 960, 430, tone(0.90), tone(0.52))
    # dust behind it
    s.add('<ellipse cx="800" cy="936" rx="260" ry="60" fill="%s" opacity="0.30"/>' % pale(0.20, 0.5))
    vignette(s, 0.20)
    grain(s, 0.26)


@scene("foumban-bronze-caster", "A bronze caster at work in a workshop on the craft street at Foumban")
def _(s):
    sky(s, pale(0.30, 0.10), pale(0.44, 0.16))
    band(s, 0, H, tone(0.34, 0.06))
    # workshop wall behind
    s.add('<rect x="-40" y="0" width="%d" height="620" fill="%s"/>' % (W + 80, tone(0.44, 0.08)))
    hatch(s, 0, 0, W, 620, hexc(BASALT), gap=16, angle=0, opacity=0.10)
    # doorway of light
    s.add('<rect x="1220" y="120" width="260" height="500" fill="%s" opacity="0.85"/>' % pale(0.06, 0.30))
    # shelf of finished castings
    s.add('<rect x="80" y="300" width="520" height="16" fill="%s"/>' % tone(0.62))
    for i, x in enumerate([130, 240, 350, 470]):
        h = 90 + (i % 3) * 34
        s.add('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s"/>'
              % (x, 300 - h, 60, h, tone(0.66, 0.30 + 0.1 * (i % 2))))
        s.add('<circle cx="%d" cy="%d" r="20" fill="%s"/>' % (x + 30, 300 - h - 12, tone(0.66, 0.30)))
    # bench
    s.add('<rect x="-40" y="700" width="%d" height="60" fill="%s"/>' % (W + 80, tone(0.74, 0.06)))
    s.add('<rect x="200" y="760" width="40" height="200" fill="%s"/>' % tone(0.74, 0.06))
    s.add('<rect x="1300" y="760" width="40" height="200" fill="%s"/>' % tone(0.74, 0.06))
    # the forge — the one bright thing in the frame
    s.add('<ellipse cx="1000" cy="700" rx="150" ry="46" fill="%s"/>' % tone(0.80))
    sun(s, 1000, 676, 46, hexc(LATERITE), glow=hexc(LATERITE), rings=4)
    s.add('<path d="M 980,640 q 26,-70 -4,-120 q 66,40 44,120 Z" fill="%s" opacity="0.45"/>' % pale(0.20, 0.7))
    # the caster at the bench, and an apprentice working the bellows behind
    figure(s, 700, 1010, 470, tone(0.96), facing=1, stride=0.18, arm=1.7)
    s.add('<path d="M 782,640 L 966,678 l -4,26 L 778,666 Z" fill="%s"/>' % tone(0.92))
    s.add('<path d="M 782,664 L 962,690 l -6,24 L 776,690 Z" fill="%s"/>' % tone(0.92))
    figure(s, 1330, 990, 400, tone(0.84), facing=-1, stride=0.22, arm=1.2, hat=True)
    vignette(s, 0.34)
    grain(s, 0.28)


@scene("foumban-throne", "A carved and beaded royal throne inside a palace museum in the western highlands")
def _(s):
    sky(s, pale(0.36, 0.06), pale(0.48, 0.10))
    band(s, 0, H, tone(0.40, 0.04))
    s.add('<rect x="-40" y="0" width="%d" height="%d" fill="%s"/>' % (W + 80, 780, tone(0.46, 0.05)))
    hatch(s, 0, 0, W, 780, hexc(BASALT), gap=18, angle=90, opacity=0.08)
    # a lit alcove
    s.add('<rect x="520" y="60" width="560" height="720" rx="280" fill="%s" opacity="0.65"/>' % pale(0.10, 0.22))
    band(s, 780, H, tone(0.62, 0.06))
    # plinth
    s.add('<rect x="560" y="900" width="480" height="60" fill="%s"/>' % tone(0.76, 0.04))
    s.add('<rect x="600" y="860" width="400" height="44" fill="%s"/>' % tone(0.70, 0.04))
    # the throne: seat, back, carved arms, beadwork
    th = tone(0.88, 0.10)
    s.add('<rect x="640" y="700" width="320" height="60" rx="10" fill="%s"/>' % th)
    s.add('<path d="M 660,700 q 140,-460 280,0 Z" fill="%s"/>' % th)
    # carved panel in the back: an inset field, a diamond motif, a small ancestor figure
    s.add('<path d="M 704,676 q 96,-326 192,0 Z" fill="%s"/>' % tone(0.66, 0.34))
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(800, 402), (854, 486), (800, 570), (746, 486)]), pale(0.16, 0.34)))
    s.add('<circle cx="800" cy="486" r="26" fill="%s"/>' % tone(0.74, 0.30))
    s.add('<rect x="770" y="596" width="60" height="66" rx="10" fill="%s"/>' % tone(0.74, 0.30))
    s.add('<circle cx="800" cy="588" r="24" fill="%s"/>' % tone(0.74, 0.30))
    for d in (-1, 1):
        s.add('<rect x="%d" y="700" width="46" height="200" fill="%s"/>' % (664 if d < 0 else 890, th))
        s.add('<circle cx="%d" cy="690" r="42" fill="%s"/>' % (687 if d < 0 else 913, tone(0.70, 0.36)))
    # beadwork bands
    rnd = random.Random(23)
    for row, y in enumerate([560, 600, 640]):
        for i in range(16):
            x = 676 + i * 18
            s.add('<circle cx="%d" cy="%d" r="7" fill="%s" opacity="0.9"/>'
                  % (x, y, [hexc(LATERITE), pale(0.10), tone(0.50, 0.30)][(i + row) % 3]))
    s.add('<rect x="640" y="760" width="320" height="150" fill="%s" opacity="0.25"/>' % hexc(BASALT))
    vignette(s, 0.34)
    grain(s, 0.28)


# ---- offices and shopfronts ----------------------------------------------------


@scene("office-frontage", "The street frontage of a small tour operator office with a hand-painted sign")
def _(s):
    sky(s, pale(0.06, 0.03), pale(0.18, 0.10))
    band(s, 0, 300, pale(0.10, 0.02), 0.4)
    canopy(s, 220, tone(0.34), seed=231, count=12, scale=1.1, x0=-40, x1=520)
    s.add('<rect x="-40" y="0" width="%d" height="820" fill="%s"/>' % (W + 80, tone(0.30, 0.03)))
    # the building face fills the frame
    s.add('<rect x="140" y="120" width="1320" height="760" fill="%s"/>' % tone(0.42, 0.04))
    hatch(s, 140, 120, 1320, 760, hexc(BASALT), gap=22, angle=0, opacity=0.08)
    # painted band and sign
    s.add('<rect x="140" y="300" width="1320" height="150" fill="%s"/>' % hexc(LATERITE))
    for i in range(3):
        s.add('<rect x="%d" y="%d" width="%d" height="16" rx="8" fill="%s" opacity="0.85"/>'
              % (400 + i * 40, 348 + i * 34, 800 - i * 180, pale(0.04)))
    # windows and door
    for i, x in enumerate([260, 620, 980]):
        s.add('<rect x="%d" y="520" width="260" height="220" fill="%s"/>' % (x, tone(0.66, 0.03)))
        s.add('<rect x="%d" y="530" width="240" height="200" fill="%s" opacity="0.85"/>' % (x + 10, pale(0.16, 0.10)))
        s.add('<rect x="%d" y="620" width="240" height="6" fill="%s" opacity="0.6"/>' % (x + 10, tone(0.66)))
    s.add('<rect x="1280" y="470" width="150" height="410" fill="%s"/>' % tone(0.74, 0.04))
    s.add('<rect x="1292" y="482" width="126" height="386" fill="%s" opacity="0.8"/>' % pale(0.12, 0.14))
    # awning
    s.add('<polygon points="%s" fill="%s"/>'
          % (pts([(180, 460), (1440, 460), (1400, 520), (220, 520)]), tone(0.50, 0.40)))
    band(s, 860, H, tone(0.60, 0.16))
    hatch(s, 0, 860, W, H - 860, hexc(LATERITE), gap=10, angle=-2, opacity=0.14)
    s.add('<rect x="140" y="856" width="1320" height="26" fill="%s"/>' % tone(0.70, 0.06))
    figure(s, 1350, 960, 180, tone(0.88), facing=-1, stride=0.16)
    # a couple of chairs outside
    for x in (300, 400):
        s.add('<rect x="%d" y="880" width="60" height="70" fill="%s"/>' % (x, tone(0.72, 0.10)))
        s.add('<rect x="%d" y="840" width="14" height="50" fill="%s"/>' % (x + 44, tone(0.72, 0.10)))
    vignette(s, 0.22)
    grain(s, 0.26)


@scene("buea-office-mountain", "A small operations office in Buea with the mountain rising behind the town")
def _(s):
    sky(s, pale(0.10, 0.04), pale(0.26, 0.16))
    cone(s, 700, 620, 400, 620, tone(0.24, 0.05), notch=0.04)
    s.add('<polygon points="%s" fill="%s" opacity="0.12"/>'
          % (pts([(700, 220), (742, 240), (1000, 620), (700, 620)]), hexc(BASALT)))
    band(s, 560, 640, pale(0.18), 0.45)
    ridge(s, 640, 26, tone(0.38, 0.04), seed=241)
    canopy(s, 700, tone(0.48), seed=242, count=22, scale=0.7)
    band(s, 780, H, tone(0.56, 0.12))
    # a scatter of town roofs
    rnd = random.Random(25)
    for i in range(11):
        x = 60 + i * 150 + rnd.uniform(-30, 30)
        w = 90 + rnd.random() * 70
        y = 740 + rnd.uniform(-20, 30)
        s.add('<rect x="%.0f" y="%.0f" width="%.0f" height="%.0f" fill="%s"/>' % (x, y, w, 60, tone(0.58, 0.06)))
        s.add('<polygon points="%s" fill="%s"/>'
              % (pts([(x - 12, y), (x + w / 2, y - 34), (x + w + 12, y)]),
                 hexc(LATERITE) if i % 3 == 0 else tone(0.52, 0.30)))
    # the office in the foreground
    shopfront(s, 520, 1000, 560, 300, tone(0.74, 0.04), tone(0.34, 0.04), sign=hexc(LATERITE),
              awning=tone(0.52, 0.36), panes=3)
    hatch(s, 0, 1000, W, 67, hexc(LATERITE), gap=9, angle=-2, opacity=0.16)
    figure(s, 1180, 1040, 190, tone(0.86), facing=-1, stride=0.14)
    vehicle(s, 260, 1050, 260, tone(0.88), tone(0.50), roofrack=True)
    vignette(s, 0.20)
    grain(s, 0.26)


def build():
    os.makedirs(OUT, exist_ok=True)
    written = []
    for name, (fn, title) in sorted(SCENES.items()):
        s = Scene(name, title)
        fn(s)
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w") as f:
            f.write(s.render())
        written.append((name, os.path.getsize(path)))
    return written


if __name__ == "__main__":
    for name, size in build():
        print("%-28s %6.1f kB" % (name + ".svg", size / 1024))
