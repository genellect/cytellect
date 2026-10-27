# Cytellect Web configuration

The default production build serves the public microscopy samples with analysis connections disabled unless `NEXT_PUBLIC_API_ORIGIN` is explicitly configured. `pnpm build:local` produces the separate loopback bundle; its UI uses same-origin API paths and never shows release download controls.

## Windows release link

`src/lib/published-release.json` records the publicly available versioned Windows ZIP, SHA-256, source commit and byte size. Update it only after the asset has been published, independently downloaded or checked against its published digest, and validated as an installed application. The fallback validates the metadata and exact versioned repository URL before displaying the download surface.

`NEXT_PUBLIC_WINDOWS_RELEASE_URL` overrides this record only when explicitly defined. An **empty value disables downloads**; an invalid value also disables them and never falls back. Removing the variable restores the recorded release on the next build. Local builds and builds with an analysis API configured preserve their workspace UI regardless of the release setting.

Only version-specific HTTPS GitHub assets in `genellect/cytellect` named `Cytellect-<version>-windows-x64.zip` are accepted. There is no `/latest` URL, browser release probe or local-service discovery. The version/checksum link appears only when the effective asset matches the recorded release, so an override cannot inherit a different version's metadata.

The public browser acceptance check defaults to the tracked release. Use `CYTELLECT_EXPECT_RELEASE_URL` to test an override, including an explicit empty string for the disabled case. Rebuild the Web app after changing build-time configuration. Do not use this configuration as evidence that a future package has passed installation or scientific validation.
