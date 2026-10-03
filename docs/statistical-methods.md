# Statistical Methods documents

New worker-generated descriptive and generic-region comparison outputs identify
their document template as
`methods_template={"id":"cytellect-statistical-methods","version":"1.0.0"}`.
This is a document protocol, distinct from the measurement, inference, figure and
enclosing reproducibility-bundle Methods versions. It changes no pixels,
selection, statistics, caption or independent-unit definition.

The feature is source implementation pending its release checks; it is not an
update to an already downloaded immutable local package. Biological validation
with private images and evaluation by researchers remain separate open gates.

## Saved facts in readable prose

The selected metric, region and actual recorded marker/stain are described along
with the applicable equation. Native corrected intensities retain their sign;
the RGB compatibility recipe instead clips negative corrected pixels to zero
and retains its recorded measurement grid. Compatibility high-intensity objects
are not automatically biological nucleoli. Area-only output explicitly states
that intensity, saturation and background correction were not measured. A
numerical-assay description does not invent an image measurement.

Descriptive Methods report saved observation/field counts and the partition of
excluded, gate-unselected and missing outcomes. They do not assign independent n
or inferential intervals. GFP selection rules are retained where applicable;
varying field thresholds remain in the complete selection ledger. Failed-field
observation counts remain unknown, rather than zero.

Comparison Methods name the test actually saved in the result: two-sided Welch
for independent groups or a two-sided paired t-test for declared matched units.
They retain the unit/pair definition, independent n versus region/field/sample
counts, field-median → sample-mean → unit-mean aggregation, A-minus-B direction,
the complete Holm family and pointwise 95% intervals. Group-mean t intervals and
the selected contrast's Welch/paired-difference interval are distinguished.
Methods never claim the recorded design or acquisition review establishes
biological independence automatically.

Complete row-level audit data remain in the existing CSV files and
`figure-data.json`. The document references those sources instead of embedding
every observation's JSON. File hashes remain in the source JSON/output or bundle
manifest. No source row is removed to shorten the document. Unrecorded microscope
settings, dye identity, randomization, blinding, sample-size rationale and other
biological facts must be completed by the author; the template does not infer
them.

## Historical output and replay

An absent `methods_template` means the original historical document body. Its
absence is retained when serializing the old manifest. An explicit null, unknown
ID/version or extra template text is rejected, not treated as historical.
New worker creation selects the new template explicitly. Library renderers keep
the historical default so older export callers cannot silently opt into new
prose.

Export and replay dispatch using the **recorded** figure metadata. New paginated
exports continue copying verified original artifact bytes. Single figures and
comparisons retain their recorded template when exported or separately replayed.
The outer legacy bundle Methods embeds the same child's document version.
Historical text is not retroactively corrected; a newly generated document is
identified separately. Replay never overwrites the original artifact.

Numerical protocols and source hashes retain their existing meanings. The new
template marker is present in figure metadata and `figure-data.json`, not in the
scientific request or calculated measurement table. New paginated validation
also verifies the Methods body against its saved source and document version;
merely replacing its bytes and updating the file hash cannot change its claims.

## Bounded verification

`tests/test_statistical_methods.py` covers the two-pixel clipping/sign reference,
selected raw/corrected/area equations, actual independent/paired test wording and
n, unknown source/template rejection, numerical-table scope, selection
missingness and bounded prose size with a complete 20,000-observation ledger.
`tests/test_statistical_methods_export.py` covers actual original/archived/replayed
Methods bytes, historical/current single and paged paths, parent/child document
agreement, area-only output and altered Methods with a recomputed file hash.
These checks concern reporting, provenance and software behavior; they do not
establish journal acceptance, biological applicability or human usability.
