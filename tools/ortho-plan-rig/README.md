# Alok Ortho Plan Rig v4 (Codex branch)

A diagnostic-first MaxScript project for 3ds Max + Chaos Corona.

## Why v4 is different

The geometry, Corona detection, rig logic, tests, and UI are separate. The script no longer hides Corona API failures behind a generic error.

## Modules

- `src/00_Core.ms` - logging, safe property access, rig tags
- `src/10_Geometry.ms` - view matrices and camera-space bounding boxes
- `src/20_CoronaProbe.ms` - creates a CoronaCam and dumps every exposed property
- `src/30_CoronaAdapter.ms` - discovers orthographic projection and Ortho View Size at runtime
- `src/40_Rig.ms` - create/fit cameras and top duplicates
- `tests/50_Tests.ms` - independent component tests
- `src/99_UI.ms` - UI only

## Recommended first run

Run `AOPR_v4_BUNDLED.ms`, then:

1. Click **RUN CORONA PROBE**.
2. Click **RUN MODULE TESTS**.
3. If both pass, pick the TOP grid and click **Create / Fit TOP**.

Probe output is saved to the 3ds Max user scripts folder as `AOPR_CoronaProbe.txt`.
Test output is saved as `AOPR_TestLog.txt`.

## Required rig behavior

- Corona cameras: FRONT, BACK, LEFT, RIGHT, TOP
- independent grid object per view
- fit horizontal width exactly to the picked grid object's camera-space bounding box
- green camera wire color
- top duplicates:
  - `1. clip hanging structure`
  - `2. clipp ceiling 1`
  - `3. clipp ceiling 2`
  - `4. clip ceiling 3`
