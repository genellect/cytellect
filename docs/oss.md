# Third-party software, weights and redistribution

Cytellect's original source is Apache-2.0. That license does not replace the
licenses of Fiji, Java, plugins, model weights, dependencies or datasets.

The [fixed runtime manifest](../engines/fiji/runtime.lock.json) records official
artifact URLs, versions through their filenames, SHA-256, license identifiers and
upstream source links. Setup writes a complete installed jar/JDK hash inventory
outside the repository. Retain it alongside deployment records.

| Component | Purpose | License evidence |
|---|---|---|
| Fiji distribution | ImageJ platform and JVM environment | Multiple licenses; preserve the archive's licenses and per-jar notices |
| Bundled Java 21 | Fixed engine execution | OpenJDK distribution notices; do not relabel Apache |
| StarDist 0.3.0 | 2D nuclear segmentation | BSD-3-Clause, artifact POM and [source license](https://github.com/stardist/stardist-imagej/blob/master/LICENSE.txt) |
| Embedded dsb2018_heavy_augment model | Versatile fluorescent nuclei weights | Separate BSD-3-Clause [model repository license](https://github.com/stardist/stardist-models/blob/master/LICENSE.txt); embedded ZIP SHA-256 pinned |
| CSBDeep 0.6.0 | Neural network execution | BSD-2-Clause, artifact POM |
| TensorFlow Java/JNI/proto 1.15.0 | CPU inference | Apache-2.0 upstream TensorFlow notices |
| ImageJ TensorFlow 1.1.9 | ImageJ/TF integration | BSD-2-Clause, artifact POM |
| MorphoLibJ 1.6.5 | Connected components | **LGPL-3.0-or-later**, inspected artifact POM; generic older website descriptions do not override this artifact |
| Clipper 6.4.2 Java port | StarDist polygon operations | BSL-1.0 [upstream repository](https://github.com/lightbringer/clipper-java) |
| Protobuf Java 3.25.8 | Compatible TF graph metadata | BSD-3-Clause, upstream protobuf distribution |
| Bio-Formats | Optional offline CZI conversion and bundled format support | GPL and BSD components; [OME policy](https://www.openmicroscopy.org/licensing/) distinguishes them |

Keep Python and Web lockfiles and produce dependency/SBOM reports from the exact
release environment. License names in package metadata are evidence, not a
complete review of all transitive obligations. Model licenses and data licenses
are separate checks. Published microscopy fixtures have source, stain metadata,
redistribution basis and hashes in fixtures/public/allowlist.json. Synthetic
fixtures serve numerical tests. No unpublished research images are distributed.

## CI evidence and license checks

`scripts/sbom.py` inventories the installed Python environment, the actual Web
notice collector and the fixed Fiji manifest, with hashes of both dependency
lockfiles. Python records preserve `License-Expression`, legacy `License` text,
license classifiers, and installed notice paths relative to the package
installation with SHA-256 and byte size. Classifier-only packages are valid
declared evidence; an ambiguous `BSD License` classifier is not converted into
an invented specific SPDX identifier. Empty optional-codec notice placeholders
are recorded by size/hash but do not count as license evidence.

The CI gate rejects a Python package with no declared expression, text,
classifier or nonempty notice. The existing Web collector requires real license
texts for direct Web dependencies and gathers vendor notices from the installed
pnpm store. Both inventories include development dependencies; they are not a
minimal production dependency graph. Missing evidence is a failure, while
recorded evidence does not decide legal compatibility or replace review of an
assembled GPL/LGPL distribution.

The existing Python vulnerability audit also emits a formal CycloneDX JSON SBOM
with `pip-audit --local --format cyclonedx-json`; there is no second network
audit or new runtime dependency. Only a successful audit's dependency SBOM is
retained. CI retains that SBOM, the combined Python/Web/Fiji inventory, Web
notice texts and an aggregate pinned-secret-scanner receipt for seven days.
Raw secret findings, source lines, author identifiers, research files and
application logs are not uploaded as CI artifacts. These checks establish their
documented software evidence, not exhaustive secrecy, safety or licensing.

Local setup downloads uv0.12.2 (MIT OR Apache-2.0) from the official Astral release
with an archive SHA-256 pinned in scripts/local_setup.ps1. Managed CPython retains
its PSF/third-party notices. The setup ZIP contains source and compiled Web assets,
not a copy of the developer's Python/Fiji installation. Preserve Web dependency
license texts in the assembled package separately from Cytellect's own license.

The immutable local.11 Windows installer pins **CPython 3.12.15**, the
[September 30 security release](https://www.python.org/downloads/release/python-31215/),
using the official Astral standalone **20261001 Windows x86-64** distribution.
The stripped install archive has SHA-256
`52124cee54126f3f360eaa378288f6f64c402c983a3c14c95eff67f4af986aaa`.
Its exact URL and a one-entry uv download catalog are fixed in the installer;
setup does not ask for the latest Python. This explicit catalog is needed because
uv0.12.2's embedded catalog predates this Python patch. Setup records the Python
version/build/archive hash and uv hash in its completion record. Local installer
acceptance must use this downloaded interpreter, including actual Tcl/Tk window
creation; earlier developer-runtime Python3.12.14 results are separate evidence.

The next source candidate uses the official PSF **Python3.14.8** x64 ZIP,
signed standard-library venv launchers and unchanged Tcl/Tk9.0.4 scripts from
the same release's pinned MSI. [Composition details](windows-runtime.md) and
the runtime/member manifests identify each input and derived asset. The base
PSF/historical/native terms, Tcl/Tk license texts and separate Vimix icon
CC-BY-SA4.0 attribution are preserved. This is a maintained composition,
not a PSF-certified distribution or an Apache-only third-party bundle. Normal
project wheels and dependencies are installed by recorded hash. The source
candidate does not alter local.11 or imply intended-PC acceptance.

The source repository contains installer recipes, not third-party runtime
binaries or pretrained weights. Before distributing a binary/container, retain
all copyright/license notices, supply corresponding source and replacement/
relinking materials where required by the included GPL/LGPL components, and
review the assembled distribution. No blanket Apache-only or completed
commercial-redistribution audit is claimed for the Fiji bundle.

Cite ImageJ/Fiji, StarDist, CSBDeep and MorphoLibJ in methods as appropriate.
The model's nuclear training domain does not establish nucleolar detection
accuracy or fitness on a particular experiment.

## Website components and media

The following COMPASS components were adapted with the copyright owner's
express permission for Cytellect. Their source is commit
`4805fb6df9e5a0bd267aef9cfa440174ccac5fb1` of `genellect/compass`.
Original copyright and adaptation notices remain in the source files.
This permission does not change the license of the upstream COMPASS repository
or the terms of its third-party assets.

| Cytellect file | COMPASS source | Adaptation |
|---|---|---|
| `EditorialHeading.tsx` | `OfficialCoreSections.tsx`, `SectionHeading` | Semantic heading structure; removed reveal effects and decorative labels |
| `ProductMenu.tsx` | `founder/MobileExternalMenu.tsx` | Outside-click, Escape and focus restoration; product navigation |
| `PublicationStage.tsx` | `founder/ProductSculpture.tsx` | Visibility-based loading, generation guard and disposal; exported figure instead of WebGL sculpture |
| `product.module.css` | `founder/founder.module.css` | Header, navigation and editorial typography adapted to Cytellect compositions |

Inter and Noto Sans JP are self-hosted under their included OFL notices.
The font subset manifest records source hashes and included application text.
Registered microscopy and generated figures retain their source manifests;
the laboratory photographs retain their separate Unsplash terms and creator
records in `apps/web/public/marketing/photo-provenance.json`.
The public asset allowlist binds each distributed file to its SHA-256, source
and license. No Lila or GraphPad photographs, fonts or source code are included.
