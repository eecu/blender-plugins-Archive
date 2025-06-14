import bpy
import bmesh
from mathutils import Matrix, Vector, Euler
from math import radians
from . registration import get_addon
from . raycast import cast_bvh_ray_from_mouse, get_grid_intersection, cast_obj_ray_from_mouse
from . math import create_rotation_matrix_from_normal, get_loc_matrix, get_rot_matrix, get_sca_matrix
from . mesh import unhide_deselect
from . normal import normal_transfer_from_obj, normal_clear_across_sharps
from . object import update_local_view, flatten, add_facemap
from . vgroup import add_vgroup, set_vgroup, get_vgroup
from . modifier import apply_mod

def align(scene, depsgraph, handle, empties):
    mm = scene.MM
    wm = bpy.context.window_manager

    set_scale(scene, depsgraph, handle, empties)

    if mm.align_mode == "CURSOR":
        handle.location = bpy.context.scene.cursor.location
        bpy.context.scene.cursor.rotation_mode = "QUATERNION"
        handle.rotation_mode = "QUATERNION"
        handle.rotation_quaternion = bpy.context.scene.cursor.rotation_quaternion

    elif mm.align_mode == "RAYCAST":
        mousepos = wm.plug_mousepos

        hitobj, loc, normal, _, _ = cast_obj_ray_from_mouse(mousepos, exclude_decals=True if get_addon('DECALmachine')[0] else False, debug=False)

        _, _, sca = handle.matrix_world.decompose()

        scamx = Matrix()
        for i in range(3):
            scamx[i][i] = sca[i]

        if hitobj:
            rotmx = create_rotation_matrix_from_normal(hitobj, normal, loc, debug=False)
            handle.matrix_world = Matrix.Translation(loc) @ rotmx @ scamx

        else:
            loc, rotmx = get_grid_intersection(mousepos)
            handle.matrix_world = Matrix.Translation(loc) @ rotmx @ scamx

def set_scale(scene, depsgraph, handle, empties):
    plugscales = scene.MM.plugscales

    if handle.MM.uuid in plugscales:
        ps = plugscales[handle.MM.uuid]

        handle.scale = ps.scale

        for e in empties:
            if e.MM.uuid in ps.empties:
                e.location = ps.empties[e.MM.uuid].location

        depsgraph.update()

def store_scale(scene, handle, empties):
    if handle.MM.uuid:
        plugscales = scene.MM.plugscales

        if handle.MM.uuid in plugscales:
            ps = plugscales[handle.MM.uuid]

        else:
            ps = plugscales.add()
            ps.name = handle.MM.uuid

        ps.scale = handle.scale

    for e in empties:
        if e.MM.uuid:
            if e.MM.uuid in ps.empties:
                emp = ps.empties[e.MM.uuid]

            else:
                emp = ps.empties.add()
                emp.name = e.MM.uuid

            emp.location = e.location

def clear_drivers(objects):
    for obj in objects:
        if not obj.modifiers:
            data = obj.animation_data

            if data:
                for path in [drv.data_path for drv in obj.animation_data.drivers]:
                    obj.driver_remove(path)

def get_plug(self, context, sel, debug=False):
    if len(sel) != 2:
        errmsg = "Select plug handle and a target object to plug into."
        errtitle = "Illegal Selection"
    else:
        active = context.active_object

        if active in sel:
            sel.remove(active)
            target = active

            if debug:
                print()
                print("target:", target.name)

            if sel[0].MM.isplughandle:
                handle = sel[0]

                if debug:
                    print("plug handle:", handle.name)

                plug = None
                deformer = None
                subsets = []
                others = []  # other are either empties or array caps or an occluder, all of these can be deleted after mods have been applied
                modifiers = list(set([mod.type for mod in handle.modifiers]))

                if handle.children:
                    children = list(handle.children)

                    while children:
                        c = children[0]
                        children.extend(list(c.children))

                        if c.MM.isplug:
                            plug = c
                        elif c.MM.isplugsubset:
                            subsets.append(c)
                        elif c.MM.isplugdeformer:
                            deformer = c
                        else:
                            others.append(c)

                        modifiers.extend([mod.type for mod in c.modifiers if mod.type not in modifiers])

                        children.pop(0)

                    if plug:
                        if debug:
                            print("plug:", plug.name)

                        conform_vgroup = plug.vertex_groups.get("conform")

                        if conform_vgroup:
                            set_vgroup(self, conform_vgroup, 'conform', init=True)

                            if debug:
                                print("subsets:", [obj.name for obj in subsets])
                                print("deformer:", deformer.name if deformer else None)
                                print("others:", [obj.name for obj in others])
                                print("modifiers:", modifiers)

                            return target, handle, plug, subsets, deformer, modifiers, others, None
                        else:
                            errmsg = "Plug is missing a 'conform' vertex group."
                            errtitle = "Invalid Plug"

                    else:
                        errmsg = "Plug handle does not seem to have a plug object as a child"
                        errtitle = "Invalid Plug"

                else:
                    errmsg = "Plugs can't just consist of a handle, they need to have a plug mesh as well."
                    errtitle = "Invalid Plug"

            else:
                errmsg = "The selected object is not a (valid) plug handle, aborting"
                errtitle = "Illegal Selection"

        else:
            errmsg = "No active object in selection."
            errtitle = "Illegal Selection"

    return None, None, None, None, None, None, None, (errmsg, errtitle)

def apply_hooks_and_arrays(depsgraph, handle, plug, subsets, deformer, others, modifiers):
    if any(mod in modifiers for mod in ['HOOK', 'ARRAY']):
        arraymods = [m for m in plug.modifiers if m.type == "ARRAY"]

        if len(arraymods) > 1:
            array2 = arraymods[1]

            flatten(array2.start_cap, depsgraph, preserve_data_layers=True)
            flatten(array2.end_cap, depsgraph, preserve_data_layers=True)

            depsgraph.update()

        applyobjs = [handle] + [plug] + subsets

        if deformer:
            applyobjs.append(deformer)
        for obj in applyobjs:
            flatten(obj, depsgraph, preserve_data_layers=arraymods)

        clear_drivers(applyobjs)

def transform(depsgraph, handle, plug, deformer, rotation, offset, offset_dist, debug=False):
    def offset_deformer(obj, amount, offset_dist, debug=False):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        for f in bm.faces:
            f.hide_set(False)
            f.select_set(False)

        top = []
        bottom = []
        side = []

        for f in bm.faces:
            dot = f.normal.dot(Vector((0, 0, 1)))

            if dot > 0.9:
                top.append(f)
            elif dot < -0.9:
                bottom.append(f)
            else:
                side.append(f)

        for f in top:
            f.select = True

        border_edges = [e for e in bm.edges if (e.link_faces[0].select and not e.link_faces[1].select) or (not e.link_faces[0].select and e.link_faces[1].select)]

        verts = {}
        for e in border_edges:
            for v in e.verts:
                if v not in verts:
                    offset_edge = [e for e in v.link_edges if e.select and e not in border_edges]
                    if offset_edge:
                        if not offset_dist:
                            offset_dist = offset_edge[0].calc_length()
                            if debug:
                                print("offset distance:", offset_dist)

                        offset_vert = offset_edge[0].other_vert(v)

                        verts[v] = offset_vert
                        if debug:
                            print("vert:", v.index, " • offset vert:", offset_vert.index)

        for f in bm.faces:
            f.select = True if f in bottom else False

        border_edges = [e for e in bm.edges if (e.link_faces[0].select and not e.link_faces[1].select) or (not e.link_faces[0].select and e.link_faces[1].select)]

        for e in border_edges:
            for v in e.verts:
                if v not in verts:
                    offset_edge = [e for e in v.link_edges if e.select and e not in border_edges]
                    if offset_edge:
                        if not offset_dist:
                            offset_dist = offset_edge[0].calc_length()
                            if debug:
                                print("offset distance:", offset_dist)

                        offset_vert = offset_edge[0].other_vert(v)

                        verts[v] = offset_vert
                        if debug:
                            print("vert:", v.index, " • offset vert:", offset_vert.index)

        for v in verts:
            v_ov_dir = (verts[v].co - v.co).normalized() * offset_dist * amount
            v.co = v.co - v_ov_dir

        bm.to_mesh(obj.data)
        bm.clear()

    def offset_perimeter(obj, amount, offset_dist, debug=False):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        border_edges = [e for e in bm.edges if not e.is_manifold]

        verts = {}
        for e in border_edges:
            for v in e.verts:
                if v not in verts:
                    offset_edge = [e for e in v.link_edges if e not in border_edges]
                    if offset_edge:
                        if not offset_dist:
                            offset_dist = offset_edge[0].calc_length()
                            if debug:
                                print("offset distance:", offset_dist)

                        offset_vert = offset_edge[0].other_vert(v)

                        verts[v] = offset_vert
                        if debug:
                            print("vert:", v.index, " • offset vert:", offset_vert.index)

        for v in verts:
            v_ov_dir = (verts[v].co - v.co).normalized() * offset_dist * amount
            v.co = v.co - v_ov_dir

        bm.to_mesh(obj.data)
        bm.clear()

    if rotation != 0:
        rmx = Matrix.Rotation(radians(rotation), 4, 'Z')

        loc, rot, sca = handle.matrix_basis.decompose()
        handle.matrix_basis = get_loc_matrix(loc) @ get_rot_matrix(rot) @ rmx @ get_sca_matrix(sca)

        depsgraph.update()

    if offset != 0:
        offset_perimeter(plug, offset, offset_dist, debug=debug)
        offset_perimeter(handle, offset, offset_dist, debug=debug)

        if deformer:
            offset_deformer(deformer, offset, offset_dist, debug=debug)

def deform(context, depsgraph, target, handle, deformer, plug, subsets, deform_plug, deform_subsets, filletoredge, use_mesh_deform, deform_interpolation_falloff, deformer_plug_precision, deformer_subset_precision, debug=False):
    if deform_plug or filletoredge == "FILLET":
        if deformer and use_mesh_deform:
            context.view_layer.objects.active = deformer
            surface_deform = deformer.modifiers.new(name="Deformer Deform", type="SURFACE_DEFORM")
            surface_deform.target = handle
            surface_deform.falloff = deform_interpolation_falloff  # by default this value is 4, but it might not be enough
            bpy.ops.object.surfacedeform_bind(modifier="Deformer Deform")
            context.view_layer.objects.active = plug
            mesh_deform = plug.modifiers.new(name="Plug Deform", type="MESH_DEFORM")
            mesh_deform.object = deformer
            mesh_deform.precision = deformer_plug_precision
            bpy.ops.object.meshdeform_bind(modifier="Plug Deform")
        else:
            context.view_layer.objects.active = plug
            surface_deform = plug.modifiers.new(name="Plug Deform", type="SURFACE_DEFORM")
            surface_deform.target = handle
            surface_deform.falloff = deform_interpolation_falloff  # by default this value is 4, but it might not be enough
            bpy.ops.object.surfacedeform_bind(modifier="Plug Deform")
    if subsets:
        subs = subsets if deform_subsets else [sub for sub in subsets if sub.MM.forcesubsetdeform]
        for sub in subs:
            context.view_layer.objects.active = sub

            if deformer and use_mesh_deform:
                mesh_deform = sub.modifiers.new(name="Plug Deform", type="MESH_DEFORM")
                mesh_deform.object = deformer
                mesh_deform.precision = deformer_subset_precision
                bpy.ops.object.meshdeform_bind(modifier="Plug Deform")
            else:
                surface_deform = sub.modifiers.new(name="Subset Deform", type="SURFACE_DEFORM")
                surface_deform.target = handle
                surface_deform.falloff = deform_interpolation_falloff  # by default this value is 4, but it might not be enough
                bpy.ops.object.surfacedeform_bind(modifier="Subset Deform")
    shrink_wrap = handle.modifiers.new(name="Shrink Wrap", type="SHRINKWRAP")
    shrink_wrap.target = target

    depsgraph.update()

    flatten(plug, depsgraph)

    if subsets:
        for sub in subs:
            flatten(sub, depsgraph)

    flatten(handle, depsgraph)

    if deformer:
        deformer.modifiers.clear()

def contain(self, context, target, handle, amount, precision, debug=False):
    handlescale = (handle.scale.x + handle.scale.y) / 2
    targetscale = (target.scale.x + target.scale.y + target.scale.z) / 3

    containamount = handlescale / targetscale * amount
    containamount = handlescale * amount

    handle.select_set(False)
    target.select_set(False)

    container = handle.copy()
    container.data = handle.data.copy()
    container.name = "container"
    context.scene.collection.objects.link(container)
    update_local_view(context.space_data, [(container, True)])

    vg = add_vgroup(container, "container", [v.index for v in container.data.vertices], debug=debug)
    set_vgroup(self, vg, 'contain')

    container.select_set(True)
    context.view_layer.objects.active = container

    if precision > 1:
        subd = container.modifiers.new(name="Subsurf", type="SUBSURF")
        subd.levels = 1
        apply_mod(subd.name)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')

    bpy.ops.transform.translate(value=(0, 0, -containamount), constraint_axis=(False, False, True), orient_type='LOCAL')
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, containamount * 2), "constraint_axis": (False, False, True), "orient_type": 'LOCAL'})
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.object.mode_set(mode='OBJECT')

    unhide_deselect(target.data)

    target.select_set(True)
    context.view_layer.objects.active = target
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode='EDIT')

    bpy.context.scene.tool_settings.transform_pivot_point = 'MEDIAN_POINT'

    bpy.ops.transform.shrink_fatten(value=containamount)

    bpy.ops.mesh.intersect(separate_mode='NONE', solver='FAST')

    container_vgroup = get_vgroup(self, target, 'contain')

    target.vertex_groups.active_index = container_vgroup.index
    bpy.ops.object.vertex_group_select()
    bpy.ops.mesh.select_more()

    bpy.ops.object.vertex_group_assign()
    bpy.ops.mesh.delete(type='FACE')

    bpy.ops.object.mode_set(mode='OBJECT')
    handle.select_set(True)

def create_plug_vgroups(self, plug, push_back=False):
    conform_vgroup = get_vgroup(self, plug, 'conform')
    plug_vgroup = plug.vertex_groups.new(name="plug")
    border_vgroup = plug.vertex_groups.new(name="border")

    set_vgroup(self, plug_vgroup, 'plug')
    set_vgroup(self, border_vgroup, 'border')

    bm = bmesh.new()
    bm.from_mesh(plug.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    groups = bm.verts.layers.deform.verify()
    conform_verts = []

    for v in bm.verts:
        if conform_vgroup.index in v[groups]:
            conform_verts.append(v)
        else:
            v[groups][plug_vgroup.index] = 1

    border_edges = [e for e in bm.edges if not e.is_manifold]
    border_verts = []

    for e in border_edges:
        for v in e.verts:
            v[groups][border_vgroup.index] = 1
            border_verts.append(v)

    if push_back:
        bm.to_mesh(plug.data)
        bm.clear()

    return bm, conform_verts, border_verts

def conform_verts_to_target_surface(self, obj, target, filletoredge, debug=False):
    if debug:
        print("\nConforming plug obj's verts to the target's surface")

    bm, conform_verts, border_verts = create_plug_vgroups(self, obj, push_back=False)

    if debug:
        print(" • border verts:", [v.index for v in border_verts])
        print(" • conform verts:", [v.index for v in conform_verts])

    if filletoredge == "EDGE":
        objmx = obj.matrix_world
        targetmx = target.matrix_world

        distances = []
        for v in border_verts + conform_verts:
            vert_origin_world_co = obj.matrix_world @ v.co  # vertex location in world space
            vert_origin_target_local_co = targetmx.inverted_safe() @ vert_origin_world_co   # vertex location in the targets local space

            hit, co, nrm, face_idx = target.closest_point_on_mesh(vert_origin_target_local_co)

            if hit:
                if debug:
                    print(" • idx:", v.index, "normal:", nrm, "target face index:", face_idx)

                vert_destination_world_co = targetmx @ co

                dist = (vert_destination_world_co - vert_origin_world_co).length
                distances.append(dist)
                if debug:
                    print("  • projection distance:", dist)

                vert_destination_obj_local_co = objmx.inverted_safe() @ vert_destination_world_co

                v.co = vert_destination_obj_local_co

        if debug:
            print(" • moved %d verts" % (len(border_verts + conform_verts)))

        avg_dist = sum(distances) / len(distances)

        if debug:
            print(" • average distance:", avg_dist)

        for v in bm.verts:
            if v not in border_verts + conform_verts:
                v.co = v.co + Vector((0, 0, -1)) * avg_dist

    bm.to_mesh(obj.data)
    obj.data.update()
    bm.clear()

def get_target_face_ids(context, handle, target, precision, debug=False):
    if debug:
        print("\nGetting target obj's faces to be replaced by the plug")

    if precision:
        context.view_layer.objects.active = handle
        subd = handle.modifiers.new(name="Subsurf", type="SUBSURF")
        subd.levels = precision
        apply_mod(subd.name)

    bm = bmesh.new()
    bm.from_mesh(handle.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    mx = handle.matrix_world
    targetmx = target.matrix_world

    face_ids = []
    for v in bm.verts:
        vert_world_co = mx @ v.co  # vertex location in world space
        vert_target_local_co = targetmx.inverted_safe() @ vert_world_co   # vertex location in the targets local space

        hit, co, nrm, face_idx = target.closest_point_on_mesh(vert_target_local_co)

        if hit:
            if debug:
                print(" • idx:", v.index, "normal:", nrm, "target face index:", face_idx)

            if face_idx not in face_ids:
                face_ids.append(face_idx)
    if debug:
        print(" • sampled %d verts" % (len(bm.verts)))

    bm.clear()

    bpy.data.objects.remove(handle, do_unlink=True)

    return face_ids

def merge_plug_into_target(self, target, face_ids, debug=False):
    boundary_vgroup = target.vertex_groups.new(name="boundary")
    set_vgroup(self, boundary_vgroup, 'boundary')

    conform_vgroup = get_vgroup(self, target, 'conform')
    border_vgroup = get_vgroup(self, target, 'border')
    container_vgroup = get_vgroup(self, target, 'contain')

    bm = bmesh.new()
    bm.from_mesh(target.data)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    groups = bm.verts.layers.deform.verify()
    faces = [f for f in bm.faces if f.index in face_ids]

    if container_vgroup:
        for f in bm.faces:
            if f in faces:
                f.select = True
            else:
                f.select = False

        for v in bm.verts:
            if container_vgroup.index in v[groups]:
                v.select = True

        bm.select_flush(True)

        faces = [f for f in bm.faces if f.select]

    boundary_edges = []
    for f in faces:
        for e in f.edges:
            if not all([f in faces for f in e.link_faces]):
                boundary_edges.append(e)

    border_verts = [v for v in bm.verts if border_vgroup.index in v[groups]]

    border_edges = []
    for v in border_verts:
        for e in v.link_edges:
            if all([v in border_verts for v in e.verts]):
                if e not in border_edges:
                    border_edges.append(e)
                    e.select = True

    bmesh.ops.delete(bm, geom=faces, context='FACES')

    if container_vgroup:
        bridge_edges = [e for e in list(set(boundary_edges + border_edges)) if e.is_valid]
    else:
        bridge_edges = [e for e in boundary_edges + border_edges if e.is_valid]

    geo = bmesh.ops.bridge_loops(bm, edges=bridge_edges)

    for f in bm.faces:
        if f in geo["faces"]:
            for v in f.verts:
                v[groups][boundary_vgroup.index] = 1
        f.select = False

    bm.select_flush(False)

    if container_vgroup:
        remove_container_boundary(bm, groups, target, container_vgroup, conform_vgroup, border_vgroup, boundary_vgroup, debug=debug)

    bm.to_mesh(target.data)
    bm.clear()

    bpy.ops.object.mode_set(mode='EDIT')

def remove_container_boundary(bm, groups, target, container_vgroup, conform_vgroup, border_vgroup, boundary_vgroup, debug=False):
    border_verts = []
    conform_verts = []
    container_verts = []
    boundary_verts = []

    for v in bm.verts:
        if border_vgroup.index in v[groups]:
            border_verts.append(v)

        if conform_vgroup.index in v[groups]:
            conform_verts.append(v)

        if container_vgroup.index in v[groups]:
            container_verts.append(v)

        if boundary_vgroup.index in v[groups]:
            boundary_verts.append(v)

    dissolve_verts = []
    for v in boundary_verts:
        if v not in border_verts and v not in container_verts:
            dissolve_verts.append(v)

    for v in container_verts:
        edges = [(e.calc_length(), e.other_vert(v)) for e in v.link_edges if e.other_vert(v) in border_verts]

        if edges:
            shortest = sorted(edges, key=lambda e: e[0])[0]
            v.co = shortest[1].co
        else:
            dissolve_verts.append(v)

    bmesh.ops.remove_doubles(bm, verts=container_verts + border_verts, dist=0.00001)

    bmesh.ops.dissolve_verts(bm, verts=dissolve_verts)

    border_verts = [v for v in boundary_verts if v.is_valid]

    for v in border_verts:
        v[groups][border_vgroup.index] = 1
        v[groups][conform_vgroup.index] = 1

    slipping_edges = []

    for v in border_verts:
        offset_edge = None

        border_edges = []

        for e in v.link_edges:
            if e.other_vert(v) in border_verts:
                border_edges.append(e)
            elif e.other_vert(v) in conform_verts:
                offset_edge = e

        if offset_edge and len(border_edges) > 2:

            for l in offset_edge.link_loops:
                if l.vert == v:
                    border_edge = l.link_loop_prev.edge
                else:
                    border_edge = l.link_loop_next.edge

                border_edges.remove(border_edge)

            for e in border_edges:
                if e not in slipping_edges:
                    slipping_edges.append(e)

    bmesh.ops.dissolve_edges(bm, edges=slipping_edges)

def cleanup(self, target, deformer, dissolve_angle, nrmsrc, filletoredge, debug=False):
    conform_vgroup = get_vgroup(self, target, 'conform')
    border_vgroup = get_vgroup(self, target, 'border')
    boundary_vgroup = get_vgroup(self, target, 'boundary')
    container_vgroup = get_vgroup(self, target, 'contain')
    plug_vgroup = get_vgroup(self, target, 'plug')

    bpy.ops.object.mode_set(mode='EDIT')

    if not container_vgroup:
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
        target.vertex_groups.active_index = boundary_vgroup.index
        bpy.ops.object.vertex_group_select()
        bpy.ops.mesh.dissolve_limited(angle_limit=radians(dissolve_angle))
        bpy.ops.mesh.tris_convert_to_quads()

    target.vertex_groups.active_index = conform_vgroup.index
    bpy.ops.object.vertex_group_select()

    if container_vgroup:
        bpy.ops.mesh.select_more()

        target.vertex_groups.active_index = plug_vgroup.index
        bpy.ops.object.vertex_group_deselect()

    normal_vgroup = add_vgroup(target, name="normal_transfer", debug=debug)
    set_vgroup(self, normal_vgroup, 'normal')

    if self.normal_transfer:
        normal_transfer_from_obj(target, nrmsrc, vgroup=normal_vgroup)
        bpy.ops.object.mode_set(mode='OBJECT')

        if filletoredge == "EDGE":
            normal_clear_across_sharps(target)

        conform_vgroup = get_vgroup(self, target, 'conform')
        border_vgroup = get_vgroup(self, target, 'border')
        boundary_vgroup = get_vgroup(self, target, 'boundary')
        container_vgroup = get_vgroup(self, target, 'contain')
        plug_vgroup = get_vgroup(self, target, 'plug')

    else:
        bpy.ops.object.mode_set(mode='OBJECT')

    if bpy.app.version < (4, 1, 0):
        if self.normal_transfer or filletoredge == 'EDGE':
            target.data.use_auto_smooth = True

    target.vertex_groups.remove(conform_vgroup)
    target.vertex_groups.remove(border_vgroup)
    target.vertex_groups.remove(boundary_vgroup)
    target.vertex_groups.remove(plug_vgroup)

    if container_vgroup:
        target.vertex_groups.remove(container_vgroup)

    if deformer:
        bpy.data.objects.remove(deformer, do_unlink=True)
    if self.normal_transfer:
        bpy.data.objects.remove(nrmsrc, do_unlink=True)
