"""Write the proposal service's strict output schema from the Python contract."""
import argparse
import json
from pathlib import Path

from cytellect_analysis.proposal_contracts import ProposalContext, draft_json_schema

TARGET = Path(__file__).resolve().parents[1] / "services/proposal-worker/src/contract.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps({"draft_schema": draft_json_schema(), "processing_draft_schema": draft_json_schema(processing_only=True), "legacy_draft_schema": draft_json_schema(legacy=True), "context_schema": ProposalContext.model_json_schema()},
                      indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            raise SystemExit("services/proposal-worker/src/contract.json is stale; run scripts/proposal_schema.py")
        print("Proposal service contract is current.")
        return
    TARGET.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
