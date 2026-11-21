import {UNIT_LABELS, measureLabel, subjectEntry, type MetricSubject, type ObservationUnit} from "./metric-catalog";

/** A research theme lists the measures that read it, with the stain each needs, the region it is measured on and what
 * one observation is (#257 NS-01). It chooses among the common measures only and computes nothing. */
export interface ThemeMeasure {metric: string; subject: MetricSubject;
  /** Stain names that can give the measure (whole words, any case); the first names the requirement. */
  stains: string[]; region: string}
export interface ResearchTheme {id: string; label: string; measures: ThemeMeasure[]}

const MARKERS = ["NPM1", "B23", "NCL", "nucleolin", "FBL", "fibrillarin"];
const NASCENT_RNA = ["5-EU", "EU", "5-ethynyluridine"];

/** 核小体ストレス, with the measures that exist (owner decision 23): no nucleolar shape per nucleolus, no pixel CV or
 * positive-area fraction (they did not pass the public check), no NCL positive-area fraction and no Potapova score. */
export const NUCLEOLAR_STRESS: ResearchTheme = {id: "nucleolar-stress", label: "核小体ストレス", measures: [
  {metric: "nucleolar_count", subject: "nucleoli", stains: MARKERS, region: "核小体"},
  {metric: "nucleolar_area_px", subject: "nucleoli", stains: MARKERS, region: "核小体"},
  {metric: "nucleolar_area_fraction", subject: "nucleoli", stains: MARKERS, region: "核小体"},
  {metric: "largest_nucleolus_fraction", subject: "nucleoli", stains: MARKERS, region: "核小体"},
  {metric: "nucleolar_eccentricity", subject: "nucleoli", stains: MARKERS, region: "核小体"},
  {metric: "log2_nucleoplasm_over_nucleolus", subject: "nucleoplasm", stains: MARKERS, region: "核質と核小体"},
  {metric: "mean", subject: "nucleoli", stains: NASCENT_RNA, region: "核小体"},
]};

const words = (value: string) => ` ${value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()} `;
/** The registered stain that gives a measure, by its recorded name; null when none does. */
export function themeStain(measure: ThemeMeasure, stains: Array<{id: string; name: string}>) {
  return stains.find(stain => measure.stains.some(name => words(stain.name).includes(words(name)))) ?? null;
}

export interface ThemeRow {metric: string; label: string; stain: string; region: string; unit: string; available: boolean}
/** One row per measure: its name as everywhere else, the stain it needs (the registered one when there is one), the
 * region and the observation unit, and whether the registered stains can give it. */
export function themeRows(theme: ResearchTheme, stains: Array<{id: string; name: string}>): ThemeRow[] {
  return theme.measures.map(measure => {
    const stain = themeStain(measure, stains);
    const needsReading = measure.metric === "mean" || measure.metric === "log2_nucleoplasm_over_nucleolus";
    const unit: ObservationUnit | undefined = subjectEntry(measure.subject, measure.metric)?.unit;
    const required = measure.stains === MARKERS ? "核小体のマーカー（NPM1・NCL・FBL）" : measure.stains[0];
    return {metric: measure.metric, label: measureLabel(measure.metric, measure.subject, needsReading ? stain?.name ?? measure.stains[0] : null),
      stain: stain ? stain.name : required, region: measure.region, unit: unit ? UNIT_LABELS[unit] : "", available: !!stain};
  });
}
