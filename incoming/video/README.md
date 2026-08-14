# Drop raw clips here

This is the staging floor for footage, not the shipping directory. Files here are
originals at whatever size they came; the finished clips live in `videos/` and
are what the page loads.

## Why not upload everything

Git keeps every binary forever. A clip committed here is in the repository's
history permanently, even after it is deleted — every future clone pays for it,
and so does every deploy. Fifty raw clips at 20–40 MB is well over a gigabyte
that never goes away in exchange for about 20 MB of finished video.

The window has twenty shot slots across three tracks and shows one clip at a
time. Three or four good clips per track is generous. Choose them first.

## What to send with each clip

Two things, in the commit message or a note beside the file:

1. **Where it was shot.** A clip goes on a shot whose caption names a place, and
   this site does not put a name on a picture it cannot stand behind. If nobody
   knows where it is, say so — it can still go on a shot that names nothing.
2. **Where it came from and under what licence.** Pexels, Pixabay, Mixkit and
   Coverr all permit commercial use, but individual clips carry their own terms
   and some have model or property restrictions.

## What happens next

Each clip is cut to the spec in `images/VIDEO.md` — 1280×720 or 1080p, H.264,
no audio track, six to twelve seconds, looping cleanly, under about 2 MB — and
written to `videos/`. The original is then deleted from here.
