"""Measure every placed image against the four things the standard names.

The standard is: bright natural exposure, natural skin tones, documentary
composition, and none of orange/teal grading, HDR, fake fog or exaggerated
saturation. Three of those are measurable and one is not, so this measures the
three and leaves composition to the eye.

  exposure   mean luminance, and how much of the frame is crushed or blown
  saturation mean and 90th-percentile HSV saturation
  split      the orange/teal signature: warm highlights against cool shadows,
             measured as the difference in mean (R-B) between the brightest
             and darkest quarter of the frame. A film shot in evening light is
             warm everywhere; a graded one is warm at the top and cold at the
             bottom, and that gap is the tell.
  halo       the HDR signature: local contrast far above what the global
             contrast would predict, measured as the mean absolute difference
             between the frame and a heavily blurred copy of it.

None of these is a verdict. They rank the set so the eye goes to the worst
first, which for eighty images is the difference between an audit and a guess.
"""
import os
import sys
from PIL import Image, ImageFilter, ImageStat

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SMALL = 400          # everything is measured at this long edge, so a 1600px
                     # frame and an 800px crop of it score the same


def load(path):
    im = Image.open(path)
    im = im.convert("RGB")
    im.thumbnail((SMALL, SMALL), Image.LANCZOS)
    return im


def pct(hist, total, p):
    """The value at percentile p of a 256-bin histogram."""
    want = total * p / 100.0
    run = 0
    for i, n in enumerate(hist):
        run += n
        if run >= want:
            return i
    return 255


def measure(path):
    im = load(path)
    n = im.width * im.height
    lum = im.convert("L")
    h = lum.histogram()
    mean = ImageStat.Stat(lum).mean[0]
    crushed = sum(h[:8]) / float(n) * 100      # % of frame at or near black
    blown = sum(h[248:]) / float(n) * 100      # % at or near white

    hsv = im.convert("HSV")
    s = hsv.split()[1]
    sh = s.histogram()
    smean = ImageStat.Stat(s).mean[0]
    s90 = pct(sh, n, 90)

    # split-tone: mean (R-B) in the darkest quarter vs the brightest quarter
    q1, q3 = pct(h, n, 25), pct(h, n, 75)
    px, lx = im.load(), lum.load()
    dark = [0, 0]
    light = [0, 0]
    step = 2 if im.width > 200 else 1
    for y in range(0, im.height, step):
        for x in range(0, im.width, step):
            v = lx[x, y]
            r, g, b = px[x, y]
            if v <= q1:
                dark[0] += r - b
                dark[1] += 1
            elif v >= q3:
                light[0] += r - b
                light[1] += 1
    dwarm = dark[0] / float(dark[1] or 1)
    lwarm = light[0] / float(light[1] or 1)
    split = lwarm - dwarm

    # halo: how far the frame sits from a heavily blurred copy of itself. An
    # HDR-processed picture has local contrast the global contrast does not
    # predict, and that gap is what this measures.
    blur = lum.filter(ImageFilter.GaussianBlur(radius=max(2, im.width // 40)))
    bl, ll = blur.load(), lum.load()
    acc = 0
    cnt = 0
    for y in range(0, im.height, step):
        for x in range(0, im.width, step):
            acc += abs(ll[x, y] - bl[x, y])
            cnt += 1
    halo = acc / float(cnt or 1)
    spread = ImageStat.Stat(lum).stddev[0]
    return {
        "mean": mean, "crushed": crushed, "blown": blown, "spread": spread,
        "smean": smean, "s90": s90, "split": split, "halo": halo,
        "w": Image.open(path).width, "h": Image.open(path).height,
    }


def main(paths):
    rows = []
    for rel in paths:
        p = os.path.join(ROOT, rel.lstrip("/"))
        if not os.path.exists(p):
            print("MISSING  " + rel)
            continue
        try:
            m = measure(p)
        except Exception as e:                      # noqa: BLE001
            print("ERROR    %s  %s" % (rel, e))
            continue
        m["rel"] = rel
        rows.append(m)
    print("%-58s %5s %5s %5s %5s %5s %6s %5s" %
          ("image", "lum", "crush", "sat", "s90", "split", "halo", "sprd"))
    for m in sorted(rows, key=lambda r: -r["split"]):
        print("%-58s %5.0f %5.1f %5.0f %5.0f %5.1f %6.1f %5.0f" %
              (m["rel"].replace("/images/", ""), m["mean"], m["crushed"],
               m["smean"], m["s90"], m["split"], m["halo"], m["spread"]))
    return rows


if __name__ == "__main__":
    main([l.strip() for l in sys.stdin if l.strip()])
