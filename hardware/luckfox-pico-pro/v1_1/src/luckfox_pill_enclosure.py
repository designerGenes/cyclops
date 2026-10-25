#!/usr/bin/env python3
"""
LuckFox Pico Pro/Max "fat pill" weatherproof wall-camera enclosure -- parametric generator (v1.1).

    pip install manifold3d numpy
    python3 luckfox_pill_enclosure.py --out ./stl              # binary STLs, mm, print orientation
    python3 luckfox_pill_enclosure.py --out ./stl --ascii      # ASCII STLs
    python3 luckfox_pill_enclosure.py --lens-d 14.6 --gland-d 20.5 --out ./stl

World frame (assembly): X right, Y forward (away from wall), Z up. Body back face is Y=0,
bottom-arc centre is Z=0, top-arc centre is Z=TOP_C. Every STL is exported already rotated
into its print orientation, sitting on Z=0 -- no supports needed for any part.

Parts
  pill_body      main shell + integral Flock-style hood, back louvre vents, O-ring groove,
                 cable-gland flat, screw bosses. Prints back-face down.
  pill_cover     front face with lens port + camera ledges, countersunk screw holes,
                 locating tongue. Prints front-face down.
  camera_clamp   U-clamp that holds the camera PCB against the cover ledges.
  board_sled     carrier rails for the 72x21 mm Pico Pro/Max (board has no mounting holes).
  wall_bracket   wall plate + 4 standoff columns (sets the rear air gap) + rain cap that
                 continues the hood back to the wall. Prints wall-face down.
"""
import argparse, math, os, struct

__version__ = "1.1"   # 1.1: size-tolerant lens port + O-ring seat; FOV gate uses published SC3336 FOV
import numpy as np
from manifold3d import Manifold, CrossSection

# ------------------------------------------------------------------ parameters (mm)
P = dict(
    SEG=96,              # segments on big arcs
    R=28.0,              # outer half-width of the pill (56 mm wide)
    WALL=2.4,            # side wall
    TOP_C=72.0,          # Z of top arc centre (bottom arc centre = 0)
    Z_FLAT=-24.5,        # outer bottom flat (cable gland seat)
    Z_FLOOR=-20.0,       # inner floor
    BACK_T=3.2,          # back wall (louvres run through this)
    Y_P=32.0,            # parting plane body|cover
    Y_F=39.6,            # cover front face
    R_BACK=4.0,          # back edge round (teardrop, printable on bed)
    R_FRONT=6.0,         # front edge round (teardrop, printable on bed)
    BAND_T=5.0,          # wall thickness of the rim band that carries the O-ring groove
    BAND_H=4.5,          # height of rim band below the parting plane
    GROOVE_W=2.6, GROOVE_D=1.5, GROOVE_IN=1.2,   # for 2.0 mm O-ring cord (25% squeeze)
    PLATE_T=2.6,         # cover front plate
    TONGUE_T=1.6, TONGUE_H=3.0, TONGUE_CLR=0.35,
    PILOT=2.6, CLR=3.4, CSK_D=6.8,               # M3 self-tap pilot / clearance / csk head
    BOSS_R=3.6, COVER_SCREW_X=21.0, TOP_SCREW_DZ=-7.0,
    # camera (SC3336 3MP (A)/(B): 25x24 PCB, ~18 deep incl. lens)  -- MEASURE LENS_D
    # LENS_D = largest barrel OD the port accepts (bore = LENS_D + LENS_CLR = 17.0). The barrel is
    # sealed by an O-ring (ID ~ barrel OD - 0.5, 2 mm CS) seated in the 45deg flare, so any barrel
    # from ~12 to 16.6 mm works without reprinting. Official FOV: 98.3 D / 84 H / 44 V deg.
    CAM_W=25.0, CAM_H=24.0, CAM_PCB=1.6, CAM_LENS_LEN=16.0, LENS_D=16.6, LENS_CLR=0.4,
    LENS_PROTRUDE=3.0, CAM_DZ=3.0, CAM_SIDE_CLR=1.0,
    # board (Pico Pro/Max 72x21, RJ45 at bottom end, USB-C at top end)
    PCB_L=72.0, PCB_W=21.0, PCB_T=1.6, ZB=14.0,
    SLED_BOSS_H=4.0, SLED_T=2.0,
    # hood
    HOOD_RIN=28.4, HOOD_ROUT0=31.4, HOOD_ROUT1=30.8, HOOD_Y_TOP=62.0, HOOD_Y_SIDE=51.0,
    # gland / drain
    GLAND_D=16.2, GLAND_Y=14.0, WEEP_D=2.5,
    # bracket
    STANDOFF=28.0, WALLPLATE_T=4.0, COL_R=5.5,
    BRACKET_SCREWS=((16.0, 26.0), (16.0, 50.0)),     # mirrored in X
    WALL_HOLES=((0.0, -6.0), (0.0, 38.0), (0.0, 88.0)),
    VENTS=True,
)


def derived(p):
    d = dict(p)
    d["Y_BAND0"] = p["Y_P"] - p["BAND_H"] - (p["BAND_T"] - p["WALL"])   # shoulder start
    d["Z_BANDFLOOR"] = p["Z_FLOOR"] + (p["BAND_T"] - p["WALL"])
    d["CAM_Z"] = p["TOP_C"] + p["CAM_DZ"]
    d["Y_LT"] = p["Y_F"] + p["LENS_PROTRUDE"]                  # lens tip
    d["Y_CAMF"] = d["Y_LT"] - p["CAM_LENS_LEN"]                # camera PCB front face
    d["Y_CAMB"] = d["Y_CAMF"] - p["CAM_PCB"]                   # camera PCB back face
    d["Y_SLED0"] = p["BACK_T"] + p["SLED_BOSS_H"]              # sled underside
    d["Y_RAILF"] = d["Y_SLED0"] + p["SLED_T"] + 1.5            # PCB rests here
    d["ZT"] = p["ZB"] + p["PCB_L"]
    d["COVER_SCREWS"] = [(s * p["COVER_SCREW_X"], z) for s in (-1, 1)
                         for z in (0.0, p["TOP_C"] + p["TOP_SCREW_DZ"])]
    # bottom pair also traps the PCB end (heads overlap the board corners); top pair sits outboard
    d["SLED_SCREWS"] = [(s * 11.6, p["ZB"] - 2.5) for s in (-1, 1)] + \
                       [(s * 16.4, d["ZT"] - 6.0) for s in (-1, 1)]
    d["BRK"] = [(s * x, z) for (x, z) in p["BRACKET_SCREWS"] for s in (-1, 1)]
    return d


# ------------------------------------------------------------------ 2D helpers (world X,Z)
def circ(cx, cz, r, n=None):
    return CrossSection.circle(r, n or P["SEG"]).translate((cx, -cz))


def rect(x0, x1, z0, z1):
    return CrossSection.square((x1 - x0, z1 - z0)).translate((x0, -z1))


def stad(r, zb=0.0, zt=None, n=None):
    zt = P["TOP_C"] if zt is None else zt
    return CrossSection.batch_hull([circ(0, zb, r, n), circ(0, zt, r, n)])


def zfloor(cs, zmin):
    return cs ^ rect(-500, 500, zmin, 1000)


def prism(cs, y0, y1):
    """extrude a world-XZ section along world Y from y0 to y1"""
    return Manifold.extrude(cs, y1 - y0).translate((0, 0, y0)).rotate((-90, 0, 0))


def cyl_y(cx, cz, r, y0, y1, n=32):
    return Manifold.cylinder(y1 - y0, r, r, n).rotate((-90, 0, 0)).translate((cx, y0, cz))


def cone_y(cx, cz, r0, r1, y0, y1, n=48):
    return Manifold.cylinder(y1 - y0, r0, r1, n).rotate((-90, 0, 0)).translate((cx, y0, cz))


def cyl_z(cx, cy, r, z0, z1, n=32):
    return Manifold.cylinder(z1 - z0, r, r, n).translate((cx, cy, z0))


def box(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def halfspace_z(zmin):
    return box(-500, 500, -500, 500, zmin, 1000)


def teardrop_profile(r, h):
    """inset of a 45-degree-limited round at height h above the face that sits on the bed"""
    a = (1 - math.sqrt(0.5)) * r
    if h <= a:
        return 2 * a - h
    return r - math.sqrt(max(r * r - (r - h) ** 2, 0.0))


def rounded_stadium_solid(R, y_face, y_far, r_edge, direction, top_c, n=None, steps=14):
    """convex stadium prism with a printable teardrop round on the face at y_face.
    direction=+1: face at low Y, body extends to +Y.  direction=-1: face at high Y."""
    n = n or P["SEG"]
    pts = []
    hs = np.linspace(0, r_edge, steps)
    for h in list(hs) + [abs(y_far - y_face)]:
        inset = teardrop_profile(r_edge, h) if h <= r_edge else 0.0
        rr = R - inset
        y = y_face + direction * h
        for k in range(n):
            a = 2 * math.pi * k / n
            x, dz = rr * math.cos(a), rr * math.sin(a)
            cz = top_c if dz >= 0 else 0.0
            pts.append((x, y, cz + dz))
    return Manifold.hull_points(np.array(pts))


# ------------------------------------------------------------------ shared 2D regions
def band_inner_smooth(d):
    s = zfloor(stad(d["R"] - d["BAND_T"]), d["Z_BANDFLOOR"])
    return s.offset(-4.0).offset(4.0)          # round the floor corners (O-ring friendly)


def boss_region(d, extra=0.0):
    cs = CrossSection()
    for (x, z) in d["COVER_SCREWS"]:
        s = 1 if x > 0 else -1
        cs = cs + CrossSection.batch_hull([circ(x, z, d["BOSS_R"] + extra, 40),
                                           circ(x + s * 4.0, z, d["BOSS_R"] + extra, 40)])
    return cs


# ------------------------------------------------------------------ parts (world frame)
def make_body(d):
    R, TOP_C = d["R"], d["TOP_C"]
    outer = rounded_stadium_solid(R, 0.0, d["Y_P"], d["R_BACK"], +1, TOP_C)
    outer = outer ^ halfspace_z(d["Z_FLAT"])

    # integral hood (cone along Y so the crest sheds water forward), visor cut swept back at the sides
    hood = cone_y(0, TOP_C, d["HOOD_ROUT0"],
                  d["HOOD_ROUT0"] + (d["HOOD_ROUT1"] - d["HOOD_ROUT0"]) * 80.0 / d["HOOD_Y_TOP"],
                  0.0, 80.0, d["SEG"])
    hood = hood - cyl_y(0, TOP_C, d["HOOD_RIN"], -1, 90, d["SEG"])
    fill = cyl_y(0, TOP_C, d["HOOD_RIN"] + 0.01, 0.0, d["Y_P"], d["SEG"]) - \
        cyl_y(0, TOP_C, 27.0, -1, d["Y_P"] + 1, d["SEG"])
    hood = (hood + fill) ^ halfspace_z(TOP_C)
    k = (d["HOOD_Y_TOP"] - d["HOOD_Y_SIDE"]) / d["HOOD_ROUT1"]
    s = math.sqrt(1 + k * k)
    hood = hood.trim_by_plane((0, -1 / s, k / s), (-d["HOOD_Y_SIDE"] + k * TOP_C) / s)
    hood = hood.trim_by_plane((0, 1, 0), 0.0)
    # drip kerf under the visor edge
    kerf = (cyl_y(0, TOP_C, 29.0, 30, 90, d["SEG"]) - cyl_y(0, TOP_C, 28.0, 29, 91, d["SEG"])) ^ halfspace_z(TOP_C + 0.5)
    kerf = kerf.trim_by_plane((0, 1 / s, -k / s), (d["HOOD_Y_SIDE"] - 4.2 - k * TOP_C) / s)
    kerf = kerf.trim_by_plane((0, -1 / s, k / s), (-(d["HOOD_Y_SIDE"] - 3.0) + k * TOP_C) / s)
    hood = hood - kerf

    solid = outer + hood

    # cavity: main + 45deg shoulder + rim band opening
    cav_main_cs = zfloor(stad(R - d["WALL"]), d["Z_FLOOR"])
    band_cs = band_inner_smooth(d)
    cav = prism(cav_main_cs, d["BACK_T"], d["Y_BAND0"])
    sh0 = prism(cav_main_cs, d["Y_BAND0"] - 0.01, d["Y_BAND0"])
    sh1 = prism(band_cs, d["Y_P"] - d["BAND_H"], d["Y_P"] - d["BAND_H"] + 0.01)
    cav = cav + Manifold.batch_hull([sh0, sh1]) + prism(band_cs, d["Y_P"] - d["BAND_H"], d["Y_P"] + 1)
    body = solid - cav

    # cover screw bosses (with web to wall), clipped to the outer skin
    bosses = prism(boss_region(d), d["BACK_T"] - 0.2, d["Y_P"]) ^ outer
    body = body + bosses
    # sled bosses + bracket screw pads
    for (x, z) in d["SLED_SCREWS"]:
        body = body + cyl_y(x, z, 3.5, d["BACK_T"] - 0.2, d["Y_SLED0"], 40)
    for (x, z) in d["BRK"]:
        body = body + cyl_y(x, z, 4.5, d["BACK_T"] - 0.2, d["BACK_T"] + 1.5, 40)

    # holes
    holes = []
    for (x, z) in d["COVER_SCREWS"]:
        holes.append(cyl_y(x, z, d["PILOT"] / 2, d["Y_P"] - 15.0, d["Y_P"] + 1, 24))
    for (x, z) in d["SLED_SCREWS"]:
        holes.append(cyl_y(x, z, d["PILOT"] / 2, 1.0, d["Y_SLED0"] + 1, 24))
    for (x, z) in d["BRK"]:
        holes.append(cyl_y(x, z, d["CLR"] / 2, -1.0, d["BACK_T"] + 3.0, 24))
    # O-ring groove in the rim band face
    g_in = band_cs.offset(d["GROOVE_IN"])
    g_out = band_cs.offset(d["GROOVE_IN"] + d["GROOVE_W"])
    holes.append(prism(g_out - g_in, d["Y_P"] - d["GROOVE_D"], d["Y_P"] + 1))
    # cable gland (teardrop so the horizontal-in-print hole needs no support) + weep hole
    rg = d["GLAND_D"] / 2
    tear = CrossSection.batch_hull([CrossSection.circle(rg, 64),
                                    CrossSection.square((0.01, 0.01), True).translate((0, rg * math.sqrt(2)))])
    holes.append(Manifold.extrude(tear, 12.0).translate((0, d["GLAND_Y"], d["Z_FLAT"] - 1)))
    holes.append(cyl_z(11.0, 6.0, d["WEEP_D"] / 2, d["Z_FLAT"] - 1, d["Z_FLOOR"] + 1, 20))
    if d["VENTS"]:
        holes += vent_slots(d)
    body = body - Manifold.batch_boolean(holes, __import__("manifold3d").OpType.Add)
    return body


def vent_slots(d):
    """45-degree louvres through the back wall: outer opening (faces the wall, inside the
    sheltered air gap) is lower than the inner opening, so water would have to climb."""
    L, H, T = 5.5, 1.4, d["BACK_T"]
    keep_in = zfloor(stad(d["R"] - d["WALL"] - 2.0), d["Z_FLOOR"] + 2.0)
    obst = boss_region(d, 1.5)
    for (x, z) in d["SLED_SCREWS"]:
        obst = obst + circ(x, z, 5.0, 32)
    for (x, z) in d["BRK"]:
        obst = obst + circ(x, z, d["COL_R"] + 1.5, 32)
    slots = []
    for xc in (-19.5, -13.0, -6.5, 0.0, 6.5, 13.0, 19.5):
        for zc in np.arange(-19.0, 100.0, 3.2):
            r2 = rect(xc - L / 2, xc + L / 2, zc - H / 2, zc + H / 2 + T)
            if (r2 - keep_in).area() > 1e-6:
                continue
            if (r2 ^ obst).area() > 1e-6:
                continue
            a = prism(rect(xc - L / 2, xc + L / 2, zc - H / 2, zc + H / 2), -0.5, -0.49)
            b = prism(rect(xc - L / 2, xc + L / 2, zc - H / 2 + T + 0.5, zc + H / 2 + T + 0.5),
                      T + 0.49, T + 0.5)
            slots.append(Manifold.batch_hull([a, b]))
    return slots


def make_cover(d):
    R, TOP_C = d["R"], d["TOP_C"]
    outer = rounded_stadium_solid(R, d["Y_F"], d["Y_P"], d["R_FRONT"], -1, TOP_C)
    outer = outer ^ halfspace_z(d["Z_FLAT"])
    band_cs = band_inner_smooth(d)
    y_plate = d["Y_F"] - d["PLATE_T"]
    # locating tongue that drops into the body's rim opening.  The cover's inner wall runs
    # straight down into the tongue, so the tongue is carried by solid wall when the cover
    # prints face-down (no floating ring, no supports).
    O = band_cs - boss_region(d, 0.4)
    w = d["TONGUE_CLR"] + d["TONGUE_T"]
    pocket = prism(O.offset(-w), d["Y_P"] - d["TONGUE_H"] - 1.0, y_plate)
    cover = outer - pocket
    tongue_cs = O.offset(-d["TONGUE_CLR"]) - O.offset(-w)
    cover = cover + (prism(tongue_cs, d["Y_P"] - d["TONGUE_H"], d["Y_P"] + 0.01) - pocket)

    # camera ledge posts
    cz = d["CAM_Z"]
    xin = d["CAM_W"] / 2 + d["CAM_SIDE_CLR"]
    posts = []
    for s in (-1, 1):
        x0, x1 = sorted((s * xin, s * (xin + 6.0)))
        posts.append(box(x0, x1, d["Y_CAMB"] + 0.25, y_plate + 0.5, cz - 5, cz + 5))
        lx0, lx1 = sorted((s * (d["CAM_W"] / 2 - 1.5), s * xin))
        posts.append(box(lx0, lx1, d["Y_CAMF"], y_plate + 0.5, cz - 5, cz + 5))
    cover = cover + Manifold.batch_boolean(posts, __import__("manifold3d").OpType.Add)

    holes = []
    for (x, z) in d["COVER_SCREWS"]:
        holes.append(cyl_y(x, z, d["CLR"] / 2, d["Y_P"] - 1, d["Y_F"] + 1, 24))
        csk = d["CSK_D"] / 2
        holes.append(cone_y(x, z, d["CLR"] / 2, csk + 0.01, d["Y_F"] - (csk - d["CLR"] / 2), d["Y_F"] + 0.01, 32))
        holes.append(cyl_y(x, z, csk + 0.01, d["Y_F"], d["Y_F"] + 5, 32))
    for s in (-1, 1):
        holes.append(cyl_y(s * (xin + 3.0), cz, d["PILOT"] / 2, d["Y_CAMB"], y_plate - 0.8, 24))
    rb = (d["LENS_D"] + d["LENS_CLR"]) / 2
    holes.append(cyl_y(0, cz, rb, y_plate - 2, d["Y_F"] + 1, 64))
    holes.append(cyl_y(0, cz, max(9.5, rb + 1.0), y_plate - 3, y_plate + 0.5, 64))  # lens-holder recess
    flare = 1.5                                                               # 45deg O-ring seat / flare
    holes.append(cone_y(0, cz, rb, rb + flare + 0.01, d["Y_F"] - flare, d["Y_F"] + 0.01, 64))
    return cover - Manifold.batch_boolean(holes, __import__("manifold3d").OpType.Add)


def make_clamp(d):
    cz = d["CAM_Z"]
    y1 = d["Y_CAMB"]
    y0 = y1 - 2.4
    pcb_bot = cz - d["CAM_H"] / 2
    xin = d["CAM_W"] / 2 + d["CAM_SIDE_CLR"]
    parts = []
    for s in (-1, 1):
        a = sorted((s * 9.5, s * (xin + 6.0)))
        parts.append(box(a[0], a[1], y0, y1, cz - 5, cz + 5))
        b = sorted((s * 9.5, s * 15.0))
        parts.append(box(b[0], b[1], y0, y1, pcb_bot - 2.7, cz - 5 + 0.01))
    parts.append(box(-15.0, 15.0, y0, y1, pcb_bot - 2.7, pcb_bot - 0.3))
    clamp = Manifold.batch_boolean(parts, __import__("manifold3d").OpType.Add)
    for s in (-1, 1):
        clamp = clamp - cyl_y(s * (xin + 3.0), cz, d["CLR"] / 2, y0 - 1, y1 + 1, 24)
    return clamp


def make_sled(d):
    y0 = d["Y_SLED0"]
    y1 = y0 + d["SLED_T"]
    zb, zt = d["ZB"], d["ZT"]
    hw = d["PCB_W"] / 2
    base_cs = rect(-12.6, 12.6, zb - 6.0, zt + 3.0)
    for (x, z) in d["SLED_SCREWS"]:
        sx = 1 if x > 0 else -1
        base_cs = base_cs + CrossSection.batch_hull([circ(x, z, 3.8, 40), circ(x - sx * 4.5, z, 3.8, 40)])
    base_cs = base_cs - rect(-8.0, 8.0, zb + 4.0, zt - 4.0)                  # airflow window
    sled = prism(base_cs, y0, y1)
    yf = d["Y_RAILF"]
    parts = [sled]
    for s in (-1, 1):
        def bx(xa, xb, ya, yb, za, zb_):
            a, b = sorted((s * xa, s * xb))
            return box(a, b, ya, yb, za, zb_)
        zr = zb + 1.0          # rails start 1 mm up: bottom screw heads trap the PCB end below this
        parts.append(bx(hw - 1.0, 12.6, y1 - 0.01, yf, zr, zt + 0.4))                       # floor ledge
        parts.append(bx(hw + 0.3, 12.6, yf - 0.01, yf + d["PCB_T"] + 0.3, zr, zt + 0.4))  # wall
        parts.append(bx(hw - 1.0, 12.6, yf + d["PCB_T"] + 0.3, yf + d["PCB_T"] + 1.5, zr, zt + 0.4))  # lip
        parts.append(bx(6.5, 12.6, y1 - 0.01, yf + d["PCB_T"] + 1.5, zt + 0.4, zt + 2.4))  # top stop
    sled = Manifold.batch_boolean(parts, __import__("manifold3d").OpType.Add)
    for (x, z) in d["SLED_SCREWS"]:
        sled = sled - cyl_y(x, z, d["CLR"] / 2, y0 - 1, y1 + 5, 24)
    return sled


def make_bracket(d):
    TOP_C = d["TOP_C"]
    yb = -d["STANDOFF"]
    yf = yb + d["WALLPLATE_T"]
    ro = d["HOOD_ROUT0"]
    rf = ro + 1.0
    plate = (circ(0, TOP_C, rf) ^ rect(-rf, rf, TOP_C, TOP_C + rf)) - \
        (circ(0, TOP_C, ro - 8.0) ^ rect(-rf, rf, TOP_C + 0.01, TOP_C + rf))
    plate = plate + rect(-6.0, 6.0, -14.0, TOP_C + ro - 2.0)                   # spine
    plate = plate + rect(-20.0, 20.0, -10.0, -2.0)                             # foot bar
    for (x, z) in d["BRK"]:
        plate = plate + circ(x, z, d["COL_R"] + 2.0, 40)
    for zc in sorted(set(z for _, z in d["BRK"])):
        plate = plate + rect(-16.0, 16.0, zc - 4.0, zc + 4.0)
    plate = plate + rect(-rf, rf, TOP_C - 4.0, TOP_C + 0.01)                   # cap footing
    br = prism(plate, yb, yf)
    cols = [cyl_y(x, z, d["COL_R"], yf - 0.1, 0.0, 48) for (x, z) in d["BRK"]]
    cap = (cyl_y(0, TOP_C, ro, yf - 0.1, -0.4, d["SEG"]) - cyl_y(0, TOP_C, d["R"], yf - 1, 1, d["SEG"])) \
        ^ halfspace_z(TOP_C)
    for sgn in (-1, 1):                                    # open the flanks below +-50 deg
        cap = cap.trim_by_plane((-sgn * math.cos(math.radians(50)), 0, math.sin(math.radians(50))),
                                TOP_C * math.sin(math.radians(50)))
    br = Manifold.batch_boolean([br, cap] + cols, __import__("manifold3d").OpType.Add)
    holes = []
    for (x, z) in d["BRK"]:
        holes.append(cyl_y(x, z, d["PILOT"] / 2, -15.0, 1.0, 24))
    for (x, z) in d["WALL_HOLES"]:
        holes.append(cyl_y(x, z, 2.3, yb - 1, yf + 1, 32))
        holes.append(cone_y(x, z, 2.3, 4.6, yf - 2.3, yf + 0.01, 32))         # 90deg csk, #8 / 4mm
    return br - Manifold.batch_boolean(holes, __import__("manifold3d").OpType.Add)


# ------------------------------------------------------------------ orientation + export
def to_print(m, part):
    if part == "pill_cover":
        m = m.rotate((-90, 0, 0))          # front face down
    else:
        m = m.rotate((90, 0, 0))           # back / wall face down
    b = m.bounding_box()
    return m.translate((-(b[0] + b[3]) / 2, -(b[1] + b[4]) / 2, -b[2]))


def remove_needles(v, f, h_eps=2e-4, weld=1e-4):
    """Weld coincident vertices, then remove zero-height (collinear) triangles left by coplanar
    booleans without opening the mesh: the neighbour across a needle's long edge is split at
    the needle's middle vertex (folded needle pairs are dropped together)."""
    key = np.round(v / weld).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    V = v[first]
    F = inv[f]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    faces = [list(map(int, t)) for t in F]

    def geo(t):
        p = V[t]
        e = [np.linalg.norm(p[(i + 1) % 3] - p[i]) for i in range(3)]
        cr = np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0]))
        return e, cr / max(max(e), 1e-12)

    emap = {}
    for fi, t in enumerate(faces):
        for i in range(3):
            emap[(t[i], t[(i + 1) % 3])] = fi

    def drop(fi):
        t = faces[fi]
        for i in range(3):
            k = (t[i], t[(i + 1) % 3])
            if emap.get(k) == fi:
                del emap[k]
        faces[fi] = None

    def add(t):
        faces.append(t)
        fi = len(faces) - 1
        for i in range(3):
            emap[(t[i], t[(i + 1) % 3])] = fi
        return fi

    queue = [fi for fi, t in enumerate(faces) if geo(t)[1] < h_eps]
    guard = 0
    while queue and guard < 200000:
        guard += 1
        bi = queue.pop()
        t = faces[bi]
        if t is None:
            continue
        e, h = geo(t)
        if h >= h_eps:
            continue
        i = int(np.argmax(e))
        a, b, mid = t[i], t[(i + 1) % 3], t[(i + 2) % 3]
        nb = emap.get((b, a))
        if nb is None or nb == bi or faces[nb] is None:
            continue
        n = faces[nb]
        k = n.index(b)
        n = n[k:] + n[:k]
        x = n[2]
        drop(bi)
        drop(nb)
        if x != mid:
            f1 = add([b, mid, x])
            f2 = add([mid, a, x])
            queue += [f1, f2]
    out = np.array([t for t in faces if t is not None], dtype=np.int64)
    used = np.unique(out)
    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[out]


def mesh_arrays(m):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(np.float64)
    f = np.asarray(mesh.tri_verts).astype(np.int64)
    return remove_needles(v, f)


def write_stl(path, m, name, ascii_=False):
    v, f = mesh_arrays(m)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1
    n = n / ln[:, None]
    if ascii_:
        out = [f"solid {name}"]
        for i in range(len(f)):
            out.append(f"facet normal {n[i,0]:.5f} {n[i,1]:.5f} {n[i,2]:.5f}")
            out.append("outer loop")
            for j in range(3):
                out.append(f"vertex {tri[i,j,0]:.5f} {tri[i,j,1]:.5f} {tri[i,j,2]:.5f}")
            out.append("endloop")
            out.append("endfacet")
        out.append(f"endsolid {name}")
        with open(path, "w") as fh:
            fh.write("\n".join(out) + "\n")
    else:
        with open(path, "wb") as fh:
            fh.write(name.encode()[:80].ljust(80, b" "))
            fh.write(struct.pack("<I", len(f)))
            data = np.zeros(len(f), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            data["n"] = n
            data["v"] = tri
            fh.write(data.tobytes())
    return len(f)


def build_all(p=None):
    d = derived(p or P)
    return d, {
        "pill_body": make_body(d),
        "pill_cover": make_cover(d),
        "camera_clamp": make_clamp(d),
        "board_sled": make_sled(d),
        "wall_bracket": make_bracket(d),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="stl")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--lens-d", type=float, help="largest lens barrel OD the port must accept (mm, default 16.6)")
    ap.add_argument("--gland-d", type=float, help="cable gland hole (16.2 = M16x1.5, 20.5 = M20x1.5)")
    ap.add_argument("--standoff", type=float, help="wall-to-body-back distance (mm)")
    ap.add_argument("--no-vents", action="store_true")
    ap.add_argument("--assembly", action="store_true",
                    help="also write assembly_preview_DO_NOT_PRINT.stl (all parts in installed position)")
    a = ap.parse_args()
    p = dict(P)
    if a.lens_d: p["LENS_D"] = a.lens_d
    if a.gland_d: p["GLAND_D"] = a.gland_d
    if a.standoff: p["STANDOFF"] = a.standoff
    if a.no_vents: p["VENTS"] = False
    d, parts = build_all(p)
    os.makedirs(a.out, exist_ok=True)
    for name, m in parts.items():
        pm = to_print(m, name)
        path = os.path.join(a.out, f"{name}.stl")
        nt = write_stl(path, pm, name, a.ascii)
        b = pm.bounding_box()
        print(f"{name:14s} {b[3]-b[0]:6.1f} x {b[4]-b[1]:6.1f} x {b[5]-b[2]:6.1f} mm  "
              f"vol {pm.volume()/1000:6.1f} cm3  tris {nt}  -> {path}")
    if a.assembly:
        asm = Manifold.batch_boolean(list(parts.values()), __import__("manifold3d").OpType.Add)
        path = os.path.join(a.out, "assembly_preview_DO_NOT_PRINT.stl")
        write_stl(path, asm, "assembly_preview", a.ascii)
        print(f"assembly preview (world frame, wall plane at Y=-{p['STANDOFF']:.0f}) -> {path}")


if __name__ == "__main__":
    main()
