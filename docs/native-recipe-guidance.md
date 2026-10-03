# Nuclear-recipe channel guidance

The image workspace checks the selected recipe against registered channel roles
before submitting an analysis. It never infers a stain or recipe from a filename,
removes an incompatible field, or changes a saved analysis to make the request fit.
The researcher selects the recipe explicitly. Channel compatibility alone does
not confirm acquisition quality, backgrounds or biological suitability.

The channel rules mirror `required_channel_roles` in the scientific contract:

| Recipe | Required acquired roles |
|---|---|
| Native NCL | Nuclear stain and NCL; also GFP when selection is enabled or an upper bound is present, including zero/negative bounds |
| Nuclear GFP | Nuclear stain and GFP |
| Historical RGB compatibility | Nuclear stain, NCL and GFP, with the registered RGB compatibility input mode |

A low nuclear-stain nucleolar definition still measures NCL, so it requires NCL.
An unused GFP threshold alone does not require a GFP channel. The historical
`dapi` role is displayed as nuclear stain; it does not establish the acquired dye.

The representative trial checks only the selected field. Batch analysis checks
all registered fields, including explicitly excluded fields, just as the API does.
An existing-mask update checks the immutable revision snapshots, omitting only
the whole-field exclusions the researcher has explicitly specified. Nucleolar
re-detection checks all retained snapshots when sending changed conditions.
Missing snapshots fail closed. The API's older three-role fallback applies only
when an existing snapshot/input record lacks the `channel_roles` property.

Each action shows its own incompatibility reason. A compatible current field
does not make an incompatible batch or saved revision eligible. Saved recipes,
measurement tables, review state and old results stay unchanged until an accepted
explicit operation creates a new revision. The server remains authoritative.

Negative-control references must also belong to the submitted scope. Previously
selected controls remain inspectable even after selection is disabled; an explicit
clear action removes them and resets their confirmation. No negative-control
identity or confirmation is inferred from a group name.

Verification uses pure boundary cases and a separate browser test for published
BBBC013 DRAQ/FKHR-EGFP inputs plus known-pixel two/three-channel fixtures. The
published-image case verifies recipe choice and immutable results, not biological
comparability or detector accuracy. Human usability evaluation remains separate.
