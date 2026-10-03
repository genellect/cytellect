# Analysis planning — version 2.0.0

Planning translates an explicit measurement question into supported workflow
candidates. It is deterministic guidance based on known choices and cited
methodological literature. It runs no image analysis, statistics, model selection,
LLM request or code supplied by a user. A planning answer is not evidence that
an image, region definition, acquisition setting or experimental design is valid.

## Canonical input and decision

`PlanInput` accepts only `format="cytellect-analysis-plan"`, `version="2.0.0"`
and strict `PlanAnswers`. Unknown fields and values are rejected. No file paths,
channel names, experiment labels, free text, URLs, external guidance, code or
executable recipe parameters are accepted in this input.

The choices distinguish:

- Measurement: area, mean intensity, integrated intensity or the existing NCL
  nucleoplasm/nucleolar intensity ratio. Unknown remains unknown.
- Structure: nucleus, nucleolus, nucleoplasm or a custom region.
- Definition: manual regions, imported labels, a confirmed nuclear-stain-based
  candidate or the existing NCL-enrichment definition.
- Actual measured signal class, native 2D input, nuclear-stain availability,
  background availability, acquisition comparability, intended comparison,
  treatment allocation and GFP selection intent.

`evaluate_plan(input)` returns a strict `PlanDecision` with status
`planning-only-not-adopted`, supported candidates, comparison intent, questions,
limitations, next decisions and a fixed primary-source reference registry.
`snapshot_plan(input)` returns `PlanSnapshot(input, decision, sha256)`. The SHA-256
covers canonical UTF-8 JSON of the full validated input and recomputed decision.
Order of JSON object keys does not change it. `validate_plan_snapshot(snapshot)`
recomputes the decision and hash rather than trusting saved guidance.

All unspecified answer fields default to `unknown` except `gating="none"`.
An empty plan has no executable candidate. Inputs from the old 1.0.x guide are
rejected for adoption with `planning_legacy_requires_review`; they do not specify
the measurement and definition needed by version 2. They may remain unadopted
notes in the interface, but they are never automatically upgraded into an
executable plan.

## Supported candidate boundary

| Stable candidate ID | Existing execution path | Measurement choices |
|---|---|---|
| `regions-manual` | Generic manual regions | Pixel/physical area, raw/corrected mean or sum |
| `regions-imported` | Generic imported labels | Same generic measurements |
| `regions-nuclei` | Fixed nuclear StarDist recipe | Same generic measurements in nuclei |
| `legacy-gfp-nuclear` | Existing native nuclear GFP recipe | Exact existing nuclear area or GFP mean/sum IDs |
| `legacy-ncl` | Existing native NCL recipe | Exact existing nuclear/nucleolar/nucleoplasmic area, NCL mean/sum, or compartment ratio IDs |

The term `legacy` in candidate IDs distinguishes the earlier product workflow;
these candidates use native images. The legacy RGB compatibility recipe is not
an automatic planning candidate. NCL compartment ratios never map to the older
whole-nucleus/high-intensity-region release metric.

Each candidate supplies its recipe ID/version, workflow, source, selector source,
allowed metric IDs, required channel roles and tasks for actual review. It has
no actual image/channel ID, threshold, ROI, mask or confirmation flag. A role list
does not require that every role have a distinct acquired channel: a single
nuclear plane can define nuclear area, for example. The adoption layer must
resolve the roles against real registered channels, retain the source identity
and explain dependence between defining and measuring signals.

Area does not require a measurement marker or a nuclear stain for a manual or
imported region. Physical area stays an option requiring actual calibration;
the plan never generates micrometre values. Raw and background-corrected intensity
remain separate metric choices. Integrated intensity is a pixel sum and is not
concentration. Current execution paths still require a reviewed background ROI
per measured channel, including workflows that later display area.

Nuclear detection requires a reported nuclear stain and applies only to nuclei.
It does not infer nucleoli or whole cells. Any measured marker can remain itself
in the generic path. A GFP nuclear plan without gating may choose either generic
or the existing GFP path; selection of the path is explicit. GFP gating is offered
only through the existing GFP/NCL workflows. The NCL path requires actual NCL for
its definition and actual GFP if GFP gating is requested. A generic gating request
cannot silently execute without its requested selection.

RGB, unsupported Z/T input and missing structural choices produce no candidate.
Background and acquisition questions may remain alongside a candidate because
the original image and actual experiment still need review. Candidate availability
does not bypass those execution gates. NCL-enrichment plans retain the limitation
that NCL redistribution can change the region used to measure NCL.

## Comparison is an intention, not a confirmation

Independent or paired comparison intentions are emitted only when the planning
answer states independently allocated biological units. Cells or fields from
one sample do not become independent replicates. Unknown allocation yields an
undetermined inferential intention while descriptive measurements remain allowed.

Even an affirmative answer produces no `independent_units_confirmed`, pair IDs,
conditions, negative-control identity or acquisition confirmation. Those must be
recorded using the actual source metadata and reviewed comparison contract.
The normal failure, missingness, pairing, batch, saturation and Holm-family gates
remain in force. No statistical threshold is tuned to obtain a smaller p-value.

## Handoff and source preservation

The API and workspace layer own explicit adoption, authorization and retention.
They may save the server-generated snapshot and selected stable candidate, then
bind actual recipe, metric and channel choices to an immutable analysis revision.
Changing an adopted choice must be visible and produce a new record; existing
results must keep their earlier source. Export and Methods should retain the
planning origin and actual adopted values separately.

The public browser guide may reproduce these deterministic rules for an offline
preview. Adoption must use the server's recomputed decision. A private plan file
contains the strict input; it does not cause the server to trust a submitted
decision, URL, code or hash. Cross-origin transfer must not put research choices
into URLs, public logs or persistent browser storage. Plan information attached
to a workspace follows its private access and expiry controls.

### Actual-source adoption protocol 1.0.0

`adopt_plan` creates an `AdoptedPlan` only for a candidate in the recomputed
decision. The adoption has a timestamp and `scope="planning-intent-only"`.
`PlanResolution` explicitly supplies the plan hash, candidate, actual metric and,
for an intensity metric, actual channel. Pixel/physical area has no intensity
channel selector. `resolve_plan` validates the real recipe and registered channel
identities rather than filling missing roles from planning answers. Automatic
nuclear analysis still requires the real defining channel and its explicit
nuclear-stain confirmation. Physical area requires confirmed finite calibration;
the older acquisition contract additionally requires a finite positive scalar
pixel size with a representable square. Neither an absent role list nor a
truthy string or integer substitutes for an actual confirmation.

The selected raw/corrected mean or sum remains its exact metric ID. NCL
compartments retain their distinct IDs, and the native nucleoplasm/nucleolar
ratios cannot become the older release index. A recipe, region source, NCL region
definition, measurement or GFP selection change requires a strict boolean
acknowledgement and is recorded in `changes`. That acknowledgement never permits
an unsupported workflow, arbitrary recipe, missing channel or invalid calibration.
The selected generic channel's actual label and stain are preserved; the helper
does not interpret an arbitrary label as proof that it is GFP, NCL or a nuclear
stain. Background, quality review and comparison validation remain separate
execution gates.

The resolved adoption is saved with a canonical `resolution_sha256` in the
immutable revision, alongside the full actual recipe and field snapshot.
`validate_revision_plan` recomputes the adoption against those saved sources,
and rejects a changed decision, selection or actual channel descriptor. Methods
distinguish planning intent from actual-source review and state that later
statistical requests retain their own metric and design. Planning responses never
generate independent units, pairs, acquisition comparability confirmations or
negative-control confirmations.

## Evidence

`tests/test_planning.py` independently checks the supported/unsupported scientific
decision boundaries, actual-review separation, legacy rejection, exact existing
metric IDs, deterministic hashes and tamper rejection. The enum-only cases in
`fixtures/planning/decisions-v2.json` support Python/TypeScript parity; regenerate
with `python scripts/generate_planning_fixtures.py` and check with `--check`.
The same command generates `apps/web/src/lib/planning-catalog.json`, containing
the fixed references, finding text and static candidate attributes. The browser
uses this catalog instead of copying the scientific explanations by hand.
Metric lists, channel-role tasks and the candidate rules remain decision-dependent
and are checked against the parity cases. Parity does not establish scientific
suitability.

`tests/test_plan_adoption.py` supplies independent actual-source boundary cases:
all native NCL mean/sum and compartment-area mappings, GFP sums, the two native
ratios, actual generic marker preservation, explicit raw/corrected choices,
missing or unconfirmed channels, invalid calibration, unsupported recipes,
strict acknowledgements, source/decision tampering, and refusal to turn plan
answers into experimental or acquisition evidence. These are computational and
contract checks, not biological validation or observed user success.

[Senft et al.](https://doi.org/10.1371/journal.pbio.3002167) motivates connecting the
measurement question, acquisition, analysis and interpretation.
[Waters](https://doi.org/10.1083/jcb.200903097) supports acquisition and fluorescence
measurement cautions; [Kodiha et al.](https://doi.org/10.1186/1471-2121-12-25)
supports explicit nucleolar region definitions. Experimental units and figures
follow [Lazic et al.](https://doi.org/10.1371/journal.pbio.2005282) and
[SuperPlots](https://doi.org/10.1083/jcb.202001064); reporting guidance follows
[Schmied et al.](https://doi.org/10.1038/s41592-023-01987-9).
These are methodological grounds for the design, not evidence of Cytellect user
success, time savings or validated biological conclusions. Human usability and
private-data validation remain separate gates.
