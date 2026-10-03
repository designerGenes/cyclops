# LuckFox Pico Pro — Weatherproof Enclosure

A parametric, Blender-built enclosure for the **LuckFox Pico Pro (RV1106)** +
**SC3336** camera, designed for outdoor security-camera duty. It is a sibling
to `firmware/luckfox-pico-pro/` and does **not** alter any deployed board,
firmware, or camera.

## Design goals

* **Symmetric & rounded (v2)** — the body is a *capsule* (stadium plan closed
  by two full semicircular ends, 106 × 30 mm), the cooling stack is a **round
  chimney** with a conical rain cap, and the camera is a **cylindrical lens
  barrel** centred on the front dome. Long hard edges are softened with a
  baked bevel so nothing reads as a square-cornered "plug".
* **Minimalist** — a single split seam, no fans, no moving parts; every part
  prints without supports.
* **Passive heat venting** — the round chimney sits directly over the RV1106
  SoC.  Cool air enters through downward-facing floor vents, rises through the
  3.5 mm stand-off plenum under the PCB, over the components, and out the top.
* **Weatherproof** — every opening is angled or shielded so gravity keeps
  rain and driven spray out:
  * intake vents open **straight down** through the floor (raised on feet),
  * chimney exhaust slots sit **behind a skirt that drops below them**, forcing
    the air path to turn downward before it reaches open air, under a pitched
    roof,
  * base/cover halves seal on a captured TPU gasket channel,
  * RJ45 port and M12 lens both sit under protective hoods.

## Parts

| Part | Purpose |
| --- | --- |
| `Base_Tub` | floor, PCB standoffs, down-facing intakes, drain weeps, RJ45 (lower), gasket channel, feet |
| `Top_Cover` | upper shell, chimney aperture, RJ45 (upper), flat rim that compresses the gasket |
| `Chimney_Stack` | round exhaust stack + conical rain cap + skirt |
| `Camera_Nose` | Ø40 lens barrel, M12 port, Ø32 lens shade tube, Ø30 rear FFC opening |
| `Gasket_Seal` | TPU cord captured in the base channel (2.4 mm deep) |
| `*_Proxy` | non-exported reference solids (PCB, RJ45, heatsink, lens, sensor) |

## Key dimensions (mm)

* body: 106.0 long × 30.0 wide, semicircular ends (r = 15), ~24 tall
* interior: 26 wide, PCB on 3.5 mm standoffs, 21.9 mm headroom over the RJ45 cage
* chimney: Ø24 stack over the SoC (Ø20 column clears the full 14 × 14 heatsink),
  Ø40 rain cap, roof apex z ≈ 48
* nose: Ø40 barrel × 20 long, lens at the body mid-height, Ø30 cable aperture
* seam: base/cover split at z = 13 with a captured TPU gasket

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

Two collections: `Luckfox_Enclosure` (the five printable parts) and
`Reference_Proxies` (PCB / RJ45 / heatsink / lens / sensor for fit-checking).
Dimensions are in millimetres (`scale_length = 0.001`).

## Regenerate / verify

```bash
cd /Users/admin/DEV/01_active_projects/cyclops
bash hardware/luckfox-pico-pro/generate.sh
uv run pytest hardware/luckfox-pico-pro/tests
```

`generate.sh` rebuilds the Blender project, exports the STLs, and re-runs
`verify_stls.py`, which proof-checks every part for watertightness
(0 non-manifold edges / 0 degenerate faces) and ray-casts the intakes, chimney
aperture, RJ45 notch, barrel opening, and exhaust slots to confirm they are
genuinely open.  The geometry tests assert the thermal/weather invariants
(skirt-below-exhaust, downward intakes, full heatsink coverage) plus the
rounding/symmetry parameters.

## Printing notes (for the future build-out)

* **Material:** PETG or ASA (outdoor UV). The gasket prints in TPU.
* **Orientation:** base tub prints flat (feet down); cover prints flat
  (rim down); chimney prints roof-side down (tall hollow column, ≥ 4
  perimeters, no supports); the nose prints lens-port down.
* **Seam:** press the TPU cord into the base channel; the cover's flat rim
  compresses it. Secure the two halves with M2.5 self-tapping screws into the
  corner bosses at the straight section.
* **Heatsink:** bond a 14 × 14 mm aluminium finned heatsink to the RV1106
  package under the Ø20 chimney column.
* **Intakes & weeps:** press 20-mesh stainless screen into the floor vents;
  leave the two front weeps open as condensation drains.
* **Ports:** fit an RJ45 weatherproof gland over the rear port and an M12
  barrel O-ring at the lens; the Ø32 shade tube doubles as a sun/rain hood.
* **Mounting posture:** intended wall/soffit mounted with the chimney up and
  the lens barrel pointing out; the Ø40 barrel is deliberately prominent
  (it must clear the 25 × 24 mm sensor module). The four feet support the
  underside for any temporary benchtop placement.

## Refinement TODOs

* wall-mount bracket (stand-off plate + screw bosses) — the rear face carries
  the RJ45 port, so a plate is planned rather than ear holes,
* countersunk fastener holes through the nose into the body bosses,
* drip lip under the rain-cap eave, and a chamfer where the barrel meets the
  front dome for a smoother blend.