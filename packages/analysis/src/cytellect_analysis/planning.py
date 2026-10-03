"""Deterministic, non-executable analysis guidance; actual adoption is separate."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .region_policy import RegionMeasurementPolicy

VERSION: Literal["2.0.0"] = "2.0.0"
SAFE_ERROR_CODES = frozenset({"planning_legacy_requires_review", "planning_snapshot_mismatch"})
ReferenceId = Literal["senft-2023", "kodiha-2011", "waters-2009", "lazic-2018", "lord-2020", "schmied-2024"]
CandidateId = Literal["regions-manual", "regions-imported", "regions-nuclei", "legacy-gfp-nuclear", "legacy-ncl"]
MetricId = Literal[
    "area_px", "area_um2", "mean", "mean_corrected", "integrated", "integrated_corrected",
    "gfp_mean", "gfp_mean_corrected", "gfp_integrated", "gfp_integrated_corrected",
    "ncl_nucleus_mean", "ncl_nucleus_mean_corrected", "ncl_nucleus_integrated", "ncl_nucleus_integrated_corrected",
    "ncl_nucleoli_mean", "ncl_nucleoli_mean_corrected", "ncl_nucleoli_integrated", "ncl_nucleoli_integrated_corrected",
    "ncl_nucleoplasm_mean", "ncl_nucleoplasm_mean_corrected", "ncl_nucleoplasm_integrated", "ncl_nucleoplasm_integrated_corrected",
    "nucleus_area_px", "nucleus_area_um2", "nucleolar_area_px", "nucleolar_area_um2",
    "nucleoplasm_area_px", "nucleoplasm_area_um2", "ncl_nucleoplasm_over_nucleoli", "ncl_log2_nucleoplasm_over_nucleoli",
]


class PlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


class PlanAnswers(PlanModel):
    measurement: Literal["unknown", "area", "mean", "integrated", "ncl-ratio"] = "unknown"
    region: Literal["unknown", "nucleus", "nucleolus", "nucleoplasm", "custom"] = "unknown"
    definition: Literal["unknown", "manual", "imported", "nuclear-stain", "ncl-enrichment"] = "unknown"
    signal: Literal["unknown", "ncl", "gfp", "other"] = "unknown"
    input: Literal["unknown", "grayscale-2d", "rgb", "zt"] = "unknown"
    nuclear_stain: Literal["unknown", "yes", "no"] = "unknown"
    background: Literal["unknown", "yes", "no"] = "unknown"
    acquisition: Literal["unknown", "matched", "different"] = "unknown"
    comparison: Literal["unknown", "descriptive", "independent", "paired"] = "unknown"
    allocation: Literal["unknown", "biological", "fields"] = "unknown"
    gating: Literal["none", "negative-control", "exploratory"] = "none"


class PlanInput(PlanModel):
    format: Literal["cytellect-analysis-plan"] = "cytellect-analysis-plan"
    version: Literal["2.0.0", "2.1.0"]
    answers: PlanAnswers

    @model_validator(mode="before")
    @classmethod
    def no_legacy_execution(cls, value):
        if isinstance(value, dict) and str(value.get("version", "")).startswith("1.0."):
            raise ValueError("planning_legacy_requires_review")
        return value


class PlanReference(PlanModel):
    id: ReferenceId
    label: str
    url: str


REFERENCES = (
    PlanReference(id="senft-2023", label="定量画像解析の実験計画 · Senft et al. (2023)", url="https://doi.org/10.1371/journal.pbio.3002167"),
    PlanReference(id="kodiha-2011", label="核小体の領域定義 · Kodiha et al. (2011)", url="https://doi.org/10.1186/1471-2121-12-25"),
    PlanReference(id="waters-2009", label="蛍光定量と撮影条件 · Waters (2009)", url="https://doi.org/10.1083/jcb.200903097"),
    PlanReference(id="lazic-2018", label="実験単位と擬似反復 · Lazic et al. (2018)", url="https://doi.org/10.1371/journal.pbio.2005282"),
    PlanReference(id="lord-2020", label="反復を区別する図 · Lord et al. (2020)", url="https://doi.org/10.1083/jcb.202001064"),
    PlanReference(id="schmied-2024", label="画像と解析の報告 · Schmied et al. (2024)", url="https://doi.org/10.1038/s41592-023-01987-9"),
)


class PlanFinding(PlanModel):
    id: str
    title: str
    detail: str
    reference: ReferenceId


class PlanCandidate(PlanModel):
    id: CandidateId
    label: str
    workflow: Literal["regions", "nuclear"]
    recipe_id: Literal["region-2d", "ncl-native-2d", "gfp-nuclear-2d"]
    recipe_version: Literal["1.0.0", "1.1.0"]
    source: Literal["manual", "imported", "stardist_nuclear"] | None
    selection_source: Literal["region", "legacy-cell"]
    allowed_metrics: list[MetricId]
    required_channel_roles: list[Literal["image", "measurement", "nuclear-stain", "ncl", "gfp"]]
    # These are tasks for adoption, never confirmation flags or ready-to-run recipes.
    actual_review_required: list[Literal[
        "native-input", "channel-mapping", "nuclear-stain", "background-rois", "region-definition",
        "metric-selection", "mask-quality", "gfp-gate", "calibration-for-physical-area",
    ]]
    measurement: RegionMeasurementPolicy | None = None

    @model_serializer(mode="wrap")
    def preserve_historical_shape(self, handler):
        value = handler(self)
        if self.measurement is None:
            value.pop("measurement", None)
        return value


class PlanDecision(PlanModel):
    version: Literal["2.0.0", "2.1.0"] = VERSION
    status: Literal["planning-only-not-adopted"] = "planning-only-not-adopted"
    candidates: list[PlanCandidate]
    comparison_intent: Literal["undetermined", "descriptive", "independent-candidate", "paired-candidate"]
    descriptive_allowed: Literal[True] = True
    questions: list[PlanFinding]
    decisions: list[PlanFinding]
    limits: list[PlanFinding]
    references: list[PlanReference]

    @model_validator(mode="after")
    def versioned_measurement_suggestions(self):
        for candidate in self.candidates:
            if self.version == "2.0.0" and "measurement" in candidate.model_fields_set:
                raise ValueError("planning_snapshot_mismatch")
            if candidate.measurement is not None and (
                candidate.workflow != "regions" or not candidate.allowed_metrics
                or not set(candidate.allowed_metrics).issubset({"area_px", "area_um2"})
            ):
                raise ValueError("planning_snapshot_mismatch")
        return self


class PlanSnapshot(PlanModel):
    input: PlanInput
    decision: PlanDecision
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _candidate(a: PlanAnswers, identifier: CandidateId, metrics: list[MetricId]) -> PlanCandidate:
    generic = identifier.startswith("regions-")
    automatic = identifier in {"regions-nuclei", "legacy-ncl", "legacy-gfp-nuclear"}
    source: Literal["manual", "imported", "stardist_nuclear"] | None = (
        "manual" if identifier == "regions-manual" else "imported" if identifier == "regions-imported"
        else "stardist_nuclear" if identifier == "regions-nuclei" else None)
    roles: list[Literal["image", "measurement", "nuclear-stain", "ncl", "gfp"]] = []
    if automatic:
        roles.append("nuclear-stain")
    if generic:
        roles.append("image" if a.measurement == "area" else "measurement")
    else:
        roles.append("ncl" if identifier == "legacy-ncl" else "gfp")
        if identifier == "legacy-ncl" and a.gating != "none":
            roles.append("gfp")
    tasks = ["native-input", "channel-mapping", "background-rois", "region-definition", "metric-selection", "mask-quality"]
    if automatic:
        tasks.append("nuclear-stain")
    if a.measurement == "area":
        tasks.append("calibration-for-physical-area")
    if a.gating != "none":
        tasks.append("gfp-gate")
    return PlanCandidate.model_validate({
        "id": identifier,
        "label": {"regions-manual": "手動領域の面積・輝度", "regions-imported": "保存した領域の面積・輝度",
                  "regions-nuclei": "核染色からの核検出・測定", "legacy-ncl": "核・核小体のNCL解析",
                  "legacy-gfp-nuclear": "核内GFP解析"}[identifier],
        "workflow": "regions" if generic else "nuclear",
        "recipe_id": "region-2d" if generic else "ncl-native-2d" if identifier == "legacy-ncl" else "gfp-nuclear-2d",
        "recipe_version": "1.1.0" if identifier == "regions-nuclei" else "1.0.0",
        "source": source, "selection_source": "region" if generic else "legacy-cell",
        "allowed_metrics": metrics, "required_channel_roles": roles, "actual_review_required": tasks,
    })


def evaluate_plan(value: PlanInput | dict) -> PlanDecision:
    """Recompute candidate guidance solely from known answers; never execute it."""
    plan = PlanInput.model_validate(value)
    a = plan.answers
    candidates: list[PlanCandidate] = []
    questions: list[PlanFinding] = []
    decisions: list[PlanFinding] = []
    limits: list[PlanFinding] = []

    def add(items, identifier, title, detail, reference: ReferenceId = "senft-2023"):
        items.append(PlanFinding(id=identifier, title=title, detail=detail, reference=reference))

    if "unknown" in (a.measurement, a.region, a.definition) or (a.measurement != "area" and a.signal == "unknown"):
        add(questions, "measurement", "測る量と領域の定義を決める", "面積、領域内の平均輝度、領域全体の積算値は別の指標です。面積だけを測る場合、測定マーカーの指定は不要です。")
    if a.input != "grayscale-2d":
        add(questions, "input", "測定用の2D原画像を確認する", "8/16-bitグレースケール2D原画像が必要です。表示用RGBの輝度復元や、Z・時系列の投影・断面選択を自動では行いません。", "waters-2009")
    if a.background != "yes":
        add(questions, "background", "原画像で背景領域を確認する", "現在の測定経路はチャンネルごとの背景ROIが必要です。核外全体を背景にせず、対象の信号がない領域を実画像で確認します。", "waters-2009")
    if a.acquisition != "matched" and a.measurement in {"mean", "integrated", "ncl-ratio"}:
        add(questions, "acquisition", "撮影・染色条件を確認する", "露光、染色、検出器、背景、飽和を確認します。バッチ補正で失われた信号は復元できません。未確認でも記述は可能ですが、群の差を生物量の差と確定しません。", "waters-2009")

    automatic = a.definition in {"nuclear-stain", "ncl-enrichment"}
    if automatic and a.nuclear_stain != "yes":
        add(questions, "nuclear-stain", "核を識別するチャンネルを確認する", "この自動検出は核染色が必要です。実画像のチャンネル対応と染色名を採用時に確認し、ファイル名や色から推測しません。")
    ready = (a.input == "grayscale-2d" and "unknown" not in (a.measurement, a.region, a.definition)
             and (a.measurement == "area" or a.signal != "unknown")
             and (not automatic or a.nuclear_stain == "yes"))
    generic_metrics: dict[str, list[MetricId]] = {
        "area": ["area_px", "area_um2"], "mean": ["mean", "mean_corrected"],
        "integrated": ["integrated", "integrated_corrected"],
    }
    if a.definition == "nuclear-stain" and a.region != "nucleus":
        add(limits, "nuclear-model-scope", "核モデルで他の構造は定義しない", "核小体や細胞全体の境界を、核用StarDistから得たものとして扱いません。手動または確認済みラベル領域を選びます。")
        ready = False
    if a.measurement == "ncl-ratio" and (a.definition != "ncl-enrichment" or a.signal != "ncl" or a.region not in {"nucleolus", "nucleoplasm"}):
        add(limits, "ratio-definition", "NCL区画比の領域定義を確認する", "現行の区画比は、核内NCL濃縮領域と、それを核から除いた核質のNCL平均輝度の比です。任意領域や別マーカーへ代用しません。", "kodiha-2011")
        ready = False
    if a.definition == "ncl-enrichment" and (a.region not in {"nucleus", "nucleolus", "nucleoplasm"} or (a.measurement != "area" and a.signal != "ncl")):
        add(limits, "ncl-definition-scope", "NCLレシピの測定対象を確認する", "NCL濃縮領域を使う既存レシピの指標と、任意マーカーの領域測定は区別します。別のマーカーをNCLとして登録しません。")
        ready = False
    if a.definition == "ncl-enrichment":
        add(limits, "circularity", "検出に使うNCLの変化も領域に影響する", "NCLの再分布で候補領域も変わり得ます。代表視野で領域を確認し、比だけで核小体ストレスを確定しません。", "kodiha-2011")
    legacy_gfp = a.definition == "nuclear-stain" and a.region == "nucleus" and a.signal == "gfp"
    legacy_ncl = a.definition == "ncl-enrichment"
    if a.gating != "none":
        if not (legacy_gfp or legacy_ncl):
            add(limits, "gating-unsupported", "この領域経路ではGFP選別を実行しない", "GFP選別は既存の核内GFP/NCLレシピに限ります。選別を行わない計画に変更するか、対応する領域定義と実際のGFP画像を用意します。")
            ready = False
        add(limits, "selection", "GFP選別を結果から調整しない", "陰性対照または探索的閾値の採用理由を実画像で記録します。処置で変わるGFP量の選別は、比較する対象と推定する効果を変えることがあります。")
    if ready:
        if a.definition in {"manual", "imported"} and a.measurement in generic_metrics:
            candidates.append(_candidate(a, "regions-manual" if a.definition == "manual" else "regions-imported", generic_metrics[a.measurement]))
        elif a.definition == "nuclear-stain" and a.measurement in generic_metrics:
            if a.gating == "none":
                candidates.append(_candidate(a, "regions-nuclei", generic_metrics[a.measurement]))
            if legacy_gfp:
                metrics: list[MetricId] = (["nucleus_area_px", "nucleus_area_um2"] if a.measurement == "area" else
                                           ["gfp_mean", "gfp_mean_corrected"] if a.measurement == "mean" else
                                           ["gfp_integrated", "gfp_integrated_corrected"])
                candidates.append(_candidate(a, "legacy-gfp-nuclear", metrics))
        elif legacy_ncl:
            prefix = {"nucleus": "nucleus", "nucleolus": "nucleoli", "nucleoplasm": "nucleoplasm"}[a.region]
            if a.measurement == "ncl-ratio":
                metrics = ["ncl_nucleoplasm_over_nucleoli", "ncl_log2_nucleoplasm_over_nucleoli"]
            elif a.measurement == "area":
                area_prefix = "nucleolar" if a.region == "nucleolus" else prefix
                metrics = [f"{area_prefix}_area_px", f"{area_prefix}_area_um2"]  # type: ignore[list-item]
            else:
                metrics = [f"ncl_{prefix}_{a.measurement}", f"ncl_{prefix}_{a.measurement}_corrected"]  # type: ignore[list-item]
            candidates.append(_candidate(a, "legacy-ncl", metrics))

    comparison: Literal["undetermined", "descriptive", "independent-candidate", "paired-candidate"] = "undetermined"
    if a.comparison == "descriptive":
        comparison = "descriptive"
        add(decisions, "descriptive", "まず測定値と分布を確認する", "独立反復が未確認でも、領域と視野の測定値を記述できます。独立n、p値、推論の信頼区間は生成しません。", "lord-2020")
    elif a.comparison == "unknown" or a.allocation != "biological":
        add(questions, "independence", "処置を独立に割り付けた単位を確認する", "細胞数や視野数を独立反復数に置き換えません。未確認なら記述図で進め、推論は実験単位と対応関係を確定してから行います。", "lazic-2018")
    else:
        comparison = "paired-candidate" if a.comparison == "paired" else "independent-candidate"
        add(decisions, "units", "実験単位と必要な対応を実記録から設定する", "視野中央値→試料内平均→実験単位内平均で集約します。対応ありは明示したペア差、独立群はWelch検定の候補です。計画の回答だけで独立性を確認済みにはしません。", "lazic-2018")
        add(limits, "sample-size", "計算の下限と十分な反復数は異なる", "各群2単位または2ペアは計算上の下限で、検出力や実験の妥当性を保証しません。比較集合と採否を結果を見る前に定めます。", "lord-2020")
    if a.measurement == "area":
        add(decisions, "area-calibration", "画素サイズが不明なら画素面積で扱う", "実画像の校正を確認するまでµm²を作りません。複数チャンネルの同じ領域を二重に数えません。")
    if a.measurement == "integrated":
        add(limits, "integrated-not-concentration", "積算値は領域内の画素値の合計", "面積や画素サイズにも依存し、平均輝度や濃度と同じ意味ではありません。比較時は空間的なサンプリングも確認します。", "waters-2009")
    add(decisions, "actual-adoption", "原画像で確認してから条件を採用する", "候補は実行設定ではありません。実チャンネル、背景、領域、指標を確認し、代表視野で試してから条件を固定します。")
    add(decisions, "traceability", "採用した条件と図の元の値を残す", "採用元の計画と、実画像で変更した条件を保存します。図の出典、Methods、解析版を追跡できる形で出力します。", "schmied-2024")
    if plan.version == "2.1.0":
        candidates = [candidate.model_copy(update={
            "measurement": RegionMeasurementPolicy(version="1.0.0", mode="area_only"),
            "actual_review_required": [task for task in candidate.actual_review_required if task != "background-rois"],
        }) if candidate.workflow == "regions" and a.measurement == "area" else candidate for candidate in candidates]
        if candidates and all(candidate.measurement is not None for candidate in candidates):
            questions = [question for question in questions if question.id != "background"]
            decisions = [decision if decision.id != "actual-adoption" else PlanFinding(
                id="actual-adoption-area", title="原画像で確認してから条件を採用する",
                detail="候補は実行設定ではありません。実チャンネル、領域、面積の単位を確認し、代表視野で試してから条件を固定します。輝度と背景補正はこの測定では行いません。",
                reference="senft-2023",
            ) for decision in decisions]
        elif any(candidate.measurement is not None for candidate in candidates):
            questions = [question if question.id != "background" else PlanFinding(
                id="background-candidate", title="輝度解析を含む候補では背景領域を確認する",
                detail="面積のみの領域測定には背景ROIは不要です。核内GFPなどの輝度解析を含む候補では、各チャンネルの信号がない領域を原画像で確認します。",
                reference="waters-2009",
            ) for question in questions]
    return PlanDecision(version=plan.version, candidates=candidates, comparison_intent=comparison, questions=questions,
                        decisions=decisions, limits=limits, references=list(REFERENCES))


def snapshot_plan(value: PlanInput | dict) -> PlanSnapshot:
    """Canonical receipt; repeated identical inputs produce the same fingerprint."""
    plan = PlanInput.model_validate(value)
    decision = evaluate_plan(plan)
    payload = {"input": plan.model_dump(mode="json"), "decision": decision.model_dump(mode="json")}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                      allow_nan=False).encode("utf-8")).hexdigest()
    return PlanSnapshot(input=plan, decision=decision, sha256=digest)


def validate_plan_snapshot(value: PlanSnapshot | dict) -> PlanSnapshot:
    saved = PlanSnapshot.model_validate(value)
    calculated = snapshot_plan(saved.input)
    if saved != calculated:
        raise ValueError("planning_snapshot_mismatch")
    return calculated
