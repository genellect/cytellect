import { formatValue } from "@/lib/types";
import styles from "./workspace.module.css";

type Row=Record<string,unknown>;
const numberLabel=(value:unknown)=>typeof value==="number"&&value!==0&&Math.abs(value)<0.0001?value.toExponential(3):formatValue(value);
export type StatisticalResult={counts:Row[];comparisons:Row[];warnings:string[];means:Row[];selection?:Row;model?:{formula?:string;baseline?:string;gfp_transform?:string;clusters?:number;coefficient_table?:Row[];gfp_relationship?:Row;trend?:Row|null;trend_status?:string;trend_reason?:string};sensitivities?:Array<{scenario:string;status:string;reason?:string;result?:StatisticalResult}>};
const explanations:Record<string,string>={
 few_clusters_confidence_intervals_are_exploratory:"視野クラスタ数が少ないため、信頼区間は探索的な結果として扱ってください。",
 nonpositive_or_missing_gfp_excluded_from_log_model:"GFPが非正値または欠測の対象を、対数回帰から除外しています。",
 incomplete_conditions_within_acquisition_date:"比較する群が揃っていない撮影日があります。",
 baseline_missing_within_acquisition_date:"基準群が含まれない撮影日があります。",
 field_clustering_does_not_model_dependence_between_fields_from_the_same_unit:"同じ独立単位に属する視野間の依存性は、視野クラスタの標準誤差では扱っていません。",
 no_valid_selected_measurements:"条件を満たす有効な測定値がありません。",

 few_clusters_inference_unreliable:"視野クラスタ数が少なく、推論の信頼性に制約があります。",
 exploratory_cell_level_inference:"細胞単位の探索解析です。独立反復に基づく確認的な結論として扱わないでください。",
 exploratory_cells_and_fields_are_not_biological_replicates:"探索解析の細胞数・視野数は、生物学的な独立反復数ではありません。",
 missing_outcomes_excluded_inspect_groupwise_missingness:"指標が欠測の対象を除外しています。群別の採用数を確認してください。",
 some_experimental_units_have_no_selected_outcomes:"採用できる測定値がない独立実験単位があります。",
 data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation:"GFPによる選別は探索的です。事前指定または独立データでの確認が必要です。",
 ncl_defined_regions_can_change_with_the_measured_ncl_distribution:"NCLで定義した領域は、測定するNCLの分布によって変化します。",
 two_nonbaseline_repeat_lengths_required:"基準群以外に2種類以上のリピート長が必要です。",
 repeat_length_trend_not_estimable:"リピート長の傾向を推定できません。",
 coefficient_inference_not_estimable:"係数の信頼区間とp値を推定できません。",
};
export const statisticalMessage=(code:string)=>explanations[code]||code;
export function ResultWarnings({warnings=[]}:{warnings?:string[]}){return <>{warnings.map((w,i)=><p key={i} className={styles.notice}>{statisticalMessage(w)}</p>)}</>;}
export function ComparisonTable({rows}:{rows:Row[]}){return <div className={styles.tableWrap}><table><thead><tr><th>群A</th><th>群B</th><th>差（A−B）</th><th>95% CI</th><th>p</th><th>Holm調整p</th></tr></thead><tbody>{rows.map((c,i)=><tr key={i}><td>{String(c.group_a)}</td><td>{String(c.group_b)}</td><td>{numberLabel(c.estimate)}</td><td>{numberLabel(c.ci_low)} – {numberLabel(c.ci_high)}</td><td>{numberLabel(c.p_value)}</td><td>{numberLabel(c.p_holm)}</td></tr>)}</tbody></table></div>;}
function CountTable({rows}:{rows:Row[]}){return <div className={styles.tableWrap}><table><thead><tr><th>群</th><th>細胞／測定値</th><th>視野</th><th>独立単位</th></tr></thead><tbody>{rows.map((r,i)=><tr key={i}><td>{String(r.condition)}</td><td>{numberLabel(r.cells??r.observations)}</td><td>{numberLabel(r.fields)}</td><td>{numberLabel(r.experimental_units)}</td></tr>)}</tbody></table></div>;}
function CoefficientTable({rows}:{rows:Row[]}){return <div className={styles.tableWrap}><table><thead><tr><th>項</th><th>係数</th><th>95% CI</th><th>p（未補正）</th><th>推定状態</th></tr></thead><tbody>{rows.map((c,i)=><tr key={i}><td>{c.term==="gfp_centered"?"GFP（撮影日内で中心化）":c.term==="repeat_length"?"リピート長":String(c.term)}</td><td>{numberLabel(c.estimate)}</td><td>{numberLabel(c.ci_low)} – {numberLabel(c.ci_high)}</td><td>{numberLabel(c.p_value)}</td><td>{c.status==="not_estimable"?statisticalMessage(String(c.reason)):"推定済み"}</td></tr>)}</tbody></table></div>;}
export function ModelResult({result}:{result:StatisticalResult}){const model=result.model;if(!model)return null;return <div className={styles.card}><h3>GFPとの関連・調整回帰</h3><p className={styles.small}>視野クラスタ標準誤差 · {model.clusters} 視野。係数とリピート長のp値は未補正で、群間比較のHolm補正とは別です。</p>{model.gfp_relationship&&<CoefficientTable rows={[model.gfp_relationship]}/>}<details><summary>回帰式と全係数</summary><p className={styles.small}>{model.formula}<br/>基準群：{model.baseline} · GFP変換：{model.gfp_transform}</p><CoefficientTable rows={model.coefficient_table||[]}/></details>{!!result.means?.length&&<details><summary>群別の調整平均</summary><p className={styles.small}>GFPの撮影日内中心化値を0とし、観測した撮影日に等しい重みを与えた平均です。</p><div className={styles.tableWrap}><table><thead><tr><th>群</th><th>調整平均</th><th>95% CI</th></tr></thead><tbody>{result.means.map((m,i)=><tr key={i}><td>{String(m.condition)}</td><td>{numberLabel(m.mean)}</td><td>{numberLabel(m.ci_low)} – {numberLabel(m.ci_high)}</td></tr>)}</tbody></table></div></details>}<h4>リピート長の傾向</h4>{model.trend?<><CoefficientTable rows={[{term:"repeat_length",...model.trend}]}/><p className={styles.small}>基準群を除いた探索解析 · {String(model.trend.clusters)} 視野</p></>:<p className={styles.small}>{statisticalMessage(model.trend_reason||"リピート長の推定結果はありません。")}</p>}</div>;}
function SelectionSummary({selection}:{selection?:Row}){if(!selection)return null;return <p className={styles.small}>入力 {numberLabel(selection.input_rows)} · 除外 {numberLabel(selection.excluded)} · GFP選別外 {numberLabel(selection.gfp_unselected)} · 指標欠測 {numberLabel(selection.missing_metric_selected)}</p>;}
function scenarioLabel(scenario:string){if(scenario.startsWith("gfp_threshold:"))return `GFP閾値 ${scenario.slice(14)}`;if(scenario.startsWith("region_revision:"))return `領域定義の解析版 ${scenario.slice(16,24)}`;if(scenario.startsWith("legacy_high_region_top"))return `NCL高輝度領域 上位${scenario.slice(22)}%`;if(["complete_dates","complete_acquisition_dates","complete_comparison_dates"].includes(scenario))return "比較群が揃った撮影日";return scenario;}
export function SensitivityResults({items}:{items:NonNullable<StatisticalResult["sensitivities"]>}){return <div className={styles.card}><h3>感度解析</h3><p className={styles.small}>主解析とは別の条件で再計算しています。Holm補正は各条件の事前指定比較内で行い、条件間をまとめた補正ではありません。</p>{items.map((s,i)=><details key={i} data-testid="sensitivity-result"><summary>{scenarioLabel(s.scenario)} · {s.status==="succeeded"?"推定済み":"推定不可"}</summary>{s.reason&&<p className={styles.notice}>{statisticalMessage(s.reason)}</p>}{s.result&&<><SelectionSummary selection={s.result.selection}/><CountTable rows={s.result.counts||[]}/><ResultWarnings warnings={s.result.warnings}/><ComparisonTable rows={s.result.comparisons||[]}/><ModelResult result={s.result}/></>}</details>)}</div>;}
