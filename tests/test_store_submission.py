import importlib.util
import io
from email.message import Message
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

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
    "minimumDirectXVersion": "DirectX100", "minimumSystemRam": "Memory2GB",
}
PUBLISHED = {
    "id": "100", "visibility": "Public", "pricing": {"priceId": "Free"},
    "listings": {"ja-jp": {"baseListing": {"description": "Cytellect"}, "platformOverrides": {}}},
    "applicationPackages": [EXISTING],
}
APP = {
    "packageIdentityName": release.PACKAGE_IDENTITY,
    "lastPublishedApplicationSubmission": {"id": "100"},
}
REPLACEMENTS = [
    {"fileName": EXISTING["fileName"], "fileStatus": "PendingDelete",
     "minimumDirectXVersion": "DirectX100", "minimumSystemRam": "Memory2GB"},
    {"fileName": NAME, "fileStatus": "PendingUpload",
     "minimumDirectXVersion": "DirectX100", "minimumSystemRam": "Memory2GB"},
]
DRAFT = {**PUBLISHED, "id": "101", "status": "PendingCommit", "fileUploadUrl": "example"}
PREPARED = {**DRAFT, "applicationPackages": REPLACEMENTS}
PACKAGE = Path("Cytellect-Store.msix")


class StoreSubmissionTests(TestCase):
    @patch.object(release, "upload_package")
    def test_base_price_uses_free_only_for_confirmed_published_submission(self, upload):
        pricing = {"priceId": "Base", "marketSpecificPricings": {"JP": "Free"}, "trialPeriod": "NoTrial"}
        wire = {**pricing, "priceId": "Free"}
        prepared = {**PREPARED, "pricing": wire}
        store = Mock()
        store.call.side_effect = [APP, {**PUBLISHED, "pricing": pricing}, {**DRAFT, "pricing": pricing},
                                  prepared, prepared, {"status": "CommitStarted"}]
        self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT, confirmed_free_id="100"))
        self.assertEqual(store.call.call_args_list[3].kwargs["body"]["pricing"], wire)
        self.assertEqual(pricing["priceId"], "Base")
        upload.assert_called_once()

    @patch.object(release, "upload_package")
    def test_confirmed_base_price_survives_store_reading_it_back_as_base(self, upload):
        pricing = {"priceId": "Base", "marketSpecificPricings": {"JP": "Free"}}
        echoed = {**PREPARED, "pricing": pricing}
        cases = {
            "fresh draft, PUT echoes Base": ([APP, {**PUBLISHED, "pricing": pricing}, {**DRAFT, "pricing": pricing},
                                              echoed, echoed, {"status": "CommitStarted"}], ""),
            "resume the attached candidate": ([{**APP, "pendingApplicationSubmission": {"id": "101"}},
                                               {**PUBLISHED, "pricing": pricing}, echoed, echoed,
                                               {"status": "CommitStarted"}], ""),
            "recover a Base clone": ([{**APP, "pendingApplicationSubmission": {"id": "101"}},
                                      {**PUBLISHED, "pricing": pricing}, {**DRAFT, "pricing": pricing},
                                      echoed, echoed, {"status": "CommitStarted"}], "101"),
        }
        for label, (responses, recover) in cases.items():
            store = Mock()
            store.call.side_effect = responses
            self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT, recover, confirmed_free_id="100"), label)
            store.call.assert_called_with("POST", "/submissions/101/commit")
        # Without the confirmation, a Base echo is never treated as free.
        store = Mock()
        store.call.side_effect = [{**APP, "pendingApplicationSubmission": {"id": "101"}},
                                  {**PUBLISHED, "pricing": pricing}, echoed]
        with self.assertRaisesRegex(release.StoreError, "Base"):
            release.submit(store, PACKAGE, VERSION, COMMIT)

    @patch.object(release, "upload_package")
    def test_price_comparison_ignores_keys_that_do_not_set_the_price(self, upload):
        clone = {**DRAFT, "pricing": {"priceId": "Free", "sales": [], "trialPeriod": "NoFreeTrial"}}
        store = Mock()
        store.call.side_effect = [APP, PUBLISHED, clone, PREPARED, PREPARED, {"status": "CommitStarted"}]
        self.assertTrue(release.submit(store, PACKAGE, VERSION, COMMIT))
        store = Mock()
        store.call.side_effect = [APP, PUBLISHED, {**DRAFT, "pricing": {"priceId": "Tier1012"}}]
        with self.assertRaisesRegex(release.StoreError, "pricing differs"):
            release.submit(store, PACKAGE, VERSION, COMMIT)

    @patch.object(release.urllib.request, "build_opener")
    def test_plain_words_and_broken_errors_do_not_become_diagnostics(self, opener):
        url = release.APP + "/submissions/101"
        body = b'{"error":{"code":"InvalidRequest","message":"Body does not match the expected description."}}'
        opener.return_value.open.side_effect = HTTPError(url, 400, "bad", Message(), io.BytesIO(body))
        with self.assertRaisesRegex(release.StoreError, r"^Update failed \(HTTP 400\)\. Code: InvalidRequest$"):
            release.request_json(url, "PUT", "Update", {})
        for error in [HTTPError(url, 400, "bad", None, io.BytesIO(body)), HTTPError(url, 400, "bad", Message(), None)]:
            opener.return_value.open.side_effect = error
            with self.assertRaisesRegex(release.StoreError, r"^Update failed \(HTTP 400\)"):
                release.request_json(url, "PUT", "Update", {})

    def test_ambiguous_or_unconfirmed_price_stops_before_creating_a_draft(self):
        for pricing, confirmation in [
            ({"priceId": "Base"}, ""), ({"priceId": "Base"}, "99"),
            ({"priceId": "Base", "marketSpecificPricings": {"JP": "Tier1012"}}, "100"),
            ({"priceId": ""}, "100"), (None, "100"),
        ]:
            store = Mock()
            store.call.side_effect = [APP, {**PUBLISHED, "pricing": pricing}]
            with self.assertRaisesRegex(release.StoreError, "pric", msg=(pricing, confirmation)):
                release.submit(store, PACKAGE, VERSION, COMMIT, confirmed_free_id=confirmation)
            self.assertEqual([call.args[0] for call in store.call.call_args_list], ["GET", "GET"])

    def test_existing_paid_price_is_preserved_even_when_free_confirmation_is_set(self):
        pricing = {"priceId": "Tier1012", "marketSpecificPricings": {"JP": "Tier96"}}
        self.assertEqual(release.package_update_pricing({**PUBLISHED, "pricing": pricing}, "100"), pricing)

    @patch.object(release, "upload_package")
    def test_resume_with_modified_price_stops_before_upload(self, upload):
        store = Mock()
        store.call.side_effect = [{**APP, "pendingApplicationSubmission": {"id": "101"}},
                                  PUBLISHED, {**PREPARED, "pricing": {"priceId": "Tier1012"}}]
        with self.assertRaisesRegex(release.StoreError, "pricing"):
            release.submit(store, PACKAGE, VERSION, COMMIT)
        upload.assert_not_called()

    @patch.object(release.urllib.request, "build_opener")
    def test_invalid_request_exposes_schema_terms_without_echoing_values(self, opener):
        headers = Message()
        headers["MS-CorrelationId"] = "11111111-1111-4111-8111-111111111111"
        url = release.APP + "/submissions/101"
        body = b'{"error":{"code":"InvalidRequest","message":"Invalid applicationPackages[0].fileName: secret"}}'
        opener.return_value.open.side_effect = HTTPError(url, 400, "bad", headers, io.BytesIO(body))
        with self.assertRaises(release.StoreError) as raised:
            release.request_json(url, "PUT", "Update", {})
        self.assertEqual(str(raised.exception), "Update failed (HTTP 400). "
                         "Request ID: 11111111-1111-4111-8111-111111111111 "
                         "Code: InvalidRequest Fields mentioned: applicationPackages, fileName")

    @patch.object(release.urllib.request, "build_opener")
    def test_invalid_response_body_preserves_http_error(self, opener):
        url = release.APP + "/submissions/101"
        opener.return_value.open.side_effect = HTTPError(url, 400, "bad", Message(), io.BytesIO(b"private"))
        with self.assertRaisesRegex(release.StoreError, r"^Update failed \(HTTP 400\)\.$"):
            release.request_json(url, "PUT", "Update", {})

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
