# Windows runtime composition

Status: source candidate under validation. The immutable local.11 release still
uses its recorded Python 3.12 runtime. Successful import, extraction or unit
checks do not establish acceptance of a new installed package on a research PC.

The candidate addresses the observed unsigned virtual-environment launcher
failure without changing Windows application control. It uses the official PSF
Python 3.14.8 x64 ZIP and its signed standard-library venv launchers. Tcl/Tk
9.0.4 scripts from the same release are added in the upstream standard loose
library layout. This is a Cytellect-maintained composition of official inputs,
not an unchanged or PSF-certified distribution. No original executable is
rewritten, re-signed or removed.

## Reproducible inputs

[Runtime lock](../engines/python/windows-runtime.lock.json) records the official
base ZIP and parent MSI URLs, versions, byte sizes and SHA-256 values, the two
script archive hashes, launcher identities, notices and the derived data asset.
[Member manifest](../engines/python/windows-tcltk-members.json) records all 929
script members and their exact destination bytes. The source repository carries
these records and build code, not the Python executables or a developer runtime.

The data builder consumes verified base/MSI/script archives and writes a
deterministic, exclusive ZIP with 929 unmodified scripts, a combined notice and
a provenance manifest. Fixed ordering, timestamps and ZIP_STORED avoid changes
from compression-library versions. It checks the base to reject path collisions;
base executables are never copied into the data ZIP. The script archives are
independently pinned descendants of the parent MSI. The data builder does not
claim to have performed MSI extraction itself.

The reviewed asset is 4,777,439 bytes, SHA-256
`937ce5f76b153f2cbe69cf2770504fc259ed155974b5840009e6e4ab9da196cc`.
Two independent output creations and complete payload round trips matched.
This is deterministic composition evidence, not application compatibility.

MSI extraction belongs on the release builder. The consumer setup receives the
small data ZIP within the versioned source/Web package, covered by its release
manifest, and obtains the pinned Python ZIP during explicit setup. The researcher
is not asked to run MSI tools, set Tcl environment variables or install packages
by hand. Runtime/model downloads remain forbidden during analysis.

## Integrity and lifecycle

The setup helper rejects traversal, Windows path aliases, links, case collisions,
file/child collisions, unexpected sizes and data containing executable content.
Existing mismatched files and additional files or directories cause refusal;
they are not deleted to make validation pass. Every base and added file belongs
to the exact installed inventory. Python runs with bytecode writing disabled so
that unrecorded cache files cannot become an exception to that inventory.

Standard-library venv creation must retain the signed PSF launcher bytes before
and after normal locked dependency installation. This composition does not make
generated third-party console entrypoints signed: product modules run through
the verified interpreter. Valid signatures and hashes are separate from actual
workstation-policy acceptance.

Release acceptance must cover the current source, normal dependency support,
scientific tests, actual Fiji, fresh/repeat setup, GUI lifecycle, installed
browser workflows, independent numerical replay and shutdown. Linux/Cloud
Python 3.12 stays a separate supported baseline. Unknown support is not repaired
with a Requires-Python override or relaxed scientific tolerance.

The compatibility experiment used source `ec7f922bf51d106477d15c5de5bbf9f348abeb35`
with only its Python support metadata extended, a normal wheel, 57 normally
installed dependencies, 22 import checks and actual hidden Tk creation. The
first full non-Fiji run had 762 passes, 126 failures and three skips. Its test
data was mistakenly placed inside the guard's inferred installation boundary;
Windows PowerShell output also needed an explicit UTF-8 test-process setting.
After correcting those harness conditions, the exact 112 affected cases and
the 14 encoding cases passed in separate runs. Twelve actual locked-Fiji cases
then passed without warnings or skips. The initial failures are retained;
this is not a claim that one full run passed. Two unconfigured secret-scanner
cases and one Windows-inapplicable POSIX process test stayed explicitly skipped.

Those results establish the bounded experiment, not acceptance of the newer
launcher/package source. The latter adds full Windows3.14 CI and exact-source
fresh/repeat package gates. Independent runtime-helper review also detected a
PowerShell reserved-variable collision before release; correction passed all
51 helper boundary tests. Existing scientific equations and tolerances were
not relaxed to accommodate the runtime.

## Notices

Keep the base `LICENSE.txt`, documentation and bundled pip/vendor notices intact.
They contain Python/PSF historical terms and Windows/native-library conditions;
they are not replaced by Cytellect's Apache-2.0 license. Both Tcl and Tk
`license.terms` files and all original per-file notices are retained.

`Lib/tk9.0/icons.tcl` separately identifies the Vimix Icon Theme contributors and
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The data notice
preserves that attribution and the upstream URL. Do not summarize the entire
script tree under a single permissive license. The change summary records only
the additional loose-library layout and notices; script content is unchanged.
The lock and notice inventory provide evidence, not a blanket legal certification
of the complete Python/Fiji/scientific-library distribution.

Earlier failed runtime/Tk experiments, the Smart App Control failure and all
subsequent corrected attempts retain separate receipts. A future successful
package does not retroactively change local.11 or satisfy private-study M4 and
researcher-usability M5.
