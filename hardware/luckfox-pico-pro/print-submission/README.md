# 3D Print Submission — LuckFox Pico Pro enclosure (first article)

One (1) full enclosure set for the **LuckFox Pico Pro/Max (RV1106) + SC3336**
Cyclops camera "eye", submitted to the the print service 3D printing
service for **fit / manufacturing verification** before we commit to three
production sets.

* Service: <https://example.invalid/print-service>
* Format: **STL, millimetres** — matches their requirement.
* Material requested: **ABS** (their only filament).
* All parts fit comfortably inside their **229 × 229 × 229 mm** build volume
  (largest single part here is the canopy at 124 × 64 × 12 mm).

## Parts in this submission (1 of each)

| File | Part | Bounding box (mm) | Est. ABS mass | Notes |
|---|---|---|---|---|
| `luckfox_enclosure_base.stl`      | Base tub        | 110.0 × 58.0 × 9.5   | 17.3 g | Main body, board mounts |
| `luckfox_enclosure_cover.stl`     | Cover / fascia  | 110.0 × 58.0 × 24.5  | 25.7 g | Recessed optical window, RJ45 side |
| `luckfox_enclosure_hood.stl`      | Top canopy      | 124.0 × 64.0 × 12.0  | 24.9 g | Weather-shedding hood; needs supports |
| `luckfox_enclosure_gasket.stl`    | Perimeter gasket| 109.6 × 57.6 × 1.4   | 0.6 g  | **Intended TPU** — ABS for fit-check only |
| `luckfox_enclosure_thermal_seal.stl` | Thermal seal | 25.0 × 27.0 × 0.8    | 0.2 g  | **Intended TPU** — ABS for fit-check only |

**Total material ≈ 68.7 g.**

Estimated cost at **$0.15/g incl. supports** → ~**$10.30** material, plus
supports (the hood and cover have overhangs) → roughly **$11–14**.
(The $1.50 minimum does not apply.) Supports are included in their pricing.

## Not included (cannot be made by the print service / not plastic)

* **`thermal_insert`** — designed as a **machined aluminium** part (metal).
  It is not a 3D print; it will be produced/blanked separately.
* **`chimney` / `nose`** — **obsolete** parts from the pre-redesign revision
  and intentionally omitted.

## Material note

The design was drawn for **PETG/ASA** shells and **TPU** seals. the print service prints
**ABS only**, which is an acceptable substitute **for this first article**
(fit, printability and assembly). Caveats:

* ABS is more UV/weather-sensitive than ASA and warps more — fine for a
  bench/fit prototype, not the final outdoor finish.
* The two seals printed in ABS are **rigid** and will **not** seal; they are
  included only to check groove/perimeter fit. Functional seals need TPU
  (print elsewhere) or a silicone / gasket-sheet substitute.

## Print notes for the operator

* Units are millimetres (no scaling required).
* Single colour is fine; the parts are separate jobs.
* Suggested orientations: base and cover open-side up; hood as-modelled
  (dome up) with supports under the front eaves; seals flat.
* All five meshes were verified **manifold with 0 degenerate faces**.

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
