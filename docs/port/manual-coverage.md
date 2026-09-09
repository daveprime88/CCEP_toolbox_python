# Manual migration coverage

All paragraphs are retained in `docs/original-manual.md`; the concise README and
workflow guide condense them. The extractor retains images at their paragraph
positions. Media checksums are in `docs/assets/manual/manifest.json`.

| Original section | Concise destination | Treatment |
| --- | --- | --- |
| Introduction, purpose, research-only context | README opening | Retained |
| Organising data, toolbox setup, MATLAB search path | README Install; guide Prepare data | MATLAB setup retained historically; Python install documented separately |
| Recommended stimulation parameters and study comparisons | guide Prepare data | Scientific qualification retained |
| Imaging inputs, DICOM conversion, maps | guide Align images | Retained; SPM historical/ANTs planned distinction explicit |
| MRI/CT preprocessing, origin and rotational alignment | guide Align images | Condensed; historical timing estimates kept only in full transcription |
| Acquisition inputs, contact count, start/end, processing | guide Align images | Retained |
| Electrode viewing, coordinate spaces | guide Align images | Retained; image3.png |
| SEEG viewer, references, timing, gain, filtering | guide Review EDF | Retained; image1.PNG |
| Manual/automatic pulses and annotation editing | guide Review EDF | Retained; deletion distinction explicit |
| RMS files | guide Process and aggregate | Retained |
| Repository creation, addition and removal limitation | guide Process and aggregate | Retained; image2.png |
| Repository filters and counts | guide Process and aggregate | Retained |
| Connectivity exclusions, aggregation and sheets | guide Process and aggregate | Retained; image4.PNG |
| ERP controls and 12-channel limit | guide Inspect ERPs | Retained; image5.PNG |
| Rankings, highlights and re-sorting | guide Inspect ERPs | Retained; image6.PNG |
| Acknowledgements, thesis, final remarks | README Credit; NOTICE | References/credit retained; greetings condensed |

The original has Figure 1 and Figures 3–7; there is no embedded Figure 2.
The extracted images were individually opened and visually checked during WP1.
No Python GUI equivalence is inferred from these historical screenshots.
