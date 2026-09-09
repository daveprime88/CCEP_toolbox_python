# Legacy behavior requiring reference characterization

These are source observations, not approved scientific corrections. No correction
has been folded into the port. All require MATLAB capture and separate delta
changes if the author decides the behavior should change.

| Source | Observation | Current treatment |
| --- | --- | --- |
| CCEPFilterFunction | Notch frequencies divided by Nyquist twice; trailing 250 samples retained after each stage | Preserved in source-derived filter; coefficients still need MATLAB comparison |
| StimPulseFinder | Threshold >400000; skip is 10 samples; final sample omitted; post-trigger read can exceed length | Preserved including explicit edge error |
| CCEPBaselineTimeGrabber | Interior annotation exclusion ±1s, near-edge exclusion ±10s; seizure pass reads mask without assigning false | Preserved; error on out-of-range legacy reads |
| CCEPProcessRMSFile | Local SamplingFreq defaults to 1000 even though DataStruct may carry another rate | Full-file parity unresolved; kernel accepts explicit rate; pipeline must not claim full-file equivalence |
| CCEPProcessRMSFile | First pulse ERP plotting stitches a baseline ~2s earlier to post-stimulus samples | Preserved in epoch source indexes and plotted offsets |
| CCEPMakeRMSZScores | Rejects <=5 pulses, not merely <5 as comment says; small-sample ranksum may not supply zval; rank ties are not averaged | Source-derived eligibility/scoring integrated for explicitly supplied relabeled anatomy; real-file metadata adaptation pending |
| CCEPMakeRMSZScores | Median ranking loop uses the number of valid means; mixed finite/Inf values can yield median rank >1 | Preserved, with quartile branches capped at 4 as in the source |
| EDF_Read / annotation editor | EDF Times is round(onset*Fs), while manual cursor/pulses index MATLAB samples; zero/one-origin ambiguity | MAT adapter currently interprets positive sample positions; real fixtures required before compatibility acceptance |
| CCEPProcessRMSBaseline | Refers to older helper names/signatures | Reachability/runtime audit needed; do not invent intended behavior |

The rank-sum candidate follows the current [MathWorks ranksum documentation](https://www.mathworks.com/help/stats/ranksum.html),
including method selection, continuity and ties. Historical runtime output must
still establish the baseline for this repository.
