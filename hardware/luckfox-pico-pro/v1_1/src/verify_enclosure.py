#!/usr/bin/env python3
"""
Verification gate for luckfox_pill_enclosure.py.  Exit code 0 = all hard checks pass.

    pip install manifold3d numpy trimesh
    python3 verify_enclosure.py                 # default parameters
    python3 verify_enclosure.py --lens-d 14.6   # same flags as the generator

Hard checks (fail the run):
  * every part is a valid closed manifold and a single connected body (also after STL
    vertex welding, which is what a slicer sees)
  * no two printed parts intersect in the assembled position
  * no printed part intersects the hardware stand-ins (PCB, RJ45 jack + plug, L-shaped USB-C
    plug, camera PCB / FPC connector / lens holder / lens barrel, gland nut + body (scaled from --gland-d),
    screw heads)
  * camera field of view is unobstructed: rays from a 4 mm-radius lens front ring over the
    published SC3336 FOV (98.3 D / 84 H / 44 V deg) plus 10% hit nothing
Reports (informational): print-orientation overhangs, mass / library cost, O-ring cord length.
"""
import argparse, itertools, math, os, sys, tempfile
import numpy as np
import trimesh
from trimesh.ray.ray_triangle import RayMeshIntersector
from manifold3d import Manifold, OpType
import luckfox_pill_enclosure as L


def tri(m):
    v, f = L.mesh_arrays(m)
    return trimesh.Trimesh(v, f, process=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lens-d", type=float)
    ap.add_argument("--gland-d", type=float)
    ap.add_argument("--standoff", type=float)
    ap.add_argument("--no-vents", action="store_true")
    a = ap.parse_args()
    p = dict(L.P)
    if a.lens_d: p["LENS_D"] = a.lens_d
    if a.gland_d: p["GLAND_D"] = a.gland_d
    if a.standoff: p["STANDOFF"] = a.standoff
    if a.no_vents: p["VENTS"] = False
    d, parts = L.build_all(p)
    fails = []
    print(f"generator version {L.__version__}")

    print("== 1. mesh validity (print orientation, after vertex welding)")
    for k, m in parts.items():
        pm = L.to_print(m, k)
        v, f = L.mesh_arrays(pm)
        t = trimesh.Trimesh(v, f, process=True)
        nb = len(t.split(only_watertight=False))
        ok = (str(m.status()).endswith("NoError") and t.is_watertight and t.is_winding_consistent
              and nb == 1 and t.bounds[0][2] > -1e-6)
        b = t.bounds[1] - t.bounds[0]
        print(f"  {'OK ' if ok else 'BAD'} {k:13s} {b[0]:6.1f} x {b[1]:6.1f} x {b[2]:5.1f} mm  "
              f"watertight={t.is_watertight} bodies={nb} tris={len(f)}")
        # round-trip through a real float32 binary STL, i.e. exactly what a slicer will load
        with tempfile.TemporaryDirectory() as td:
            fp = os.path.join(td, k + ".stl")
            L.write_stl(fp, pm, k, False)
            r = trimesh.load(fp)
            rt = r.is_watertight and len(r.split(only_watertight=False)) == 1 and (r.area_faces < 1e-8).sum() == 0
        print(f"      STL file round-trip: {'clean' if rt else 'BROKEN'}")
        ok = ok and rt
        if not ok: fails.append(f"validity:{k}")
        if max(b) > 229: fails.append(f"too big for 229mm library printer:{k}")

    print("== 2. part-to-part interference in assembly")
    clean = True
    for x, y in itertools.combinations(parts, 2):
        v = (parts[x] ^ parts[y]).volume()
        if v > 0.01:
            clean = False; fails.append(f"interference:{x}x{y}")
            print(f"  BAD {x} x {y}: {v:.3f} mm3")
    if clean: print("  OK  no overlaps")

    print("== 3. hardware stand-ins vs printed parts")
    B = L.box
    yf, pt, zb, zt, cz = d["Y_RAILF"], d["PCB_T"], d["ZB"], d["ZT"], d["CAM_Z"]
    prox = {
        "Pico Pro/Max PCB 72x21": B(-10.5, 10.5, yf, yf + pt, zb, zt),
        "RJ45 jack 16w x 13.5h": B(-8, 8, yf + pt, yf + pt + 13.5, zb - 1.5, zb + 21),
        "RJ45 plug + boot": B(-6.5, 6.5, yf + pt + 1, yf + pt + 12.5, zb - 26, zb - 1.5),
        "USB-C right-angle plug": B(-6, 6, yf + pt, yf + pt + 7.5, zt, zt + 10),
        "camera PCB 25x24": B(-12.5, 12.5, d["Y_CAMB"], d["Y_CAMF"], cz - 12, cz + 12),
        "camera FPC connector": B(-8, 8, d["Y_CAMB"] - 2.5, d["Y_CAMB"], cz - 12, cz - 6),
        "lens holder 15x15x9.5": B(-7.5, 7.5, d["Y_CAMF"], d["Y_CAMF"] + 9.5, cz - 7.5, cz + 7.5),
        "lens barrel (max accepted OD)": L.cyl_y(0, cz, d["LENS_D"] / 2, d["Y_CAMF"] + 9.5, d["Y_LT"], 48),
        "gland locknut (scales w/ --gland-d)": L.cyl_z(0, d["GLAND_Y"], 0.71 * d["GLAND_D"], d["Z_FLOOR"], d["Z_FLOOR"] + 5, 6),
        "gland body outside (scales)": L.cyl_z(0, d["GLAND_Y"], 0.68 * d["GLAND_D"], d["Z_FLAT"] - 14, d["Z_FLAT"], 6),
    }
    y_sled_top = d["Y_SLED0"] + d["SLED_T"]
    for (x, z) in d["SLED_SCREWS"]:
        prox[f"sled screw head ({x:+.1f},{z:.1f})"] = L.cyl_y(x, z, 2.9, y_sled_top, y_sled_top + 2.4, 24)
    for (x, z) in d["BRK"]:
        prox[f"bracket screw head ({x:+.1f},{z:.1f})"] = L.cyl_y(x, z, 2.9, d["BACK_T"] + 1.5, d["BACK_T"] + 3.9, 24)
    clean = True
    for nm, pm in prox.items():
        for k, m in parts.items():
            v = (pm ^ m).volume()
            if v > 0.01:
                clean = False; fails.append(f"hardware:{nm}x{k}")
                print(f"  BAD {nm} x {k}: {v:.2f} mm3")
    if clean: print(f"  OK  {len(prox)} stand-ins clear of all printed parts")
    for (x, z) in d["SLED_SCREWS"][:2]:
        reach = z + math.sqrt(max(0.0, 2.9 ** 2 - (abs(x) - 10.5) ** 2))
        print(f"  info bottom sled screw head reaches z={reach:.2f} over PCB end z={zb:.2f} -> traps board")

    print("== 4. camera field of view (Luckfox SC3336 spec: 98.3 D / 84 H / 44 V deg, F2.0, 3.95 mm)")
    # Equidistant (f-theta) model calibrated so the 16:9 image corner sits at the 98.3 deg diagonal;
    # it then lands at ~86 H / ~48 V, a touch wider than the published 84 / 44 -> conservative.
    asm = Manifold.batch_boolean([parts["pill_body"], parts["pill_cover"], parts["wall_bracket"]], OpType.Add)
    I = RayMeshIntersector(tri(asm))
    o0 = np.array([0.0, d["Y_LT"], cz])
    rc = math.hypot(1.0, 9.0 / 16.0)
    kdeg = 49.15 / rc
    for scale, label, hard in [(1.10, "spec FOV +10% margin (HARD)", True),
                               (1.25, "spec FOV +25% stress (info)", False)]:
        O, D = [], []
        for ring in (0.0, 2.0, 4.0):                       # points across the lens front element
            for ph in np.linspace(0, 2 * math.pi, 12, endpoint=False):
                o = o0 + np.array([ring * math.cos(ph), 0, ring * math.sin(ph)])
                for u in np.linspace(-1, 1, 25):
                    for w in np.linspace(-9 / 16, 9 / 16, 15):
                        r = math.hypot(u, w)
                        th = math.radians(kdeg * r * scale)
                        az = math.atan2(w, u) if r > 0 else 0.0
                        dv = np.array([math.sin(th) * math.cos(az), math.cos(th), math.sin(th) * math.sin(az)])
                        O.append(o); D.append(dv)
        O, D = np.array(O), np.array(D)
        hit = I.intersects_any(O + D * 0.05, D)
        ok = hit.sum() == 0
        tag = "OK " if ok else ("BAD" if hard else "info")
        print(f"  {tag} {label:30s} {hit.sum()} / {len(hit)} rays blocked "
              f"(half-angles H {kdeg*scale:.0f} / V {kdeg*scale*9/16:.0f} / D {49.15*scale:.0f} deg)")
        if hard and not ok: fails.append(f"fov:{label}")

    print("== 5. print-orientation overhang audit (no supports intended)")
    for k, m in parts.items():
        t = tri(L.to_print(m, k))
        nz = t.face_normals[:, 2]
        zmin = t.vertices[t.faces][:, :, 2].min(1)
        ar = t.area_faces
        steep = (nz < -math.cos(math.radians(40))) & (zmin > 0.25)
        flat = (nz < -0.98) & (zmin > 0.25)
        print(f"  {k:13s} >50deg overhang {ar[steep].sum():6.1f} mm2, near-horizontal {ar[flat].sum():6.1f} mm2")

    print("== 6. mass / example print cost ($0.15/g, solid upper bound, PLA 1.24 / PETG 1.27 g/cc)")
    tot = 0.0
    for k, m in parts.items():
        g = m.volume() / 1000 * 1.27
        tot += g
        print(f"  {k:13s} {m.volume()/1000:5.1f} cm3  <= {g:5.1f} g  <= ${g*0.15:5.2f}")
    print(f"  total <= {tot:.0f} g  <= ${tot*0.15:.2f}")

    print("== 7. seal")
    band = L.band_inner_smooth(d)
    mid = band.offset(d["GROOVE_IN"] + d["GROOVE_W"] / 2)
    perim = sum(np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1).sum() for c in mid.to_polygons())
    squeeze = (2.0 - d["GROOVE_D"]) / 2.0 * 100
    fill = math.pi * 1.0 ** 2 / (d["GROOVE_W"] * d["GROOVE_D"]) * 100
    print(f"  2.0 mm cord, groove {d['GROOVE_W']} x {d['GROOVE_D']} mm: squeeze {squeeze:.0f}%, gland fill {fill:.0f}%, "
          f"cut length {perim:.0f} mm (+5 mm)")
    print(f"  vents: {len(L.vent_slots(d)) if d['VENTS'] else 0} louvres")

    print("\nRESULT:", "PASS" if not fails else "FAIL -> " + ", ".join(fails))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
