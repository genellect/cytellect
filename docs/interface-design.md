# Interface direction

The public website and analysis workspace serve different purposes. This
direction incorporates the owner's October 4 review and supersedes the earlier
landing-page copy and repeated feature-card layouts.

## Public website

The owner's October 22 direction supersedes the earlier dark-blue art direction,
the cell-sculpture hero and the title-less essay layout. The canonical design
record, section by section, is [the LP design record](lp-optical-preview.md).

- Keep the light optical direction: light stone surfaces over the moving
  Blender/Three.js optical space (`OpticalHero`, `optical-scene-engine.ts`).
  The 3D space is the atmosphere, not the subject: no cell photographs, swirls,
  microscope or paper diagrams in the background. Its static poster is the
  fallback for reduced motion and WebGL failure.
- Follow the structure of leading product sites: the product in motion
  immediately, one promise, a sequence of product moments, a band of verified
  numbers, a way to try it live, trust, the offering and a final call to
  action. Atmosphere and intuitive understanding matter as much as data.
- Preserve the hero: **Get your microscopy publication-ready.**, with strong
  Japanese sub-copy. Marketing copy may be bold and aspirational
  (「画像をアップロードするだけで、論文の図まで。」), but every number and every
  scientific claim must be a verified fact with a public source.
- Primary action: **デモを触る** (`/demo`). Secondary: the Windows download.
  Product moments deep-link into the demo (`/demo?step=image`, `statistics`,
  `figure`). Keep installation requirements, supported inputs and data
  retention one click away from the download.
- Show the real product and real public microscopy only: recorded product
  footage, captures from public images and exported figures. No stock
  photography, generated cells, invented results, customer quotes, team
  sections or unsupported endorsements.
- Content sits on rounded light sheets that float over the 3D space; one dark
  sheet carries the numbers. Section headings are set in deliberate lines at
  phrase boundaries. Use Inter and Noto Sans JP, self-hosted. Body text may use
  the secondary ink colour; no glowing or coloured words inside running text.
- The AI illustration uses the workspace's own UI style and is labelled as an
  example. It shows settings, never results.
- Motion: one hero entrance, the looping product clip and the 3D space. Clips
  play only on screen, never start under reduced motion, always offer a
  pause control, and fall back to the same still on failure. Phones show a
  still when the clip is not legible at that width.
- The header wordmark returns to the hero (`#top`) on the landing page.
  "About the Developer" lives in the footer and the mobile menu.
- Keep development status, evaluation records and asset provenance in the
  relevant documentation and `apps/web/public/marketing/provenance.json`.

Visual references: [Linear](https://linear.app/), [Stripe](https://stripe.com/),
[Vercel](https://vercel.com/), [Benchling](https://www.benchling.com/),
[BioRender](https://www.biorender.com/), and for light, space and typography
[Lila](https://www.lila.ai/). Their imagery, fonts and claims are not
substituted for Cytellect's own assets or capabilities. Reuse the owner's
COMPASS components with source attribution; see [the asset register](oss.md).

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
