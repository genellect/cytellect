# Cytellect

From 2D fluorescence images to reviewed measurements, statistics and publication-ready figures.

[日本語](README.ja.md) · [Requirements](docs/requirements.md) · [Methods](docs/methods.md) · [Validation](docs/validation.md)

[Analysis planning](https://cytellect.vercel.app/plan) · [Public sample viewer](https://cytellect.vercel.app/demo) · [Local browser delivery](docs/local.md) · [Hosting costs and trade-offs](docs/hosting-costs.ja.md)

**Early research prototype.** The Web/API/worker workflow is implemented and tested with published microscopy and independent numerical references. Suitability for the user's experiment and researcher PoC remain unvalidated. The public sample viewer uses published microscopy; a UI deployment does not imply an available analysis server.

Cytellect connects the measurement question, region review, fluorescence quantification and experimental-unit comparisons in one Japanese browser workspace. Researchers can inspect and correct regions, then produce editable figures linked to their source measurements and analysis conditions. Fiji + StarDist/ImageJ/MorphoLibJ supplies the initial image-analysis engine; original measurement pixels, display settings and detection preprocessing remain separate. Existing nuclear, nucleolar, NCL and GFP recipes are retained alongside generic 2D region measurements.

## Current improvement cycle

The product is expanding toward purpose-first 2D fluorescence region measurement. [Researcher workflow](docs/research-workflow.md) records the evidence-led design, role split and release gates. The [planning guide](docs/analysis-planning.md) explains applicable recipes and unresolved conditions without uploading images; a supported choice can be explicitly adopted into a workspace and resolved against actual channels. The source includes [named channels, reviewed batch registration, manual/imported regions and confirmed nuclear-stain detection](docs/generic-regions.md), optional experimental metadata, original-pixel area/intensity measurements, [per-field descriptive figures](docs/descriptive.md) and explicit [experimental-unit comparisons](docs/region-comparisons.md). Arbitrary-object detection and automatic cell boundaries remain outside this slice. [Independent review](docs/scientific-review.md) separates numerical checks, public-image execution and biological/human acceptance.

The published local.11 Windows package includes statistics1.2.3, figure1.1.3, generic measurement1.0.0, nuclear initialization recipe1.1.0, descriptive output1.0.0 and region comparisons1.0.0. Its release record separates the successful CI-installed run, the retained initial browser failure and a Smart App Control block on another PC. A deployed public UI does not update an installed local package.

The development source additionally supports area-only measurement2.0.0 without background ROIs and planning2.1.0. Intensity remains explicitly unmeasured in this mode; changing modes retains corrected masks in a new unreviewed revision. A combined Windows package is pending exact-source installation and browser acceptance. The public planning guide stays on2.0.0 until that package is available.

## Windows preview

The local edition uses the browser workspace with a private API and Fiji worker on the same PC. Published setup packages appear on the [releases page](https://github.com/genellect/cytellect/releases) only after their installation and browser checks pass. Extract the ZIP, open **Cytellect Setup.cmd**, then start Cytellect from its shortcut. Setup provisions pinned dependencies without changing system Python, PATH or an existing Fiji. Research images remain on the PC;24-hour expiry cleanup while the application is off resumes at next launch. See [local delivery](docs/local.md) for limits and verification.

The same scientific code and contracts support the later hosted edition. No cloud analysis server or paid plan is included in this preview.

[Download Windows preview 0.1.0-local.11](https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.11) · [Checksum and acceptance record](docs/local-release-0.1.0.md) · [First analysis with public images (Japanese)](docs/quickstart.ja.md)

## Local development

Use Python3.12, Node.js24 and pnpm11.19.0.

```sh
uv sync --locked --dev
pnpm install --frozen-lockfile
# Set an absolute private directory outside this checkout:
export CYTELLECT_DATA_DIR=/absolute/private/cytellect
export CYTELLECT_APP_ORIGIN=http://localhost:3000
export CYTELLECT_SECURE_COOKIES=false
uv run python scripts/fiji_setup.py /absolute/private/fiji --platform linux-x64
export CYTELLECT_FIJI_EXECUTABLE=/absolute/private/fiji
uv run cytellect invite --hours 24
```

Run `uv run cytellect serve`, `uv run cytellect-worker`, and `pnpm dev` in separate terminals with the same environment. On Windows use PowerShell environment variables and `--platform windows-x64`. The invite is private: never paste it into logs/issues. Nuclear detection requires pinned Fiji. Manual/imported generic region measurements do not run a detector. An unavailable detector produces an explicit failure, never a fallback to another model.

For containers, set `CYTELLECT_RUNTIME_DIR` to a private Linux directory owned by UID10001, outside the checkout, then `docker compose up --build -d`. See [operations](docs/security.md) and [Fiji](docs/fiji.md) for host verification and TLS.

## Scope and evidence

- Native8/16-bit 2D TIFF and verified2/3-channel OME-TIFF; separate legacy RGB recipe. Explicit channel mapping/backgrounds and immutable revisions.
- CZI conversion stays offline in Fiji/Bio-Formats; follow the [pixel-preserving conversion procedure](docs/converting-czi.md) before import.
- Nuclear/nucleolar/manual ROI editing; GFP/NCL measurements; paired/Welch and exploratory clustered regression; CSV, editable SVG/PDF, ROI/masks, Methods and replay package.
- Published real microscopy for image integration/public samples; synthetic pixels only for exact numerical tests. Dataset identity, stains and provenance are recorded.
- No registration, LLM, Supabase, payments, 3D/time series, UBF or automatic cell-boundary inference.

“Publication-ready” means editable figures, explicit conditions, traceable measurements and replayable outputs. It is not scientific certification. See [roadmap](docs/roadmap.md) for remaining gates.

## Research information

Private research images, source names, conditions and derived results never belong in GitHub, CI, external AI or public demos. Runtime data is private and expires24hours after explicit activity. Public deployment must pass ownership, TLS, deletion and worker isolation checks before accepting private research data. [Data protection](docs/security.md)

Own source is Apache-2.0; third-party code, Fiji, model weights and public datasets retain their own licenses. [OSS inventory](docs/oss.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
