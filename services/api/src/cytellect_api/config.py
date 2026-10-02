import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    app_origin: str = "http://localhost:3000"
    secure_cookies: bool = True
    demo: bool = False
    fiji_executable: str = ""
    retention_seconds: int = 86400
    job_timeout_seconds: int = 3600
    max_upload_bytes: int = 2 * 1024**3
    max_fields: int = 100
    worker_memory_mb: int = 4096

    @property
    def cookie_name(self):
        return "__Host-cytellect" if self.secure_cookies else "cytellect_dev"

    @classmethod
    def from_env(cls):
        configured = os.environ.get("CYTELLECT_DATA_DIR")
        if not configured:
            raise ValueError("CYTELLECT_DATA_DIR must explicitly name a private runtime volume")
        root = Path(configured).resolve()
        checkout = Path(__file__).resolve().parents[4]
        if root == checkout or checkout in root.parents:
            raise ValueError("Research data must be outside the repository")
        return cls(
            root,
            os.environ.get("CYTELLECT_APP_ORIGIN", "http://localhost:3000").rstrip("/"),
            os.environ.get("CYTELLECT_SECURE_COOKIES", "true").lower() == "true",
            os.environ.get("CYTELLECT_DEMO", "false").lower() == "true",
            os.environ.get("CYTELLECT_FIJI_EXECUTABLE", ""),
            retention_seconds=int(os.environ.get("CYTELLECT_RETENTION_SECONDS", "86400")),
            job_timeout_seconds=int(os.environ.get("CYTELLECT_JOB_TIMEOUT_SECONDS", "3600")),
            max_upload_bytes=int(os.environ.get("CYTELLECT_MAX_UPLOAD_BYTES", str(2 * 1024**3))),
            max_fields=int(os.environ.get("CYTELLECT_MAX_FIELDS", "100")),
            worker_memory_mb=int(os.environ.get("CYTELLECT_WORKER_MEMORY_MB", "4096")),
        )


def configure_private_tmp(settings: Settings) -> Path:
    """Multipart and library scratch stays in the private runtime volume."""
    root = settings.data_dir.resolve()
    checkout = Path(__file__).resolve().parents[4]
    if root == checkout or root.is_relative_to(checkout):
        raise ValueError("Research data must be outside the repository")
    temporary = root / "tmp"
    if temporary.is_symlink() or temporary.resolve().parent != root:
        raise ValueError("Private temporary directory cannot redirect outside runtime")
    temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        temporary.chmod(0o700)
    for variable in ("TMPDIR", "TEMP", "TMP"):
        os.environ[variable] = str(temporary)
    # tempfile caches its selected directory; assigning explicitly also protects
    # imports that queried it before application startup.
    tempfile.tempdir = str(temporary)
    return temporary
