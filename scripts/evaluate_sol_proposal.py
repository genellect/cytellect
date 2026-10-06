"""Semantic oracle for the public-only Worker evaluation; never calls a model.

Reads one registered public evaluation context/draft via stdin and emits fixed
validation codes. Used by services/proposal-worker/src/public-evaluation.test.ts.
"""
import json
import sys

from cytellect_analysis.proposal_contracts import ProposalContext
from cytellect_analysis.proposal_validation import ProposalRejected, validate_draft


def main() -> None:
    # JSON over a pipe is UTF-8. Windows locale defaults can otherwise corrupt
    # Japanese goals before Pydantic sees them; never rely on console encoding.
    request = json.loads(sys.stdin.buffer.read())
    try:
        validated = validate_draft(
            ProposalContext.model_validate(request["context"]), request["draft"],
            model="gpt-6.1-sol", prompt_version="2026-10-06.2",
        )
        print(json.dumps({"valid": True, "codes": [], "needs_confirmation": validated.needs_confirmation}))
    except ProposalRejected as error:
        print(json.dumps({"valid": False, "codes": error.codes}))


if __name__ == "__main__":
    main()
