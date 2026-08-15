"""Cut a raw clip down to something a homepage can carry.

    python3 tools/tourism/build.py cut incoming/video/whatever.mp4 --name city-lagos-marina
    python3 tools/tourism/build.py cut https://github.com/.../releases/download/v/raw.mp4 \
        --name wild-bwindi-gorillas --seconds 9 --mb 2

WHY THIS EXISTS

The window sits directly under the hero. A visitor on a phone pays for whatever
is in it before they have decided to stay, so the budget is about two megabytes
and roughly ten seconds — and a raw clip off a camera or a stock site is
routinely twenty-five to several hundred times that.

It is also why the original does not belong in the repository. Git keeps every
binary forever: a 25 MB master committed once is 25 MB in the history of every
clone and every deploy from then on, in exchange for the 2 MB that is actually
served. Fetch it, cut it, commit the cut, leave the master wherever it came
from. Passing a URL instead of a path is what makes that easy: the master is
fetched into incoming/video/masters/, which is gitignored.

WHAT IT DOES

  - strips the audio track. The player is muted and looping, so audio is weight
    with no way to hear it, and it is 15-20% of most files.
  - scales to 1280 wide by default, keeping the aspect. The frame is about
    690px on a 1440 screen, so 720p is already more than it can show.
  - trims to `--seconds` from `--start`.
  - two-pass encodes to a bitrate computed from the byte budget and the
    duration, so the result lands near the target instead of near a guess.
  - fails if the output is still over budget, rather than writing it and
    letting somebody find out from a phone bill.

It does not decide where a clip goes. That is tourism/motion.json, and it is a
judgement about whether the caption is true — see footage.py for why nothing
automated is allowed to make it.
"""

import os
import re
import subprocess
import urllib.request

from .model import ROOT
from .providers.base import UA

OUT_DIR = os.path.join(ROOT, "videos")
# Where a fetched master lands. Gitignored, and that is the whole point: the
# original is working material, the cut is the deliverable. Staged Pexels
# candidates live one level up in incoming/video/ and are committed on purpose,
# because a candidate nobody can see is a candidate nobody can judge.
MASTERS = os.path.join(ROOT, "incoming", "video", "masters")

WIDTH = 1280
SECONDS = 10.0
MB = 2.0
# A budget is a ceiling, not a target. A three-second trim would otherwise be
# handed the whole two megabytes — about 5 Mbps at 720p, several times what the
# picture can use, and the surplus goes on sensor noise and compression of
# grain. Past roughly this the file gets bigger and does not get better, so the
# encode is capped here and comes in under budget rather than filling it.
CAP_KBPS = 2600                   # at WIDTH; scaled by area for other widths
# H.264 in an mp4 that starts playing before it has finished arriving.
FAAST = ["-movflags", "+faststart", "-pix_fmt", "yuv420p"]
# And the same picture as VP9 in a WebM. Two reasons, and the second is the one
# that made it worth the extra file. VP9 is roughly a third smaller than H.264
# at the same quality, so most visitors fetch less; and H.264 is patent-encumbered,
# so the open-source Chromium the checks drive cannot decode it at all. Without a
# WebM the one behaviour that matters here — the clip plays through and hands the
# rail on — could not be tested in any browser available to this repository.
# Every browser that can play one of these can play the other.
VP9_KBPS = 0.72                   # of the H.264 rate, for about the same picture


def ffmpeg():
    try:
        import imageio_ffmpeg
    except ImportError:
        raise SystemExit(
            "No ffmpeg. `pip install imageio-ffmpeg` fetches a static build from "
            "PyPI, which is reachable from here when very little else is.")
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path):
    """Duration and dimensions, read out of ffmpeg's own report on the file."""
    out = subprocess.run([ffmpeg(), "-hide_banner", "-i", path],
                         capture_output=True, text=True).stderr
    secs, w, h = None, None, None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            hh, mm, ss = line.split(",")[0].split("Duration:")[1].strip().split(":")
            secs = int(hh) * 3600 + int(mm) * 60 + float(ss)
        if " Video: " in line:
            for bit in line.split(","):
                bit = bit.strip().split(" ")[0]
                if "x" in bit and bit.replace("x", "").isdigit():
                    w, h = (int(v) for v in bit.split("x"))
                    break
    return secs, w, h


def fetch(url, into):
    """Pull a master from a URL so it never has to be committed."""
    os.makedirs(os.path.dirname(into), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    # Everything that can refuse the URL is checked before the file is opened,
    # so a refusal leaves nothing behind to be mistaken for a download.
    with urllib.request.urlopen(req, timeout=600) as r:
        if r.status != 200:
            raise SystemExit("HTTP %s fetching %s" % (r.status, url))
        ctype = r.headers.get("Content-Type", "")
        if "video" not in ctype and "octet-stream" not in ctype:
            raise SystemExit("%s is not a video (%s)" % (url, ctype))
        with open(into, "wb") as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
    return into


def cut(src, name, seconds=SECONDS, start=0.0, width=WIDTH, mb=MB,
        keep_audio=False, log=print):
    """Cut one piece. `keep_audio` is off because the window plays muted.

    IF A NARRATED MASTER TURNS UP LATER

    Nothing here has to be rebuilt for it. Hand this the narrated file with
    keep_audio=True and the same boundaries produce the same pieces with the
    voice in them, because the boundaries live in film.py as timecodes rather
    than being discovered from whatever file is passed in.

    What it cannot do is make a voice run unbroken across sixteen separate
    files. A browser gives no guarantee about the gap between one media element
    ending and the next starting — it is a few tens of milliseconds on a fast
    connection and can be a second on a slow one — and a sentence split across
    that boundary is audibly cut in half. Narration that has to flow belongs in
    one file. See images/VIDEO.md.
    """
    # The name becomes a path and a URL, so it is held to what both can carry.
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", name or ""):
        raise SystemExit(
            "--name has to be lowercase letters, digits and hyphens — it becomes "
            "a filename and a URL. The photographs are named the same way: "
            "city-lagos-marina, wild-bwindi-gorillas.")
    exe = ffmpeg()
    os.makedirs(OUT_DIR, exist_ok=True)
    dst = os.path.join(OUT_DIR, name + ".mp4")

    had, w, h = probe(src)
    if had and start >= had - 0.5:
        raise SystemExit(
            "--start %.1f is at or past the end of a %.1fs clip; there would be "
            "nothing after it to keep." % (start, had))
    if had:
        seconds = min(seconds, had - start)
    log("in : %s  %sx%s  %.1fs  %.1f MB"
        % (os.path.basename(src), w, h, had or 0,
           os.path.getsize(src) / 1048576.0))

    # Audio, if it is being kept, is paid for out of the same budget rather than
    # on top of it — the ceiling is what a visitor downloads, not what the video
    # stream costs. 96 kbps AAC is transparent enough for a spoken voice.
    AAC = 96
    budget_bits = mb * 1024 * 1024 * 8
    if keep_audio:
        budget_bits -= AAC * 1000 * seconds
    # Leave a tenth for container overhead — mp4 headers and the faststart index
    # are not free, and landing just over the ceiling means doing it again.
    kbps = max(200, int((budget_bits * 0.9) / seconds / 1000))
    cap = max(200, int(CAP_KBPS * (width / float(WIDTH)) ** 2))
    capped = kbps > cap
    kbps = min(kbps, cap)

    sound = (["-c:a", "aac", "-b:a", "%dk" % AAC, "-ac", "2"]
             if keep_audio else ["-an"])
    common = ["-ss", "%.3f" % start, "-i", src, "-t", "%.3f" % seconds,
              "-vf", "scale=%d:-2:flags=lanczos" % width,
              "-c:v", "libx264", "-b:v", "%dk" % kbps,
              "-preset", "slow", "-profile:v", "high", "-level", "4.0"] + sound
    log("out: %s  %dpx wide  %.1fs  %s %g MB at %d kbps"
        % (name + ".mp4", width, seconds,
           "under" if capped else "target", mb, kbps))
    if capped:
        log("     the %g MB budget would have bought more bitrate than %dpx can "
            "use; capped at %d kbps." % (mb, width, cap))
    passlog = os.path.join(OUT_DIR, ".passlog-" + name)

    def run_pass(cmd, what, p):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("%s pass %d failed:\n%s" % (what, p, r.stderr[-800:]))

    ceiling = mb * 1024 * 1024

    # H.264. Pass one drops the audio whatever the setting: encoding a track to
    # /dev/null twice is time spent for no reason.
    run_pass([exe, "-hide_banner", "-loglevel", "error", "-y"]
             + common[:-len(sound)] + ["-an", "-pass", "1",
                                       "-passlogfile", passlog, "-f", "mp4",
                                       os.devnull], "h264", 1)

    def h264(rate):
        run_pass([exe, "-hide_banner", "-loglevel", "error", "-y"]
                 + [a if a != "%dk" % kbps else "%dk" % rate for a in common]
                 + ["-pass", "2", "-passlogfile", passlog] + FAAST + [dst],
                 "h264", 2)
        return os.path.getsize(dst)

    # VP9.
    vp9 = ["-c:v", "libvpx-vp9", "-b:v", "%dk" % int(kbps * VP9_KBPS),
           "-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
    # Opus rather than AAC: it is what WebM carries, and it is better than AAC
    # at this bitrate, which matters more for a voice than for anything else.
    wsound = (["-c:a", "libopus", "-b:a", "%dk" % AAC] if keep_audio else ["-an"])
    web = os.path.join(OUT_DIR, name + ".webm")
    vbase = ["-ss", "%.3f" % start, "-i", src, "-t", "%.3f" % seconds,
             "-vf", "scale=%d:-2:flags=lanczos" % width]
    run_pass([exe, "-hide_banner", "-loglevel", "error", "-y"] + vbase
             + ["-c:v", "libvpx-vp9", "-b:v", "%dk" % int(kbps * VP9_KBPS),
                "-row-mt", "1", "-deadline", "good", "-cpu-used", "2", "-an",
                "-pass", "1", "-passlogfile", passlog + "-vp9", "-f", "webm",
                os.devnull], "vp9", 1)

    def vp9enc(rate):
        run_pass([exe, "-hide_banner", "-loglevel", "error", "-y"] + vbase
                 + ["-c:v", "libvpx-vp9", "-b:v", "%dk" % rate, "-row-mt", "1",
                    "-deadline", "good", "-cpu-used", "2"] + wsound
                 + ["-pass", "2", "-passlogfile", passlog + "-vp9", web],
                 "vp9", 2)
        return os.path.getsize(web)

    # A two-pass encoder aims at the bitrate it was given and lands near it, not
    # on it — a short piece of a busy scene overshoots by a few per cent, which
    # is enough to fail a ceiling. Rather than padding the constant until it is
    # loose enough for the worst case (and slack for every other piece), miss and
    # correct: the overshoot ratio says exactly what rate would have fitted.
    def fit(enc, rate, what):
        for attempt in range(3):
            got = enc(rate)
            if got <= ceiling:
                if attempt:
                    log("     %s fitted on attempt %d at %d kbps"
                        % (what, attempt + 1, rate))
                return got
            rate = max(200, int(rate * (ceiling / float(got)) * 0.97))
        return got

    got_mp4 = fit(h264, kbps, "mp4")
    got_web = fit(vp9enc, int(kbps * VP9_KBPS), "webm")

    for junk in os.listdir(OUT_DIR):
        if junk.startswith(".passlog-" + name):
            os.remove(os.path.join(OUT_DIR, junk))

    over = []
    for f in (dst, web):
        n = os.path.getsize(f)
        gs, gw, gh = probe(f)
        log("     %-34s %.2f MB  %sx%s  %.1fs"
            % (os.path.basename(f), n / 1048576.0, gw, gh, gs or 0))
        if n > ceiling:
            over.append(f)
    if over:
        for f in (dst, web):
            if os.path.exists(f):
                os.remove(f)
        raise SystemExit(
            "%s would not come under the %g MB ceiling in three attempts and "
            "neither file was kept. Try a shorter --seconds, or --width 960."
            % (", ".join(os.path.basename(f) for f in over), mb))
    log("set \"clip\": \"/videos/%s.mp4\" on the shot it belongs to in "
        "tourism/motion.json — the .webm beside it is found from that, and is "
        "what most browsers will actually fetch. Only put it on a shot whose "
        "caption you can stand behind." % name)
    return dst
