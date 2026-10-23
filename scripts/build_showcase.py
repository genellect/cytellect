"""Build the serverless public showcase with the real pipeline (see docs/showcase.md).

Usage (runtimes and scratch data outside the checkout):

    CYTELLECT_CELLPOSE_PYTHON=/opt/cellpose-runtime/bin/python \
    CYTELLECT_CELLPOSE_MODEL_DIR=/opt/cellpose-models \
    uv run python scripts/build_showcase.py services/showcase/datasets/<dataset>.json \
        --work /private/showcase-build --cache /private/showcase-cache --fiji /opt/fiji

Stages: prepare, scenario, grid, publish, snapshot, qa (``--stages`` selects a subset).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "showcase" / "src"))

from cytellect_showcase.build import main  # noqa: E402

if __name__ == "__main__":
    main()
