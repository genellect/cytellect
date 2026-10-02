"""Content identifiers for the scientific code, independent of a mutable Git checkout."""

import hashlib
import importlib.metadata
import os
import platform
import re
from pathlib import Path


def software_identity():
    import cytellect_analysis
    import cytellect_api

    import cytellect_worker

    files = {}
    for module in (cytellect_analysis, cytellect_api, cytellect_worker):
        directory = Path(module.__file__).parent
        for path in sorted(directory.rglob("*.py")):
            key = module.__name__ + "/" + path.relative_to(directory).as_posix()
            files[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    aggregate = hashlib.sha256(
        "".join(k + ":" + v + "\n" for k, v in sorted(files.items())).encode()
    ).hexdigest()
    revision = os.environ.get("CYTELLECT_CODE_REVISION", "")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        revision = None
    return {
        "version": importlib.metadata.version("cytellect"),
        "git_commit": revision,
        "source_sha256": aggregate,
        "source_files": files,
        "python": platform.python_version(),
        "platform": platform.system(),
    }
