# Interface direction

The public website and analysis workspace serve different purposes. This
direction incorporates the owner's October 4 review and supersedes the earlier
landing-page copy and repeated feature-card layouts.

## Public website

The [LP design policy](lp-art-direction.md) (Japanese, rewritten 2026-11-25) is
the canonical standard for the landing page. It fixes only the purpose, honesty
rules and quality floor; colour, type, layout and material follow the current
expressive direction stated there and are judged by the owner on the rendered
page. Earlier visual rules (the light palette, photoreal footage as the lead,
the fixed hero, one text colour) are kept as a
[record](archive/lp-art-direction-2026-11.md) and no longer bind the page.

Functional requirements that stay with every redesign:

- Primary action: **ダウンロード**. Product examples and setup information have
  separate, direct links. The header wordmark returns to the top of the page.
- Keep installation requirements, supported inputs and data retention
  accessible before download.
- Show actual public-demo outputs. Never invent results, independent
  replicates or a customer quote to complete a composition.
- Keep development status, evaluation records and asset provenance in the
  documentation, not as badges or disclaimers on the page. Credit third-party
  assets as described in the [asset register](oss.md).

## Analysis workspace

The October 4 acceptance is superseded by the owner's October 5 review: the
workspace is redesigned as one image-centred workspace described in
[workspace redesign](workspace-redesign.md). The principles below still apply.

- Use operation names, field labels and concise instructions. Do not put
  advertising headlines or emotive copy in forms, panels or error messages.
- Write Japanese UI text as research software does: short noun headings and
  buttons, states as 「項目：値」, one-sentence reasons, no conditional coaching,
  stacked negatives or explanations in parentheses (UC-01–UC-07 in the
  [result-statement requirements](drafts/results-and-demo-story/requirements.md#e-ui-の文言uc)).
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
