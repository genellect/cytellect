import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

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
    "minimumDirectXVersion": "DX11", "minimumSystemRam": "Memory4GB",
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
    {"fileName": EXISTING["fileName"], "fileStatus": "PendingDelete",
     "minimumDirectXVersion": "DX11", "minimumSystemRam": "Memory4GB"},
    {"fileName": NAME, "fileStatus": "PendingUpload",
     "minimumDirectXVersion": "DX11", "minimumSystemRam": "Memory4GB"},
]
DRAFT = {**PUBLISHED, "id": "101", "status": "PendingCommit", "fileUploadUrl": "example"}
PREPARED = {**DRAFT, "applicationPackages": REPLACEMENTS}
PACKAGE = Path("Cytellect-Store.msix")


class StoreSubmissionTests(TestCase):
    @patch.object(release, "upload_package")
    def test_recover_only_the_named_unmodified_clone(self, upload):
        for requested, draft, allowed in [
            ("101", DRAFT, True), ("", DRAFT, False),
            ("102", DRAFT, False), ("101", {**DRAFT, "pricing": {}}, False),
            ("101", {**DRAFT, "visibility": "Private"}, False),
            ("101", {**DRAFT, "status": "CommitFailed"}, False),
            ("101", {**DRAFT, "applicationPackages": []}, False),
            ("101", {**DRAFT, "listings": {}}, False),
        ]:
            with self.subTest(requested=requested, allowed=allowed):
                store = Mock()
                store.call.side_effect = [
                    {**APP, "pendingApplicationSubmission": {"id": "101"}}, PUBLISHED,
                    draft, PREPARED, PREPARED, {"status": "CommitStarted"},
                ]
                if allowed:
                    self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT, requested))
                    self.assertEqual(store.call.call_args_list[3].kwargs["body"], {
                        "visibility": "Public", "pricing": PUBLISHED["pricing"],
                        "listings": PUBLISHED["listings"], "applicationPackages": REPLACEMENTS,
                    })
                else:
                    with self.assertRaises(release.StoreError):
                        release.submit(store, PACKAGE, VERSION, COMMIT, requested)
                    self.assertTrue(all(call.args[0] == "GET" for call in store.call.call_args_list))

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
