from . math import average_normals, get_distance_between_verts

def init_sweeps(bm, active, rails, verts=True, edges=True, loop_candidates=True, freestyle=True, loops=True, handles=True, avg_face_normals=True, rail_lengths=True, debug=False):
    sweeps = []
    for idx, vertpair in enumerate(zip(rails[0], rails[1])):
        sweep = {}
        if verts:
            sweep["verts"] = vertpair
        if edges:
            sweep["edges"] = [bm.edges.get(vertpair)]
        if loop_candidates:

            candidates = []
            for v in sweep["verts"]:
                side = []
                for e in v.link_edges:
                    if not e.select:
                        if e.calc_length() != 0:
                            side.append(e)
                        elif debug:
                            print("Zero length edge detected, ignoring edge %d. Results may be unexpected!" % (e.index))

                if freestyle:
                    fsloopcount = sum([active.data.edges[e.index].use_freestyle_mark for e in side])

                    if fsloopcount > 0:
                        if fsloopcount == 1 and len(side) != 1:
                            side = [e for e in side if active.data.edges[e.index].use_freestyle_mark]
                            if debug:
                                print("Using freestyle edge %d as the only loop candidate." % (side[0].index))
                        else:
                            exclude = [e for e in side if active.data.edges[e.index].use_freestyle_mark]
                            if debug:
                                for e in exclude:
                                    print("Excluding freestyle edge %d from loop edge candidates" % (e.index))
                            side = [e for e in side if e not in exclude]

                candidates.append(side)
            sweep["loop_candidates"] = candidates
        if loops:
            sweep["loops"] = []
        if handles:
            sweep["handles"] = []
        if avg_face_normals:
            inos = []
            for v in sweep["verts"]:
                inos.append(average_normals([f.normal.normalized() for f in v.link_faces if not f.select and f not in sweep["edges"][0].link_faces]))
            sweep["avg_face_normals"] = inos
        if rail_lengths:
            rlens = []

            if idx == 0:
                rlens.extend([0, 0])
            else:
                vA = vertpair[0]
                priorvA = rails[0][idx - 1]

                vB = vertpair[1]
                priorvB = rails[1][idx - 1]

                distA = get_distance_between_verts(vA, priorvA)
                distB = get_distance_between_verts(vB, priorvB)

                rlens.extend([distA, distB])

            sweep["rail_lengths"] = rlens

        sweeps.append(sweep)
        if debug:
            debug_sweeps([sweeps[-1]], index=idx, verts=verts, edges=edges, loop_candidates=loop_candidates, loops=loops, handles=handles, avg_face_normals=avg_face_normals, rail_lengths=rail_lengths)

    return sweeps

def debug_sweeps(sweeps, index=None, cyclic=False, verts=True, edges=True, loop_candidates=True, loops=True, loop_types=True, handles=True, avg_face_normals=True, rail_lengths=True):
    for idx, sweep in enumerate(sweeps):
        if index:
            idx = index
        print("sweep:", idx)
        if verts:
            print("  • verts:", sweep["verts"][0].index, " - ", sweep["verts"][1].index)
        if edges:
            print("  • edges:", sweep["edges"][0].index)
        if loop_candidates:
            print("  • loop_candidates:", [[l.index for l in lcs] for lcs in sweep["loop_candidates"]])
        if loops:
            print("  • loops:")
            for idx, loop_tuple in enumerate(sweep["loops"]):
                loop_type, remote_co, loop_edge_idx, angle, smooth, bevel_weight= loop_tuple
                print("    %d." % idx, "type:", loop_type, "remote co:", remote_co, "edge index:", loop_edge_idx, "angle:", angle, "smooth:", smooth, "bevel weight:", bevel_weight)
        if handles:
            print("  • handles:", [hco for hco in sweep["handles"]])
        if avg_face_normals:
            print("  • avg_face_normals:", [ino for ino in sweep["avg_face_normals"]])
        if rail_lengths:
            print("  • rail lengths:", [length for length in sweep["rail_lengths"]])
        print()

    if cyclic:
        print("Selection is cyclic!")
