"""Generic OME import using the same bounded, complete-plane TIFF decoder."""
import hashlib
import json
import shutil
from typing import Annotated

import numpy as np
import tifffile
from cytellect_analysis.images import read_tiff, sha256
from cytellect_analysis.region_contracts import RegionFieldInput, RegionImageInfo
from defusedxml import ElementTree
from fastapi import Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select, update

from .db import fields, uid, workspaces


def read_region_ome(path):
    with tifffile.TiffFile(path, _multifile=False) as tif:
        xml = tif.ome_metadata
        if not tif.is_ome or not xml or len(xml) > 4 * 1024 * 1024:
            raise ValueError("valid_ome_metadata_required")
        root = ElementTree.fromstring(xml)
        images = [node for node in root if node.tag.rsplit("}", 1)[-1] == "Image"]
        pixels = [node for image in images for node in image if node.tag.rsplit("}", 1)[-1] == "Pixels"]
        if len(images) != 1 or len(pixels) != 1:
            raise ValueError("single_series_required")
        count = int(pixels[0].attrib["SizeC"])
        if not 1 <= count <= 4:
            raise ValueError("one_to_four_channels_required")
        channels = [node for node in pixels[0] if node.tag.rsplit("}", 1)[-1] == "Channel"]
        if len(channels) != count:
            raise ValueError("ome_channel_count_mismatch")
        names = [node.attrib.get("Name", "").strip() or None for node in channels]
    # The existing decoder verifies Z/T, dimensions, datatype, external UUIDs,
    # IFD coverage and byte ranges before allocating/decoding image planes.
    stack = read_tiff(path, channel_indices=list(range(count)) if count > 1 else None, max_channels=4)
    if count == 1:
        stack = stack[None, ...]
    return stack, names


def register_region_ome_routes(api, store, settings, owner, workspace, touch, view_model, is_region):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/workspaces/{wid}/region-fields/ome", status_code=201, response_model=view_model)
    async def upload_ome(wid: str, who: Owner, ome: UploadFile = File(...), client_upload_id: str | None = Form(None)):
        workspace(wid, who)
        fid = uid()
        folder = store.safe_path("workspaces", wid, "fields", fid)
        folder.mkdir(parents=True)
        keep = False
        total = 0
        try:
            path = folder / "ome.tif"
            with path.open("wb") as stream:
                while chunk := await ome.read(1024 * 1024):
                    total += len(chunk)
                    if total > 256 * 1024**2:
                        raise HTTPException(413, "field_upload_limit")
                    stream.write(chunk)
            inputs = {"ome": {"sha256": sha256(path), "bytes": total}}
            fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()

            def existing(conn):
                if client_upload_id is None:
                    return None
                row = conn.execute(select(fields).where(fields.c.workspace_id == wid,
                    fields.c.client_upload_id == client_upload_id)).mappings().first()
                if row is not None:
                    if row["upload_fingerprint"] != fingerprint:
                        raise HTTPException(409, "region_upload_id_conflict")
                    return dict(row)
                return None

            with store.transaction() as conn:
                touch(conn, wid)
                prior = existing(conn)
                if prior is not None:
                    return prior
            stack, names = read_region_ome(path)
            spec = RegionFieldInput.model_validate({"version": "1.1.0", "client_upload_id": client_upload_id,
                "channels": [{"channel_id": f"c{i + 1}", "label": name or f"c{i + 1}", "stain": name,
                              "identity_source": "ome_metadata" if name else "unresolved"}
                             for i, name in enumerate(names)]})
            arrays = {}
            for index, channel in enumerate(spec.channels):
                output = folder / f"channel-{channel.channel_id}.npy"
                np.save(output, stack[index], allow_pickle=False)
                arrays[channel.channel_id] = {"sha256": sha256(output), "bytes": output.stat().st_size}
            info = RegionImageInfo.model_validate({"shape": list(stack.shape[1:]), "channels": spec.channels,
                "inputs": inputs, "channel_arrays": arrays, "labels_array": None, "calibration": None, "input_mode": "native"})
            with store.transaction() as conn:
                touch(conn, wid)
                prior = existing(conn)
                if prior is not None:
                    return prior
                record = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                count = conn.execute(select(func.count()).select_from(fields).where(fields.c.workspace_id == wid)).scalar_one()
                if count >= settings.max_fields or record["bytes"] + total > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                if any(not is_region(row) for row in conn.execute(select(fields).where(fields.c.workspace_id == wid)).mappings()):
                    raise HTTPException(409, "workflow_kind_mismatch")
                conn.execute(fields.insert().values(id=fid, workspace_id=wid, metadata=spec.metadata.model_dump(mode="json"),
                    image_info=info.model_dump(mode="json"), synthetic=False, client_upload_id=client_upload_id,
                    upload_fingerprint=fingerprint))
                conn.execute(update(workspaces).where(workspaces.c.id == wid).values(bytes=record["bytes"] + total))
                result = dict(conn.execute(select(fields).where(fields.c.id == fid)).mappings().one())
            keep = True
            return result
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "unsupported_or_invalid_region_ome") from None
        finally:
            if not keep:
                shutil.rmtree(folder)
            await ome.close()
