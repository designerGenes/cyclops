# LuckFox Pico Pro — Top-Hood Weather Camera

A parametric Blender enclosure for the **LuckFox Pico Pro (RV1106)** and
**SC3336** camera. This remains an isolated hardware-design project: it does
not alter deployed Cyclops cameras or firmware.

## Design direction

This revision replaces the separate round chimney and projecting camera
barrel with a broad, contained camera body. It borrows the *weather-shedding
method* of a top-hooded outdoor camera—recessed optics, a broad raised canopy,
and water paths that lead away from the window—without copying a specific
product's dimensions or shell geometry.

* **Broad, rounded housing:** 110 × 58 × 34 mm with rounded-rectangle corners.
  The SC3336 board and all camera-facing hardware sit within the main body
  envelope.
* **Recessed optical panel:** a flush-looking 20 × 18 mm dark window sits
  1.2 mm behind the front fascia; the M12 lens is behind the panel, not in an
  external barrel. Two shallow channels flank the window to route water down
  the front.
* **Top canopy:** a separate 124 × 64 mm rounded canopy stands 8 mm above the
  case on four supports. It overhangs the front face by 10 mm and has a slight
  forward pitch. Its eaves protect the window and provide a sheltered ambient
  air path over the thermal fins.
* **Thermal path:** a gasketed aluminum insert passes through a 20 × 20 mm
  roof port over the RV1106. A metal stem bridges the SoC heatsink to a
  low-profile, six-fin heat-spreader under the canopy. The electronics cavity
  remains sealed; outside airflow is around the insert, not through the
  electronics.
* **Service seam:** the base and cover compress a TPU perimeter gasket. A
  second small TPU seal sits under the thermal insert flange.

This is a CAD concept, not a validated IP-rated enclosure. The actual optical
window material/seal, RJ45 gland, canopy retention, thermal interface,
condensation behavior, and operating temperatures still need to be verified
on the selected hardware before outdoor deployment.

## Assembly parts

| Part | Material / purpose |
| --- | --- |
| `base` | PETG/ASA lower tub, PCB standoffs, lower optical recess, lower RJ45 opening, perimeter gasket groove |
| `cover` | PETG/ASA upper shell, recessed front window pocket, thermal port, upper RJ45 opening, canopy sockets |
| `hood` | PETG/ASA canopy plate and four supports; overhang shades the optics and shelters the fins |
| `gasket` | TPU main shell seal |
| `thermal_seal` | TPU seal under the heat-spreader flange |
| `thermal_insert` | aluminum concept part: roof flange, bridge stem, and six low fins |
| `Optical_Window` | non-exported smoked-polycarbonate/glass placeholder, recessed behind the fascia |
| `Reference_Proxies` | PCB, RJ45, SC3336, M12 lens, and RV1106 heatsink fit references (viewport only) |

The *lens panel* and *thermal insert* are separate hardware items; only the
shell, hood, and TPU seals are intended for plastic printing. The metal insert
and canopy attachment need mechanical detailing before a production print.

## Dimensions (nominal, mm)

* Main body: **110 × 58 × 34**, rounded corners (R9).
* Internal envelope: **106 × 54**; 2 mm walls and 3.5 mm PCB standoffs.
* Window: **20 × 17**, with the M12 lens recessed behind it.
* Canopy: **124 × 64**, 3 mm roof, 8 mm air gap, 10 mm front overhang.
* Roof thermal port: **20 × 20**; **28 × 26** flange; six 3 mm fins with
  approximately 3.9 mm clearance to the canopy underside.
* Case seam: z = 9.5 mm, below the recessed optical panel; a 1.6 mm TPU bead
  is captured in the base groove.

All dimensions are nominal CAD values. Confirm the board, jack, camera module,
FFC bend radius, thermal insert, and fastener sizes against the actual inbound
board revision before manufacturing.

## Project files

```
hardware/luckfox-pico-pro/
├── enclosure_geometry.py     # Blender-independent parametric model
├── generate_case.py          # Blender scene, STLs, and image previews
├── verify_stls.py             # manifold + opening/clearance feature probes
├── generate.sh                # regenerate and verify the deliverables
├── tests/test_enclosure_geometry.py
└── out/
    ├── luckfox_pico_pro_enclosure.blend
    ├── stl/luckfox_enclosure_*.stl
    └── preview/luckfox_enclosure_*.png
```

## Open and refine in Blender

```bash
blender hardware/luckfox-pico-pro/out/luckfox_pico_pro_enclosure.blend
```

Collections are `Luckfox_Enclosure`, `Recessed_Optics`, and `Reference_Proxies`.
Reference proxies are visible in the viewport but hidden from preview renders;
toggle their collection to check internal fit. Units are millimetres.

## Regenerate and test

```bash
# from the repository root
bash hardware/luckfox-pico-pro/generate.sh
uv run pytest hardware/luckfox-pico-pro/tests
```

`generate.sh` rebuilds the `.blend`, six part STLs, and iso/front/rear/top/side
previews. The STL verifier checks every part for zero non-manifold edges and
degenerate faces; it also ray-casts the optical window, thermal port, and RJ45
openings to catch failed booleans.

## Printing the first article

`out/stl/` holds the six current exportable parts. `print-submission/` is a
ready-to-send bundle of one enclosure set (base, cover, hood and the two seals)
for fit and manufacturing verification — see `print-submission/README.md` for
the part list, material caveats and example cost. The two seals are included
for fit-checking only; the aluminum thermal insert and the obsolete
`chimney`/`nose` parts are omitted.

## Manufacturing / validation notes

* Use PETG or ASA for the shell and hood; use TPU for both seals. The thermal
  insert is modeled as aluminum, not as a printed plastic heatsink.
* The canopy is shown as a separate piece with support posts seated in shallow
  roof sockets. Add a positive retention feature (for example, sealed screws
  or a gasketed clip) before using the model outdoors; it is not yet wind-load
  tested.
* Seat a sealed, UV-stable optical window into the front recess and confirm
  that it does not vignette the SC3336 lens at the required field of view.
* Validate the thermal insert's contact pressure, thermal pad thickness,
  fin airflow, and sustained RV1106 temperature on a real board. The proxy
  geometry is not CFD or thermal test data.
* Check the actual cable gland and connector strain relief. The rear RJ45
  notch is a nominal opening, not a finished gland interface.
* The printed parts have been checked for mesh integrity, not for slicer
  support strategy, screw strength, UV life, or a specific ingress-protection
  rating.

## Follow-up refinements

* secure the hood posts with a sealed retention detail and define fastener
  dimensions,
* add a proper window retainer / perimeter seal,
* add the pole/wall mounting interface and RJ45 gland dimensions,
* fit-check thermal bridge and FFC bend using the exact production board,
* measure temperature and verify water ingress before deployment.
