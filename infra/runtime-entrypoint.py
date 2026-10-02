"""Create private temporary directories before multipart/image libraries import."""

import os
from pathlib import Path

os.umask(0o077)
root = Path(os.environ["CYTELLECT_DATA_DIR"])
root.mkdir(mode=0o700, parents=True, exist_ok=True)
for name in ("tmp", "matplotlib"):
    (root / name).mkdir(mode=0o700, exist_ok=True)
os.execvp(os.sys.argv[1], os.sys.argv[1:])
