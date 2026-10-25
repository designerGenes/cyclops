# LuckFox Pico Pro/Max "fat pill" wall-camera enclosure — v1.1

## Changes since v1

- **Lens port is size-tolerant.** v1 had a 14.4 mm bore sized to an unverified 14.0 mm barrel.
  The Luckfox camera pages and the interface PDF do not state the barrel diameter. v1.1 uses a
  Ø17.0 bore with a 0.6 mm land and a 45° cone to Ø20.0 at the face. Any barrel up to 16.6 mm
  passes. The seal is an O-ring rolled onto the barrel that seats in the cone, so the barrel
  size only decides which O-ring to buy, not what gets printed. The inner recess is Ø19 x 0.5 mm.
- **FOV gate uses the published optics.** Luckfox lists the SC3336 at 98.3° diagonal, 84°
  horizontal and 44° vertical (wiki.luckfox.com/SC3336-3MP-Camera). The gate now ray-casts an
  equidistant lens model calibrated to the 98.3° diagonal, plus 10%. It passes with 0 rays
  blocked.
- **Visor length re-checked.** A sweep showed that extending the visor (crown overhang 30 mm or
  more) clips the image corners, because the hood wraps down the sides. The v1 visor (22.4 mm
  crown overhang) is at the practical limit and is unchanged.
- **Only `pill_cover.stl` changed geometrically.** The other four STLs are byte-identical to v1.
  This directory is a complete, self-contained set.

Weatherproof, wall-standoff enclosure for a Luckfox Pico Pro/Max (RV1106, 72 x 21 mm) with an
SC3336 3MP CSI camera (A or B version). Five printed parts, all STL in millimetres, all
pre-rotated to their print orientation and sitting on Z=0. No part needs supports. Every part
fits the the print service's 229 x 229 x 229 mm limit.

Source of truth: `src/luckfox_pill_enclosure.py` (parametric, manifold3d, `__version__ = "1.1"`).
Gate: `src/verify_enclosure.py` (must print `RESULT: PASS`).

## Parts

| STL | Print size (mm) | Orientation | Solid mass (PETG) |
|---|---|---|---|
| `pill_body.stl` | 62.8 x 127.9 x 62.0 | back face down, hood points up | <= 81 g |
| `pill_cover.stl` | 56.0 x 124.5 x 14.4 | front face down | <= 36 g |
| `wall_bracket.stl` | 64.8 x 118.4 x 28.0 | wall face down | <= 33 g |
| `board_sled.stl` | 40.4 x 81.3 x 6.6 | flat | <= 5 g |
| `camera_clamp.stl` | 39.0 x 19.7 x 2.4 | flat | <= 1 g |

The total is at most 157 g, which is at most about $23.50 at the library's $0.15/g. That is a solid
upper bound; normal perimeter and infill settings come in lower.

## What was wrong with v0 (`luckfox_enclosure_{base,cover,hood,gasket,thermal_seal}.stl`)

- Base and cover met in a flat butt joint at z=9.5. There were no screws, clips, lip or overlap,
  so nothing held them together.
- The gasket groove left 0.2 mm side walls, which cannot be printed. The gasket was a
  rectangle sitting in a V-ish groove and stood only 0.2 mm proud. It also bridged across an
  open port.
- The hood's four pins went about 0.9 mm into 1 mm sockets, so nothing retained them.
- The hood plate sat 8 mm directly in front of the camera's 20 mm square aperture, which blocked
  the field of view completely.
- There were no board standoffs, no camera mount and no wall-mount features. Two rectangular
  ports were left open with no seals.
- The "thermal_seal" was a 0.8 mm flat frame around the lens hole with nothing compressing it.

## Geometry (world frame used in the source)

The X axis runs right, Y runs forward (away from the wall) and Z runs up. The body's back face
is at Y=0. The bottom arc centre is at Z=0 and the top arc centre at Z=72.

- **Pill:** 56 mm wide (R=28 stadium) by 124.5 mm tall (Z -24.5 to 100). Depth is 39.6 mm:
  the body runs Y 0 to 32 and the cover Y 32 to 39.6.
  - The back edge has a 4 mm teardrop round and the front edge a 6 mm teardrop round. Both are
    printable on the bed.
  - The bottom is flattened at Z=-24.5 to seat the cable gland.
- **Hood (integral with body):**
  - Shape: an arc shell over the top semicircle, inner R 28.4 and outer R 31.4 to 30.8.
  - Water shedding: it slopes about 1° forward and has a drip kerf under the edge.
  - Reach: the visor reaches Y=62 at the crown (22.4 mm past the front face) and is swept back
    to Y=51 at the sides.
  - Clearances: it sits 0.4 mm above the cover so the cover slides in underneath, and it shields
    the top parting seam.
- **Camera:**
  - Position: lens axis at Z=75, which is 25.4 mm below the hood underside.
  - PCB location: the PCB front face rests on two cover ledges at Y=26.6.
  - Lens protrusion: the lens tip (Y=42.6) protrudes 3.0 mm past the front face.
  - Lens port: a Ø17.0 bore (accepts barrels up to 16.6 mm) with a 45° O-ring seat that flares
    to Ø20.0 at the face.
  - Recess: the inner face has a Ø19, 0.5 mm-deep recess for the lens holder.
- **Field of view:** the hood is ray-cast clear for the published FOV (98.3° D / 84° H / 44° V)
  plus 10%, from a 4 mm-radius lens ring.
- **Board:**
  - Mounting: the Pico Pro/Max sits in a slide-in sled on 4 bosses, with a 4 mm air gap behind
    it, PCB at Y 10.7 to 12.3 and Z 14 to 86.
  - Orientation: the RJ45 end points down at the gland and the USB-C end points up.
  - Retention: the bottom two sled screw heads overlap the PCB end corners and trap it. Top stops
    clear the USB-C plug.
- **Seal:**
  - Cord and groove: 2.0 mm nitrile O-ring cord in a 2.6 x 1.5 mm groove in a 5 mm rim band on
    the body. That gives 25% squeeze and 81% gland fill. Cut length is 301 mm plus 5 mm.
  - Location: the cover's back land compresses the cord, and a locating tongue (0.35 mm
    clearance) keys the cover into the body opening.
- **Cover fastening:** 4 x M3 countersunk screws at (±21, 0) and (±21, 65) go into body bosses
  (2.6 mm pilot holes).
- **Venting:**
  - 118 louvres (5.5 x 1.4 mm) run through the 3.2 mm back wall at 45°. The outer opening is
    lower than the inner one, so water would have to climb 3.2 mm to get in.
  - Inlets sit low and outlets high, which drives a chimney flow through the board's own air gap.
  - All openings face the wall, inside the sheltered standoff gap.
- **Wall bracket:**
  - Body attachment: the wall plate stands the body off by 28 mm (24 mm air gap) on 4 columns at
    (±16, 26) and (±16, 50). M3x16 screws go from inside the body into the column pilots.
  - Wall fixing: 3 countersunk wall holes for #8 / 4 mm screws sit at Z -6, 38 and 88. They are
    hidden behind the body once it is mounted.
  - Rain cap: the cap continues the hood back to the wall over ±50° of the crown, so rain stays
    out of the gap. Its flanks are open so warm air leaves the gap sideways instead of pooling.
- **Cable:** M16x1.5 nylon gland in a teardrop hole on the bottom flat at Y=14. A 2.5 mm weep
  hole sits beside it.

## Hardware (stainless where it is exposed)

- **Cover:** 4 x M3x16 countersunk (DIN 965 or ISO 10642), plus a dab of neutral-cure silicone
  in each countersink.
- **Body to bracket:** 4 x M3x16 pan/button head with nylon or rubber sealing washers, driven
  from inside the body.
- **Sled:** 4 x M3x8 pan head. The bottom pair also traps the board.
- **Camera clamp:** 2 x M3x10 pan head.
- **Cable gland:** 1 x M16x1.5 nylon gland, IP68, 4 to 8 mm clamp range (one Cat5e). Use a
  2-hole insert if USB power also enters.
- **Seal:** 2.0 mm nitrile (Buna-N) O-ring cord, about 31 cm, with the ends butt-joined with
  CA glue.
- **Lens seal:** a nitrile O-ring with ID about 0.5 mm smaller than the barrel OD, rolled onto
  the barrel and seated in the 45° cone.
  - Barrel 13.5 to 16.6 mm: use 2 mm cross-section.
  - Barrel 12 to 13.5 mm: use 3 mm cross-section, so it still reaches the cone.
  - Alternative: a thin bead of neutral-cure silicone after focusing. This also locks the focus.
- **Wall:** 3 x #8 / 4 mm wall screws with anchors suited to the wall.
- **Optional:** stainless insect mesh glued over the louvres on the inside.

M3 machine screws thread directly into the 2.6 mm pilots in PETG or PLA.

## Assembly order

1. Screw the bracket to the wall with the rain cap at the top, and level it.
2. Hold the body against the four columns. Drive the 4 x M3x16 with sealing washers from inside
   the body.
3. Fit the M16 gland into the bottom flat and pass the Ethernet cable through.
4. Slide the Pico into the sled from the sled's open bottom end until it meets the top stops.
   Screw the sled in with 4 x M3x8.
5. Connect Ethernet and, if used, the right-angle USB-C plug. Leave a drip loop on the cable
   below the gland.
6. Focus the camera on the bench first. Seat it on the cover ledges with the lens through the
   port and clamp it with 2 x M3x10.
7. Connect the camera FPC to the board. The metal contacts face the RV1106 side of the board.
8. Glue the O-ring cord into a loop and press it into the body groove.
9. Close the cover with 4 x M3x16 countersunk screws, tightening them in a cross pattern until
   the cover land seats on the rim.
10. Seal the lens barrel: push the barrel O-ring forward until it seats in the cone, or apply a
    silicone bead.

## Printing (library or otherwise)

- **Material:** PETG or ASA strongly preferred. PLA softens around 55 to 60 °C, and a sunny
  sun-exposed wall can exceed that inside a dark part. If only PLA is offered, use white or light grey
  and accept some creep risk.
- **Settings:** 0.2 mm layers, at least 4 perimeters, 20 to 25% gyroid infill, 5 top and bottom
  layers, no supports.
- **Brim:** a 5 mm brim on `pill_body` helps, because the hood stands 62 mm tall.
- **Sled overhang:** the sled's rail lips are 1.3 mm horizontal ledges. They print fine on
  current printers; if any droop, clean them with a hobby knife.
- **the print service:** you need a library card. Submit by emailing
  print@example.invalid with the STL files in millimetres. The size limit is
  229 x 229 x 229 mm, the charge is $0.15/g including supports with a $1.50 minimum, and you
  pay in person.

## Assumptions to confirm (each can be fixed with a generator flag, then re-verify)

1. **Lens barrel OD** is still unpublished, but no longer blocks printing. The port accepts up
   to 16.6 mm. Measure it only to choose the barrel O-ring. If the barrel is larger than
   16.6 mm, regenerate with `--lens-d <mm>` (the largest OD the port must accept).
2. **Camera module:**
   - The PCB is 25 x 24 mm and the lens tip is about 16 mm in front of the PCB face.
   - The lens is centred within ±1 mm. Side clearance at the posts is 1.0 mm, and the lens
     itself locates the camera.
   - The clamp presses on the back-side strip at |x| 9.5 to 12.5 mm, so that strip must be free
     of components.
3. **Board:**
   - The Pico Pro/Max has the RJ45 at one end and USB-C at the other.
   - There are no pin headers. The rails grip the bare long edges.
   - The RJ45 jack is no taller than 13.5 mm.
   - Any USB-C plug is a right-angle type no taller than 7.5 mm.
4. **Gland:** M16x1.5. An M20 gland's nut does not fit at the default body depth, and verify
   rejects `--gland-d 20.5`.
5. **Field of view:** checked against the published 98.3° D / 84° H / 44° V plus 10%, with
   0 rays blocked. At plus 25% (D 123°), 32 of 13,500 rays graze the visor corners. That
   matters only if the real lens is far wider than its spec.
6. **Weather rating:** the enclosure is rain-resistant (louvred, sheltered, capped), not
   submersible. Do not pressure-wash the back.
7. **Tilt:** none. The camera looks level. A downward pitch would be a bracket change.

## Regenerate / verify

```
python3 -m venv .venv && .venv/bin/pip install manifold3d numpy trimesh
.venv/bin/python src/luckfox_pill_enclosure.py --out print            # binary STLs
.venv/bin/python src/luckfox_pill_enclosure.py --out stl --ascii      # ASCII STLs
.venv/bin/python src/luckfox_pill_enclosure.py --out preview --assembly
cd src && ../.venv/bin/python verify_enclosure.py                    # must end RESULT: PASS
```

Flags available on both scripts: `--lens-d` (largest barrel OD accepted, default 16.6), `--gland-d`,
`--standoff`, `--no-vents`.
Tested with Python 3.12, manifold3d 3.5.4, numpy 2.4, trimesh 5.1.

## Verification log (default parameters, v1.1)

```
generator version 1.1
== 1. mesh validity (print orientation, after vertex welding)
  OK  pill_body       62.8 x  127.9 x  62.0 mm  watertight=True bodies=1 tris=11776
      STL file round-trip: clean
  OK  pill_cover      56.0 x  124.5 x  14.4 mm  watertight=True bodies=1 tris=8950
      STL file round-trip: clean
  OK  camera_clamp    39.0 x   19.7 x   2.4 mm  watertight=True bodies=1 tris=274
      STL file round-trip: clean
  OK  board_sled      40.4 x   81.3 x   6.6 mm  watertight=True bodies=1 tris=908
      STL file round-trip: clean
  OK  wall_bracket    64.8 x  118.4 x  28.0 mm  watertight=True bodies=1 tris=3012
      STL file round-trip: clean
== 2. part-to-part interference in assembly
  OK  no overlaps
== 3. hardware stand-ins vs printed parts
  OK  18 stand-ins clear of all printed parts
  info bottom sled screw head reaches z=14.18 over PCB end z=14.00 -> traps board
  info bottom sled screw head reaches z=14.18 over PCB end z=14.00 -> traps board
== 4. camera field of view (Luckfox SC3336 spec: 98.3 D / 84 H / 44 V deg, F2.0, 3.95 mm)
  OK  spec FOV +10% margin (HARD)    0 / 13500 rays blocked (half-angles H 47 / V 27 / D 54 deg)
  info spec FOV +25% stress (info)    32 / 13500 rays blocked (half-angles H 54 / V 30 / D 61 deg)
== 5. print-orientation overhang audit (no supports intended)
  pill_body     >50deg overhang   63.9 mm2, near-horizontal    3.6 mm2
  pill_cover    >50deg overhang    0.2 mm2, near-horizontal    0.2 mm2
  camera_clamp  >50deg overhang    0.0 mm2, near-horizontal    0.0 mm2
  board_sled    >50deg overhang  185.6 mm2, near-horizontal  185.6 mm2
  wall_bracket  >50deg overhang    0.0 mm2, near-horizontal    0.0 mm2
== 6. mass / the print service cost ($0.15/g, solid upper bound, PLA 1.24 / PETG 1.27 g/cc)
  pill_body      64.1 cm3  <=  81.4 g  <= $12.22
  pill_cover     28.6 cm3  <=  36.3 g  <= $ 5.45
  camera_clamp    0.8 cm3  <=   1.0 g  <= $ 0.15
  board_sled      4.0 cm3  <=   5.1 g  <= $ 0.77
  wall_bracket   25.9 cm3  <=  32.9 g  <= $ 4.94
  total <= 157 g  <= $23.52
== 7. seal
  2.0 mm cord, groove 2.6 x 1.5 mm: squeeze 25%, gland fill 81%, cut length 301 mm (+5 mm)
  vents: 118 louvres

RESULT: PASS
```
