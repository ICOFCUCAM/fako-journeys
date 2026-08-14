# Two generated images, kept and not used

`unused-savanna-walker-1024w.jpg` and `unused-lodge-waterhole-1536w.jpg` arrived
in `images/uploads/` as `Park.jpeg` and `Elephants.jpeg`. They are not
photographs, and they are here rather than there because everything in
`images/uploads/` is served with `data-provider="upload"` and read by a visitor
as a picture of somewhere real.

What gives them away, in case the next person wants to check rather than take
this on trust:

**`unused-savanna-walker-1024w.jpg`** — 1024×1024, which is a generation size and
not a camera's. Both of the walker's hands are malformed. The tents at the left
and right edges dissolve rather than end. The elephants behind her do not agree
with each other about how many legs an elephant has, and the two nearest share an
outline.

**`unused-lodge-waterhole-1536w.jpg`** — 1536×1536, same reasoning. The near
elephant's tusks emerge from the wrong side of its trunk and its front legs merge
into the decking rather than stand on the ground behind it. The pool's edge is
geometrically impossible: it is simultaneously an infinity edge and a raised
lip, and the water meets the horizon at two different heights.

They are kept because they belong to whoever uploaded them, and it is not this
repository's business to delete somebody's file. They are unused because of what
the site already says about generated pictures, in `tourism/people.json` and in
every commit that has removed a claim the files could not support: a visitor
cannot tell the difference until they arrive, and the second of these is
specifically a photograph of a lodge that does not exist, on a site where the
next button says "begin a journey".

A generated image is allowed on this site. It has to live here, carry
`data-generated="true"`, and not depict a real named place. A fabricated luxury
lodge shown to somebody deciding where to spend money fails the last of those in
spirit even if it names nowhere, so neither of these is placed.

The seven photographs that arrived in the same upload are in `images/uploads/`
under their subjects, and are used.

---

# Nine more, from the upload of 14 August

They arrived as `African Royal Courtyard Celebration.png` and eight files named
`ChatGPT Image Aug 14, 2026, ...`, and they are here rather than in
`images/uploads/` for the reason at the top of this file: everything in uploads
is served with `data-provider="upload"` and read as a picture of somewhere real.
They have been converted from PNG to JPEG and renamed for what they show, which
took 25 MB down to 3 MB and made the names usable in a URL.

The rule this file already sets is the one applied to them: **a generated image
is allowed, it lives here, it carries `data-generated="true"`, and it does not
depict a real named place.** Measured against that:

**`gen-monument-flag-1536w.jpg` fails it outright.** It shows a national
monument — three white concrete fronds rising from a plaza with fountains — with
what reads as the Cameroon flag flying beside it. The monument does not exist.
The flag is what makes it fail: it fixes the picture to a real country, so a
visitor deciding where to go is being shown a landmark they can never be taken
to. This is the same fault as the fabricated lodge above, and worse, because a
landmark is a thing people put on an itinerary.

**`gen-alpine-peaks-1536w.jpg` fails it in substance.** Jagged snow-dusted
spires above a cloud inversion, with walkers on a path below. No mountain in any
of the 22 countries looks like this. Mount Cameroon is a broad volcano and the
Mandara spires are bare volcanic plugs in dry farmland — both are on this site as
photographs, and both would be a disappointment next to this. It names nowhere,
so it passes the letter of the rule and not the point of it.

**The other seven name nowhere and depict nowhere in particular** — a city street
at dusk, a reef beach, a food stall, a sea stack, a coastal city, a crater lake,
a courtyard celebration. By the rule they could be used, labelled, wherever the
page is illustrating an idea rather than promising a place.

None of them is placed, and that is a decision rather than an oversight. Every
image slot on this site today sits under a caption that says where it is —
that is what `build.py placements` lists — so there is currently nowhere for a
picture that has to be captioned "nowhere in particular". If a section is built
that illustrates rather than promises, these are the files for it, and the two
above are still not.

The eighteen photographs that arrived in the same upload are real, and eight of
them are in `images/uploads/` at web sizes under their subjects. The other ten
are VLC frame grabs of shots that are now video pieces in `videos/`.
