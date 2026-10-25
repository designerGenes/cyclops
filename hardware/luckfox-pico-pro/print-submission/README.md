# 3D Print Submission — LuckFox Pico Pro enclosure (first article)

One full enclosure set for the **LuckFox Pico Pro/Max (RV1106) + SC3336**
Cyclops camera eye, prepared for fit and manufacturing verification before
printing additional production sets.

* Format: **STL, millimetres**.
* Material requested for the first article: **ABS**.
* All parts fit within a **229 × 229 × 229 mm** build volume. The largest
  single part is the canopy at 124 × 64 × 12 mm.

## Parts in this submission (1 of each)

| File | Part | Bounding box (mm) | Est. ABS mass | Notes |
|---|---|---|---|---|
| `luckfox_enclosure_base.stl` | Base tub | 110.0 × 58.0 × 9.5 | 17.3 g | Main body, board mounts |
| `luckfox_enclosure_cover.stl` | Cover / fascia | 110.0 × 58.0 × 24.5 | 25.7 g | Recessed optical window, RJ45 side |
| `luckfox_enclosure_hood.stl` | Top canopy | 124.0 × 64.0 × 12.0 | 24.9 g | Weather-shedding hood; needs supports |
| `luckfox_enclosure_gasket.stl` | Perimeter gasket | 109.6 × 57.6 × 1.4 | 0.6 g | **Intended TPU** — ABS for fit-check only |
| `luckfox_enclosure_thermal_seal.stl` | Thermal seal | 25.0 × 27.0 × 0.8 | 0.2 g | **Intended TPU** — ABS for fit-check only |

**Total material ≈ 68.7 g.**

At an example rate of **$0.15/g including supports**, the estimated material
cost is approximately **$10.30**, or **$11–14** after allowing for the hood and
cover overhangs. Confirm current pricing and support settings with the chosen
print provider.

## Not included

* **`thermal_insert`** — designed as a **machined aluminium** part, not a
  plastic print. It will be produced separately.
* **`chimney` / `nose`** — obsolete parts from the pre-redesign revision and
  intentionally omitted.

## Material note

The design was drawn for **PETG/ASA** shells and **TPU** seals. ABS is an
acceptable substitute **for this first article** (fit, printability, and
assembly), with caveats:

* ABS is more UV/weather-sensitive than ASA and warps more. It is suitable for
  a bench/fit prototype, not the final outdoor finish.
* The two seals printed in ABS are **rigid** and will **not** seal. They are
  included only to check groove/perimeter fit. Functional seals need TPU or a
  silicone/gasket-sheet substitute.

## Print notes for the operator

* Units are millimetres; no scaling is required.
* Single colour is fine; the parts are separate jobs.
* Suggested orientations: base and cover open-side up; hood as modelled
  (dome up) with supports under the front eaves; seals flat.
* All five meshes were verified **manifold with zero degenerate faces**.

## Integrity (SHA-256)

```
e1050313c6d0a52ea58f9970da848f9b6f96f2d075d7528aae191b2bb7049755  luckfox_enclosure_base.stl
ad4d5e71b61d0356fabb90d396fac2ba4d9ea0bf7802dec7a4c5dd38b839583f  luckfox_enclosure_cover.stl
866fb9976e60b6809493ba97fce48c3841fa8a296eedce5bfa0204186f41e112  luckfox_enclosure_gasket.stl
8f516f0d0da37caf5d3ec1787905d22963a9a70c5b6d8821a2442cf521c6248d  luckfox_enclosure_hood.stl
40a9453e8cf53ccb5d234a7d7bb573ee3f8bbdb76c9b42e885ec60d63ffb1b50  luckfox_enclosure_thermal_seal.stl
```

## Sourcing

Regenerate from source with Blender:

```sh
bash hardware/luckfox-pico-pro/generate.sh
```

Design source of truth: `hardware/luckfox-pico-pro/` (see its `README.md`).
