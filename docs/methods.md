# Scientific contract

Intended semantics; see handoff.md for unimplemented/untested parts.

Original grayscale pixels are immutable. Detection normalization and display LUTs never alter measurements. Label masks use original coordinates. Each nucleolus has exactly one containing nucleus; nuclear edits invalidate dependent children.

Background b is the median of a confirmed background ROI. Export raw values and x-b values; native negatives remain signed. Intensity integral is sum of pixels. It is not normalized concentration.

Nucleus N, nucleolar union U, nucleoplasm P=N minus U. Measure N/U/P separately; cell-level U mean is pixel-weighted, with object measurements in a separate table. Native index is log2(mean(P-b)/mean(U-b)), defined only when both means are positive. Empty/invalid compartments produce explicit missing reasons.

NCL-defined regions can change with NCL redistribution. Record the region definition and limitation. DAPI-low is a separate definition. Missing candidates are never substituted with the nucleus/top fraction in native mode.

Legacy RGB/resizing/background/clipping/epsilon and whole-nucleus/high-NCL ratio are a separate versioned recipe. Exact reproduction is unverified at this checkpoint.

GFP gate uses confirmed negative control or exploratory manual/batch Otsu; reference group does not automatically mean negative. Save transform, threshold/range and reasons.

Aggregation: field median → sample mean → independent-unit mean. Predeclared Welch/paired tests use Holm families. Exploratory group/GFP/date regression uses field-clustered SE; verify rank/confounding/controls and few clusters. Cell counts are not independent replicate counts.

References:
- [StarDist](https://imagej.net/plugins/stardist)
- [Nucleolar fluorescence quantification](https://link.springer.com/article/10.1186/1471-2121-12-25)
- [SuperPlots](https://pubmed.ncbi.nlm.nih.gov/32346721/)
- [CellProfiler examples](https://cellprofiler.org/examples)
