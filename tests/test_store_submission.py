import hashlib
import importlib.util
import json
import re
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

source = Path(__file__).resolve().parents[1] / "scripts" / "submit_windows_msix.py"
spec = importlib.util.spec_from_file_location("submit_windows_msix", source)
assert spec is not None and spec.loader is not None
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

COMMIT = "b" * 40
VERSION = "1.0.4.0"
NAME = f"Cytellect-Store-{VERSION}-{COMMIT}.msix"
EXISTING = {
    "fileName": "Cytellect-Store-1.0.3.0.msix", "version": "1.0.3.0",
    "architecture": "X64", "fileStatus": "Uploaded",
}
PUBLISHED = {
    "id": "100", "visibility": "Public", "pricing": {"priceId": "Free"},
    "listings": {"ja-jp": {"description": "Cytellect"}},
    "applicationPackages": [EXISTING],
}
APP = {
    "packageIdentityName": release.PACKAGE_IDENTITY,
    "lastPublishedApplicationSubmission": {"id": "100"},
}
REPLACEMENTS = [
    {"fileName": EXISTING["fileName"], "fileStatus": "PendingDelete"},
    {"fileName": NAME, "fileStatus": "PendingUpload"},
]
DRAFT = {**PUBLISHED, "id": "101", "status": "PendingCommit", "fileUploadUrl": "example"}
PREPARED = {**DRAFT, "applicationPackages": REPLACEMENTS}
PACKAGE = Path("Cytellect-Store.msix")


class StoreSubmissionTests(TestCase):
    def test_waits_for_the_first_public_release(self):
        store = Mock()
        store.call.side_effect = [APP, {**PUBLISHED, "visibility": "Private"}]
        self.assertFalse(release.submit(store, PACKAGE, VERSION, COMMIT))
        self.assertEqual([call.args[0] for call in store.call.call_args_list], ["GET", "GET"])

    def test_leaves_another_submission_in_certification(self):
        store = Mock()
        store.call.side_effect = [
            {**APP, "pendingApplicationSubmission": {"id": "101"}}, PUBLISHED,
            {**DRAFT, "status": "Certification"},
        ]
        self.assertFalse(release.submit(store, PACKAGE, VERSION, COMMIT))
        self.assertEqual([call.args[0] for call in store.call.call_args_list], ["GET", "GET", "GET"])

    @patch.object(release, "upload_package")
    def test_replaces_only_the_package_and_keeps_listing_and_price(self, upload):
        store = Mock()
        store.call.side_effect = [
            APP, PUBLISHED, DRAFT, PREPARED, PREPARED, {"status": "CommitStarted"},
        ]
        self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT))
        request = store.call.call_args_list[3].kwargs["body"]
        self.assertEqual(request["listings"], PUBLISHED["listings"])
        self.assertEqual(request["pricing"], PUBLISHED["pricing"])
        self.assertEqual(request["applicationPackages"], REPLACEMENTS)
        upload.assert_called_once_with("example", PACKAGE, NAME)
        store.call.assert_called_with("POST", "/submissions/101/commit")

    @patch.object(release, "upload_package")
    def test_does_not_commit_a_submission_changed_during_upload(self, upload):
        store = Mock()
        store.call.side_effect = [
            {**APP, "pendingApplicationSubmission": {"id": "101"}}, PUBLISHED,
            PREPARED, {**PREPARED, "pricing": {"priceId": "changed"}},
        ]
        with self.assertRaisesRegex(release.StoreError, "changed while"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        upload.assert_called_once()
        self.assertTrue(all(call.args[0] == "GET" for call in store.call.call_args_list))


OLDER = "a" * 40
STALE_NAME = f"Cytellect-Store-1.0.3.9-{OLDER}.msix"
PENDING_APP = {**APP, "pendingApplicationSubmission": {"id": "101"}}
STALE = {
    **PREPARED,
    "applicationPackages": [
        {"fileName": EXISTING["fileName"], "fileStatus": "PendingDelete"},
        {"fileName": STALE_NAME, "fileStatus": "PendingUpload"},
    ],
}
NEW_DRAFT = {**DRAFT, "id": "102"}
NEW_PREPARED = {**PREPARED, "id": "102"}


def methods(store):
    return [(call.args[0], *call.args[1:2]) for call in store.call.call_args_list]


class UnfinishedSubmissionTests(TestCase):
    @patch.object(release, "upload_package")
    def test_replaces_a_draft_an_earlier_run_left_for_another_commit(self, upload):
        store = Mock()
        store.call.side_effect = [
            PENDING_APP, PUBLISHED, STALE, {}, APP, NEW_DRAFT, NEW_PREPARED, NEW_PREPARED,
            {"status": "CommitStarted"},
        ]
        self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT))
        self.assertIn(("DELETE", "/submissions/101"), methods(store))
        upload.assert_called_once_with("example", PACKAGE, NAME)
        store.call.assert_called_with("POST", "/submissions/102/commit")

    def test_keeps_an_unfinished_draft_whose_settings_someone_changed(self):
        store = Mock()
        store.call.side_effect = [
            PENDING_APP, PUBLISHED, {**STALE, "listings": {"ja-jp": {"description": "edited"}}},
        ]
        with self.assertRaisesRegex(release.StoreError, "needs attention"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        self.assertNotIn("DELETE", [method for method, *_ in methods(store)])

    def test_keeps_a_draft_with_a_package_this_workflow_did_not_name(self):
        manual = {**STALE, "applicationPackages": [
            {"fileName": EXISTING["fileName"], "fileStatus": "PendingDelete"},
            {"fileName": "Cytellect-1.0.5.0.msix", "fileStatus": "Uploaded"},
        ]}
        store = Mock()
        store.call.side_effect = [PENDING_APP, PUBLISHED, manual]
        with self.assertRaisesRegex(release.StoreError, "needs attention"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        self.assertNotIn("DELETE", [method for method, *_ in methods(store)])

    def test_stops_when_the_unfinished_draft_could_not_be_deleted(self):
        store = Mock()
        store.call.side_effect = [
            PENDING_APP, PUBLISHED, STALE, release.StoreError("Microsoft Store API failed (HTTP 409)."),
            PENDING_APP,
        ]
        with self.assertRaisesRegex(release.StoreError, "could not be replaced"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        self.assertNotIn(("POST", "/submissions"), methods(store))

    @patch.object(release, "upload_package", side_effect=release.StoreError("upload failed"))
    def test_deletes_its_new_draft_when_the_upload_fails(self, upload):
        store = Mock()
        store.call.side_effect = [APP, PUBLISHED, DRAFT, PREPARED, {}]
        with self.assertRaisesRegex(release.StoreError, "upload failed"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        store.call.assert_called_with("DELETE", "/submissions/101")

    def test_deletes_a_new_draft_that_did_not_inherit_the_public_release(self):
        store = Mock()
        store.call.side_effect = [APP, PUBLISHED, {**DRAFT, "visibility": "Private"}, {}]
        with self.assertRaisesRegex(release.StoreError, "did not inherit"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        store.call.assert_called_with("DELETE", "/submissions/101")

    @patch.object(release, "upload_package")
    def test_does_not_delete_a_resumed_draft_when_the_upload_fails(self, upload):
        upload.side_effect = release.StoreError("upload failed")
        store = Mock()
        store.call.side_effect = [PENDING_APP, PUBLISHED, PREPARED]
        with self.assertRaisesRegex(release.StoreError, "upload failed"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        self.assertNotIn("DELETE", [method for method, *_ in methods(store)])


MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10">
  <Identity Name="{name}" Publisher="CN=Test" Version="{version}" ProcessorArchitecture="{arch}" />
</Package>
"""


class PackageVerificationTests(TestCase):
    def build(self, directory: Path, *, name=release.PACKAGE_IDENTITY, arch="x64", commit=COMMIT,
              receipt_commit=COMMIT):
        package = directory / "Cytellect-Store.msix"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("AppxManifest.xml", MANIFEST.format(name=name, version=VERSION, arch=arch))
            archive.writestr("store-package.json", json.dumps({"version": VERSION, "source_commit": commit}))
        receipt = directory / "Cytellect-Store.json"
        receipt.write_text(json.dumps({
            "version": VERSION, "source_commit": receipt_commit, "identity": release.PACKAGE_IDENTITY,
            "msix_bytes": package.stat().st_size,
            "msix_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        }), encoding="utf-8")
        return package, receipt

    def test_accepts_the_package_its_receipt_describes(self):
        with tempfile.TemporaryDirectory() as directory:
            package, receipt = self.build(Path(directory))
            self.assertEqual(release.verify_package(package, receipt, COMMIT), VERSION)

    def test_refuses_a_package_changed_after_the_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            package, receipt = self.build(Path(directory))
            with package.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"Q")
            with self.assertRaisesRegex(release.StoreError, "checksum"):
                release.verify_package(package, receipt, COMMIT)

    def test_refuses_a_receipt_for_another_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            package, receipt = self.build(Path(directory), receipt_commit=OLDER)
            with self.assertRaisesRegex(release.StoreError, "selected commit"):
                release.verify_package(package, receipt, COMMIT)

    def test_refuses_a_package_built_from_another_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            package, receipt = self.build(Path(directory), commit=OLDER)
            with self.assertRaisesRegex(release.StoreError, "embedded build record"):
                release.verify_package(package, receipt, COMMIT)

    def test_refuses_another_identity_or_architecture(self):
        for options in ({"name": "Cytellect.Development"}, {"arch": "arm64"}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                package, receipt = self.build(Path(directory), **options)
                with self.assertRaisesRegex(release.StoreError, "manifest"):
                    release.verify_package(package, receipt, COMMIT)

    def test_refuses_an_abbreviated_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            package, receipt = self.build(Path(directory))
            with self.assertRaisesRegex(release.StoreError, "full main commit"):
                release.verify_package(package, receipt, COMMIT[:12])


class UploadTests(TestCase):
    URL = "https://example.blob.core.windows.net/ingestion/upload?sv=2023-11-03&sig=secret"

    def upload(self, status: int, url: str = URL):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "Cytellect-Store.msix"
            package.write_bytes(b"package")
            uploaded = {}

            def request(method, path, body, headers):
                uploaded.update(method=method, path=path, headers=headers)
                with zipfile.ZipFile(body) as archive:
                    uploaded["names"] = archive.namelist()

            connection = MagicMock()
            connection.request.side_effect = request
            connection.getresponse.return_value.__enter__.return_value.status = status
            with patch.object(release.http.client, "HTTPSConnection", return_value=connection) as opened:
                release.upload_package(url, package, NAME)
            opened.assert_called_once_with("example.blob.core.windows.net", timeout=240)
            return uploaded

    def test_puts_one_zip_holding_the_named_package_to_the_returned_blob(self):
        uploaded = self.upload(201)
        self.assertEqual(uploaded["method"], "PUT")
        self.assertEqual(uploaded["path"], "/ingestion/upload?sv=2023-11-03&sig=secret")
        self.assertEqual(uploaded["headers"]["x-ms-blob-type"], "BlockBlob")
        self.assertEqual(uploaded["names"], [NAME])

    def test_reports_a_refused_upload(self):
        with self.assertRaisesRegex(release.StoreError, "HTTP 403"):
            self.upload(403)

    def test_refuses_an_unexpected_destination(self):
        for url in ("http://example.blob.core.windows.net/x?sig=1", "https://example.com/x?sig=1",
                    "https://user@example.blob.core.windows.net/x?sig=1",
                    "https://example.blob.core.windows.net/x"):
            with self.subTest(url=url), self.assertRaisesRegex(release.StoreError, "upload destination"):
                release.upload_package(url, PACKAGE, NAME)


class RequestTests(TestCase):
    def test_a_deleted_submission_answers_without_a_body(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b""
        with patch.object(release.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(release.request_json("https://x", "DELETE", "Store", {}), {})
            with self.assertRaisesRegex(release.StoreError, "readable"):
                release.request_json("https://x", "GET", "Store", {})


WORKFLOW = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "windows-store-release.yml").read_text(
    encoding="utf-8")


class WorkflowTests(TestCase):
    def job(self, name: str) -> str:
        lines = WORKFLOW.splitlines()
        start = lines.index(f"  {name}:")
        end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  [\w-]+:\s*$", lines[i])), len(lines))
        return "\n".join(lines[start:end])

    def test_nothing_runs_on_a_schedule(self):
        self.assertNotIn("schedule", WORKFLOW)

    def test_the_package_is_built_only_while_submissions_are_enabled(self):
        self.assertIn("vars.STORE_SUBMISSIONS_ENABLED == 'true'", self.job("package"))

    def test_only_a_package_accepted_on_both_scenarios_reaches_the_approval_gated_job(self):
        accept = self.job("accept")
        self.assertIn("needs: package", accept)
        self.assertIn("scenario: [fresh, migration]", accept)
        self.assertIn("name: store-msix-${{ github.sha }}", accept)
        select = self.job("select")
        self.assertIn("needs: accept", select)
        self.assertIn("store-msix-accepted-${context.sha}-${scenario}", select)
        self.assertIn("fresh.has(item.workflow_run.id) && migration.has(item.workflow_run.id)", select)
        submit = self.job("submit")
        self.assertIn("needs: select", submit)
        self.assertIn("environment: store-release", submit)
        self.assertNotIn("environment:", "\n".join(self.job(name) for name in ("package", "accept", "select")))

    def test_store_and_development_packages_share_one_build_script(self):
        development = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "windows-msix.yml").read_text(
            encoding="utf-8")
        for text in (WORKFLOW, development):
            self.assertIn("./packaging/windows/msix/ci-build.ps1", text)
            self.assertIn("./packaging/windows/msix/ci-sign.ps1", text)
            self.assertNotIn("build_windows_msix.py", text)


class ResumedSubmissionTests(TestCase):
    def test_does_not_resume_a_draft_for_this_package_whose_settings_someone_changed(self):
        store = Mock()
        store.call.side_effect = [PENDING_APP, PUBLISHED, {**PREPARED, "pricing": {"priceId": "changed"}}]
        with self.assertRaisesRegex(release.StoreError, "needs attention"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        self.assertNotIn("DELETE", [method for method, *_ in methods(store)])
