# Working on Cytellect

Read docs/requirements.md, docs/methods.md and docs/security.md before changing behavior.
Inspect Git status. Preserve user work and original research outputs.

## Research data boundary
- Synthetic data is for deterministic numerical tests. Published real microscopy is required for image integration and public demos; public assets need recorded source, accurate stain metadata, redistribution terms and hashes. Never substitute another stain for NCL/GFP.
- Never copy unpublished/private research images, research PDFs, source paths, study-specific results, participant identifiers, credentials, or invitation/session tokens into code, logs, issues, PRs, screenshots, or external AI services. Registered public fixtures follow the source and redistribution requirements above.
- Keep runtime data outside the checkout. Never use production credentials for development.
- Run private validation separately; publish only an explicitly approved sanitized report.

## Scientific behavior
- Original pixel values are immutable. Detection preprocessing and display LUTs must never change measurement values.
- Label masks in original image coordinates are canonical. Changing nuclei invalidates their dependent nucleoli; changing masks or exclusions invalidates derived statistics/figures.
- Changes to thresholds, background, gating, equations or statistics require a recipe/version change, methods documentation and numerical tests.
- Missing/undefined is not zero. Never tune parameters to obtain significance or silently discard failed fields.
- Keep nuclei, nucleoli, fields, samples and independent experimental units distinct.
- The API and analysis package own numeric results; never calculate authoritative measurements in the browser.

## Development
- Codex Cloud is the default code environment. Use synthetic numerical fixtures and registered public datasets only. Local execution is permitted for setup and verification, especially the private validation boundary.
- Pin dependencies and model hashes. Review licenses separately for code, weights and data.
- No runtime package/model downloads, arbitrary submitted code/macros or remote image URLs.
- Run `uv run pytest`, `uv run ruff check .`, `pnpm check`, `pnpm test`, and relevant integration tests. Do not mark skipped Fiji/private-data checks as passed.
- Record purpose, scientific impact, validation evidence and limitations in PRs.
- Distinguish source implementation, CI, deployment, hosted behavior and scientific validation.
- Follow the user's current authorization for publishing, external transmission, settings changes and deployment. Do not install paid services or add LLM/Supabase dependencies to the MVP.
- Keep README status truthful. An unfinished requirement remains open in docs/roadmap.md.
- Local browser delivery is an execution adapter. Keep one shared measurement/statistics implementation and preserve the future hosted API boundary. Read docs/local.md before changing local bootstrap, installer, session or retention behavior.
