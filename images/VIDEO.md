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
