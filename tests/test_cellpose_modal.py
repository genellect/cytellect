"""The Modal deployment keeps the remote-inference privacy and cost contract.

Read statically: CI does not install Modal. A Modal Server proxies requests to the
container without storing payloads, unlike Web Functions (inputs kept up to 7 days).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "infra" / "modal_cellpose.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def server_options():
    for node in ast.walk(TREE):
        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and getattr(decorator.func, "attr", "") == "server":
                    return {keyword.arg: keyword.value for keyword in decorator.keywords}
    raise AssertionError("no @app.server class")


def test_modal_app_is_an_authenticated_single_gpu_server_without_storage():
    options = server_options()
    assert ast.literal_eval(options["gpu"]) == "L4"
    assert ast.literal_eval(options["max_containers"]) == 1
    assert ast.literal_eval(options["unauthenticated"]) is False
    assert "volumes" not in options and "enable_memory_snapshot" not in options
    # Web Function decorators would retain request inputs; none may be used.
    for name in ("fastapi_endpoint", "web_endpoint", "asgi_app", "wsgi_app", "web_server", "method"):
        assert f"modal.{name}" not in SOURCE


def test_modal_app_runs_the_published_image_and_unchanged_server():
    image = re.search(r'IMAGE = "([^"]+)"', SOURCE).group(1)
    assert re.fullmatch(r"ghcr\.io/genellect/cytellect-cellpose-gpu@sha256:[0-9a-f]{64}", image)
    assert '"/app/engines/cellpose/server.py"' in SOURCE and '"gpu.lock.json"' in SOURCE
    assert 'user=10001' in SOURCE


def test_modal_deploy_runs_only_from_main_with_hashed_client():
    workflow = (ROOT / ".github" / "workflows" / "cellpose-modal-deploy.yml").read_text(encoding="utf-8")
    assert "if: github.ref == 'refs/heads/main'" in workflow and "--require-hashes" in workflow
    requirements = (ROOT / "infra" / "modal-requirements.txt").read_text(encoding="utf-8")
    assert "modal==1.6.2" in requirements and "--hash=sha256:" in requirements
