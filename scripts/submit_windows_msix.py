"""Submit an existing Cytellect Store package through the Microsoft Store API."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

APPLICATION = "9PGKTQGV7X5C"
PACKAGE_IDENTITY = "24D2FD66.Cytellect"
AUTHORITY = "https://login.microsoftonline.com"
RESOURCE = "https://manage.devcenter.microsoft.com"
APP = f"{RESOURCE}/v1.0/my/applications/{APPLICATION}"
APPX_NS = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
WRITABLE_FIELDS = {
    "applicationCategory", "pricing", "visibility", "targetPublishMode", "targetPublishDate",
    "listings", "hardwarePreferences", "automaticBackupEnabled", "canInstallOnRemovableMedia",
    "isGameDvrEnabled", "gamingOptions", "hasExternalInAppProducts", "meetAccessibilityGuidelines",
    "notesForCertification", "packageDeliveryOptions", "enterpriseLicensing",
    "allowMicrosoftDecideAppAvailabilityToFutureDeviceFamilies",
    "allowMicrosftDecideAppAvailabilityToFutureDeviceFamilies", "allowTargetFutureDeviceFamilies",
    "trailers",
}
IN_REVIEW = {
    "CommitStarted", "PreProcessing", "Certification", "Release",
    "PendingPublication", "Publishing", "Published",
}


class StoreError(RuntimeError):
    """An error that can be printed without exposing credentials or submission contents."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validation_diagnostic(error: urllib.error.HTTPError) -> str:
    """Report only known schema terms and a Microsoft request ID, never raw error messages."""
    fields = WRITABLE_FIELDS | {
        "applicationPackages", "fileName", "fileStatus", "minimumDirectXVersion", "minimumSystemRam",
        "baseListing", "images", "imageType", "description", "keywords", "priceId", "marketSpecificPricings",
        "packageRollout", "fallbackSubmissionId", "isMandatoryUpdate", "mandatoryUpdateEffectiveDate",
    }
    codes = {"InvalidRequest", "InvalidParameter", "InvalidParameterValue", "InvalidValue", "InvalidOperation",
             "InvalidState", "BadRequest", "InvalidRequestBody", "InvalidSubmission", "InvalidArgument",
             "ValidationError", "ResourceNotFound", "ServiceError", "PackageValidationFailed"}
    parts = []
    request_id = next((error.headers.get(key) for key in (
        "MS-CorrelationId", "x-ms-correlation-request-id", "x-ms-request-id", "request-id",
    ) if error.headers.get(key)), None)
    if request_id and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", request_id):
        parts.append(f"Request ID: {request_id}")
    try:
        payload = json.loads(error.read(65536))
    except (OSError, ValueError, RecursionError, http.client.HTTPException):
        payload = None
    if isinstance(payload, dict):
        # Some endpoints use an error envelope; others put code and message at the root.
        detail = payload.get("error", payload)
        if isinstance(detail, dict):
            code = detail.get("code")
            if isinstance(code, str) and code in codes:
                parts.append(f"Code: {code}")
            terms = {term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9]*", json.dumps(detail))}
            mentioned = sorted(field for field in fields if field.casefold() in terms)
            if mentioned:
                parts.append("Fields mentioned: " + ", ".join(mentioned))
    return " ".join(parts)


def request_json(url: str, method: str, operation: str, headers: dict, data=None) -> dict:
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=90) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        with error:
            detail = validation_diagnostic(error) if url.startswith(APP + "/") and error.code == 400 else ""
        raise StoreError(f"{operation} failed (HTTP {error.code}). {detail}".rstrip()) from None
    except (OSError, ValueError):
        raise StoreError(f"{operation} did not return a readable API response.") from None
    if not isinstance(result, dict):
        raise StoreError(f"{operation} returned an unexpected API response.")
    return result


class Store:
    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    @classmethod
    def authenticate(cls):
        try:
            tenant = uuid.UUID(os.environ["STORE_TENANT_ID"])
            client = uuid.UUID(os.environ["STORE_CLIENT_ID"])
            secret = os.environ["STORE_CLIENT_SECRET"]
        except (KeyError, ValueError):
            raise StoreError("Configure the Store release environment with Entra credentials.") from None
        if not secret:
            raise StoreError("The Store client secret is empty.")
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials", "client_id": str(client),
            "client_secret": secret, "resource": RESOURCE,
        }).encode("ascii")
        result = request_json(
            f"{AUTHORITY}/{tenant}/oauth2/token", "POST", "Entra authentication",
            {"Content-Type": "application/x-www-form-urlencoded"}, data,
        )
        token = result.get("access_token")
        if not token:
            raise StoreError("Entra authentication did not return an access token.")
        return cls(token)

    def call(self, method: str, suffix: str = "", *, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        return request_json(APP + suffix, method, f"Microsoft Store API {method} {suffix or '/'}", self.headers, data)


def version_parts(version: str) -> tuple[int, ...]:
    if not isinstance(version, str) or not re.fullmatch(r"\d{1,5}(\.\d{1,5}){3}", version):
        raise StoreError("An MSIX version has an invalid format.")
    return tuple(map(int, version.split(".")))


def verify_package(package: Path, receipt_path: Path, commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise StoreError("Expected a full main commit SHA.")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    version = receipt["version"]
    version_parts(version)
    if receipt["identity"] != PACKAGE_IDENTITY or receipt["source_commit"] != commit:
        raise StoreError("The receipt does not match the Store identity and selected commit.")
    if receipt["msix_bytes"] != package.stat().st_size:
        raise StoreError("The MSIX size does not match the receipt.")
    with package.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != receipt["msix_sha256"]:
            raise StoreError("The MSIX checksum does not match the receipt.")
    with zipfile.ZipFile(package) as archive:
        identity = ET.fromstring(archive.read("AppxManifest.xml")).find(APPX_NS + "Identity")
        metadata = json.loads(archive.read("store-package.json"))
    if (identity is None or identity.get("Name") != PACKAGE_IDENTITY
            or identity.get("Version") != version or identity.get("ProcessorArchitecture") != "x64"
            or metadata != {"version": version, "source_commit": commit}):
        raise StoreError("The MSIX manifest and embedded build record do not match the receipt.")
    return version


def upload_package(url: str, package: Path, name: str) -> None:
    sas = urllib.parse.urlsplit(url)
    if (sas.scheme != "https" or not sas.hostname or sas.netloc != sas.hostname
            or not sas.hostname.endswith(".blob.core.windows.net") or not sas.query):
        raise StoreError("The Store returned an unexpected package upload destination.")
    with tempfile.TemporaryDirectory() as directory:
        archive_path = Path(directory) / "submission.zip"
        with zipfile.ZipFile(archive_path, "w", allowZip64=True) as archive:
            archive.write(package, name)
        headers = {
            "Content-Length": str(archive_path.stat().st_size),
            "Content-Type": "application/zip",
            "x-ms-blob-type": "BlockBlob",
            "x-ms-version": "2023-11-03",
        }
        connection = http.client.HTTPSConnection(sas.hostname, timeout=240)
        try:
            with archive_path.open("rb") as stream:
                connection.request("PUT", f"{sas.path}?{sas.query}", body=stream, headers=headers)
                with connection.getresponse() as response:
                    if response.status != 201:
                        raise StoreError(f"Store package upload failed (HTTP {response.status}).")
        except (OSError, http.client.HTTPException):
            raise StoreError("The Store package upload connection failed.") from None
        finally:
            connection.close()


def submission_path(reference: dict) -> str:
    identifier = reference.get("id")
    if not isinstance(identifier, str) or not re.fullmatch(r"\d+", identifier):
        raise StoreError("The Store returned an invalid submission ID.")
    return f"/submissions/{identifier}"


def is_public(submission: dict) -> bool:
    return submission.get("visibility") == "Public"


def has_candidate(submission: dict, name: str) -> bool:
    packages = submission.get("applicationPackages", [])
    return (
        is_public(submission)
        and submission.get("status") == "PendingCommit"
        and sum(item["fileName"] == name for item in packages) == 1
        and all(item["fileStatus"] in {"PendingUpload", "Uploaded"} if item["fileName"] == name
                else item["fileStatus"] == "PendingDelete" for item in packages)
    )


def submit(store: Store, package: Path, version: str, commit: str, recover_id: str = "") -> bool:
    app = store.call("GET")
    if app.get("packageIdentityName") != PACKAGE_IDENTITY:
        raise StoreError("The API resolved to a different Store package identity.")
    published_ref = app.get("lastPublishedApplicationSubmission")
    if not published_ref:
        print("Waiting for a published Store submission.")
        return False
    published = store.call("GET", submission_path(published_ref))
    if not is_public(published):
        print("Waiting for the first public Store release.")
        return False
    suffix = f"-{commit}.msix"
    name = f"Cytellect-Store-{version}{suffix}"
    published_packages = published.get("applicationPackages", [])
    if any(item["fileName"].endswith(suffix) for item in published_packages):
        print(f"{commit} is already published.")
        return True
    if len(published_packages) != 1 or published_packages[0].get("architecture", "").lower() != "x64":
        raise StoreError("The published package layout no longer matches the single x64 MSIX release.")
    if version_parts(published_packages[0]["version"]) >= version_parts(version):
        raise StoreError("The candidate version must be newer than every published package.")
    pending_ref = app.get("pendingApplicationSubmission")
    replacement = {
        "fileName": name, "fileStatus": "PendingUpload",
        "minimumDirectXVersion": published_packages[0].get("minimumDirectXVersion", "None"),
        "minimumSystemRam": published_packages[0].get("minimumSystemRam", "None"),
    }
    if pending_ref:
        path = submission_path(pending_ref)
        draft = store.call("GET", path)
        packages = draft.get("applicationPackages", [])
        if draft.get("status") in IN_REVIEW:
            print(f"Waiting for Store submission {pending_ref['id']} to finish.")
            return any(item["fileName"].endswith(suffix) for item in packages)
        changed_fields = sorted(key for key in WRITABLE_FIELDS if draft.get(key) != published.get(key))
        recover_clone = (
            pending_ref["id"] == recover_id and not changed_fields and packages == published_packages
            and is_public(draft) and draft.get("status") == "PendingCommit"
        )
        if not has_candidate(draft, name) and not recover_clone:
            if pending_ref["id"] == recover_id:
                if packages != published_packages:
                    changed_fields.append("applicationPackages")
                if draft.get("status") != "PendingCommit":
                    changed_fields.append("status")
                raise StoreError(f"Recovery stopped for {recover_id}. Different fields: {', '.join(changed_fields)}.")
            raise StoreError(f"Store submission {pending_ref['id']} needs attention before continuing.")
    else:
        draft = store.call("POST", "/submissions")
        path = submission_path(draft)
        print(f"Created Store submission {draft['id']} for {version}.")
    if not has_candidate(draft, name):
        if not is_public(draft) or draft.get("status") != "PendingCommit":
            raise StoreError("The new submission did not inherit the published public release settings.")
        metadata = {key: value for key, value in draft.items() if key in WRITABLE_FIELDS}
        packages = [
            {"fileName": item["fileName"], "fileStatus": "PendingDelete",
             "minimumDirectXVersion": item.get("minimumDirectXVersion", "None"),
             "minimumSystemRam": item.get("minimumSystemRam", "None")}
            for item in draft.get("applicationPackages", [])
        ]
        draft = store.call("PUT", path, body={
            **metadata, "applicationPackages": [*packages, replacement],
        })
        if any(draft.get(key) != value for key, value in metadata.items()):
            raise StoreError("The Store changed release settings while attaching the package.")
        if not has_candidate(draft, name):
            raise StoreError("The Store did not attach the intended package.")
    upload_package(draft["fileUploadUrl"], package, name)
    current = store.call("GET", path)
    if not has_candidate(current, name) or any(
        current.get(key) != draft.get(key) for key in WRITABLE_FIELDS
    ):
        raise StoreError("The Store submission changed while the package was being uploaded.")
    result = store.call("POST", path + "/commit")
    if result.get("status") not in IN_REVIEW:
        raise StoreError("The Store did not confirm that certification was started.")
    print(f"Submitted {version} from {commit} for Store certification.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        version = verify_package(args.package, args.receipt, args.commit)
        accepted = submit(Store.authenticate(), args.package, version, args.commit,
                          os.environ.get("STORE_RECOVERY_SUBMISSION_ID", ""))
        if accepted and (output := os.environ.get("GITHUB_OUTPUT")):
            with Path(output).open("a", encoding="utf-8") as stream:
                stream.write("accepted=true\n")
    except StoreError as error:
        parser.exit(1, f"{error}\n")
    except (KeyError, OSError, ValueError, ET.ParseError, zipfile.BadZipFile):
        parser.exit(1, "The package, receipt or Store API response was incomplete.\n")


if __name__ == "__main__":
    main()
