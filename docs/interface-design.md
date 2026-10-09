# Interface direction

The public website and analysis workspace serve different purposes. This
direction incorporates the owner's October 4 review and supersedes the earlier
landing-page copy and repeated feature-card layouts.

## Public website

- Preserve the hero: **Get your microscopy publication-ready.**
- Lila is the primary visual reference; GraphPad supplies the information
  hierarchy. Lead with the researcher's ambition, then reduced repetitive work,
  accessible analytical decisions and communication through a figure. Feature
  categories such as "images and measurements" are not benefit headlines.
- Dark and Blue are mandatory art direction: deep midnight-blue space,
  saturated blue illumination, strong dark/light contrast and generous scale.
  Charcoal alone, a blue button or a background gradient does not satisfy this
  direction. Reserve large white surfaces for real application screens and
  exported figures, rather than alternating pale explanatory panels.
- Use Blender for the hero's authored organic form, surface detail, materials
  and static render; use Three.js for its browser scene, lighting and motion.
  On desktop and portrait tablet, compose one complete subject beside or below
  the exact hero copy, clear of the navigation. Keep the copy and actions in
  the first viewport, including short windows. On mobile (up to 760 px), use
  the owner-requested integrated composition: a full-height cell background
  behind the copy, with intentional cover cropping for visual impact. Mobile
  copy and actions must still fit together in the first viewport.
  Avoid generic nested glass spheres, star fields and decorative particles.
  Record authored artwork separately from measured microscopy in provenance.
  A three-dimensional figure card made with CSS does not meet the 3D hero
  requirement. Reuse COMPASS renderer lifecycle and cleanup where applicable.
- Review the actual rendered silhouette, texture, lighting and composition
  before calling the hero complete. Keep a matching static fallback, respect
  reduced motion and pause rendering offscreen; performance work must preserve
  the intended visual quality rather than remove the requested art direction.
- Use the actual photography, composition, whitespace and typography to carry
  the visual identity. Do not explain the intended atmosphere in the copy.
- Below the hero, take Lila's design and emotional pull, not its grid
  (`lp-sections.module.css`): no section titles or English labels. Each
  section opens with its own first sentence set large (weight 400), followed
  by body text in the same single column; pictures use wide rounded panels,
  and a pale panel marks the exported figure and the download. The owner's
  story has no title and is set in one size throughout. All text uses one
  colour (one on dark, one on light): no faded or translucent text, no
  scroll-linked dimming, no tilted or animated figures. Japanese lines break
  at phrase boundaries; no coloured or glowing words inside running text.
- The header wordmark returns to the hero (`#top`) on the landing page.
- Primary action: **ダウンロード**. Product examples and setup information have
  separate, direct links.
- Alternate full-width photography, portrait compositions, readable product
  screens and the exported figure. Avoid a sequence of identical feature cards.
- Keep development status, scientific evaluation records and asset provenance
  in the relevant documentation. Do not add development badges, stock-photo
  disclaimers, defensive captions or unsupported endorsements to the page.
- Keep installation requirements, supported inputs and data retention
  accessible before download. These are functional product information.
- Show actual public-image measurements and outputs. Never invent results,
  independent replicates or a customer quote to complete a composition.
- Use self-hosted Inter and Noto Sans JP. Reuse the owner's COMPASS components
  with source attribution; see [the asset register](oss.md).

Visual references: [Lila](https://www.lila.ai/),
[COMPASS](https://compass-official.pages.dev/),
[Yuto Matsui](https://yuto-matsui.com/) and
[GraphPad](https://www.graphpad.com/). Their photographs, fonts and claims are
not substituted for Cytellect's own assets or capabilities.

## Analysis workspace

The October 4 acceptance is superseded by the owner's October 5 review: the
workspace is redesigned as one image-centred workspace described in
[workspace redesign](workspace-redesign.md). The principles below still apply.

- Use operation names, field labels and concise instructions. Do not put
  advertising headlines or emotive copy in forms, panels or error messages.
- Keep image, region tools, settings and measurements visually distinct.
- Put region-editing controls near the image and expose the next available
  operation without requiring a long explanatory paragraph.
- Put extended method explanations in expandable help. Preserve required
  confirmations, invalid input feedback, exclusion reasons, stale-result state
  and protection of unsaved changes.
- Presentation wording does not revise the scientific contracts. Planning
  findings retain their identifiers, references and saved answers; measurements
  and statistical results remain owned by the API.

## Review and delivery

Review desktop, tablet and mobile as separate compositions. Check visible
type, image crops, figure readability, menu focus, motion preferences and media
failure fallback. A static page must remain usable without animation.

Keep original-pixel calculations, mask identity, experimental-unit handling
and numerical replay checks independent of visual review. Publish code through
PR, passing checks and main, followed by Vercel's Git deployment. A downloadable
package has its own installed-copy acceptance and immutable identity.
