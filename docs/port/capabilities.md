# Capability and acceptance matrix

Baseline: `a25ed5d75536e5d3a8c2570c48f3196055a7f4bd`.
Paths below are relative to `CCEP Toolbox/`. This groups the 101 first-party
source candidates in the complete [file index](legacy-inventory.md).
**No capability is MATLAB-verified yet.** See [status](status.md) for implementation
progress; this matrix defines the remaining first-release obligations.

| ID | User capability / source entry points | Required fixture and acceptance |
| --- | --- | --- |
| F01 | Launcher, persisted settings: CCEPGUIInit; Parameters and intialisation/CCEPInitialisationParams | Defaults with/without GUI, saved settings replay |
| F02 | Session/permanent file discovery: File Import/FilePathMenu | Duplicate filenames, companion-file lookup, cancellation |
| F03 | EDF headers/channel selection/scaling: EDF Load/EDF_Read, Get_EDF_FileHeaders, Get_EDF_Channels, Load_EDF_Point_to_Point | EDF/EDF+, units, record boundaries, mixed rates, malformed/truncated files |
| F04 | Patient maps/contact metadata: Load_Patient_Map, Load_Patient_Map_Bipolar, Fill_Contact_Information, LabelCheck | Original and Formatted worksheets, names/numbers/OUT, duplicate/missing rows |
| F05 | Recording/electrode integration: CCEPEDFDataImport, CCEPIndividualDataImport, CCEPDataStructCreate, CCEPSEEGDataImport, CCEPEDFBatchDataImport | Matched EDF, electrodes, annotations; channel order and companion lookup |
| F06 | Bipolar montages: Create_BipolarEEG, Get_Bipolar_Channels, General Functions/BipolarDataConversionFunction | Adjacent/nonadjacent contacts, polarity, coordinates, anatomy; two legacy entry paths |
| F07 | Trigger pulses: General Functions/StimPulseFinder | Threshold, refractory samples, final-sample behavior, units |
| F08 | SEEG display: SEEG Viewer/CCEPSEEGViewer, CCEPSEEGRedisplay, CCEPSEEGViewerCallback | Load, select, reference, scroll, time/gain, filtering; plotted arrays and units |
| F09 | Annotation/pulse review: CCEPAnnotationEditor, CCEPAnnotationCallback | Browse/add/replace/delete, manual undo, automatic acquisition, MAT save/reopen |
| F10 | Stimulus annotation parsing: Processing functions/CCEPStimAnnotConvert | Real label grammar, start/end matching, frequencies/current, manual overrides |
| F11 | Filtering: CCEPFilterFunction | FIR coefficients, GUI/default values, notch normalization, retained tail, dtype |
| F12 | Epoch/baseline windows: CCEPStimFreqDataTimeAllocation, CCEPProcessRMSFile | All frequency branches, inclusive indexes, first pulse baseline shift, edge failures |
| F13 | Random baselines: CCEPBaselineTimeGrabber | Actual selected windows/RNG, exclusion masks, seizure/annotation edge cases |
| F14 | RMS/std metrics: CCEPSimilarityDistanceMetricsRMSOnly | Per-pulse arrays, nonfinite and constant signals, single/double precision |
| F15 | Statistical scores/ranks: CCEPMakeRMSZScores | Validity thresholds, anatomy exclusions, ranksum method/ties, means/medians/QV |
| F16 | File/batch processing: CCEPProcessRMS, CCEPProcessRMSFile, CCEPProcessRMSBaseline | Full matched dataset, outputs and effective settings; audit apparently stale baseline helper |
| F17 | Anatomy and coordinates: CCEPMapImport, CCEPCoOrdRead; General Functions/*Label*, CoOrdDist, CCEPAnatomicalMapRead | Acronym mapping, hemispheres, combined labels, tissue/coordinate semantics |
| F18 | Repository creation/update: Stimulation Repository/CCEPRepositoryCompileUpdate, CCEPRepositoryUpdateIndividual, CCEPReposMenu | Saved MAT schema, duplicate addition, path handling, file identity |
| F19 | Repository search: CCEPReposGUI, CCEPListFinderReposGUI | Every filter, counts, selection intersections, empty results |
| F20 | Electrode/stimulation plots: CCEPSelectedReposElectrodePlot, CCEPSelectedReposElectrodeSetPlot | Participant selection, spaces, reset; plotted coordinates |
| F21 | Anatomical connectivity: Processing functions/CCEPCompileAnatomicalPipeline | Patient-normalised aggregation, exclusions, per-site XLSX report |
| F22 | ERP display: Results Display/CCEPERPViewer, CCEPProcessERPPlot, CCEPERPReference, CCEPERPPatientMenu, CCEPERPFileMenu, CCEPCustomSubplot | Files, references, multi-train averaging, 12 channels, axes |
| F23 | Ranking results: CCEPERPRankingViewer, CCEPRankingSort | Sort metrics, selected-channel highlights, changed pulse-train selections |
| F24 | Stimulation geometry/calculation: Safety GUI/CCEPSafetyEstimate, CCEPSafetyElectrodeToggle | Shapes, dimensions, units, threshold curves; retain historical interpretation |
| F25 | Safety studies/table: CCEPReviewSafetyTableData, CCEPStimSafetyGUI, CCEPStudyTableViewer, CCEPStimSafetyPlot | Bundled table import, selection/detail/plot equivalence |
| F26 | Imaging selection/preprocessing: MRI and CT Coregistration routine/CCEPImageSelectMenu, Preprocess/CCEPImageImport, CCEPMRICTPreprocessing | MRI+CT or second MRI, state/cancellation, persisted imaging metadata |
| F27 | Manual reorientation: AutoReorient, CheckReg and inline SPM callbacks | Origin/rotation around chosen point; world/voxel conventions and overlays |
| F28 | Realignment/coregistration: RealignmentFunc, CoregFunc | CT→MRI and extra images; landmarks mm, interpolation and repeated runs |
| F29 | Bias/segmentation/normalization: CCEPSegmentFunc | SPM six-class reference; proposed three-class ANTs outcome comparison, native/standard maps, transform direction and images |
| F30 | Coordinate acquisition: CoOrdGrabGui/CCEPSPMCoOrdGUIInit, CCEPStartCoOrdAcquire, CCEPEndCoOrdAcquire | Counts/endpoints/reacquire, interpolation, voxel and world coordinates |
| F31 | ROI warp: CCEPROICreateandWarp, ShapeWarp, CCEPProcessCoOrds | 1.5mm sphere, 1mm target grid, >=.99 / >=.95 fallback, MNI positions |
| F32 | Tissue/atlas lookup: CCEPTissueProbCalc, TissueProbCylinderCreate, CylinderCreation, RotationalAffine, VectorTangentNorm, Preprocess/CCEPGetMNIAnatomicalAreas | Actual sample points, boundaries/labels, probabilities and geometry |
| F33 | Imaging display: CCEPElectrodePlotter, CCEPPlotElectrodeCall | Surface, contact identity, atlas/tissue display, coordinate space |
| F34 | Image/session compatibility: CCEPMRICleanUpFunction and save/load calls | NIfTI/Analyze, MAT, SPM y-fields, ANTs transform metadata; no implicit substitution |
| F35 | Conversion helpers: DicomFunc, IMG2NII | DICOM branches commented in main workflow; establish active entry route before release decision |
| F36 | Utilities: General Functions remaining helpers; EDF_Load_Examples | Test through consumers; SynthesizeDataStruct is not a synthetic signal generator |

## Existing interface register

| Interface | Legacy content | Migration decision / evidence still needed |
| --- | --- | --- |
| EDF and EDF+ | Headers, physical signals, labels, annotation TALs | Preserve scaling/time axis; discontinuous recordings require explicit representation |
| Annotation MAT | Annotations and pulse times from CCEPAnnotationCallback | Inspect actual fields; preserve untouched metadata and manual/automatic distinction |
| Electrode/imaging MAT | Electrode/contact anatomy, patient/MNI coordinates, companions | Real files needed for complete schema validation |
| RMS MAT (v7.3) | StimAnnot, Baseline, DataStruct | Preserve nested structures, shapes and variable names; cross-language round trip |
| Repository MAT | CurrentCCEPRepository | Supplied example is an asset, not validated full corpus |
| Excel maps and reports | Formatted maps, acronym maps, multi-sheet reports | Preserve column/sheet meanings and numeric precision |
| NIfTI/Analyze/SPM deformation | Images, probability/label volumes, y-fields | Explicit geometry adapter; ANTs transforms are not SPM fields |
| Plots | SEEG, ERP, electrode/surface, safety curves | Compare plotted data and control behavior; Python appearance may differ |
| New CSV/native exports | Additive tables and structured arrays | Version schema, include units/provenance; never replace legacy interfaces silently |

## Dependencies and assets

- 427 tracked vendor files: MarsBaR 0.44, xlwrite/Apache POI, sort_nat.
  Replace only used behavior; original files are not Python runtime assets.
- SPM12/CAT12, Signal Processing, Statistics, Parallel Computing and MATLAB
  Runtime references require per-call audit; parallel execution is an implementation
  choice while outputs and randomness must be preserved.
- All 15 non-source assets are hashed in the file inventory. Examples and atlases
  remain in the adjacent original checkout until a specific runtime/fixture use is
  established. Do not infer reuse permission from an arbitrary bundled filename.
