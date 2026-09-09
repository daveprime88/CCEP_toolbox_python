# Remaining implementation and acceptance work

The initial development workflow is executable: EDF/annotations → explicit
processing configuration → RMS/ERP and optional metadata-based scoring → GUI
review and CLI export. It is not the agreed complete first release. Keep the
36-capability matrix as the release scope; no feature has been dropped.

## Next implementation sequence

1. **Legacy metadata and analysis integration (WP3a/WP2).** Characterize real
   `DataStruct`, electrode and RMS MAT files. Port hemisphere/acronym/combined
   anatomy relabeling, contact coordinates and companion discovery. Connect these
   adapters to the existing explicit scoring interface and GUI settings. Preserve
   both reference paths, sample-rate quirks, MAT schemas and untouched fields.
   The generic MAT writer and selected-metric comparator are not a complete legacy
   analysis importer/exporter. Add full-file comparisons before accepting parity.
2. **Repositories and connectivity (WP3a/WP2/WP5).** Implement the original
   participant/repository structures, search intersections, electrode displays and
   anatomical reports. The source has nontrivial per-contact/per-participant
   aggregation and apparent duplicate-removal quirks; capture these before deciding
   on any correction. Do not substitute a generic pooled mean or ordinary dedup.
3. **Remaining recording interactions (WP2/WP3a).** Complete batch/companion-file
   handling, mixed-rate/discontinuous EDF and ambiguous-label behavior, annotation
   grammar and time-origin cases, result-file/reference switching, all scientific
   parameter controls, and responsive cancellation for realistic recordings.
4. **Imaging completion (WP3b/WP2/WP5).** Port manual reorientation, full image
   selection/registration/segmentation state, coordinate session compatibility,
   atlas/tissue shape sampling and 3D displays. Review normalization/template
   choices and the user's SPM12/ANTs comparison resource. The trade study and
   staged six-tissue normalization candidate are now implemented; compare them
   with representative SPM cases before choosing scientific defaults. In particular,
   verify N4/segmentation mask choices, iterative estimation, the six-class tissue
   model, cropped-field behavior, and discrete SPM modulation versus pull-Jacobian
   densities. Add matched image outcome reports and unit adapters. Resolve
   ANTs/Python 3.14 installation separately. See `docs/research/` and
   `imaging-verification.md` for completed engineering evidence.
5. **Safety and remaining utilities (WP2/WP3a).** Complete study-detail selection,
   historical plot/table semantics and all remaining reachable utility workflows.
6. **Release evidence (WP4/WP6).** Complete corpus coverage, author GUI walkthroughs,
   live Codex workflow acceptance, supported OS/Python installations, performance
   measurements and final asset/dependency review. Publish only after these gates.

## External evidence required

Run `reference/matlab/capture_kernels.m` on the reference computer and retain its
manifest, MAT artifacts and log. Capture real workflows and imaging cases using
`reference/README.md`. Supply original runtime versions and effective settings,
input hashes, actual baseline windows, sample-index artifacts and image geometry.
Choose fixture-specific numerical and imaging thresholds before accepting results.
No actual MATLAB/SPM corpus comparison has been run during this implementation.

Continue port commits independently of correction commits. Every source discrepancy
remains unapproved for scientific correction until the affected legacy behavior has
been demonstrated. The known observations are in `legacy-discrepancies.md`.
