/** One-sentence explanations for visitors who are not biologists (requirements DM-11). Plain words, no numbers
 * from any result: values are read only from the saved results (RS-06). */
export const TERMS: Record<string, string> = {
  "核": "細胞の中で DNA をしまっている部屋。青い染色（Hoechst）で光る。",
  "核小体": "核の中にある小さな塊で、タンパク質を作る工場（リボソーム）の部品を作る場所。",
  "核質": "核の中で、核小体を除いた残りの部分。",
  "NPM1": "核小体に集まるタンパク質。ここでは核小体の目印として光らせている。",
  "Hoechst": "DNA に結合して青く光る色素。核の形を見るために使う。",
  "5-EU": "新しく作られた RNA に取り込まれる目印。光が強いほど、その場所で RNA を盛んに作っている。",
  "離心率": "形がどれだけ細長いかを表す数。0 がまん丸で、1 に近いほど細長い。",
  "総面積": "1 つの核の中にある核小体の面積を、すべて足したもの。",
  "実験回": "同じ実験を繰り返した 1 回分。回ごとに同じ向きに変わるかで、結果の確かさを見る。",
  "オキサリプラチン": "白金を含む抗がん剤。大腸がんの標準治療に使われる。",
  "シスプラチン": "白金を含む抗がん剤。多くのがんに使われるが、大腸がんには使われない。",
  "アクチノマイシン D": "RNA を作る働きを止める薬。ActD とも書く。",
  "PLK1": "細胞が分裂するのに欠かせない遺伝子。働かなくすると細胞が増えにくくなる。",
  "ノックアウト": "遺伝子を壊して、働かないようにすること。",
};

/** What a metric means, shown under the result in the demo. */
export const METRIC_HINTS: Record<string, string> = {
  nucleolar_eccentricity: "核小体の離心率：形がどれだけ細長いか。0 がまん丸で、1 に近いほど細長い。",
  nucleolar_area_px: "核小体の総面積：1 つの核の中にある核小体の面積の合計。",
  nucleolar_area_um2: "核小体の総面積：1 つの核の中にある核小体の面積の合計。",
  nucleolar_count: "核小体数：1 つの核の中にある核小体の数。",
  area_px: "面積：輪郭で囲んだ部分の広さ。",
  area_um2: "面積：輪郭で囲んだ部分の広さ。",
  mean: "平均輝度：輪郭の中の明るさの平均。染めたものが多いほど明るい。",
  median: "中央値：輪郭の中の明るさを並べたときの真ん中の値。",
  integrated: "積算輝度：輪郭の中の明るさの合計。染めたものの総量の目安。",
  nucleus_count: "視野あたりの核数：1 枚の画像に写っている細胞（核）の数。",
  nucleus_density_per_mm2: "核の密度：一定の広さあたりの細胞（核）の数。",
  positive_fraction: "陽性率：決めた明るさを超えた核の割合。",
  log2_nucleoplasm_over_nucleolus: "核質／核小体の比：信号が核小体と核質のどちらに多いか。",
};
