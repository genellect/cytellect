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
    # Ordered, explicit candidates: no larger GPU counts or unbounded "any" pool.
    assert ast.literal_eval(options["gpu"]) == ["L4", "A10"]
    assert ast.literal_eval(options["max_containers"]) == 1
    assert ast.literal_eval(options["unauthenticated"]) is False
    assert "volumes" not in options and "enable_memory_snapshot" not in options
    assert "buffer_containers" not in options
    # Web Function decorators would retain request inputs; none may be used.
    for name in ("fastapi_endpoint", "web_endpoint", "asgi_app", "wsgi_app", "web_server", "method"):
        assert f"modal.{name}" not in SOURCE


def test_modal_app_runs_the_published_image_and_unchanged_server():
    image = re.search(r'IMAGE = "([^"]+)"', SOURCE).group(1)
    assert re.fullmatch(r"ghcr\.io/genellect/cytellect-cellpose-gpu@sha256:[0-9a-f]{64}", image)
    assert '"/app/engines/cellpose/server.py"' in SOURCE and '"gpu.lock.json"' in SOURCE
    assert 'user=10001' in SOURCE


def test_inflight_inference_is_tracked_and_can_finish_before_shutdown():
    options = server_options()
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in TREE.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
    }
    # A request occupies the only slot; max_concurrency alone does not enable
    # demand tracking. Keep scale-to-zero independent of the shutdown grace.
    assert ast.literal_eval(options["target_concurrency"]) == 1
    assert ast.literal_eval(options["max_concurrency"]) == 1
    assert constants[options["scaledown_window"].id] == 20
    assert "min_containers" not in options
    client = ast.parse((ROOT / "packages/analysis/src/cytellect_analysis/cellpose_engine.py").read_text(encoding="utf-8"))
    deadline = next(
        ast.literal_eval(node.value) for node in client.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "REMOTE_REQUEST_TIMEOUT_SECONDS" for target in node.targets)
    )
    grace = constants[options["exit_grace_period"].id]
    assert deadline <= grace <= 3600  # Modal Server's supported upper bound.


def test_modal_deploy_runs_only_from_main_with_hashed_client():
    workflow = (ROOT / ".github" / "workflows" / "cellpose-modal-deploy.yml").read_text(encoding="utf-8")
    assert "if: github.ref == 'refs/heads/main'" in workflow and "--require-hashes" in workflow
    requirements = (ROOT / "infra" / "modal-requirements.txt").read_text(encoding="utf-8")
    assert "modal==1.6.2" in requirements and "--hash=sha256:" in requirements
