from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from scripts import submit_windows_msix as release


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
