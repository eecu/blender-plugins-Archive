import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty
import bmesh
import math
import mathutils
from .. items import normal_flatten_threshold_preset_items, loop_mapping_items, loop_mapping_dict
from .. utils.developer import output_traceback
from .. utils.graph import build_mesh_graph
from .. utils.selection import get_2_rails_from_chamfer, get_selection_islands
from .. utils.normal import normal_clear, normal_transfer_from_stash, normal_clear_across_sharps, remerge_sharp_edges
from .. utils.math import get_edge_normal
from .. utils.mesh import shade, flip_normals, get_coords
from .. utils.registration import get_prefs
from .. utils.ui import init_cursor, wrap_cursor, draw_init, draw_title, draw_prop, update_HUD_location
from .. utils.ui import init_status, finish_status
from .. utils.draw import draw_mesh_wire
from .. utils.property import step_collection, step_enum
from .. utils.modifier import apply_mod
from .. utils.vgroup import set_vgroup, get_vgroup
from .. colors import white

class NormalFlatten(bpy.types.Operator):
    bl_idname = "machin3.normal_flatten"
    bl_label = "MACHIN3: Normal Flatten"
    bl_description = "Flatten uneven shading on (mostly) ngons"
    bl_options = {'REGISTER', 'UNDO'}

    normalthreshold: FloatProperty(name="Angle Threshold", default=15, min=0)
    def update_normalthreshold_preset(self, context):
        if self.normalthreshold_preset != "CUSTOM":
            self.normalthreshold = float(self.normalthreshold_preset)

    normalthreshold_preset: EnumProperty(name="Angle Threshold Presets", items=normal_flatten_threshold_preset_items, default="CUSTOM", update=update_normalthreshold_preset)
    clear: BoolProperty(name="Clear Existing Normals", default=False)
    allowmodalthreshold: BoolProperty(default=False)
    passthrough = False

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, "normalthreshold")

        row = column.row()
        row.prop(self, "normalthreshold_preset", expand=True)

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Normal Flatten")

            draw_prop(self, "Angle Threshold", self.normalthreshold, active=self.allowmodalthreshold, hint="move LEFT/RIGHT, toggle W, reset ALT + W, presets Z/Y, X, C, V, B")
            self.offset += 10

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            return len([f for f in bm.faces if f.select]) >= 1

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        events = ['W', 'R', 'Y', 'Z', 'X', 'C', 'V', 'B']

        if self.allowmodalthreshold:
            events.append('MOUSEMOVE')

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalthreshold:
                        divisor = 100 if event.shift else 1 if event.ctrl else 10

                        delta_x = event.mouse_x - self.last_mouse_x
                        delta_threshold = delta_x / divisor

                        self.normalthreshold += delta_threshold
                        self.normalthreshold_preset = "CUSTOM"

            elif (event.type == 'Y' or event.type == 'Z') and event.value == "PRESS":
                self.normalthreshold_preset = "5"

            elif event.type == 'X' and event.value == "PRESS":
                self.normalthreshold_preset = "15"

            elif event.type == 'C' and event.value == "PRESS":
                self.normalthreshold_preset = "30"

            elif event.type == 'V' and event.value == "PRESS":
                self.normalthreshold_preset = "60"

            elif event.type == 'B' and event.value == "PRESS":
                self.normalthreshold_preset = "90"

            elif event.type == 'W' and event.value == "PRESS":
                if event.alt:
                    self.allowmodalthreshold = False
                    self.normalthreshold = self.init_threshold
                else:
                    self.allowmodalthreshold = not self.allowmodalthreshold

            try:
                ret = self.main(self.active, modal=True)

                if not ret:
                    self.finish()
                    return {'FINISHED'}
            except Exception as e:
                self.finish()

                if bpy.context.mode == 'OBJECT':
                    bpy.ops.object.mode_set(mode='EDIT')

                output_traceback(self, e)
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'}:
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object

        self.active.update_from_editmode()

        self.init_threshold = self.normalthreshold

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        init_cursor(self, event)

        try:
            ret = self.main(self.active, modal=True)

            if not ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'Normal Flatten')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        active = context.active_object

        try:
            self.main(active)
        except Exception as e:
            output_traceback(self, e)

        return {'FINISHED'}

    def main(self, active, modal=False):
        debug = True
        debug = False

        bpy.ops.object.mode_set(mode='OBJECT')

        if modal:
            self.initbm.to_mesh(active.data)

        mesh = active.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()

        if bpy.app.version < (4, 1, 0):
            mesh.calc_normals_split()

        loop_normals = []
        for loop in mesh.loops:
            loop_normals.append(loop.normal)

        faces = [f for f in bm.faces if f.select]

        if self.clear:
            for v in (v for v in bm.verts if v.select):
                for loop in v.link_loops:
                    loop_normals[loop.index] = mathutils.Vector()

        for f in faces:

            border_faces = []
            for v in f.verts:
                for face in v.link_faces:
                    if face not in border_faces and face != f:
                        border_faces.append(face)

            edge_faces = []
            for bf in border_faces:
                for e in bf.edges:
                    if e in f.edges:
                        edge_faces.append(bf)
                        if e.smooth and math.degrees(e.calc_face_angle()) < self.normalthreshold:
                            for loop in e.link_loops:
                                loop_normals[loop.index] = f.normal
                                loop_normals[loop.link_loop_next.index] = f.normal

            for bf in border_faces:
                if bf not in edge_faces:
                    cf = bf
                    if all([e.smooth for e in cf.edges]) and math.degrees(cf.normal.angle(f.normal)) < self.normalthreshold:
                        cv = [v for v in cf.verts if v in f.verts][0]
                        loop = [l for l in cv.link_loops if l in cf.loops][0]
                        loop_normals[loop.index] = f.normal

        mesh.normals_split_custom_set(loop_normals)

        if bpy.app.version < (4, 1, 0):
            mesh.use_auto_smooth = True

        bpy.ops.object.mode_set(mode='EDIT')

        return True

class NormalStraighten(bpy.types.Operator):
    bl_idname = "machin3.normal_straighten"
    bl_label = "MACHIN3: Normal Straighten"
    bl_description = "Straighten uneven shading on straight fuse surface sections"
    bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout

        column = layout.column()

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            return len([f for f in bm.faces if f.select]) >= 2

    def execute(self, context):
        active = context.active_object

        try:
            self.main(active)
        except Exception as e:
            output_traceback(self, e)

        return {'FINISHED'}

    def main(self, active, modal=False):
        debug = True
        debug = False

        if modal:
            self.initbm.to_mesh(active.data)

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

        selected = [f for f in bm.faces if f.select]

        islands = get_selection_islands(bm, debug=debug)

        for verts, edges, faces in islands:
            for f in selected:
                if f in faces:
                    f.select_set(True)
                else:
                    f.select_set(False)

            mg = build_mesh_graph(bm, debug=debug)

            ret = get_2_rails_from_chamfer(bm, mg, verts, faces, False, debug=debug)

            if ret:
                rails, cyclic = ret

                for rail in rails:

                    for idx, rv in enumerate(rail[1:-1]):
                        re = bm.edges.get([rv, rail[idx + 2]])  # + 1 because we start witht the second vert, and + 1 becuase we want the next vert
                        if re.smooth:
                            fe = be = None
                            for e in rv.link_edges:
                                if e.other_vert(rv) in rail:
                                    continue
                                if e.select:
                                    fe = e
                                else:
                                    be = e
                            if fe and be:
                                edge_normal = get_edge_normal(fe)

                                for loop in rv.link_loops:
                                    loop_normals[loop.index] = edge_normal

        mesh.normals_split_custom_set(loop_normals)
        
        if bpy.app.version < (4, 1, 0):
            mesh.use_auto_smooth = True

        bpy.ops.object.mode_set(mode='EDIT')

        return True

class NormalTransfer(bpy.types.Operator):
    bl_idname = "machin3.normal_transfer"
    bl_label = "MACHIN3: Normal Transfer"
    bl_description = "Transfer Normals from Stash"
    bl_options = {'REGISTER'}

    mapping: EnumProperty("Mapping", items=loop_mapping_items, default="NEAREST FACE")
    xray: BoolProperty(name="X-Ray", default=False)
    alpha: FloatProperty(name="Alpha", default=0.2, min=0.01, max=0.99)
    apply_data_transfer: BoolProperty(name="Apply Normal Transfer", default=True)
    remove_vgroup: BoolProperty(name="Remove Vertex Group", default=True)
    limit_by_sharps: BoolProperty(name="Limit by Sharps", default=True)
    matcap_switch: BoolProperty(name="MatCap Switch", default=True)
    debug: BoolProperty(default=False)
    normal_offset = 0.002
    batch = None
    toggled_wires = False
    initial_matcap = ""

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            active = bpy.context.active_object
            if active and active.MM.stashes and active.mode == "EDIT":
                bm = bmesh.from_edit_mesh(active.data)
                return len([v for v in bm.verts if v.select]) >= 1

    def draw_HUD(self, context):
        if context.area == self.area:
            hintoffset = 225 if self.mapping == "NEAREST FACE" else 240 if self.mapping == "NEAREST NORMAL" else 280 if self.mapping == "NEAREST POLY NORMAL" else 200

            draw_init(self)

            draw_title(self, "Normal Transfer")

            draw_prop(self, "Stash", "%d/%d" % (self.stash.index + 1, len(self.active.MM.stashes)), hint_offset=hintoffset, hint="scroll UP/DOWN")
            self.offset += 10

            if self.stash.obj:
                draw_prop(self, "X-Ray", self.xray, offset=18, hint_offset=hintoffset, hint="toggle X")
                draw_prop(self, "Alpha", self.alpha, decimal=1, offset=18, hint_offset=hintoffset, hint="ALT scroll UP/DOWN")
                self.offset += 10

                draw_prop(self, "Flipped", self.stash.flipped, offset=18, hint_offset=hintoffset, hint="toggle F")
                self.offset += 10

                draw_prop(self, "Display", self.data_transfer.show_viewport, offset=18, hint_offset=hintoffset, hint="toggle D")

                if self.matcap_mode and self.switch_matcap and self.switch_matcap != "NOT FOUND" and self.switch_matcap != self.initial_matcap:
                    draw_prop(self, "Switch Matcap", self.matcap_switch, offset=18, hint_offset=hintoffset, hint="toggle M")

                self.offset += 10
                draw_prop(self, "Mapping", self.mapping, offset=18, hint_offset=hintoffset, hint="CTRL scroll UP/DOWN")
                draw_prop(self, "Apply Mod", self.apply_data_transfer, offset=18, hint_offset=hintoffset, hint="toggle A")

                if self.apply_data_transfer:
                    draw_prop(self, "Remove VGroup", self.remove_vgroup, offset=18, hint_offset=hintoffset, hint="toggle R")
                    draw_prop(self, "Limit by Sharps", self.limit_by_sharps, offset=18, hint_offset=hintoffset, hint="toggle L")

            else:
                draw_prop(self, "INVALID", "Stash Object Not Found", offset=18, HUDcolor=(1, 0, 0))

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.batch:
                draw_mesh_wire(self.batch, color=white, alpha=self.alpha, xray=self.xray)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        if event.type in {'WHEELUPMOUSE', 'ONE'} and event.value == 'PRESS':
            if event.alt:
                self.alpha += 0.1

            elif event.ctrl:
                self.mapping = step_enum(self.mapping, loop_mapping_items, 1)
                self.data_transfer.loop_mapping = loop_mapping_dict[self.mapping]

            else:
                self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", -1)

                if self.stash.obj:
                    offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
                    self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

                    self.data_transfer.object = self.stash.obj

                else:
                    self.batch = None

        elif event.type in {'WHEELDOWNMOUSE', 'TWO'} and event.value == 'PRESS':
            if event.alt:
                self.alpha -= 0.1

            elif event.ctrl:
                self.mapping = step_enum(self.mapping, loop_mapping_items, -1)
                self.data_transfer.loop_mapping = loop_mapping_dict[self.mapping]

            else:
                self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", 1)

                if self.stash.obj:
                    offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
                    self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

                    self.data_transfer.object = self.stash.obj

        if self.stash.obj:

            if event.type == 'F' and event.value == 'PRESS':

                if self.stash.obj:
                    flip_normals(self.stash.obj.data)

                    self.stash.flipped = not self.stash.flipped

            if event.type == 'S' and event.value == 'PRESS':
                if self.stash.obj:
                    shade(self.stash.obj.data, smooth=True)

            if event.type == 'M' and event.value == 'PRESS':
                if self.matcap_mode and self.switch_matcap and self.switch_matcap != "NOT FOUND" and self.switch_matcap != self.initial_matcap:
                    self.matcap_switch = not self.matcap_switch
                    self.shading.studio_light = self.switch_matcap if self.matcap_switch else self.initial_matcap

            elif event.type == 'X' and event.value == 'PRESS':
                self.xray = not self.xray

            elif event.type == 'D' and event.value == 'PRESS':
                self.data_transfer.show_viewport = not self.data_transfer.show_viewport

            elif event.type == 'A' and event.value == 'PRESS':
                self.apply_data_transfer = not self.apply_data_transfer

            elif event.type == 'R' and event.value == 'PRESS':
                self.remove_vgroup = not self.remove_vgroup

            elif event.type == 'L' and event.value == 'PRESS':
                self.limit_by_sharps = not self.limit_by_sharps

        if event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            if self.stash.obj:
                if self.apply_data_transfer:

                    apply_mod(self.data_transfer.name)

                    if self.remove_vgroup:
                        vgroup = get_vgroup(self, self.active, 'normal_transfer')

                        print(f"INFO: removing {vgroup.name}")
                        self.active.vertex_groups.remove(vgroup)

                    if self.limit_by_sharps:

                        if get_prefs().experimental:
                            remerge_sharp_edges(self.active)

                        else:
                            normal_clear_across_sharps(self.active)

            else:

                self.active.modifiers.remove(self.data_transfer)

                vgroup = get_vgroup(self, self.active, 'normal_transfer')

                print(f"INFO: removing {vgroup.name}")
                self.active.vertex_groups.remove(vgroup)

            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:

            self.active.modifiers.remove(self.data_transfer)

            vgroup = get_vgroup(self, self.active, 'normal_transfer')

            print(f"INFO: removing {vgroup.name}")
            self.active.vertex_groups.remove(vgroup)

            self.finish()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

        bpy.ops.object.mode_set(mode='EDIT')

        if self.matcap_switch:
            self.shading.studio_light = self.initial_matcap

        if self.toggled_wires:
            self.active.show_wire = True

    def invoke(self, context, event):
        self.active = context.active_object

        if self.active.show_wire:
            self.active.show_wire = False
            self.toggled_wires = True

        vgroup, self.data_transfer = normal_transfer_from_stash(self.active, mapping=self.mapping)

        if not vgroup:
            return {'CANCELLED'}

        set_vgroup(self, vgroup, 'normal_transfer')

        self.stash = self.active.MM.stashes[self.active.MM.active_stash_idx]

        if self.stash.obj:
            offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
            self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

        else:
            self.batch = None

        self.shading = context.space_data.shading
        self.matcap_mode = self.shading.type == 'SOLID' and self.shading.light == 'MATCAP'
        self.switch_matcap = get_prefs().matcap
        self.initial_matcap = self.shading.studio_light

        init_cursor(self, event)

        if self.matcap_mode and self.matcap_switch and self.switch_matcap and self.switch_matcap != 'NOT FOUND' and self.switch_matcap != self.initial_matcap:
            self.shading.studio_light = self.switch_matcap

        init_status(self, context, 'Normal Transfer')

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class NormalClear(bpy.types.Operator):
    bl_idname = "machin3.normal_clear"
    bl_label = "MACHIN3: Normal Clear"
    bl_description = "Reset normals of the selected geometry, keep unselected geo as is"
    bl_options = {'REGISTER', 'UNDO'}

    limit_to_selection: BoolProperty(name="Limit to Selection", default=False)
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, "limit_to_selection")

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            mesh = context.active_object.data
            bm = bmesh.from_edit_mesh(mesh)
            return mesh.has_custom_normals and len([v for v in bm.verts if v.select]) >= 1

    def execute(self, context):
        active = context.active_object

        try:
            normal_clear(active, limit=self.limit_to_selection)
        except Exception as e:
            output_traceback(self, e)

        return {'FINISHED'}
