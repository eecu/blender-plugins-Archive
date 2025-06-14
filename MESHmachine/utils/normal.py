import bpy
import mathutils
import bmesh
from . vgroup import add_vgroup
from . modifier import apply_mod
from . registration import get_prefs
from . system import printd
from .. items import loop_mapping_dict

def add_normal_transfer_mod(obj, nrmsrc, name, vgroup, mapping=None, debug=False):
    data_transfer = obj.modifiers.new(name, "DATA_TRANSFER")
    data_transfer.object = nrmsrc
    data_transfer.use_loop_data = True

    if mapping:
        data_transfer.loop_mapping = loop_mapping_dict[mapping]
    else:
        data_transfer.loop_mapping = loop_mapping_dict["NEAREST FACE"]

    data_transfer.vertex_group = vgroup.name

    data_transfer.data_types_loops = {'CUSTOM_NORMAL'}
    data_transfer.show_expanded = False
    data_transfer.show_in_editmode = True

    data_transfer.use_object_transform = False

    if bpy.app.version < (4, 1, 0):
        obj.data.use_auto_smooth = True

    if debug:
        print(" • Added modifier '%s' to object '%s'." % (name, obj.name))

    return data_transfer

def normal_transfer_from_stash(active, mapping=None):
    bpy.ops.object.mode_set(mode='OBJECT')

    if get_prefs().experimental:
        bm = bmesh.new()
        bm.from_mesh(active.data)
        bm.normal_update()

        is_face_select = bool([f for f in bm.faces if f.select])
        sharps = [e for e in bm.edges if not e.smooth if any([v.select for v in e.verts])]

        if sharps:
            split = bmesh.ops.split_edges(bm, edges=sharps, use_verts=False)

            for e in split['edges']:

                if is_face_select:
                    e.select_set(any([f.select for f in e.link_faces]))

                else:
                    e.select_set(True)

            bm.to_mesh(active.data)
            bm.free()

    vert_ids = [v.index for v in active.data.vertices if v.select]

    if not vert_ids:
        bpy.ops.object.mode_set(mode='EDIT')
        return None, None

    vgroup = add_vgroup(active, "NormalTransfer", vert_ids)
    active.show_wire = False

    stashobj = active.MM.stashes[active.MM.active_stash_idx].obj
    data_transfer = add_normal_transfer_mod(active, stashobj, vgroup.name, vgroup, mapping)
    return vgroup, data_transfer

def normal_transfer_from_obj(active, nrmsrc, vertids=False, vgroup=False, remove_vgroup=False):
    bpy.ops.object.mode_set(mode='OBJECT')

    if vertids:
        vgroup = add_vgroup(active, "NormalTransfer", vertids)

    if vgroup:
        vgname = vgroup.name
        data_transfer = add_normal_transfer_mod(active, nrmsrc, vgname, vgroup)
        apply_mod(data_transfer.name)

        if remove_vgroup and (vg := active.vertex_groups.get(vgname)):
            active.vertex_groups.remove(vg)

    bpy.ops.object.mode_set(mode='EDIT')

def normal_clear(active, limit=False):
    debug = True
    debug = False

    bpy.ops.object.mode_set(mode='OBJECT')

    mesh = active.data

    if bpy.app.version < (4, 1, 0):
        mesh.calc_normals_split()

    loop_normals = []
    for loop in mesh.loops:
        loop_normals.append(loop.normal)

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    verts = [v for v in bm.verts if v.select]
    faces = [f for f in bm.faces if f.select]

    for v in verts:
        for l in v.link_loops:
            if not limit or l.face in faces:
                loop_normals[l.index] = mathutils.Vector()

    mesh.normals_split_custom_set(loop_normals)

    if bpy.app.version < (4, 1, 0):
        mesh.use_auto_smooth = True

    bpy.ops.object.mode_set(mode='EDIT')

    return True

def normal_clear_across_sharps(active):
    mesh = active.data

    if bpy.app.version < (4, 1, 0):
        mesh.calc_normals_split()

    loop_normals = []
    for loop in mesh.loops:
        loop_normals.append(loop.normal)

    bm = bmesh.new()
    bm.from_mesh(active.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    verts = [v for v in bm.verts if v.select]
    edges = [e for e in bm.edges if e.select]
    faces = [f for f in bm.faces if f.select]

    faces_across = []
    for e in edges:
        for f in e.link_faces:
            if f not in faces:
                if not e.smooth:  # sharp boundary edge
                    faces_across.append(f)  # unselected face across sharp boundary
                break

    if faces_across:
        for v in verts:
            for l in v.link_loops:
                if l.face in faces_across:
                    loop_normals[l.index] = mathutils.Vector()

        mesh.normals_split_custom_set(loop_normals)

        if bpy.data.version < (4, 1, 0):
            mesh.use_auto_smooth = True

def remerge_sharp_edges(active):
    bm = bmesh.new()
    bm.from_mesh(active.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    sharps = [e for e in bm.edges if not e.smooth and not e.is_manifold]

    if sharps:
        verts = {v for e in sharps for v in e.verts}

        for v in verts:
            v.select_set(True)

        bmesh.ops.remove_doubles(bm, verts=list(verts), dist=0.00001)

        bm.select_flush(True)

        bm.to_mesh(active.data)
        bm.free()
