import bpy
from bpy.props import IntProperty, BoolProperty
import bmesh
import mathutils
import math
from .. utils.bmesh import loop_index_update
from .. utils.draw import draw_vector
from .. utils.collection import create_realmirror_collections, sort_into_realmirror_collections
from .. items import axis_mapping_dict

mirrored = []
custom_normals = []

class RealMirror(bpy.types.Operator):
    bl_idname = "machin3.real_mirror"
    bl_label = "MACHIN3: Real Mirror"
    bl_description = "Convert Mirrod Modifiers into real geometry with proper origins and properly mirrored custom normals"
    bl_options = {'REGISTER', 'UNDO'}

    uoffset: IntProperty(name="U", default=0)
    voffset: IntProperty(name="V", default=0)
    mirror_custom_normals: BoolProperty(name="Mirror Custom Normals", default=True)
    create_collections: BoolProperty(name="Create RealMirror Collections", default=True)
    apply_data_transfers: BoolProperty(name="Apply Data Transfers", default=True)
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object

    def draw(self, context):
        layout = self.layout

        box = layout.box()

        col = box.column()
        col.prop(self, "mirror_custom_normals")
        col.prop(self, "create_collections")
        col.prop(self, "apply_data_transfers")

        box = layout.box()

        row = box.row(align=True)
        row.label(text="UV Offset")
        row.prop(self, "uoffset")
        row.prop(self, "voffset")

    def execute(self, context):
        debug = False

        sel = context.selected_objects

        originals = sel.copy()

        global mirrored
        mirrored = []

        while sel:
            context.view_layer.objects.active = sel[0]
            active = context.active_object

            mirrors = [mod for mod in active.modifiers if mod.type == "MIRROR" and mod.show_render and mod.show_render and any(mod.use_axis)]

            if not mirrors:
                sel.remove(active)

            else:
                self.custom_normals = active.data.has_custom_normals

                loop_data = self.get_loop_data(active) if self.custom_normals else None

                for mod in mirrors:
                    target = mod.mirror_object if mod.mirror_object else active

                    mod.show_viewport = False
                    mod.show_render = False

                    uvs = (mod.use_mirror_u, mod.use_mirror_v)
                    uvoffsets = (self.uoffset, self.voffset)

                    if mod.use_axis[0]:
                        mirror_obj1 = self.real_mirror(active, target, loop_data, mod.name, "X", uvs, uvoffsets, debug=debug)
                        loop_data1 = self.get_loop_data(mirror_obj1) if self.custom_normals else (None, None)

                        sel.append(mirror_obj1)
                        mirrored.append(mirror_obj1)

                        if mod.use_axis[1]:
                            mirror_obj2 = self.real_mirror(mirror_obj1, target, loop_data1, mod.name, "Y", uvs, uvoffsets, debug=debug)
                            loop_data2 = self.get_loop_data(mirror_obj2) if self.custom_normals else (None, None)

                            sel.append(mirror_obj2)
                            mirrored.append(mirror_obj2)

                            if mod.use_axis[2]:
                                mirror_obj3 = self.real_mirror(mirror_obj2, target, loop_data2, mod.name, "Z", uvs, uvoffsets, debug=debug)

                                sel.append(mirror_obj3)
                                mirrored.append(mirror_obj3)

                        if mod.use_axis[2]:
                            mirror_obj2 = self.real_mirror(mirror_obj1, target, loop_data1, mod.name, "Z", uvs, uvoffsets, debug=debug)
                            loop_data2 = self.get_loop_data(mirror_obj2) if self.custom_normals else (None, None)

                            sel.append(mirror_obj2)
                            mirrored.append(mirror_obj2)

                    if mod.use_axis[1]:
                        mirror_obj1 = self.real_mirror(active, target, loop_data, mod.name, "Y", uvs, uvoffsets, debug=debug)
                        loop_data1 = self.get_loop_data(mirror_obj1) if self.custom_normals else (None, None)

                        sel.append(mirror_obj1)
                        mirrored.append(mirror_obj1)

                        if mod.use_axis[2]:
                            mirror_obj2 = self.real_mirror(mirror_obj1, target, loop_data1, mod.name, "Z", uvs, uvoffsets, debug=debug)

                            sel.append(mirror_obj2)
                            mirrored.append(mirror_obj2)

                    if mod.use_axis[2]:
                        mirror_obj1 = self.real_mirror(active, target, loop_data, mod.name, "Z", uvs, uvoffsets, debug=debug)
                        sel.append(mirror_obj1)
                        mirrored.append(mirror_obj1)

        if self.create_collections and mirrored:
            _, rmocol, rmmcol = create_realmirror_collections(context.scene)

            sort_into_realmirror_collections(originals, rmocol, mirrored, rmmcol)

        if mirrored:
            global custom_normals
            custom_normals = [True if self.mirror_custom_normals and obj.data.has_custom_normals else False for obj in mirrored]

            bpy.ops.machin3.draw_realmirror()

        return {'FINISHED'}

    def real_mirror(self, active, target, loop_data, modname, axis, uvs, uvoffsets, debug=False):
        mirror_obj, loop_data = self.mirror_object(active, target, loop_data, axis, modname, debug=debug)

        bm = self.apply_transformation(mirror_obj, axis)

        if any(uvs):
            bm = self.mirror_uvs(bm, *uvs, *uvoffsets)

        if self.mirror_custom_normals and self.custom_normals:
            self.mirror_normals(bm, mirror_obj, loop_data, axis, debug=debug)
        else:
            bm.to_mesh(mirror_obj.data)
            bm.clear()

        mirror_obj.data.update()

        return mirror_obj

    def mirror_uvs(self, bm, umirror, vmirror, uoffset=0, voffset=0):
        uvs = bm.loops.layers.uv.active

        if uvs:

            us = []
            vs = []
            mir_us = []
            mir_vs = []

            for face in bm.faces:
                for loop in face.loops:
                    uv = loop[uvs].uv

                    us.append(uv[0])
                    vs.append(uv[1])

                    if umirror:
                        loop[uvs].uv = uv.reflect(mathutils.Vector((1, 0)))
                    if vmirror:
                        loop[uvs].uv = uv.reflect(mathutils.Vector((0, 1)))

                    uv = loop[uvs].uv

                    mir_us.append(uv[0])
                    mir_vs.append(uv[1])

            for face in bm.faces:
                for loop in face.loops:
                    loop[uvs].uv += mathutils.Vector((min(us) - min(mir_us), min(vs) - min(mir_vs)))

                    if any([uoffset, voffset]):
                        loop[uvs].uv += mathutils.Vector((uoffset, voffset))

        return bm

    def mirror_normals(self, bm, mirror_obj, loop_data, axis, debug=False):
        mirror_loops = self.pair_loops(bm, mirror_obj, loop_data["indices"], debug=debug)

        new_loop_normals = self.create_loop_normals(loop_data["normals"], mirror_loops, axis)

        if bpy.app.version < (4, 1, 0):
            mirror_obj.data.calc_normals_split()

        mirror_obj.data.normals_split_custom_set(new_loop_normals)

    def create_loop_normals(self, orig_loop_normals, mirror_loops, axis):
        new_loop_normals = []

        for idx in range(len(orig_loop_normals)):
            nrm = orig_loop_normals[mirror_loops[idx]]

            new_loop_normals.append(nrm.reflect(axis_mapping_dict[axis]))

        return new_loop_normals

    def pair_loops(self, bm, obj, orig_loop_indices, debug=False):
        loop_index_update(bm)

        mirror_loops = {}

        for face in bm.faces:
            if debug:
                print("face:", face.index)

            for loop in face.loops:
                if debug:
                    print(" • vert:", loop.vert.index, "loop:", loop.index)
                    print("  • original loop:", orig_loop_indices[(face.index, loop.vert.index)])
                mirror_loops[loop.index] = orig_loop_indices[(face.index, loop.vert.index)]

        bm.to_mesh(obj.data)
        bm.clear()

        return mirror_loops

    def apply_transformation(self, obj, axis):
        mx_world = obj.matrix_world.copy()
        mx_scale = mathutils.Matrix.Scale(-1, 4)

        mx_rotation = mathutils.Matrix.Rotation(math.radians(180), 4, axis)

        obj.matrix_world = mx_world @ mx_rotation @ mx_scale @ mx_world.inverted_safe() @ mx_world

        bm = bmesh.new()
        bm.from_mesh(obj.data)

        for v in bm.verts:
            v.co = mx_rotation @ mx_scale @ v.co

        for f in bm.faces:
            f.normal_flip()

        return bm

    def mirror_object(self, obj, target, loop_data, axis, mirrormodname, debug=False):
        targetmx = target.matrix_world

        mir = obj.copy()
        mir.data = obj.data.copy()

        for col in obj.users_collection:
            col.objects.link(mir)

        bpy.context.view_layer.objects.active = mir

        if mir.modifiers.get(mirrormodname):
            bpy.ops.object.modifier_remove(modifier=mirrormodname)

        if self.apply_data_transfers:
            data_transfers = [mod for mod in mir.modifiers if mod.type == "DATA_TRANSFER"]
            subds = [mod for mod in mir.modifiers if mod.type == "SUBSURF"]

            if not subds:
                for d in data_transfers:
                    bpy.ops.object.modifier_apply(modifier=d.name)

            self.custom_normals = mir.data.has_custom_normals

            if self.custom_normals:
                loop_data = self.get_loop_data(mir, debug=debug)

        mir_mx = mathutils.Matrix.Scale(-1, 4, axis_mapping_dict[axis])

        mir.matrix_world = targetmx @ mir_mx @ targetmx.inverted_safe() @ mir.matrix_world

        return mir, loop_data

    def get_loop_data(self, obj, debug=False):
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

        loop_indices = {}
        for face in bm.faces:
            if debug:
                print("face:", face.index)
            for loop in face.loops:
                if debug:
                    print(" • vert:", loop.vert.index, "loop:", loop)

                loop_indices[(face.index, loop.vert.index)] = loop.index

        bm.clear()

        loop_data = {}
        loop_data["normals"] = loop_normals
        loop_data["indices"] = loop_indices

        return loop_data
