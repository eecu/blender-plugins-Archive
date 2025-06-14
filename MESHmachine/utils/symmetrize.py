import bpy
import bmesh
from . property import negate_string
from . normal import normal_clear, normal_transfer_from_obj
from . bmesh import loop_index_update
from . registration import get_addon
from .. items import axis_mapping_dict

hypercursor = None

def symmetrize(obj, direction='POSITIVE_X', threshold=0.0001, partial=False, remove=False, remove_redundant_center=True, redundant_threshold=0, mirror_vertex_groups=False, mirror_custom_normals=False, custom_normal_method='INDEX', fix_center=False, fix_center_method='CLEAR', clear_sharps=False, debug=False):
    def sort_verts_into_sides(debug=False):
        symdir, axis = direction.split('_')

        original = []
        mirror = []
        center = []

        verts = [v for v in bm.verts if v.select] if partial else bm.verts

        for v in verts:

            if axis == "X":
                if -threshold < v.co[0] < threshold:
                    v.co[0] = 0
                    if debug:
                        print("centered vertex %d" % (v.index))

                if symdir == "POSITIVE":
                    if v.co[0] == 0:
                        center.append(v.index)
                    elif v.co[0] > 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)
                elif symdir == "NEGATIVE":
                    if v.co[0] == 0:
                        center.append(v.index)
                    elif v.co[0] < 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)

            if axis == "Y":
                if -threshold < v.co[1] < threshold:
                    v.co[1] = 0
                    if debug:
                        print("centered vertex %d" % (v.index))

                if symdir == "POSITIVE":
                    if v.co[1] == 0:
                        center.append(v.index)
                    elif v.co[1] > 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)
                elif symdir == "NEGATIVE":
                    if v.co[1] == 0:
                        center.append(v.index)
                    elif v.co[1] < 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)

            if axis == "Z":
                if -threshold < v.co[2] < threshold:
                    v.co[2] = 0
                    if debug:
                        print("centered vertex %d" % (v.index))

                if symdir == "POSITIVE":
                    if v.co[2] == 0:
                        center.append(v.index)
                    elif v.co[2] > 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)
                elif symdir == "NEGATIVE":
                    if v.co[2] == 0:
                        center.append(v.index)
                    elif v.co[2] < 0:
                        original.append(v.index)
                    else:
                        mirror.append(v.index)

            v.select = False
        bm.select_flush(False)

        if len(original) != len(mirror):
            print(" ! WARNING, uneven vertex list sizes!")

        return (original, mirror, center), axis

    def get_mirror_verts_via_index(original, mirror, center, debug=False):
        mirror_verts = {}
        for vm, vp in zip(mirror, original):
            mirror_verts[vp] = vm

        for vz in center:
            mirror_verts[vz] = vz

        if debug:
            print("verts")
            for mv in mirror_verts:
                print(mv, mirror_verts[mv])
            print()

        return mirror_verts

    def get_mirror_verts_via_location(original, mirror, center, axis, debug=False):
        precision = 10

        if debug:
            print("original:", original)
            print("mirror:", mirror)

        if axis == "X":
            yz = {}
        elif axis == "Y":
            xz = {}
        elif axis == "Z":
            xy = {}

        for v in bm.verts:
            x = "%.*f" % (precision, v.co[0])
            y = "%.*f" % (precision, v.co[1])
            z = "%.*f" % (precision, v.co[2])

            if debug:
                print(v.index, "•", x, y, z)

            if axis == "X":
                if (y, z) not in yz:
                    yz[(y, z)] = {}

                yz[(y, z)][x] = v.index
            elif axis == "Y":
                if (x, z) not in xz:
                    xz[(x, z)] = {}

                xz[(x, z)][y] = v.index
            elif axis == "Z":
                if (x, y) not in xy:
                    xy[(x, y)] = {}

                xy[(x, y)][z] = v.index

        if debug:
            print()
            if axis == "X":
                print("yz keys")
                for vert in yz:
                    print(vert)
                    print(" •", yz[vert])
            elif axis == "Y":
                print("xz keys")
                for vert in xz:
                    print(vert)
                    print(" •", xz[vert])
            elif axis == "Z":
                print("xy keys")
                for vert in xy:
                    print(vert)
                    print(" •", xy[vert])

        mirror_verts = {}

        for idx in original:
            vo = bm.verts[idx]

            x = "%.*f" % (precision, vo.co[0])
            y = "%.*f" % (precision, vo.co[1])
            z = "%.*f" % (precision, vo.co[2])

            if axis == "X":
                mirror_verts[idx] = yz[(y, z)][negate_string(x)]
            elif axis == "Y":
                mirror_verts[idx] = xz[(x, z)][negate_string(y)]
            elif axis == "Z":
                mirror_verts[idx] = xy[(x, y)][negate_string(z)]

        for vc in center:
            mirror_verts[vc] = vc

        if debug:
            for mv in mirror_verts:
                print(mv, mirror_verts[mv])

        return mirror_verts

    def get_mirror_faces(mirror_verts, debug=False):
        faces = {}
        loops = {}
        for face in bm.faces:
            vertlist = [v.index for v in face.verts]
            faces[frozenset(vertlist)] = face.index

            for loop in face.loops:
                loops[(face.index, loop.vert.index)] = loop.index

        if debug:
            print(faces)
            print()
            print(loops)
            print()

        mirror_faces = {}
        for vertlist in faces:
            try:
                mirrored_vertlist = frozenset([mirror_verts[idx] for idx in vertlist])
                mirror_faces[faces[vertlist]] = faces[mirrored_vertlist]
            except:
                pass

        if debug:
            print("faces")
            for mf in mirror_faces:
                print(mf, mirror_faces[mf])
            print()

        return mirror_faces, loops

    def get_mirror_loops(mirror_verts, mirror_faces, loops, debug=False):
        mirror_loops = {}
        for fidx in mirror_faces:
            for loop in bm.faces[fidx].loops:
                mirror_loops[loop.index] = loops[(mirror_faces[fidx], mirror_verts[loop.vert.index])]

        if debug:
            print("loops")
            for ml in mirror_loops:
                print(ml, mirror_loops[ml])

            for face in bm.faces:
                print("face:", face.index)
                for loop in face.loops:
                    print(" • ", "loop: %d, vert: %d" % (loop.index, loop.vert.index))

        return mirror_loops

    def fix_center_seam(center, debug=False):
        for v in obj.data.vertices:
            if v.index in center:
                v.select = True

        bpy.ops.object.mode_set(mode='EDIT')

        mode = tuple(bpy.context.scene.tool_settings.mesh_select_mode)

        if mode != (True, False, False):
            bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

        bpy.ops.mesh.loop_multi_select(ring=False)

        if clear_sharps:
            if debug:
                print("INFO: Removing Center Seam Sharps.")
            bpy.ops.mesh.mark_sharp(clear=True)

        if fix_center_method == "CLEAR":
            normal_clear(obj, limit=False)

        elif fix_center_method == "TRANSFER":
            normal_transfer_from_obj(obj, nrmsrc, vertids=center, remove_vgroup=True)

        bpy.ops.mesh.select_all(action='DESELECT')

        if mode != (True, False, False):
            bpy.context.scene.tool_settings.mesh_select_mode = mode

    def remove_vertex_groups(bm, vg, sides):
        for idx in sides[1]:
            v = bm.verts[idx]

            for idx, vgdata in v[vg].items():
                del v[vg][idx]  # this actually removes the vert from the vg, whereas the other just sets the weight to 0 (which would still select the vert in the vg panel)

        for idx in sides[2]:
            v = bm.verts[idx]

            for idx, vgdata in v[vg].items():
                del v[vg][idx]

    global hypercursor

    if hypercursor is None:
        hypercursor = get_addon('HyperCursor')[0]

    nrmsrc = None

    if not remove and not partial and obj.data.has_custom_normals:
        if debug:
            print("INFO: Custom Normals detected!")

        if mirror_custom_normals and fix_center and fix_center_method == "TRANSFER":
            if debug:
                print("INFO: Creating normal source!")

            obj.update_from_editmode()

            nrmsrc = obj.copy()
            nrmsrc.data = obj.data.copy()

    if not partial:
        bpy.ops.mesh.reveal()
        bpy.ops.mesh.select_all(action='SELECT')

    bpy.ops.mesh.symmetrize(direction=direction, threshold=threshold)

    if not partial:
        bpy.ops.mesh.select_all(action='DESELECT')

    if not remove and not partial and obj.data.has_custom_normals and mirror_custom_normals:

        if bpy.app.version < (4, 1, 0) and not obj.data.use_auto_smooth:
            obj.data.use_auto_smooth = True

        bpy.ops.object.mode_set(mode='OBJECT')

        if bpy.app.version < (4, 1, 0):
            obj.data.calc_normals_split()

        loop_normals = []
        for idx, loop in enumerate(obj.data.loops):
            loop_normals.append(loop.normal.normalized())  # normalize them, or you will run into weird issues at the end!

            if debug:
                print(idx, loop.normal)

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        loop_index_update(bm)

        sides, axis = sort_verts_into_sides(debug=debug)

        if custom_normal_method == "INDEX":
            mirror_verts = get_mirror_verts_via_index(*sides, debug=debug)

        elif custom_normal_method == "LOCATION":
            mirror_verts = get_mirror_verts_via_location(*sides, axis, debug=debug)

        mirror_faces, loops = get_mirror_faces(mirror_verts, debug=debug)

        mirror_loops = get_mirror_loops(mirror_verts, mirror_faces, loops, debug=debug)

        mirror_vector = axis_mapping_dict[axis]

        for ml in mirror_loops:
            loop_normals[mirror_loops[ml]] = loop_normals[ml].reflect(mirror_vector)

        obj.data.normals_split_custom_set(loop_normals)

        if sides[2] and fix_center:
            fix_center_seam(sides[2], debug=debug)
        else:
            bpy.ops.object.mode_set(mode='EDIT')

        if nrmsrc:
            if debug:
                print("INFO: Removing normal source!")

            bpy.data.objects.remove(nrmsrc, do_unlink=True)

        return {'original': sides[0], 'mirror': sides[1], 'center': sides[2], 'custom_normal': True, 'vertmap': mirror_verts, 'facemap': mirror_faces, 'loopmap': mirror_loops}

    else:
        bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        loop_index_update(bm)

        vg = bm.verts.layers.deform.verify()
        sides, _ = sort_verts_into_sides(debug=debug)

        if not mirror_vertex_groups:
            remove_vertex_groups(bm, vg, sides)
            bm.to_mesh(obj.data)

        bpy.ops.object.mode_set(mode='EDIT')

        if remove or remove_redundant_center:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.normal_update()
            bm.verts.ensure_lookup_table()

            if remove:
                verts = [bm.verts[idx] for idx in sides[1]]
                bmesh.ops.delete(bm, geom=verts, context='VERTS')

            elif remove_redundant_center:
                redundant_center_edges = [e for e in bm.edges if e.is_manifold and all(v.index in sides[2] for v in e.verts) and round(e.calc_face_angle(), 5) <= redundant_threshold]

                bmesh.ops.dissolve_edges(bm, edges=redundant_center_edges, use_verts=True, use_face_split=False)

                sides = (sides[0], sides[1], [])

            bmesh.update_edit_mesh(obj.data)

        return {'original': sides[0], 'mirror': sides[1], 'center': sides[2], 'custom_normal': False}
