import bpy
from bpy.props import BoolProperty, IntProperty, FloatProperty, EnumProperty, StringProperty
import bmesh
from .. utils.developer import Benchmark
from .. utils.plug import get_plug, store_scale, apply_hooks_and_arrays, transform, deform, contain, conform_verts_to_target_surface, create_plug_vgroups, get_target_face_ids, merge_plug_into_target, cleanup
from .. utils.stash import create_stash
from .. utils.ui import popup_message
from .. utils.object import unparent, parent
from .. utils.vgroup import get_vgroup
from .. utils.registration import get_prefs
from .. items import fillet_or_edge_items

vert_ids = []

class Plug(bpy.types.Operator):
    bl_idname = "machin3.plug"
    bl_label = "MACHIN3: Plug"
    bl_description = "Embed Plug into mesh surface"
    bl_options = {'REGISTER', 'UNDO'}

    contain: BoolProperty(name="Contain", default=False)
    contain_amnt: FloatProperty(name="Amount", default=0.07, min=0.001)
    filletoredge: EnumProperty(name="Fillet or Edge", items=fillet_or_edge_items, default="FILLET")
    offset: FloatProperty(name="Offset", default=0, min=-0.9, max=4, step=5)
    rotation: FloatProperty(name="Rotation", default=0, step=200)
    deformation: BoolProperty(name="Deformation", default=True)
    deform_plug: BoolProperty(name="Deform Plug", default=False)
    deform_subsets: BoolProperty(name="Deform Subsets", default=False)
    deform_interpolation_falloff: FloatProperty(name="Interpolation Falloff (Surface Deform)", default=16, min=0)
    use_mesh_deform: BoolProperty(name="Mesh Deform", default=True)
    deformer_plug_precision: IntProperty(name="Plug Precision", default=4, min=0)
    deformer_subset_precision: IntProperty(name="Subset Precision", default=4, min=0)
    precision: IntProperty(name="Precision", default=2, min=0, max=5)
    dissolve_angle: FloatProperty(name="Dissolve Angle", default=1, min=0, step=50)
    normal_transfer: BoolProperty(name="Normal Transfer", default=False)
    init: BoolProperty(name="Initial Run", default=False)
    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Integration")

        row = box.row()
        row.prop(self, "contain")

        row = box.row()
        row.prop(self, "precision")
        if not self.contain:
            row.prop(self, "dissolve_angle")

        box = layout.box()
        box.label(text="Transformation")

        row = box.row()
        row.prop(self, "offset")
        row.prop(self, "rotation")

        box = layout.box()
        box.prop(self, "deformation")
        if self.deformation:
            if any([self.subsets, self.filletoredge == "EDGE", self.deformer]):
                row = box.split(factor=0.4)
                if self.deformer:
                    row.prop(self, "use_mesh_deform", text="Use Deformer")
                if self.filletoredge == "EDGE":
                    row.prop(self, "deform_plug", text="Plug")
                if self.subsets:
                    row.prop(self, "deform_subsets", text="Subsets")
                if self.deformer and self.use_mesh_deform:
                    if self.deformer_plug_precision > 4 or self.deformer_subset_precision > 4:
                        box.label(text="Careful, values above 4 are increasingly slow", icon="ERROR")

                    row = box.row()
                    row.prop(self, "deformer_plug_precision")
                    if self.subsets and self.deform_subsets:
                        row.prop(self, "deformer_subset_precision")
        box = layout.box()
        box.label(text="Appereance")

        column = box.column()

        column.prop(self, "normal_transfer")

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            if active:
                return not active.MM.isplughandle

    def invoke(self, context, event):
        self.debug = False

        target, handle, plug, subsets, deformer, modifiers, others, err = get_plug(self, context, context.selected_objects, debug=self.debug)
        if err:
            popup_message(err[0], err[1])
            return {'CANCELLED'}

        else:
            bpy.context.scene.tool_settings.vertex_group_weight = 1  # set the vertex group tool weight to 1, without it the normal transfer may not work as expected
            self.rotation = 0
            self.offset = 0
            self.offset_dist = None

            if plug.MM.hasfillet:
                self.filletoredge = "FILLET"
            else:
                self.filletoredge = "EDGE"

            self.subsets = True if subsets else False
            self.deformer = True if deformer else False
            self.deformer_plug_precision = plug.MM.deformerprecision
            if subsets:
                self.deformer_subset_precision = max([sub.MM.deformerprecision for sub in subsets])
            if deformer:
                self.use_mesh_deform = deformer.MM.usedeformer
        return self.execute(context)

    def execute(self, context):
        target, handle, plug, subsets, deformer, modifiers, others, err = get_plug(self, context, context.selected_objects, debug=self.debug)
        shrinkwraps = [mod for subset in subsets for mod in subset.modifiers if mod.type == 'SHRINKWRAP' and mod.target == plug]

        self.plug(context, target, handle, plug, subsets, deformer, modifiers, others)
        for mod in shrinkwraps:
            mod.target = target

        return {'FINISHED'}

    def plug(self, context, target, handle, plug, subsets, deformer, modifiers, others):
        dg = context.evaluated_depsgraph_get()

        T = Benchmark(False)

        store_scale(context.scene, handle, [o for o in others if o.type == "EMPTY"])

        T.measure("store plug scale")

        nrmsrc = False
        if self.normal_transfer:
            nrmsrc = target.copy()
            nrmsrc.data = target.data.copy()

        T.measure("create normal source")

        for sub in subsets + [plug]:
            sub.show_in_front = False

        apply_hooks_and_arrays(dg, handle, plug, subsets, deformer, others, modifiers)
        T.measure("apply hooks")

        for obj in others:
            bpy.data.objects.remove(obj, do_unlink=True)

        T.measure("delete others")

        subs = [sub for sub in subsets if sub.parent in [plug, handle]]

        transform(dg, handle, plug, deformer, self.rotation, self.offset, self.offset_dist, debug=self.debug)
        T.measure("transform")

        for obj in [plug] + subs:
            unparent(obj)
        T.measure("unparent")

        for obj in subs:
            parent(obj, target)
        T.measure("parent")

        if not target.MM.stashes:
            create_stash(active=target, source=target, dg=dg)
        T.measure("create_stash")

        if self.deformation:
            deform(context, dg, target, handle, deformer, plug, subsets, self.deform_plug, self.deform_subsets, self.filletoredge, self.use_mesh_deform, self.deform_interpolation_falloff, self.deformer_plug_precision, self.deformer_subset_precision, debug=self.debug)
        T.measure("deformation")

        if self.contain:
            contain(self, context, target, handle, self.contain_amnt, self.precision, debug=self.debug)
        T.measure("contain_handle")

        if self.deformation:
            conform_verts_to_target_surface(self, plug, target, self.filletoredge, debug=self.debug)
        else:
            create_plug_vgroups(self, plug, push_back=True)
        T.measure("conform_verts_to_target_surface")

        face_ids = get_target_face_ids(context, handle, target, precision=self.precision, debug=self.debug)
        T.measure("get_target_face_ids")

        target.select_set(True)
        plug.select_set(True)
        context.view_layer.objects.active = target

        bpy.ops.object.join()
        T.measure("join")

        merge_plug_into_target(self, target, face_ids, debug=self)
        T.measure("merge_plug_into_target")

        bpy.ops.object.mode_set(mode='OBJECT')

        cleanup(self, target, deformer, self.dissolve_angle, nrmsrc, self.filletoredge)
        T.measure("cleanup")

        global vert_ids
        vert_ids = self.get_perimeter_edge_ids(target)

        bpy.ops.machin3.draw_plug()
        T.measure("modal_wire")

        T.total()
        return {'FINISHED'}

    def get_perimeter_edge_ids(self, target):
        vgroup = get_vgroup(self, target, 'normal')

        bm = bmesh.new()
        bm.from_mesh(target.data)

        groups = bm.verts.layers.deform.verify()
        indices = []

        for e in bm.edges:
            for v in e.verts:
                if vgroup.index in v[groups]:
                    indices.append((v.index, e.other_vert(v).index))

        bm.clear()

        return indices

class DeletePlug(bpy.types.Operator):
    bl_idname = "machin3.delete_plug"
    bl_label = "MACHIN3: Delete Plug"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context, properties):
        handles = [obj for obj in context.selected_objects if obj.MM.isplughandle]

        if len(handles) > 1:
            return "Delete Selected Handles, Plugs and all Support Objects"
        else:
            return "Delete Handle, Plug and all Support Objects"

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if obj.MM.isplughandle]

    def execute(self, context):
        handles = [obj for obj in context.selected_objects if obj.MM.isplughandle]

        for handle in handles:
            self.objects = [handle]

            for obj in self.get_plug_objects(handle):
                if obj.type == 'MESH':
                    bpy.data.meshes.remove(obj.data, do_unlink=True)
                else:
                    bpy.data.objects.remove(obj, do_unlink=True)

        plugscol = bpy.data.collections.get('Plugs')

        if plugscol:
            for col in plugscol.children:
                if not col.objects:
                    bpy.data.collections.remove(col)

            if not any([plugscol.children, plugscol.objects]):
                    bpy.data.collections.remove(plugscol)

        return {'FINISHED'}

    def get_plug_objects(self, obj):
        for child in obj.children:
            self.objects.append(child)

            if child.children:
                self.get_plug_objects(child)

        return self.objects
