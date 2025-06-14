import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty
import bmesh
from math import radians
from .. utils.ui import draw_init, draw_title, draw_prop, init_cursor, update_HUD_location, popup_message
from .. utils.ui import init_status, finish_status
from .. utils.selection import get_loop_edges, neighbor_loop_select, get_isolated_edges
from .. utils.mesh import get_coords
from .. utils.draw import draw_points
from .. utils.selection import get_selection_islands
from .. utils.developer import output_traceback
from .. colors import green

class VSelect(bpy.types.Operator):
    bl_idname = "machin3.vselect"
    bl_label = "MACHIN3: Vertex Group Select"
    bl_description = "Visually select mesh elements by Vertex Group"
    bl_options = {'REGISTER', 'UNDO'}

    sel_idx: IntProperty(name="Selection Index")

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Vertex Group Select")

            draw_prop(self, "Groups", "%d/%d" % (self.sel_idx + 1, len(self.groups["list"])), hint="scroll UP/DOWN")
            self.offset += 10

            draw_prop(self, "Name", self.active.vertex_groups[self.gidx].name, offset=18)
            draw_prop(self, "Select", self.groups[self.gidx]["select"], offset=18, hint="toggle individual S, toggle all A")

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            transp_ids = {v.index for idx in self.groups['list'] for v in self.groups[idx]['verts']}
            draw_points(self.coords, indices=transp_ids, color=(0.35, 0.35, 0.35), size=5, alpha=1)

            green_ids = [v.index for group in self.green for v in self.green[group]]
            if green_ids:
                draw_points(self.coords, indices=green_ids, color=green, size=8)
                draw_points(self.coords, indices=green_ids, color=(0, 0, 0), size=6, alpha=0.5)

            white_ids = [v.index for v in self.groups[self.gidx]['verts']]

            draw_points(self.coords, indices=white_ids, size=4)

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            active = context.active_object
            return active.vertex_groups

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        if event.type in ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO']:

            if event.type in ['WHEELUPMOUSE', 'ONE'] and event.value == "PRESS":
                self.sel_idx += 1

            elif event.type in ['WHEELDOWNMOUSE', 'TWO'] and event.value == "PRESS":
                self.sel_idx -= 1

            if self.sel_idx > len(self.groups["list"]) - 1:
                self.sel_idx = 0

            elif self.sel_idx < 0:
                self.sel_idx = len(self.groups["list"]) - 1

            self.gidx = self.groups["list"][self.sel_idx]

        if event.type in ['S'] and event.value == "PRESS":
            self.groups[self.gidx]["select"] = not self.groups[self.gidx]["select"]

            if self.groups[self.gidx]["select"]:
                self.green[self.gidx] = self.groups[self.gidx]["verts"]

            else:
                self.green[self.gidx] = []

        elif event.type in ['A'] and event.value == "PRESS":
            for gidx in self.green:

                if self.green[gidx]:
                    self.green[gidx] = []
                    self.groups[gidx]["select"] = False

                else:
                    self.green[gidx] = self.groups[gidx]["verts"]
                    self.groups[gidx]["select"] = True

        elif event.type in {'MIDDLEMOUSE'} or event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE'] and not event.value == 'RELEASE':
            self.select_vgroup(self.active)

            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish()
            self.active.select_set(True)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        self.active = context.active_object

        init_cursor(self, event)

        try:
            ret = self.main(self.active)
        except Exception as e:
            output_traceback(self, e)
            return {'CANCELLED'}

        if not ret:
            return {'CANCELLED'}

        elif len(self.groups["list"]) == 1:
            self.green[self.gidx] = self.groups[self.gidx]["verts"]
            self.select_vgroup(self.active)
            return {'FINISHED'}

        else:
            self.coords = get_coords(self.active.data, mx=self.active.matrix_world)

            init_status(self, context, 'Vertex Group Select')
            self.active.select_set(True)

            self.area = context.area
            self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
            self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

    def main(self, active):
        debug = False

        all_vgroups = set(range(len(active.vertex_groups)))

        self.bm = bmesh.from_edit_mesh(active.data)
        self.bm.normal_update()
        self.bm.verts.ensure_lookup_table()

        groups = self.bm.verts.layers.deform.verify()
        verts = [v for v in self.bm.verts if v.select]

        if verts:
            vgroups = self.get_selected_vgroups(verts, groups, debug=debug)

        else:
            vgroups = list(all_vgroups)

        if vgroups:
            if self.sel_idx > len(vgroups) - 1:
                self.sel_idx = 0
            elif self.sel_idx < 0:
                self.sel_idx = len(vgroups) - 1

            self.groups = {"list": vgroups}

            self.green = {}

            for vg in vgroups:
                self.groups[vg] = {}
                self.groups[vg]["verts"] = []
                self.groups[vg]["select"] = False
                self.green[vg] = []

            self.gidx = self.groups["list"][self.sel_idx]

            for v in self.bm.verts:
                for vg in vgroups:
                    if vg in v[groups]:
                        self.groups[vg]["verts"].append(v)

            return True
        else:
            return False

    def select_vgroup(self, active):
        for group in self.green:
            for v in self.green[group]:
                v.select = True

        self.bm.select_flush(True)

        bmesh.update_edit_mesh(active.data)

    def get_selected_vgroups(self, verts, deform_layer, debug=False):
        selected = []
        for v in verts:
            selected.extend(v[deform_layer].keys())
        selected = list(set(selected))

        if debug:
            print(" • selected vgroups:", selected)

        return selected

    def get_common_vgroups(self, verts, vgroups, deform_layer, debug=False):
        if debug:
            print(" • all vgroups:", vgroups)

        for v in verts:
            vgroups.intersection_update(set(v[deform_layer].keys()))
        if debug:
            print(" • common vgroups:", vgroups)

        return list(vgroups)

class SSelect(bpy.types.Operator):
    bl_idname = "machin3.sselect"
    bl_label = "MACHIN3: Sharp Select"
    bl_description = "Select all sharp edges connected to the existing selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            return [e for e in bm.edges if e.select and not e.smooth]

    def execute(self, context):
        active = context.active_object

        bm = bmesh.from_edit_mesh(active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        sharps = [e for e in bm.edges if e.select and not e.smooth]
        select = sharps.copy()

        while sharps:
            sharp = sharps[0]

            for v in sharp.verts:
                for e in v.link_edges:
                    if not e.smooth and e not in select:
                        select.append(e)
                        sharps.append(e)

            sharps.remove(sharp)

        for e in select:
            e.select = True

        bmesh.update_edit_mesh(active.data)

        return {'FINISHED'}

class LSelect(bpy.types.Operator):
    bl_idname = "machin3.lselect"
    bl_label = "MACHIN3: Loop Select"
    bl_description = "Turn isolated edge preselections into loop selections with control overthe loop-angle"
    bl_options = {'REGISTER', 'UNDO'}

    min_angle: IntProperty(name="Min Angle", default=60, min=0, max=180)
    def draw(self, context):
        layout = self.layout

        column = layout.column()
        column.prop(self, 'min_angle')

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)

            if tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False):
                return [e for e in bm.edges if e.select]

            elif tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True):
                return len([f for f in bm.faces if f.select]) == 2

    def execute(self, context):
        active = context.active_object

        bm = bmesh.from_edit_mesh(active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        if tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False):
            edges = [e for e in bm.edges if e.select]

            isolated = get_isolated_edges(edges)
            self.loop_select_edges(active, isolated)

        elif tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True):
            faces = [f for f in bm.faces if f.select]
            self.loop_select_faces(active, faces)

        return {'FINISHED'}

    def loop_select_edges(self, active, edges):
        for edge in edges:
            vert = edge.verts[0]
            get_loop_edges(180 - self.min_angle, edges, edge, vert, select=True)

            vert = edge.other_vert(vert)
            get_loop_edges(180 - self.min_angle, edges, edge, vert, select=True)

            bmesh.update_edit_mesh(active.data)

    def loop_select_faces(self, active, faces):
        common = set(faces[0].edges).intersection(set(faces[1].edges))

        if common:
            center_edge = common.pop()

            selected = neighbor_loop_select(faces, center_edge)

            if selected:
                neighbor_loop_select(faces, center_edge, reverse=True)

                bmesh.update_edit_mesh(active.data)

            else:
                popup_message("Couldn't find 2 quads on either side of the selection!", title="Invalid Selection")
        else:
            popup_message("Selected 2 faces are not next to each other!", title="Invalid Selection")

class Select(bpy.types.Operator):
    bl_idname = "machin3.select"
    bl_label = "MACHIN3: Select"
    bl_description = "Run VSelect, SSelect, LSelect or pass through to Blender"
    bl_options = {'REGISTER', 'UNDO'}

    loop: BoolProperty(name="Loop Select", default=False)
    always_loop_select: BoolProperty(name="Always Loop Select", description="By default connected Sharps are selected, if entire edge selection consists of sharp edges, otherwise an angle based loop selection is done.\nWith Always Loop Select enabled, this behavior os overidden", default=False)
    min_angle: IntProperty(name="Min Angle", default=60, min=0, max=180)
    draw_props: BoolProperty(name="Draw Properties", default=False)
    faceloop = False
    vgroup = False

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        if self.draw_props:
            column.prop(self, 'always_loop_select', toggle=True)

            row = column.row(align=True)
            r = row.row(align=True)
            r.active = not self.always_loop_select
            r.prop(self, "loop", text="Loop Select" if self.loop else "Sharp Select", toggle=True)

            r = row.row(align=True)
            r.active = self.loop or self.always_loop_select
            r.prop(self, 'min_angle')

    def invoke(self, context, event):
        self.loop = False
        self.faceloop = False
        self.vgroup = False

        self.draw_props = False

        bm = bmesh.from_edit_mesh(context.active_object.data)

        if tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (True, False, False):
            if context.active_object.vertex_groups:
                verts = [v for v in bm.verts if v.select]

                if verts:
                    bpy.ops.machin3.vselect('INVOKE_DEFAULT')
                    self.vgroup = True
                    return {'FINISHED'}

        elif tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, True, False):
            edges = [e for e in bm.edges if e.select]

            if edges and self.always_loop_select:
                self.select_type = 'LOOP'
                self.loop = True

                isolated = get_isolated_edges(edges)

                if isolated:
                    bpy.ops.machin3.lselect(min_angle=self.min_angle)
                    self.draw_props = True

                    return {'FINISHED'}

            else:
                self.select_type = self.get_edge_type(edges)

                if self.select_type:
                    if self.select_type == 'LOOP':
                        self.loop = True
                        bpy.ops.machin3.lselect(min_angle=self.min_angle)

                    elif self.select_type == 'SHARP':
                        bpy.ops.machin3.sselect()

                    self.draw_props = True
                    return {'FINISHED'}

        elif tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True):
            faces = [f for f in bm.faces if f.select]

            if len(faces) == 2:
                islands = get_selection_islands(bm, debug=False)

                if len(islands) == 1 and len(islands[0][2]) == 2:
                    bpy.ops.machin3.lselect()
                    self.faceloop = True
                    return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        if self.select_type:

            if self.loop is False:
                bm = bmesh.from_edit_mesh(context.active_object.data)
                edges = [e for e in bm.edges if e.select]

                if all([e.smooth for e in edges]):
                    self.loop = True

            if self.loop or self.always_loop_select:
                bpy.ops.machin3.lselect(min_angle=self.min_angle)
            else:
                bpy.ops.machin3.sselect()
            return {'FINISHED'}

        else:
            return {'PASS_THROUGH'}

    def get_edge_type(self, edges):
        isolated = get_isolated_edges(edges)

        if isolated:
            anysmooth = any([e.smooth for e in isolated])
            return 'LOOP' if anysmooth else 'SHARP'

        else:
            return None
