# Cytellect

Reproducible immunofluorescence analysis, from nuclear and nucleolar segmentation to quantification, statistics, and publication-ready figures.

[日本語](README.ja.md) · [Requirements](docs/requirements.md) · [Methods](docs/methods.md) · [Validation](docs/validation.md)

**Early research prototype.** The Web/API/worker workflow is implemented and under integration testing. Suitability for the user's experiment and researcher PoC remain unvalidated. The public sample viewer uses published microscopy; a UI deployment does not imply an available analysis server.

Cytellect brings DAPI nuclear segmentation, NCL nucleolar candidates, manual mask correction, GFP selection, compartment measurements, statistics and editable figures into one Japanese workspace. The initial engine is Fiji + StarDist/ImageJ/MorphoLibJ. Raw measurement pixels, display settings and detection preprocessing are separate.

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

Run `uv run cytellect serve`, `uv run cytellect-worker`, and `pnpm dev` in separate terminals with the same environment. On Windows use PowerShell environment variables and `--platform windows-x64`. The invite is private: never paste it into logs/issues. Without Fiji, only the explicitly synthetic numerical test path can execute; actual uploads never fall back to a different detector.

For containers, set `CYTELLECT_RUNTIME_DIR` to a private Linux directory owned by UID10001, outside the checkout, then `docker compose up --build -d`. See [operations](docs/security.md) and [Fiji](docs/fiji.md) for host verification and TLS.

## Scope and evidence

- Native8/16-bit 2D TIFF and verified3-channel OME-TIFF; separate legacy RGB recipe. Explicit channel mapping/backgrounds and immutable revisions.
- Nuclear/nucleolar/manual ROI editing; GFP/NCL measurements; paired/Welch and exploratory clustered regression; CSV, editable SVG/PDF, ROI/masks, Methods and replay package.
- Published real microscopy for image integration/public samples; synthetic pixels only for exact numerical tests. Dataset identity, stains and provenance are recorded.
- No registration, LLM, Supabase, payments, 3D/time series, UBF or automatic cell-boundary inference.

“Publication-ready” means editable figures, explicit conditions, traceable measurements and replayable outputs. It is not scientific certification. See [roadmap](docs/roadmap.md) for remaining gates.

## Research information

Private research images, source names, conditions and derived results never belong in GitHub, CI, external AI or public demos. Runtime data is private and expires24hours after explicit activity. Public deployment must pass ownership, TLS, deletion and worker isolation checks before accepting private research data. [Data protection](docs/security.md)

Own source is Apache-2.0; third-party code, Fiji, model weights and public datasets retain their own licenses. [OSS inventory](docs/oss.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)
