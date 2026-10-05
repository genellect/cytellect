"""Docker acceptance using the same closed-form arithmetic and replay checks.

Unlike installed-copy acceptance, this authenticates with an invitation from the
container's Store. It does not fabricate local-setup responses or bypass source
hash comparisons. Only generated test images are uploaded.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from verify_installed_regions import LocalSession, verify_workflow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--api-origin", required=True)
    parser.add_argument("--web-origin", required=True)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"cytellect-[a-z0-9-]+-api-1", args.container):
        raise ValueError("explicit_cytellect_container_required")
    if not re.fullmatch(r"[a-f0-9]{40}", args.expected_source):
        raise ValueError("expected_source_required")
    web = urlsplit(args.web_origin)
    if (web.scheme != "http" or web.hostname not in ("localhost", "127.0.0.1")
            or not web.port or web.username or web.password or web.query or web.fragment
            or web.path not in ("", "/")):
        raise ValueError("loopback_web_origin_required")
    output = args.output.resolve()
    checkout = Path(__file__).resolve().parents[1]
    if output == checkout or checkout in output.parents:
        raise ValueError("acceptance_output_must_be_external")
    output.mkdir(parents=True, exist_ok=False)
    session = LocalSession(args.api_origin, app_origin=args.web_origin)
    token = subprocess.check_output([
        args.docker, "exec", args.container, "python", "-c",
        "from pathlib import Path;from cytellect_api.db import Store;print(Store(Path('/data')).invite(600))",
    ], text=True, timeout=30).strip()
    session.json("/v1/invitations/redeem", {"token": token})
    result = verify_workflow(session, output, args.expected_source, initialize_local=False)
    receipt = {
        "schema": "cytellect-docker-regions-acceptance/1", "passed": True,
        "source_commit": args.expected_source,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shared_checks_sha256": hashlib.sha256((checkout / "scripts/verify_installed_regions.py").read_bytes()).hexdigest(),
        "scope": "Docker generated-pixel closed-form inference and full export/replay; not installed-copy or biological certification",
        "workflow": result,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "replay": result["replay"]}))


if __name__ == "__main__":
    main()
