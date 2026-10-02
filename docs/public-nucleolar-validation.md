# Published DAPI/NCL image validation

## Source and actual execution

Cytellect ran the locked Fiji / StarDist 2D / ImageJ / MorphoLibJ pipeline on the full publicly supplied **4DNFI7FAWT6C** image: 1,739 x 1,536 pixels per channel, uint16, one OME series, two channels, Z=1 and T=1. The default starting settings were used without tuning to this field. StarDist used 16 deterministic tiles. The run produced **100 nuclear objects and 182 NCL-defined nucleolar candidates**.

These counts are software outputs, not accuracy scores. No nucleus/nucleolus ground-truth annotation accompanies this field. This check establishes real-image execution, valid nuclear parent relationships and traceable source-pixel measurements. It does not establish F1 targets, biological conclusions, or suitability for a private experiment.

The [4DN file record](https://data.4dnucleome.org/files-microscopy/4DNFI7FAWT6C/) belongs to NPC experiment set 4DNESLP3I9VG. The data availability statement in [Li et al., Sceptic, Genome Biology 26:209 (2025)](https://doi.org/10.1186/s13059-025-03679-3) explicitly identifies that experiment set. Attribution: Li, Kim, Pendyala et al.; Doug Fowler laboratory, University of Washington; 4D Nucleome.

## Channel review and limits

The file's embedded OME metadata names index0 Camera NIR (700 nm) and index1 Camera DAPI (488 nm). Visual inspection also shows concentrated nucleolar signal in index0 and nuclear DNA morphology in index1. This validation explicitly adopts **DAPI=index1 and NCL=index0**.

The portal's imaging_paths assigns ch00 to DAPI and ch01 to NCL, which is the opposite order. That metadata discrepancy is retained in the manifest and public demonstration; confirmation from the data provider is not claimed. Cytellect does not infer channel roles from a filename.

No GFP was acquired. There are no fabricated GFP values, GFP selection, group comparison or p values in this public demonstration. Tables show raw DAPI and raw NCL means in nuclear, nucleolar-union and nucleoplasmic regions. Background correction requires a confirmed background ROI in the normal workflow and was not applied in this display example.

The supplied TIFF is 2D. The publication describes z-stack acquisition and analysis of maximum projections. Cytellect did not perform projection and does not claim this file is an original optical section.

## Access and publication of derived results

The [official 4DN AWS Open Data registry](https://registry.opendata.aws/4dnucleome/) permits anonymous download, analysis and publication of results. The file metadata supplies an open_data_url in that documented public bucket. The source is not relabeled Apache-2.0 or CC0. The [4DN use guidance](https://data.4dnucleome.org/help/user-guide/faq) requests attribution and coordination for scientific publications; no paper or abstract is being submitted by this software check.

Only source-attributed derived display images, object contours and calculated measurements may be included in the public demonstration. The original TIFF remains outside the repository. The data-use statement is distinct from the article's CC BY 4.0 text license.

The original's MD5 matches the portal record. SHA-256 and exact public retrieval URL are pinned in fixtures/public/nucleolar/manifest.json. Derived RGB uses independent 1st to 99.8th percentile display scaling, NCL in red and DAPI in blue with a small green contribution. Original source pixels and original-resolution masks supply every table value; the RGB display is not a measurement input.

## Reproduce

From the repository in the locked Python environment:

    python scripts/public_nucleolar.py --data-dir /private/public-nucleolar --output /private/public-nucleolar/evaluation --fiji /opt/fiji

The downloader accepts only the pinned public accession and validates its size and SHA-256. Runtime data and originals must stay outside the checkout. No model or package is downloaded by the detector. The script produces demo.json, per-channel/display PNGs, canonical labels and detailed engine provenance.

The public image helps test realistic appearance and data handling. Synthetic analytical tests remain useful for exact expected arithmetic and failure cases. Private experimental validation and research-user evaluation remain separate requirements.
