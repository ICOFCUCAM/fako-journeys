# Putting a clip in the window

The section under the hero is built for footage and has none. Every shot in
`tourism/motion.json` carries a `clip` and every one is `null`, so today the
frame cross-fades photographs. Fill one in and that shot plays instead, with no
other change to any file.

## Where the files go

`videos/` at the repo root, named for the subject the way the photographs are:

    videos/city-lagos-marina.mp4
    videos/wild-bwindi-gorillas.mp4
    videos/culture-foumban-casting.mp4

## If your file is too big to upload

GitHub's web uploader stops at 25 MB, and a clip off a camera or a stock site is
routinely well past that. Don't fight it — a 25 MB file was never going in the
repository anyway. Git keeps every binary forever, so a master committed once
costs its full size in every clone and every deploy from then on, in exchange
for the 2 MB that is actually served.

Put the master somewhere the repository can reach without swallowing it, and
commit only the cut:

**A GitHub release asset** takes up to 2 GB and does not enter the git history.
On this repository: Releases → Draft a new release → tag it `footage` → drag the
file into the attachments box → publish. Then

    python3 tools/tourism/build.py cut \
      https://github.com/ICOFCUCAM/fako-journeys/releases/download/footage/lagos.mp4 \
      --name city-lagos-marina

Any direct link works the same way — Drive, Dropbox or WeTransfer, as long as the
URL serves the file itself rather than a preview page. The master lands in
`incoming/video/masters/`, which is gitignored.

**Or hand it over locally**, if you have the file on the machine already:

    python3 tools/tourism/build.py cut incoming/video/masters/lagos.mp4 \
      --name city-lagos-marina

Either way what gets committed is one file in `videos/`, around 2 MB.

### What the cut does

Strips the audio track, scales to 1280 wide, trims to ten seconds and two-pass
encodes to a bitrate computed from the budget — then checks the result and
**deletes it if it is still over**, rather than writing it and letting somebody
find out from a phone bill. Useful flags:

    --seconds 8         how much to keep (default 10)
    --start 4.5         where in the master the good part begins
    --width 960         narrower, when 1280 will not fit the budget
    --mb 1.5            a tighter ceiling

If it refuses, take less: `--seconds` first, then `--width`. Ten seconds of a
still-ish landscape fits in two megabytes comfortably; ten seconds of a crowded
market at dusk may not, because there is more moving in every frame.

## About a voiceover

**Short answer: the window does not want one, and adding one here would not
work the way it sounds like it should.**

Three things stand in the way, and none of them is about effort.

**A browser will not play sound you did not ask for.** Chrome, Safari and
Firefox all block audible autoplay. A video may autoplay *muted*, which is what
this one does, and the moment it carries a voice the browser keeps it muted
anyway until the visitor clicks something. So a narrated window is a silent
window for almost everyone who sees it — the narration would be paid for in
bytes by every visitor and heard by the few who go looking for an unmute button.

**The window is scenery, not a programme.** It sits directly under the hero
while a visitor is still deciding whether to stay, and they are reading the
headline next to it. A voice competes with the words it was put there to
support. That is also why it loops silently and why every shot carries a
caption: the caption is the narration, and it works with the sound off.

**And the film is sixteen files.** A voice that runs across a cut has to be one
continuous stream. Between one `<video>` ending and the next starting there is a
gap the browser makes no promise about — tens of milliseconds on a fast
connection, up to a second on a slow one — so a sentence spanning a boundary
would be audibly chopped. Sixteen pieces and one flowing narration cannot both
be true.

### If you want a narrated film anyway — and there is a good case for one

Give it its own place rather than putting it under the hero. A documentary piece
is something a visitor *chooses*: a still frame, a play button, and then two
minutes with sound, full width, nothing competing. That is a different thing
from the window and a good thing to have.

It needs to be **one continuous file**, not the sixteen pieces, because of the
gap problem above. Everything for it already exists:

    python3 tools/tourism/build.py cut incoming/video/masters/narrated.mp4 \
      --name the-film --seconds 120 --mb 12 --keep-audio

`--keep-audio` keeps the voice (AAC in the mp4, Opus in the WebM) and pays for
it out of the same byte ceiling rather than on top of it.

### What has been organised so the voice does not break anything

- **The cut is regenerable, not hand-made.** The sixteen boundaries live as
  timecodes in `tools/tourism/film.py`, not in whatever file happened to be
  passed in. Hand a *narrated* master to `build.py film` and the same sixteen
  pieces come out with the voice in them, same boundaries, same captions, one
  command. Nothing is re-cut by hand and no caption moves.
- **Boundaries are the film's own cuts**, and consecutive pieces join exactly —
  each one ends where the next begins, with no gap and no overlap. That is
  checked (`build.py film --list` reports it, and the suite fails if they stop
  joining). It is the condition that makes a continuous narration survive as
  well as it possibly can across separate files, if you ever do want to try.
- **Audio is a switch, not a rebuild.** `--keep-audio` on `cut` and `film`.
- **The master never enters git**, so re-cutting from a narrated version later
  costs nothing that has already been spent.

If you would rather the voice go in the window regardless, say so — it is a
one-line change to the generator. It will be muted for most visitors, and that
is the trade you would be making.

## What the page needs from a file

- **MP4, H.264, AAC or no audio track.** The player is muted and looping, so
  audio is never heard; a file with no audio track is smaller and is preferred.
- **1920×1080 or 1280×720.** The frame is 16:9 and about 690px wide at 1440, so
  1080p is already more than it can show. Larger is only weight.
- **Under about 4 MB, and ideally under 2.** This sits directly under the hero.
  A visitor on a phone pays for it before they have decided to stay.
- **Six to twelve seconds, and it must loop cleanly.** The frame holds each shot
  for 5.2 seconds when it is a photograph; a clip is allowed its own length and
  hands on when it ends.
- **No burnt-in titles, logos, watermarks or handles.** One city photograph was
  already turned away for a TikTok handle across the frame.

## What to write in motion.json

Beside the shot, replace `"clip": null`:

    {
      "photo": "/images/uploads/city-lagos-1200w.jpg",
      "photo_w": 1200, "photo_h": 630,
      "alt": "…",
      "say": "Lagos",
      "clip": "/videos/city-lagos-marina.mp4"
    }

The photograph stays. It becomes the poster frame, which is what a visitor sees
while the file is still arriving and what they keep if the clip cannot play.
That is why a shot needs a photograph even once it has a clip.

## The one rule that matters

**A clip has to be of the thing its shot claims.** Generic African street
footage under a caption saying Lagos is the same fault as a generated photograph
of a real city — a visitor cannot tell, and finds out on arrival. If a clip is
good but you cannot say where it is, put it on a shot whose caption does not
name a place, or leave the photograph.

Footage from the operators beats stock for exactly this reason: somebody can say
where it was taken and when.

## Rights

Pexels, Pixabay, Mixkit and Coverr all licence free commercial use without
attribution, but each clip carries its own terms and some have model or property
restrictions. Whatever the source, the licence has to permit commercial use on a
site that sells travel. Record where each clip came from in the commit that adds
it, so the next person does not have to guess.

## Checking it

    python3 tools/tourism/build.py gateway
    python3 tools/tourism/tests.py

The suite already has `every clip named is a clip that exists`, which fails on a
path that points at nothing. It reports `0 clips` today.
