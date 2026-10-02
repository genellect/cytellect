# Cytellect Web configuration

The default production build serves the public microscopy samples with analysis connections disabled unless `NEXT_PUBLIC_API_ORIGIN` is explicitly configured. `pnpm build:local` produces the separate loopback bundle; its UI uses same-origin API paths and never shows release download controls.

## Windows release link

Set `NEXT_PUBLIC_WINDOWS_RELEASE_URL` only after the tagged ZIP asset in `genellect/cytellect` has been published and independently checked as publicly downloadable. Use the full version-specific HTTPS GitHub release asset URL, with an asset named `Cytellect-<version>-windows-x64.zip`. Rebuild the public Web app after changing this variable.

There is deliberately no default or `/latest` URL. Empty/invalid URLs, local builds, and builds with an analysis API configured preserve the existing workspace UI. The browser performs no release or localhost probing. Clear the variable and rebuild to remove the download surface. Do not set it to an unpublished candidate or use this UI configuration as evidence of package validation.

The optional browser acceptance check uses `CYTELLECT_EXPECT_RELEASE_URL` with the same verified public URL. Without it, the public test requires the disconnected invitation placeholder and no download CTA.
