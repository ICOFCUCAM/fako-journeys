"""Cut one supplied film into the pieces the window can carry, and place none.

    python3 tools/tourism/build.py film --list
    python3 tools/tourism/build.py film incoming/video/masters/afrinkong-master.mp4

WHY A TABLE AND NOT AN ALGORITHM

The obvious thing is to slice the film every eight seconds. It is also wrong
here, and the reason is the caption. The window labels every shot — "Lagos",
"Mountain gorilla", "A bronze caster at Foumban" — and a mechanical slice puts
a waterfall, a silverback and an aerial city into one piece that then has to be
called something. There is no honest name for that piece.

So the boundaries are the film's own. Scene detection found 36 cuts in 119.42
seconds, and every boundary below is one of them: no piece begins or ends in the
middle of a shot, consecutive pieces are seamless, and the sixteen of them cover
the film end to end with nothing dropped and nothing repeated. The lengths that
come out of that are five to twelve seconds rather than eight exactly, because
the film decides where it can be cut and not the arithmetic.

WHAT THE CAPTIONS MAY SAY

The same rule the photographs live under: a caption names a place only where
the whole piece is that place and it can be recognised. The Lekki-Ikoyi bridge,
the Third Mainland bridge and the giraffe standing against the Nairobi skyline
are identifiable to anyone who knows them. Several of the aerial cities in this
film are not — they could be four or five different places — so those pieces are
captioned by what is happening rather than by where, which is true and can stay
true. See footage.py for the argument at length; it is the same argument.
"""

import json
import os

from . import cut as cutter
from .model import ROOT

MOTION = os.path.join(ROOT, "tourism", "motion.json")
POSTERS = os.path.join(ROOT, "images", "uploads")
MB = 1.6                       # sixteen of these, so a little under the usual 2

# start, end, slug, caption, alt
# Boundaries are scene cuts in the supplied film; end == the next piece's start.
PIECES = [
    (0.00, 8.81, "lagos-third-mainland", "Lagos, from the air",
     "The Third Mainland Bridge carrying traffic across Lagos lagoon seen from "
     "the air, followed by two aerial passes over a city of mid-rise blocks and "
     "green suburbs"),
    (8.81, 14.68, "plains-and-giza", "Zebra, and then Giza",
     "Zebra and wildebeest crowded at a dry waterhole, then the pyramids at Giza "
     "beyond the shoulder of a woman looking towards them"),
    (14.68, 20.09, "dusk-and-lekki", "Dusk, and the Lekki bridge",
     "A city at dusk with traffic on a wide highway under a low sun, then the "
     "Lekki-Ikoyi Link Bridge in Lagos from the air with its single white pylon"),
    (20.09, 27.09, "grass-and-indoors", "Out there, and inside",
     "Two zebra walking through green grass, then three women in patterned dress "
     "coming through a decorated room hung with mirrors and cane furniture"),
    (27.09, 33.47, "lions-and-highland", "Lions, and the high ground",
     "A lion and lioness resting together on a rock, then green highland ridges "
     "under low cloud"),
    (33.47, 38.84, "victoria-falls", "Victoria Falls",
     "Water pouring over the lip of Victoria Falls in close-up through spray, "
     "then the full width of the falls seen through trees with a rainbow across "
     "the gorge"),
    (38.84, 45.31, "mountain-gorilla", "Mountain gorilla",
     "A mountain gorilla feeding in dense green undergrowth, close enough to see "
     "the leaf in its hand, then a zebra standing in open woodland"),
    (45.31, 54.75, "on-game-drive", "On game drive",
     "Open bush country, then an elephant crossing a track in front of a stopped "
     "white vehicle, then a line of safari vehicles waiting on a rise with an "
     "impala in the foreground"),
    (54.75, 63.03, "elephants-and-lions", "Elephants, and lions again",
     "Elephants bathing and rolling in a brown river, a lion and lioness on their "
     "rock, then a line of elephants walking through dry grass"),
    (63.03, 74.11, "the-river-and-who-comes", "The river, and who comes to it",
     "Elephants spread along a wide river below dry hills, a giraffe browsing the "
     "top of a thorn tree, and zebra and wildebeest packed together at a waterhole"),
    (74.11, 82.05, "nairobi-from-the-park", "Nairobi, from the park",
     "A giraffe standing in dry scrub, zebra at a waterhole, then a giraffe "
     "browsing with the towers of central Nairobi standing on the horizon behind it"),
    (82.05, 91.19, "traffic-and-water", "Traffic, and the water",
     "A busy street under lines of bunting with tricycle taxis and motorcycles "
     "threading through traffic, then the Lekki-Ikoyi Link Bridge from directly "
     "overhead, then a waterfront city seen from the air"),
    (91.19, 99.07, "market-and-procession", "Market day, and a procession",
     "Stalls of fruit and vegetables piled under a market roof with shoppers "
     "moving between them, then men in white robes carrying instruments in "
     "procession, then a city from the air"),
    (99.07, 104.27, "in-the-pot", "In the pot",
     "Close on a large pot over a flame, a hand turning meat and pepper sauce "
     "through it with a wooden spoon, a second pot and a basin alongside"),
    (104.27, 111.04, "lagos-mid-morning", "Lagos, mid-morning",
     "Lagos from the air in the middle of the morning, low blocks and office "
     "towers running back from a green highway verge towards the sea"),
    (111.04, 119.42, "lekki-bridge", "The Lekki bridge",
     "The Lekki-Ikoyi Link Bridge in Lagos seen from the air: a single white "
     "pylon with its cable stays fanning out over the lagoon, traffic crossing "
     "in both directions, and the streets and towers of Ikoyi behind it"),
]

TRACK = {
    "slug": "film",
    "label": "The film",
    "line": "two minutes, end to end",
}


def poster(clip_path, slug, log=print):
    """The piece's own first frame, so the still and the clip are the same shot.

    A poster from anywhere else is a small lie: it is what a visitor looks at
    while the file is arriving, and if it shows a different place than the one
    about to play, the frame jumps when it does.
    """
    exe = cutter.ffmpeg()
    import subprocess
    out = os.path.join(POSTERS, "film-%s-1280w.jpg" % slug)
    r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y",
                        "-i", clip_path, "-frames:v", "1", "-q:v", "4", out],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("could not take a poster from %s:\n%s"
                         % (clip_path, r.stderr[-400:]))
    return "/images/uploads/" + os.path.basename(out)


def covers():
    """Every second of the film is in exactly one piece, or this is not true."""
    gaps = []
    for a, b in zip(PIECES, PIECES[1:]):
        if abs(a[1] - b[0]) > 0.001:
            gaps.append("%.2f -> %.2f" % (a[1], b[0]))
    return gaps


def run(src, mb=MB, keep_audio=False, log=print):
    gaps = covers()
    if gaps:
        raise SystemExit("the pieces do not join up: " + "; ".join(gaps))
    shots = []
    for i, (a, b, slug, say, alt) in enumerate(PIECES):
        name = "film-%02d-%s" % (i + 1, slug)
        log("\n[%2d/%d] %s  %.2f -> %.2f  (%.2fs)"
            % (i + 1, len(PIECES), say, a, b, b - a))
        cutter.cut(src, name, seconds=b - a, start=a, mb=mb,
                   keep_audio=keep_audio, log=log)
        clip = "/videos/%s.mp4" % name
        shots.append({
            "photo": poster(os.path.join(ROOT, "videos", name + ".mp4"), slug),
            "photo_w": 1280, "photo_h": 720,
            "alt": alt, "say": say, "clip": clip,
        })
    return shots


def place(shots, log=print):
    """Put the film in as its own track, ahead of the three photograph tracks."""
    with open(MOTION, encoding="utf-8") as fh:
        data = json.load(fh)
    tracks = [t for t in data.get("tracks") or [] if t.get("slug") != "film"]
    track = dict(TRACK)
    track["shots"] = shots
    data["tracks"] = [track] + tracks
    with open(MOTION, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    log("\nplaced %d pieces as the '%s' track, ahead of %d photograph track(s)"
        % (len(shots), TRACK["slug"], len(tracks)))
