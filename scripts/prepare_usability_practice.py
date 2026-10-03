"""Generate artificial operator-task material outside the checkout; never user data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import tifffile

REPO = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
BASE = ((1, 1, (-2, 2, 10)), (1, 1, (4,)), (1, 2, (8, 12)),
        (2, 1, (5,)), (2, 1, (1, 5, 9)), (3, 1, (6, 8)))
OFFSETS = {1: 3, 2: -1, 3: 2}
VARIANTS = ("independent", "paired", "missing")
HEADER = ("視野", "条件", "試料", "独立実験単位", "撮影日／バッチ", "対応ペア")


def records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in ("A", "B"):
        for unit, sample, values in BASE:
            rows.append({"field_id": f"f{len(rows) + 1:02d}", "condition": condition,
                         "unit_index": unit, "sample": f"{condition}{unit}-s{sample}",
                         "values": [v + (OFFSETS[unit] if condition == "B" else 0) for v in values]})
    return rows


def metadata(row, variant):
    if variant not in VARIANTS:
        raise ValueError("unknown_practice_variant")
    unit = (f"M-{row['unit_index']}" if variant == "paired"
            else f"U-{row['condition']}{row['unit_index']}")
    return {"condition": row["condition"], "sample": row["sample"],
            "experimental_unit": None if variant == "missing" and row["field_id"] == "f02" else unit,
            "acquisition_date": "generated-batch-1",
            "pair": f"P-{row['unit_index']}" if variant == "paired" else None, "repeat_length": None}


def reference():
    """Hand-derived constants: deliberately independent of the analysis implementation."""
    return {"scope": "Artificial task material, not biological or human acceptance",
            "human_evaluation_performed": False, "fields": 12, "regions": 24, "samples": 8,
            "independent_units_by_variant": {"independent": 6, "paired": 3, "missing": None},
            "units_per_condition_when_complete": 3, "paired_complete_pairs": 3,
            "background_value": 10, "area_px_per_region": 144, "calibration": None,
            "field_medians": [2, 4, 10, 5, 5, 7, 5, 7, 13, 4, 4, 9],
            "sample_means": {"A1-s1": 3, "A1-s2": 10, "A2-s1": 5, "A3-s1": 7,
                             "B1-s1": 6, "B1-s2": 13, "B2-s1": 4, "B3-s1": 9},
            "unit_values": {"A": [6.5, 5, 7], "B": [9.5, 4, 9]},
            "group_means": {"A": "37/6", "B": "15/2"}, "effect_a_minus_b": "-4/3",
            "welch_se_squared": "31/9", "welch_df": "15376/6245",
            "paired_differences": [-3, 1, -2], "paired_se_squared": "13/9", "paired_df": 2,
            "wrong_region_pool": {"A": "17/3", "B": "43/6", "effect": "-3/2"},
            "wrong_equal_field_mean": {"A": "11/2", "B": "7", "effect": "-3/2"},
            "wrong_equal_sample_mean": {"A": "25/4", "B": "8", "effect": "-7/4"},
            "missing_record": {"field_id": "f02", "unknown": "experimental_unit",
                               "expected_error": "region_comparison_metadata_required"}}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def card(variant, rows):
    relationship = ("M-1〜M-3はそれぞれ同じ人工単位で、AとBの両条件に登場します。P-1〜P-3はその対応です。"
                    if variant == "paired" else "U-A1〜U-A3とU-B1〜U-B3は別々の人工単位です。AとBの対応関係はありません。")
    if variant == "missing":
        relationship += " f02の独立実験単位は未記録です。試料名や画像の見た目から補わないでください。"
    return ("# 人工画像の記録カード\n\n実在する細胞・染色・研究結果を表さない操作練習です。\n\n"
            "依頼：練習信号の人工領域内の平均（背景補正）について、差A−Bを図と表で示してください。"
            "何を1単位と数えたか説明してください。必要な情報が不足していれば、推測せず不足を示してください。\n\n"
            "表示名は「練習信号」、実際の染色・画素サイズ・取得時の飽和値は設定していないため空欄です。"
            "画像は同じ規則で生成した16-bitグレースケールTIFF、マスクは同寸法の整数ラベルです。"
            "generated-batch-1は人工的な生成条件で、実際の撮影日や装置を表しません。\n\n"
            "左上 x=0〜12, y=0〜12 は全画像で画素値10の背景です。マスクとは重なりません。"
            "この既知の人工背景を、実画像の核外を背景とみなす根拠にはしないでください。\n\n"
            + relationship + "\n\n| " + " | ".join(HEADER) + " |\n|---|---|---|---|---|---|\n"
            + "\n".join("| " + " | ".join(row) + " |" for row in rows) + "\n")


def prepare(output: Path):
    """Allow only explicit, empty destinations outside this source checkout."""
    if output.is_symlink():
        raise ValueError("practice_output_must_not_be_symlink")
    output = output.expanduser().resolve()
    if output.is_relative_to(REPO) or output == Path(output.anchor):
        raise ValueError("practice_output_must_be_outside_checkout")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("practice_output_must_be_empty")
    output.mkdir(parents=True, exist_ok=True)
    for folder in ("participant/images", "participant/masks", "participant/cards", "observer"):
        (output / folder).mkdir(parents=True)
    data = records()
    for row in data:
        image, labels = np.full((80, 80), 10, dtype=np.uint16), np.zeros((80, 80), dtype=np.uint32)
        for number, (value, (y, x)) in enumerate(zip(row["values"], ((24, 16), (24, 48), (52, 32))), 1):
            image[y:y + 12, x:x + 12] = 10 + value
            labels[y:y + 12, x:x + 12] = number
        for folder, suffix, array in (("images", "signal", image), ("masks", "labels", labels)):
            tifffile.imwrite(output / "participant" / folder / f"{row['field_id']}-{suffix}.tif",
                             array, photometric="minisblack", metadata=None)
    for variant in VARIANTS:
        rows = []
        for row in data:
            md = metadata(row, variant)
            rows.append([row["field_id"], md["condition"], md["sample"], md["experimental_unit"] or "",
                         md["acquisition_date"], md["pair"] or ""])
        with (output / "participant/cards" / f"{variant}-records.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)
        (output / "participant/cards" / f"{variant}.ja.md").write_text(card(variant, rows), encoding="utf-8")
    write_json(output / "observer/reference.json", reference())
    write_json(output / "observer/generated-values.json", data)
    (output / "README.ja.md").write_text(
        "# 人工操作課題 v1\n\n人による評価は未実施です。独立群・対応あり・情報不足のカードを1種類ずつ使います。"
        "participant の画像と割り当てたカードだけを参加者へ渡し、observer の正解値は見せません。\n\n"
        "現行の領域・輝度解析で、1チャンネルの画像末尾を -signal、整数マスク末尾を -labels として一括登録できます。"
        "metadata CSVの自動取込はありません。記録カードに従って入力します。\n\n"
        "詳しい観察者準備・期待値・制限はソースの docs/usability-practice.ja.md を参照してください。"
        "生成成功はブラウザ・インストーラー・生物学・人の操作評価の成功ではありません。\n", encoding="utf-8")
    manifest = {"schema": "cytellect-artificial-practice/1", "version": VERSION,
                "source": "Deterministic artificial values; no biological observations",
                "human_evaluation_performed": False, "numpy": np.__version__, "tifffile": tifffile.__version__,
                "files": [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in sorted(output.rglob("*")) if path.is_file()]}
    write_json(output / "manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Empty directory outside the source checkout")
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({"schema": manifest["schema"], "files": len(manifest["files"]),
                      "human_evaluation_performed": False}))


if __name__ == "__main__":
    main()
