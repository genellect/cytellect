# Cytellect Web configuration

The default production build serves the public microscopy samples with analysis connections disabled unless `NEXT_PUBLIC_API_ORIGIN` is explicitly configured. `pnpm build:local` produces the separate loopback bundle; its UI uses same-origin API paths and never shows release download controls.

## Windows release link

`src/lib/published-release.json` records the publicly available versioned Windows asset: `version`, `asset` (`installer` or `zip`), `url`, `sha256`, `source_commit` and `size_bytes`. From 0.1.0-local.21 a release carries the per-user installer `Cytellect-Setup-<version>.exe`, and the record names it with `"asset": "installer"`; `zip` (`Cytellect-<version>-windows-x64.zip`) remains only for versions without an installer. The site shows the installer steps (open, press 「インストール」, sign in with the e-mail code) only for the installer, and the ZIP steps only for the ZIP. Update the record only after the asset has been published, independently downloaded or checked against its published digest, and validated as an installed application. The fallback validates the metadata and the exact URL of that asset of that version before displaying the download surface.

Switching the site to a newly published installer is its own PR, after the owner has published the release:

1. Download `Cytellect-Setup-<version>.exe` from the public release without signing in, and check its SHA-256 against the release's `.sha256` file and against `installer.sha256` in the signed `Cytellect-update-<version>.json` ([integrity check](../../docs/install-windows.ja.md#2-ダウンロードと確認)).
2. Set `version`, `"asset": "installer"`, `url` (`https://github.com/genellect/cytellect/releases/download/v<version>/Cytellect-Setup-<version>.exe`), `sha256`, `source_commit` (the release's source commit, 40 hex characters) and `size_bytes` (the byte size of the downloaded file).
3. After the merge and deployment, run the release download check below (`CYTELLECT_TEST_RELEASE_DOWNLOAD=1`) against the canonical site.

`NEXT_PUBLIC_WINDOWS_RELEASE_URL` overrides this record only when explicitly defined. An **empty value disables downloads**; an invalid value also disables them and never falls back. Removing the variable restores the recorded release on the next build. Local builds and builds with an analysis API configured preserve their workspace UI regardless of the release setting.

Only version-specific HTTPS GitHub assets in `genellect/cytellect` are accepted: `releases/download/v<version>/Cytellect-Setup-<version>.exe`, whose tag and file name carry the same version, or `Cytellect-<version>-windows-x64.zip`. There is no `/latest` URL, browser release probe or local-service discovery. The version/checksum link appears only when the effective asset matches the recorded release, so an override cannot inherit a different version's metadata.

The public browser acceptance check defaults to the tracked release. `CYTELLECT_TEST_RELEASE_DOWNLOAD=1` additionally downloads the recorded asset through the button and compares its file name, size and SHA-256 with the record. Use `CYTELLECT_EXPECT_RELEASE_URL` to test an override, including an explicit empty string for the disabled case. Rebuild the Web app after changing build-time configuration. Do not use this configuration as evidence that a future package has passed installation or scientific validation.
