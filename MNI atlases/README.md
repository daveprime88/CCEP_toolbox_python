# MNI atlases

Five unchanged NIfTI images from the user-supplied McGill **symmetric ICBM152
2009a** archive, tracked with Git LFS. T1 and T2 are anatomical intensity
templates; GM, WM and CSF are tissue probability priors, not region-label atlases.
All five share a 197 × 233 × 189 grid with 1 mm spacing.

Original filenames and bytes are preserved. See `manifest.json` for SHA-256
hashes and archive provenance, and retain `COPYING` with redistributed copies.

From the repository root, retrieve and verify the data:

```bash
git lfs install
git lfs pull --include="MNI atlases/*.nii"
python tools/check_mni_atlases.py
```

The checker needs NumPy and NiBabel (available in the imaging extra). It checks
hashes, grids, finite values, decoded nonzero counts and tissue probability ranges
against the existing frozen 2009a reference. CI fetches these files in one imaging
job. Other jobs do not need the data. These repository assets are not installed
inside the Python wheel; a pip installation alone does not retrieve LFS files.

This is exactly the requested five-image subset, not the complete ten-image
archive accepted by `image-template-install`. That command still imports the
original ZIP, including its mask assets. The current `image-normalize` code still
requires six priors; the planned three-class production path remains to be
implemented and validated with a suitable subject brain mask. Do not supply these
three maps to that six-prior interface or invent the missing classes.

See [template checks](../docs/port/icbm152_2009a.md) and
[current roadmap checklist](../docs/port/roadmap-checklist.md).
