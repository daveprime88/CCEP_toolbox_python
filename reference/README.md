# Portable MATLAB reference capture

Copy `matlab/capture_kernels.m` to the computer with MATLAB and the original
CCEP Toolbox. This captures **six kernel cases**, not a full toolbox baseline.
No participant files are required by these cases. It has not been executed here:
this computer has no MATLAB runtime. Source inspection and Python tests cannot
replace that run.

In MATLAB, close the CCEP launcher (the filtering case captures function defaults):

```matlab
capture_kernels('/path/to/CCEP Toolbox', '/path/to/new-reference-bundle')
```

Use a new output directory. The harness records runtime/toolbox versions, source
hashes, RNG states, actual baseline windows, per-case failure reports and hashed
MAT artifacts. It calls five original functions plus the MATLAB `ranksum` primitive used by
`CCEPMakeRMSZScores`; it does not yet execute the full eligibility wrapper. Missing Signal Processing or
Statistics toolboxes make the corresponding case fail explicitly. It temporarily
adds the toolbox to MATLAB's path and restores the previous path afterward.
The original filter may start a parallel pool and can take time.

Copy the bundle back through your usual authorized transfer method. Then:

```python
from pathlib import Path
from ccep.reference import validate_bundle
print(validate_bundle(Path('references/local/run1'),
    source_root=Path('../CCEP_Toolbox/CCEP Toolbox')))
```

A complete manifest is **capture completeness**, not numerical parity. Compare
arrays with fixture-specific `Tolerance` values chosen before accepting results.
Use recorded MATLAB coefficients to separate filter design differences from
filter application differences. Replay the saved baseline endpoints rather than
expecting equal RNG seeds to produce equal cross-language samples.

## Full workflow capture still required

For each corpus case record input hashes, effective GUI/default settings, companion
files, original source revision and entry point. Run the unmodified processing
workflow on working copies of the reference data: `CCEPProcessRMSFile` writes an
RMS MAT beside its EDF. Retain `DataStruct`, `StimAnnot`, `Baseline`, actual
`BaselineTimes`, `ERPDataInds` and `PlotERPIndexes`, plus processed intermediates
from a documented instrumented copy if needed. Do not alter the frozen source.

Capture all capability groups in `docs/port/capabilities.md`, including real EDF
scaling, annotation MAT time origins, anatomy/rank exclusions, repositories and
Excel exports. For imaging, retain SPM inputs/settings, transforms, segmentations,
actual tissue-sampling points, landmarks and overlays. Choose millimetre/overlap/
probability acceptance limits before accepting the ANTs implementation.

Keep restricted recordings and identifying artifacts outside public fixtures.
A reference manifest identifies inputs without requiring transfer of raw recordings.
Kernel bundles do not cover these full workflow or imaging requirements.

## Execute Python comparisons

`ccep --json reference-replay BUNDLE LIMITS.json` replays captured inputs. The
limits file has an `arrays` mapping containing these numerical comparisons:

- `metrics.rms`, `metrics.std`, `ranksum.z`: dimensionless.
- `filter.band_coefficients`, `filter.notch_coefficients`: dimensionless.
- `filter.uni`, `filter.bi`, `filter.uni_captured_coefficients`,
  `filter.bi_captured_coefficients`: `synthetic amplitude` units.

Each entry supplies `absolute`, `relative`, `unit`, and a scientific `rationale`.
No default acceptance tolerances are supplied. Trigger indexes and epoch window
identities are exact; saved baseline endpoints are checked against the exclusion
mask and sampling bounds. The captured-coefficient comparisons distinguish FIR
application from FIR design. A complete, passing kernel report still does not
certify the full toolbox.

For a saved original analysis, use `ccep --json inspect RMS.mat`, then
`ccep --json compare-mat PYTHON.npz RMS.mat LIMITS.json`. This checks the shared
metrics and indexes without requiring MATLAB to run locally. The JSON report
states the compared scope and exclusions. Preserve the original recording,
metadata, effective settings and runtime provenance alongside that MAT file.
