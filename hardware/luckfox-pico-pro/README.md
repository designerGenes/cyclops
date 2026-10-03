# LuckFox Pico Pro — Weatherproof Enclosure

A parametric, Blender-built enclosure for the **LuckFox Pico Pro (RV1106)** +
**SC3336** camera, designed for outdoor security-camera duty. It is a sibling
to `firmware/luckfox-pico-pro/` and does **not** alter any deployed board,
firmware, or camera.

## Design goals

* **Minimalist** — a slim 77.2 × 26.2 mm body (≈ 47 mm to the chimney roof
  apex) with no moving parts, a single split seam, and no fans.
* **Passive heat venting** — a "chimney" sits directly over the RV1106 SoC.
  Cool air is drawn in through floor-level downward vents, rises through the
  3.5 mm stand-off plenum under the PCB, over the components, and out the top.
* **Weatherproof** — every opening is angled or shielded so gravity keeps
  rain and driven spray out:
  * intake vents open **straight down** through the floor (raised on feet),
  * chimney exhaust slots are **behind a rain-cap skirt** that forces the air
    path to turn downward before it reaches open air, with a pitched roof,
  * base/cover halves seal on a captured TPU gasket,
  * RJ45 port and M12 lens both sit under protective hoods.

## Parts

| Part | Purpose |
| --- | --- |
| `Base_Tub` | floor, PCB standoffs, down-facing intakes, drain weeps, RJ45 (lower), gasket groove, feet |
| `Top_Cover` | upper shell, chimney aperture, RJ45 (upper), gasket groove |
| `Chimney_Stack` | exhaust stack + rain cap + skirt + pitched roof |
| `Camera_Nose` | SC3336 housing, M12 lens port, lens hood, FFC pass-through |
| `Gasket_Seal` | TPU o-ring captured between the two halves |
| `*_Proxy` | non-exported reference solids (PCB, RJ45, heatsink, lens, sensor) |

## Layout

```
hardware/luckfox-pico-pro/
├── enclosure_geometry.py   # pure-Python parametric model (no Blender import)
├── generate_case.py        # Blender driver: builds geometry, STLs, renders
├── verify_stls.py          # headless STL manifold + feature probe checks
├── generate.sh             # one-shot regenerate + verify
├── tests/
│   └── test_enclosure_geometry.py
└── out/                    # generated artifacts (committed deliverables)
    ├── luckfox_pico_pro_enclosure.blend
    ├── stl/luckfox_enclosure_*.stl
    └── preview/luckfox_enclosure_*.png
```

## Open in Blender

```bash
blender /Users/admin/DEV/01_active_projects/cyclops/hardware/luckfox-pico-pro/out/luckfox_pico_pro_enclosure.blend
```

The scene contains two collections: `Luckfox_Enclosure` (the five printable
parts, one manifold mesh each) and `Reference_Proxies` (PCB / RJ45 / heatsink
/ lens / sensor shown for fit-checking). Dimensions are in millimetres
(`scale_length = 0.001` places one Blender unit at 1 mm).

## Regenerate

```bash
cd /Users/admin/DEV/01_active_projects/cyclops
bash hardware/luckfox-pico-pro/generate.sh
```

Requires a headless-capable Blender (v4+/v5) on `PATH` (`BLENDER=/path/to/blender ./generate.sh` to override).

## Verify

```bash
uv run pytest /Users/admin/DEV/01_active_projects/cyclops/hardware/luckfox-pico-pro/tests
```

The geometry tests assert PCB/heatsink/lens/FFC clearance, that the exhaust
slots are shielded by the cap skirt, that intakes face down beneath the PCB
plenum, and that the footprint stays within the minimal bounds.

## Printing notes (for the future build-out)

* **Material:** PETG or ASA (outdoor UV). The gasket prints in TPU.
* **Orientation:** base tub / cover print flat; chimney prints roof-side down
  (the skirt is a tall hollow column — minimum 4 perimeters, no supports);
  the nose prints lens-port down.
* **Seam:** press the printed TPU gasket into either groove, then fasten the
  two halves with M2.5 self-tapping screws into the corner bosses.
* **Heatsink:** bond a 14 × 14 mm aluminium finned heatsink to the RV1106
  package so it sits under the 16 × 16 mm chimney aperture.
* **Intakes & weeps:** press 20-mesh stainless screen into the floor vents;
  the two front weeps remain open as condensation drains.
* **Ports:** fit an RJ45 weatherproof cable gland over the rear port and an
  M12 barrel O-ring at the lens.

## Refinement TODOs

These are deliberate deferrals — modelled enough to visualise, not yet final:

* wall-mount bracket (stand-off plate + screw bosses) — the rear face has the
  RJ45 port, so a mount plate is planned rather than ear holes,
* countersunk fastener holes through the nose into the body bosses,
* drip-edge lip under the rain-cap eave.