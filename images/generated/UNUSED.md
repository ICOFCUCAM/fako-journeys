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
