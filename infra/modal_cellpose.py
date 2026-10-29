"""Remote Cellpose inference on a Modal GPU, from the published fixed image.

Deploy (owner, with MODAL_TOKEN_ID/MODAL_TOKEN_SECRET):

    modal deploy infra/modal_cellpose.py

The container runs the unchanged engines/cellpose/server.py from the image digest
below, so runner, model and package hashes match this release. It is a Modal
Server: requests are proxied to the container and their payloads are not stored.
Modal proxy-auth tokens are required; the scientific server keeps nothing on disk
and logs only request durations.
"""
from __future__ import annotations

import os
import subprocess

import modal

# Published by .github/workflows/cellpose-gpu-image.yml from main 1d96814.
IMAGE = "ghcr.io/genellect/cytellect-cellpose-gpu@sha256:cf061eb495f418732d31868180d6880b4101b5b9c1d445997d38606fdccfa934"
PORT = 8080
# Idle seconds before scaling to zero: short enough that a finished batch stops
# billing quickly, long enough to keep the model loaded between fields of a batch.
SCALEDOWN_SECONDS = 20
# Let accepted inference finish when Modal drains a container. Match the remote
# client's request deadline; this is a shutdown grace, not an always-warm period.
EXIT_GRACE_SECONDS = 1800

image = modal.Image.from_registry(IMAGE, setup_dockerfile_commands=["USER root"])
app = modal.App("cytellect-cellpose")


@app.server(
    image=image,
    # Prefer L4; allow A10 when scheduling capacity is unavailable. One GPU per
    # container, with the actual device retained in each inference receipt.
    gpu=["L4", "A10"],
    cpu=2,
    memory=8192,
    max_containers=1,
    target_concurrency=1,
    max_concurrency=1,
    scaledown_window=SCALEDOWN_SECONDS,
    exit_grace_period=EXIT_GRACE_SECONDS,
    startup_timeout=600,
    port=PORT,
    unauthenticated=False,
)
class CellposeServer:
    @modal.enter()
    def start(self):
        environment = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "CYTELLECT_CELLPOSE_RUNTIME_LOCK": "gpu.lock.json",
            "CYTELLECT_CELLPOSE_MODEL": "/opt/cellpose-models/cpsam_v2",
            "CYTELLECT_CELLPOSE_HOST": "0.0.0.0",
            "CYTELLECT_CELLPOSE_PORT": str(PORT),
            "CYTELLECT_REQUIRE_GPU": "1",
        }
        # The image's unprivileged user runs the scientific server, as in Docker.
        self.process = subprocess.Popen(
            ["/opt/cellpose-runtime/bin/python", "-I", "/app/engines/cellpose/server.py"],
            env=environment, user=10001, group=10001, cwd="/app")

    @modal.exit()
    def stop(self):
        self.process.terminate()
