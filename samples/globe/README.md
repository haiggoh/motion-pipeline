# Sample project — globe opening

Neutral copy, no client logo, no client assets. Scaffold it into a project:

    cp -r samples/globe projects/my-globe
    # then: set scheme.json (menu step 1), run the generator, render

The globe graphic is Natural Earth 110m (public domain) via world-atlas (ISC),
orthographic projection by `motion_pipeline/graphics/globe.js` (pure function of time).
