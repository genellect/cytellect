"""Non-root, read-only, offline container smoke; uses only generated known pixels."""
import json
import os
import socket
import tempfile
from pathlib import Path

import numpy as np
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.engine import detect
from cytellect_analysis.synthetic import synthetic_field

assert os.geteuid() == 10001, "worker_must_be_nonroot"
assert os.statvfs("/").f_flag & os.ST_RDONLY, "root_filesystem_must_be_readonly"
assert {name for _, name in socket.if_nameindex()} == {"lo"}, "worker_network_interface_present"
with socket.socket() as connection:
    connection.settimeout(2)
    try:
        connection.connect(("198.51.100.1", 443))
    except OSError:
        pass
    else:
        raise AssertionError("worker_outbound_connection_succeeded")
assert Path(tempfile.gettempdir()).resolve() == Path("/data/tmp"), "temporary_data_not_private"
channels, _, _ = synthetic_field()
originals = {role: values.copy() for role, values in channels.items()}
nuclei, nucleoli, provenance = detect(channels, Recipe(), Path("/data/smoke"), os.environ["CYTELLECT_FIJI_EXECUTABLE"])
assert len(np.unique(nuclei))-1 == 9 and len(np.unique(nucleoli))-1 == 18
assert all(np.array_equal(channels[role], pixels) for role, pixels in originals.items())
assert provenance["headless"]
print(json.dumps({"nonroot": True, "read_only_root": True, "network": "loopback_only_outbound_denied", "private_temp": True, "actual_fiji_nuclei": 9, "nucleolar_candidates": 18, "model_sha256": provenance["model_sha256"]}))
