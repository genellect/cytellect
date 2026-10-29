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

## Segmentation models and commercial service policy

Cytellect selects models for research-laboratory SaaS, local execution and
reproducible analysis. Adoption records separate four assets: software, the
selected checkpoint, its base model, and training/evaluation data. They also
separate hosted inference, redistribution and fine-tuning. A permissive software
license supports commercial use under its conditions; it does not assign a
license to a separately distributed checkpoint or dataset.

The [model strategy](segmentation-models.ja.md) describes the current architecture
and product expansion. The evidence below was inspected on **2026-10-29**.

### Current Cellpose evidence

| Asset | Evidence | Handling |
|---|---|---|
| Cellpose 4.2.1.1 software | The official PyPI wheel contains `cellpose-4.2.1.1.dist-info/licenses/LICENSE`, with the HHMI copyright and three BSD conditions. Wheel SHA-256: `6c5c5159fd459115bee390ffb01d94d5e1006b97c211bf3c1a7b37d5395a1a13`; verified against [PyPI's release metadata](https://pypi.org/pypi/cellpose/4.2.1.1/json) | BSD-3-Clause. Preserve copyright, conditions and disclaimer; observe the non-endorsement condition. The artifact's text takes precedence over a generic package classifier or README badge |
| Official `cpsam_v2` checkpoint | The [model card at the selected revision](https://huggingface.co/mouseland/cellpose-sam/blob/7c61431b5fbb078f3296754bd15d9f51b320f837/README.md) declares `bsd-3-clause`. The [runtime manifest](../engines/cellpose/runtime.lock.json) pins that revision, file size and SHA-256 | Record the upstream checkpoint declaration separately from the software license. CPU and CUDA use this same checkpoint |
| Cytellect NCL fine-tunes | [Genellect/Cytellect revision 7670daa1](https://huggingface.co/Genellect/Cytellect/tree/7670daa1edbfcb3d4611c9e053766d91f6125e74) publishes 375- and 750-update weights, JSON provenance, a BSD-3-Clause card, `LICENSE.cellpose` and `NOTICE.md` | Preserve upstream notices and the statement that fine-tuning modified the weights. Bind each checkpoint to its own hash, data permissions and evaluation record |
| SAM base and inference dependencies | SAM ViT-L is identified by the [Cellpose model documentation](https://cellpose.readthedocs.io/en/latest/models.html); the [CPU](../engines/cellpose/requirements.lock) and [GPU](../engines/cellpose/requirements-cuda.lock) requirements pin the installed packages | Retain the exact installed dependencies' notices, including Segment Anything and PyTorch, with each assembled runtime |
| Upstream training data | The [Cellpose README at commit a54cb488](https://github.com/MouseLand/cellpose/blob/a54cb48849b7e225a81e8e43dcb042d42427f543/README.md) states that its models were trained on CC-BY-NC data and identifies the annotated dataset as CC-BY-NC | Keep this evidence alongside the checkpoint declaration. Dataset restrictions and the license granted for weights are distinct questions; the SaaS rights review resolves the relationship for the selected artifact |
| Cytellect training/evaluation data | Public fixtures have an allowlist; laboratory data follows the [team's data rules](team-development.md#6-研究データの扱い) | Record permission for evaluation, training, sharing and publication separately. Access to a research image does not itself authorize training or publication |

`scripts/cellpose_setup.py` verifies the model's size and SHA-256 and the
runner/dependency lock hashes. Dependencies are installed with required hashes;
model acquisition occurs during explicit setup/build, before analysis. The
runtime tests check this fixed identity. These checks bind execution to the
reviewed artifact; license interpretation belongs in the adoption record.

The local bundle includes `engines/cellpose/LICENSE.cellpose.txt` and the setup
recipes; it obtains weights during setup. The GPU image contains the runtime,
weights and engine files. Notices and distribution obligations are therefore
reviewed against each actual package, including a container image, rather than
only against the source repository.

### Candidate model licensing

This table guides selection. It does not add these candidates to the deployed
runtime. Exact release/checkpoint terms are recorded when a candidate is chosen.

| Candidate | Software evidence | Checkpoint and SaaS adoption route |
|---|---|---|
| StarDist 3D | [BSD-3-Clause](https://github.com/stardist/stardist/blob/main/LICENSE.txt) | Select a 3D checkpoint or train one on authorized data. The current 2D `dsb2018_heavy_augment` has separate [model-repository BSD-3-Clause evidence](https://github.com/stardist/stardist-models/blob/master/LICENSE.txt); that identity is not a substitute for a 3D model record |
| microSAM | [MIT](https://github.com/computational-cell-analytics/micro-sam/blob/master/LICENSE) | Select a named LM or EM checkpoint from the [official model catalog](https://computational-cell-analytics.github.io/micro-sam/micro_sam.html), retain that checkpoint's terms and base-model provenance, and record commercial inference/distribution permissions |
| nnU-Net | [Apache-2.0](https://github.com/MIC-DKFZ/nnUNet/blob/master/LICENSE) | Use as a training framework with rights-controlled datasets. Record the resulting model's terms; separately review any externally supplied weights |
| CellposeDINO | Cellpose software license plus the [DINOv3 License](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md) for DINO materials | Review the selected derivative's weight terms together with DINOv3's use, redistribution and attribution conditions. Do not classify the entire stack as BSD solely from Cellpose's software license |
| CellSAM | [Apache-2.0](https://github.com/vanvalenlab/cellSAM/blob/master/LICENSE) | Its [authenticated model distribution](https://github.com/vanvalenlab/cellSAM/blob/master/cellSAM/_auth.py) supplies separate assets. Capture the access terms and weight license for the chosen version before commercial adoption |
| Omnipose | [NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE) | Commercial SaaS adoption requires commercial rights from University of Washington CoMotion. Keep it outside the default commercial model set until those rights are obtained |
| Big-FISH spot detection | [BSD-3-Clause](https://github.com/fish-quant/big-fish/blob/master/LICENSE) | Preserve notices for the selected software and dependencies. Treat any separately added segmentation weights as their own assets; the spot-detection path is a method, not a pretrained checkpoint |

### SaaS adoption procedure

1. **Identify the deliverable.** Record version, immutable source URL/revision,
   SHA-256, model purpose, base checkpoint, dependencies and deployment mode.
2. **Establish rights for each use.** Record the license text and its retrieval
   date for software, weights and data; evaluate paid hosted inference,
   redistribution, modification, fine-tuning and publication separately.
   Resolve conflicting declarations or unclear grants with the rights holder or
   qualified counsel, with the question tied to a specific artifact and use.
3. **Prepare the distribution.** Preserve notices and attribution, and provide
   source/relinking materials where the included licenses require them. Review
   network-service conditions where applicable; hosting is not a universal
   exemption from license obligations.
4. **Record the decision.** The product owner approves the intended commercial
   use, citing the evidence and any additional license agreement. Release records
   bind that decision to the model/runtime hashes. A different checkpoint or
   distribution mode receives its own review.
5. **Protect customer data.** In the SaaS design, distinguish service processing
   from optional training and public model release. Define tenant isolation,
   retention, deletion, subprocessors and data location in the service terms and
   data-processing arrangements. Train on customer data only with the necessary
   permissions for that purpose.

### Model adoption review record

This is the operational record for evidence gaps and follow-up work. README and
the product strategy describe capabilities and direction; this section and the
roadmap hold release conditions and review status.

| Item | Verified evidence | Next decision or implementation |
|---|---|---|
| Current Cellpose software and weights | Exact wheel license and hash; pinned checkpoint card declares BSD-3-Clause; runtime hashes are enforced | Retain the exact wheel license evidence alongside the release inventory; the manifest's code-license source currently points to upstream `main` |
| Cellpose commercial SaaS rights | BSD-3-Clause software/weight declarations and upstream CC-BY-NC training-data statement are both recorded | Obtain and record a rights-holder clarification or legal assessment addressing paid inference, checkpoint redistribution and derived fine-tunes. This document does not record completion of that assessment or change the model's declared license |
| Isolated Cellpose runtimes | CPU/CUDA dependency lockfiles and artifact hashes are fixed | Extend release SBOM/notice collection to the isolated Cellpose environments and checkpoint assets. The current general Python inventory covers its running interpreter, not every isolated runtime |
| Expansion candidates | Official capability and software-license sources in the tables above | Select exact checkpoints, capture weight/base/data terms, and evaluate on independent experiments before a product adoption decision |
| Cytellect fine-tunes | NCL checkpoints and their provenance/notice files are publicly available at the fixed revision above | Carry those records into the selected product release and retain the data-use/publication permissions with the owner's release decision; use the same record structure for subsequent fine-tunes |

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
| `ProductMenu.tsx` | `founder/MobileExternalMenu.tsx` | Outside-click, Escape and focus restoration; product navigation |
| `OpticalHero.tsx`, `optical-scene-engine.ts` | `founder/ProductSculpture.tsx`, `founder/product-sculpture-engine.ts` | Visibility-triggered WebGL setup, generation guards, lighting environment and explicit renderer/resource disposal; Cytellect Blender optical background |
| `product.module.css` | `founder/founder.module.css` | Header, navigation and editorial typography adapted to Cytellect compositions |

Inter and Noto Sans JP are self-hosted under their included OFL notices.
The font subset manifest records source hashes and included application text.
Registered microscopy and generated figures retain their source manifests;
the laboratory photographs retain their separate Unsplash terms and creator
records in `apps/web/public/marketing/photo-provenance.json`.
The public asset allowlist binds each distributed file to its SHA-256, source
and license. No Lila or GraphPad photographs, fonts or source code are included.

Three.js `0.185.1` and `@types/three` `0.185.4` are fixed in the Web
manifest and pnpm lockfile. Both declare MIT; preserve their installed license
notices with the Web distribution. Three.js renders only the landing-page
Blender background (`optical-assembly.glb`), with no analysis, segmentation or
measurement role. Its renderer and GLTF loader are loaded on demand; before
loading, with reduced motion or on WebGL failure, the page shows the same
artwork's Blender-rendered desktop or mobile poster
(`apps/web/public/marketing/optical-provenance.json`). Upstream license:
https://github.com/mrdoob/three.js/blob/r185/LICENSE
The type package's transitive dependencies are development dependencies;
they are not additional runtime analysis engines.
