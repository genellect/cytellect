import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cytellect_analysis.proposal_contracts import PROPOSAL_PROMPT_VERSION

from .public_uploads import load_allowlist


def checkout_root(module_file: str | Path | None = None) -> Path | None:
    """The source checkout that private data must stay outside, if any.

    In a checkout this module lives at ``services/api/src/cytellect_api``, four
    levels below the repository. An installed wheel only resolves to the
    filesystem root when site-packages is itself four levels deep (Pyodide's
    ``/lib/python3.x/site-packages``); every path would then count as inside the
    repository. A filesystem root is still treated as a checkout when it holds
    the project file, so a repository copied to ``/`` keeps its protection.
    """
    candidate = Path(module_file if module_file is not None else __file__).resolve().parents[4]
    if candidate == Path(candidate.anchor) and not (candidate / "pyproject.toml").is_file():
        return None
    return candidate


def _inside_checkout(path: Path) -> bool:
    checkout = checkout_root()
    return checkout is not None and (path == checkout or path.is_relative_to(checkout))


def _proposal_token_from_env() -> str:
    """An optional Docker-mounted device credential; never a provider API key."""
    direct = os.environ.get("CYTELLECT_PROPOSAL_TOKEN", "")
    secret_file = os.environ.get("CYTELLECT_PROPOSAL_TOKEN_FILE", "")
    if not secret_file:
        return direct
    if direct:
        raise ValueError("proposal_token_sources_conflict")
    try:
        path = Path(secret_file).expanduser().resolve()
        if _inside_checkout(path) or not path.is_file():
            raise ValueError("invalid_source")
        with path.open("rb") as source:
            raw = source.read(257)
        token = raw.decode("ascii").strip()
        if len(raw) > 256 or re.fullmatch(r"[A-Za-z0-9_-]{20,200}", token) is None:
            raise ValueError("invalid_token")
        return token
    except (OSError, UnicodeError, ValueError):
        raise ValueError("proposal_token_file_invalid") from None


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
    proposal_url: str = ""
    proposal_token: str = ""
    proposal_timeout_seconds: int = 300
    proposal_model: str = "gpt-6.1-sol"
    proposal_prompt_version: str = PROPOSAL_PROMPT_VERSION
    desktop_owner: bool = False
    workspace_retention_mode: str = "ttl"
    # Digests of the registered public files a shared development environment accepts (public_uploads.py).
    upload_allowlist: frozenset[str] | None = None

    def __post_init__(self):
        if self.workspace_retention_mode not in {"ttl", "manual"}:
            raise ValueError("workspace_retention_mode_invalid")
        # Manual retention is for a researcher's own PC (Windows launcher or Docker
        # Desktop on loopback). A hosted service keeps continuous TTL deletion.
        if (self.workspace_retention_mode == "manual"
                and urlsplit(self.app_origin).hostname not in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("workspace_retention_manual_requires_loopback")

    @property
    def retention_policy(self):
        return {"retention_mode": self.workspace_retention_mode,
                "retention_hours": None if self.workspace_retention_mode == "manual"
                else self.retention_seconds / 3600}

    @property
    def cookie_name(self):
        return "__Host-cytellect" if self.secure_cookies else "cytellect_dev"

    @classmethod
    def from_env(cls):
        configured = os.environ.get("CYTELLECT_DATA_DIR")
        if not configured:
            raise ValueError("CYTELLECT_DATA_DIR must explicitly name a private runtime volume")
        root = Path(configured).resolve()
        if _inside_checkout(root):
            raise ValueError("Research data must be outside the repository")
        return cls(
            root,
            os.environ.get("CYTELLECT_APP_ORIGIN", "http://localhost:3000").rstrip("/"),
            os.environ.get("CYTELLECT_SECURE_COOKIES", "true").lower() == "true",
            os.environ.get("CYTELLECT_DEMO", "false").lower() == "true",
            os.environ.get("CYTELLECT_FIJI_EXECUTABLE", ""),
            retention_seconds=int(os.environ.get("CYTELLECT_RETENTION_SECONDS", "86400")),
            workspace_retention_mode=os.environ.get("CYTELLECT_WORKSPACE_RETENTION_MODE", "ttl"),
            job_timeout_seconds=int(os.environ.get("CYTELLECT_JOB_TIMEOUT_SECONDS", "3600")),
            max_upload_bytes=int(os.environ.get("CYTELLECT_MAX_UPLOAD_BYTES", str(2 * 1024**3))),
            max_fields=int(os.environ.get("CYTELLECT_MAX_FIELDS", "100")),
            worker_memory_mb=int(os.environ.get("CYTELLECT_WORKER_MEMORY_MB", "4096")),
            proposal_url=os.environ.get("CYTELLECT_PROPOSAL_URL", ""),
            proposal_token=_proposal_token_from_env(),
            proposal_timeout_seconds=int(os.environ.get("CYTELLECT_PROPOSAL_TIMEOUT_SECONDS", "300")),
            proposal_model=os.environ.get("CYTELLECT_PROPOSAL_MODEL", "gpt-6.1-sol"),
            proposal_prompt_version=os.environ.get("CYTELLECT_PROPOSAL_PROMPT_VERSION", PROPOSAL_PROMPT_VERSION),
            desktop_owner=os.environ.get("CYTELLECT_DESKTOP_OWNER", "false").lower() == "true",
            upload_allowlist=(load_allowlist(os.environ["CYTELLECT_UPLOAD_ALLOWLIST"])
                              if os.environ.get("CYTELLECT_UPLOAD_ALLOWLIST") else None),
        )


def configure_private_tmp(settings: Settings) -> Path:
    """Multipart and library scratch stays in the private runtime volume."""
    root = settings.data_dir.resolve()
    if _inside_checkout(root):
        raise ValueError("Research data must be outside the repository")
    temporary = root / "tmp"
    if temporary.is_symlink() or temporary.resolve().parent != root:
        raise ValueError("Private temporary directory cannot redirect outside runtime")
    temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        temporary.chmod(0o700)
    matplotlib_cache = temporary / "matplotlib"
    if matplotlib_cache.is_symlink() or matplotlib_cache.resolve().parent != temporary:
        raise ValueError("Private font cache cannot redirect outside runtime")
    matplotlib_cache.mkdir(exist_ok=True, mode=0o700)
    if os.name != "nt":
        matplotlib_cache.chmod(0o700)
    os.environ["MPLCONFIGDIR"] = str(matplotlib_cache)
    for variable in ("TMPDIR", "TEMP", "TMP"):
        os.environ[variable] = str(temporary)
    # tempfile caches its selected directory; assigning explicitly also protects
    # imports that queried it before application startup.
    tempfile.tempdir = str(temporary)
    return temporary
