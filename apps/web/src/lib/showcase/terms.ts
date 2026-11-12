/** One-line definitions for visitors who are not biologists (requirements DM-11, UC-01–UC-07). No number from
 * any result: values are read only from the saved results (RS-06). */
export const TERMS: Record<string, string> = {
  "核": "DNA を収める細胞内の区画。Hoechst で青く染まる。",
  "核小体": "核内の構造体。リボソーム（タンパク質の合成装置）の部品を作る。",
  "核質": "核のうち、核小体を除いた部分。",
  "NPM1": "核小体に局在するタンパク質。本データでは核小体の標識。",
  "Hoechst": "DNA に結合する青色の蛍光色素。核の標識。",
  "5-EU": "新しく合成された RNA に取り込まれる標識。強いほど RNA 合成が盛ん。",
  "離心率": "形の細長さの指標。0 で円、1 に近いほど細長い。",
  "総面積": "1 核あたりの核小体の面積の合計。",
  "実験回": "繰り返した実験の 1 回分。回ごとの一致で再現性をみる。",
  "オキサリプラチン": "白金系抗がん剤。大腸がんの標準治療薬。",
  "シスプラチン": "白金系抗がん剤。大腸がんには用いられない。",
  "アクチノマイシン D": "RNA 合成の阻害剤（ActD）。",
  "PLK1": "細胞分裂に必須の遺伝子。",
  "ノックアウト": "遺伝子を破壊し、機能を失わせる操作。",
};

/** The metric's definition, shown under the result heading in the demo. */
export const METRIC_HINTS: Record<string, string> = {
  nucleolar_eccentricity: "離心率：形の細長さ。0 で円、1 に近いほど細長い。",
  nucleolar_area_px: "核小体の総面積：1 核あたりの核小体の面積の合計。",
  nucleolar_area_um2: "核小体の総面積：1 核あたりの核小体の面積の合計。",
  nucleolar_count: "核小体数：1 核あたりの核小体の数。",
  area_px: "面積：輪郭内の面積。",
  area_um2: "面積：輪郭内の面積。",
  mean: "平均輝度：輪郭内の画素値の平均。標識量の目安。",
  median: "中央値：輪郭内の画素値の中央値。",
  integrated: "積算輝度：輪郭内の画素値の合計。標識の総量の目安。",
  nucleus_count: "視野あたりの核数：1 視野に写る細胞（核）の数。",
  nucleus_density_per_mm2: "核の密度：単位面積あたりの核の数。",
  positive_fraction: "陽性率：しきい値を超えた核の割合。",
  log2_nucleoplasm_over_nucleolus: "核質／核小体比：信号の核質と核小体への分配。",
};
