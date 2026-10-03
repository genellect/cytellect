# Repeatable independent review

The [review registry](../validation/review-plan.json) connects scientific questions and primary references to existing independent test modules. It does not execute code from a publication or prescribe a new method. Fixed numerical fixtures establish arithmetic; published images establish a separate integration scope; biological annotations and actual researchers are separate acceptance evidence.

The existing Python CI run writes JUnit once. `scripts/scientific_review.py` consumes that result and emits a source-commit-identified receipt. It does not run another copy of the tests. A required module that is absent, failed, errored or skipped cannot pass. Failures elsewhere in the same run also prevent a green receipt. Raw test diagnostics and image/measurement content are excluded from this public summary. The hash of the test report links the receipt to its input without publishing that input.

Local example (write evidence outside the checkout):

```sh
uv run pytest tests -m "not fiji" --junitxml=/private/evidence/tests.xml \
  --scientific-collection=/private/evidence/collection.json
uv run python scripts/scientific_review.py --junit /private/evidence/tests.xml \
  --collection /private/evidence/collection.json \
  --output /private/evidence/scientific-review.json --source-commit FULL_40_CHARACTER_SHA
```

Add `--source-dirty` if testing uncommitted changes; a commit ID alone does not identify those changes. For a release, rerun required CI at the committed source. No receipt retrospectively changes an older release's evidence.

Registered checks cover original-pixel/compartment arithmetic, independent inferential calculations, figure/source consistency, public-input regression boundaries, generic API/edit/replay integrity, explicit nuclear initialization, generic-unit comparisons and planning-to-actual-source boundaries. The descriptive path stays noninferential. In the non-Fiji run, selected engine contract tests do not stand in for deselected real-Fiji cases. Public dataset regression tests do **not** download and run the real dataset. Real Fiji, independent ImageJ measurements, source hashes, accepted/rejected fields and exact preprocessing belong in their separate run reports. Biological validity is never inferred from a passing Python check.

Each review cycle must also inspect applicability: model training overlap, acquisition metadata, segmentation ground truth, experimental allocation, missing data, selection effects, cluster count and traceability. Preserve negative and inconclusive results. When a defect is found, first reproduce it independently, change the appropriate scientific protocol/version, add the regression, then repeat the affected runtime and visual checks.

The active role split and release order are in [Researcher workflow](research-workflow.md). Private evaluation and novice/expert usability remain explicitly unassessed by CI.
