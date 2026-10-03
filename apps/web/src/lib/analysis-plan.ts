/** Planning guidance, not a numerical analysis or an automatic recipe adoption. */
export const PLAN_VERSION = "1.0.1";

export type PlanAnswers = {
  region: "unknown" | "nucleus" | "nucleolus" | "custom";
  signal: "unknown" | "ncl" | "gfp" | "other";
  input: "unknown" | "grayscale-2d" | "rgb" | "zt";
  nuclearStain: "unknown" | "yes" | "no";
  background: "unknown" | "yes" | "no";
  acquisition: "unknown" | "matched" | "different";
  comparison: "unknown" | "descriptive" | "independent" | "paired";
  allocation: "unknown" | "biological" | "fields";
  gating: "none" | "negative-control" | "exploratory";
};

export const emptyPlan: PlanAnswers = {
  region: "unknown", signal: "unknown", input: "unknown", nuclearStain: "unknown",
  background: "unknown", acquisition: "unknown", comparison: "unknown",
  allocation: "unknown", gating: "none",
};

export const planReferences = [
  { id: "senft-2023", label: "定量画像解析の実験計画 · Senft et al., PLOS Biology (2023)", url: "https://doi.org/10.1371/journal.pbio.3002167" },
  { id: "kodiha-2011", label: "核小体の領域定義と蛍光定量 · Kodiha et al., BMC Cell Biology (2011)", url: "https://doi.org/10.1186/1471-2121-12-25" },
  { id: "waters-2009", label: "蛍光定量と撮影条件 · Waters, JCB (2009)", url: "https://doi.org/10.1083/jcb.200903097" },
  { id: "lazic-2018", label: "実験単位と擬似反復 · Lazic et al., PLOS Biology (2018)", url: "https://doi.org/10.1371/journal.pbio.2005282" },
  { id: "lord-2020", label: "反復を区別する図 · Lord et al., JCB (2020)", url: "https://doi.org/10.1083/jcb.202001064" },
  { id: "schmied-2024", label: "画像と解析の報告 · Schmied et al., Nature Methods (2024)", url: "https://doi.org/10.1038/s41592-023-01987-9" },
] as const;

type Finding = { id: string; title: string; detail: string; source: typeof planReferences[number]["id"] };
export type PlanResult = {
  version: string;
  recipe: "ncl-native-2d" | "gfp-nuclear-2d" | null;
  recipeLabel: string | null;
  statistics: "descriptive" | "experimental-unit-candidate" | "paired-candidate" | "undetermined";
  questions: Finding[];
  decisions: Finding[];
  limits: Finding[];
};

export function buildPlan(a: PlanAnswers): PlanResult {
  const result: PlanResult = { version: PLAN_VERSION, recipe: null, recipeLabel: null, statistics: "undetermined", questions: [], decisions: [], limits: [] };
  const add = (list: Finding[], id: string, title: string, detail: string, source: Finding["source"] = "senft-2023") => list.push({ id, title, detail, source });
  if (a.region === "unknown" || a.signal === "unknown") {
    add(result.questions, "measurement", "測る領域とチャンネルを決める", "どの構造の、どの蛍光を測るかを先に決めます。明るさを比べる平均値と、領域全体の信号を表す積算値は異なる指標です。");
  }
  if (a.input !== "grayscale-2d") {
    add(result.questions, "input", "測定用の原画像を確認する", a.input === "zt" ? "この版の対象はZ=1・T=1の2D画像です。投影や断面を自動選択しません。目的に合う2Dデータを準備し、変換手順を残してください。" : "通常解析は8/16-bitグレースケールTIFF、または確認済みの単一シリーズ2D OME-TIFFです。表示用RGBから元の輝度は復元できません。", "waters-2009");
  }
  if (a.region === "custom" || a.signal === "other") {
    add(result.decisions, "general-regions", "汎用領域のワークスペースで定量する", "実際のチャンネル名を登録し、手動の領域や取り込んだラベル画像から面積・蛍光量を測定できます。蛍光核は確認済みの核染色から初期領域を検出できます。その他の構造を核のモデルで自動検出したことにはしません。");
  } else if (a.region !== "unknown" && a.signal !== "unknown") {
    if (a.nuclearStain !== "yes") {
      add(result.questions, "nuclear-stain", "核を識別するチャンネルを確認する", "現在の自動検出には核染色チャンネルが必要です。撮影記録で染色名を確認してください。ファイル名や色だけでは判断しません。");
    }
    if (a.region === "nucleolus" && a.signal !== "ncl") {
      add(result.limits, "compartment-signal", "核小体の領域定義を別に確認する", "現在の核小体レシピはNCLから候補を定義します。GFPだけから核小体や細胞境界を推定しません。");
    } else if (a.input === "grayscale-2d" && a.nuclearStain === "yes") {
      result.recipe = a.signal === "ncl" ? "ncl-native-2d" : "gfp-nuclear-2d";
      result.recipeLabel = a.signal === "ncl" ? "核・核小体のNCL定量" : "核内GFP定量";
    }
  }
  if (a.background !== "yes") {
    add(result.questions, "background", "信号を含まない背景領域を用意する", "背景ROIを画像上で確認します。核の外側には細胞質があるため、核外全体を背景とはみなしません。適切な領域がなければ撮影時の対照や背景の扱いを検討してください。", "waters-2009");
  }
  if (a.acquisition !== "matched") {
    add(result.questions, "acquisition", "撮影・染色条件の比較可能性を確認する", "露光、レーザー、検出器、染色条件などが異なる輝度は、そのまま生物量の差と解釈できません。バッチを統計に入れても飽和や失われた信号は修復できません。", "waters-2009");
  }
  if (a.signal === "ncl" && a.region === "nucleolus") {
    add(result.limits, "circularity", "領域を定める信号と、測る信号の関係", "NCLの変化によって検出領域も変わり得ます。自動候補を確認し、必要に応じて別の領域定義と比較します。比の変化だけで核小体ストレスを確定しません。", "kodiha-2011");
  }
  if (a.comparison === "descriptive") {
    result.statistics = "descriptive";
    add(result.decisions, "descriptive", "測定値と分布を確認する", "領域・視野・試料を区別した分布図と元の測定表を保存できます。独立反復が未確認でも検定を伴わない図を作成でき、独立性を確定してから実験単位の比較へ進めます。", "lord-2020");
  } else if (a.comparison === "unknown" || a.allocation !== "biological") {
    add(result.questions, "independence", "処置を別々に割り付けた単位を確認する", "同じ試料の細胞や視野を増やしても独立反復は増えません。動物、独立培養など、研究の結論を広げたい単位と割付方法を確認します。撮影日だけでは判断できません。", "lazic-2018");
  } else {
    result.statistics = a.comparison === "paired" ? "paired-candidate" : "experimental-unit-candidate";
    add(result.decisions, "units", a.comparison === "paired" ? "対応関係を記録して、実験単位で比較する" : "実験単位に集約して比較する", a.comparison === "paired" ? "同じ個体・対応する試料に同じペアIDを付け、比較する両群に1組ずつの値があるか確認します。撮影日が同じだけでは対応になりません。" : "既定は視野内中央値→試料内の視野平均→実験単位内の試料平均です。単位間の比較ではWelch検定が候補になりますが、設計と分布を確認して決定します。", "lazic-2018");
    add(result.limits, "sample-size", "計算できることと、十分な反復数は異なる", "各群2単位は検定を計算するための下限で、研究上十分という意味ではありません。効果量、不確実性、実験設計を合わせて検討します。", "lord-2020");
  }
  if (a.gating !== "none") {
    if (a.signal !== "gfp") add(result.questions, "gating-channel", "陽性選別に使うGFPを別途確認する", "現在の選別機能はGFPチャンネルが必要です。この画面の選択だけで撮影チャンネルを追加・変換しません。");
    add(result.limits, "selection", a.gating === "negative-control" ? "陰性対照の分布から閾値を確定する" : "手動・Otsuによる選別は探索的に扱う", "比較結果を見ながら閾値を動かさず、採用条件と除外数を保存します。処置で変わるGFP量による選別や調整は、比較対象・推定する効果を変える可能性があります。");
  }
  add(result.decisions, "review", "代表視野で確認してから、条件を固定する", "元の画素で測定し、表示の明るさ調整と分けます。領域の修正・除外を確定後、同じ条件を全視野へ適用します。");
  add(result.decisions, "traceability", "図と一緒に、測定表と解析条件を残す", "比較する群と補正対象を結果を見る前に指定します。図の点がどの測定値・解析版に由来するかを保存し、Methodsを確認して使います。", "schmied-2024");
  return result;
}

export function planReceipt(answers: PlanAnswers) {
  return { format: "cytellect-analysis-plan", version: PLAN_VERSION, status: "planning-only-not-adopted", answers, guidance: buildPlan(answers), references: planReferences };
}
