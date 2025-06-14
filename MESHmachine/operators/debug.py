import bpy
import blf
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty
import bmesh
from .. items import fuse_method_items, handle_method_items, tension_preset_items, side_selection_items
from .. utils.graph import build_mesh_graph
from .. utils.selection import get_2_rails_from_chamfer, get_sides, get_selected_vert_sequences
from .. utils.sweep import init_sweeps
from .. utils.loop import get_loops
from .. utils.handle import create_loop_intersection_handles, create_face_intersection_handles
from .. utils.math import get_angle_between_edges
from .. utils.ui import draw_init, draw_title, draw_prop, init_cursor, wrap_cursor, popup_message
from .. utils.developer import output_traceback
from .. utils.property import step_enum, step_collection
from .. utils.mesh import hide, unhide, select, deselect, unhide_select, unhide_deselect
from .. utils.object import add_facemap
from .. utils.vgroup import add_vgroup
from .. utils.draw import draw_point, draw_vector, draw_vectors, draw_line, draw_points
import math

class DebugWhatever(bpy.types.Operator):
    bl_idname = "machin3.debug_whatever"
    bl_label = "MACHIN3: Debug Whatever"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return {'FINISHED'}

class DebugToggle(bpy.types.Operator):
    bl_idname = "machin3.meshmachine_debug"
    bl_label = "MACHIN3: Debug MESHmachine"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mm = context.scene.MM
        mm.debug = not mm.debug

        return {'FINISHED'}

class GetAngle(bpy.types.Operator):
    bl_idname = "machin3.get_angle"
    bl_label = "MACHIN3: Get Angle"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = context.active_object
        mesh = active.data

        bpy.ops.object.mode_set(mode='OBJECT')

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()

        edges = [e for e in bm.edges if e.select]

        if len(edges) == 1:
            e = edges[0]

            angle = math.degrees(e.calc_face_angle())
            print("angle between two faces:", angle)

        elif len(edges) == 2:
            e1 = edges[0]
            e2 = edges[1]

            angle = get_angle_between_edges(e1, e2, radians=False)
            print("angle between two faces:", angle)

        bm.to_mesh(mesh)

        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

class GetLength(bpy.types.Operator):
    bl_idname = "machin3.get_length"
    bl_label = "MACHIN3: Get Length"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
            active = context.active_object
            mesh = active.data

            bpy.ops.object.mode_set(mode='OBJECT')

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bm.normal_update()

            edges = [e for e in bm.edges if e.select]

            for edge in edges:
                print("edge:", edge.index, "length:", edge.calc_length())

            bm.to_mesh(mesh)

            bpy.ops.object.mode_set(mode='EDIT')

            return {'FINISHED'}

class DrawDebug(bpy.types.Operator):
    bl_idname = "machin3.draw_debug"
    bl_label = "MACHIN3: Draw Debug"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = context.active_object
        mxw = active.matrix_world

        bm = bmesh.from_edit_mesh(active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        faces = [f for f in bm.faces if f.select]

        for f in faces:
            center = f.calc_center_median()
            draw_point(center, mx=mxw, modal=False)

            draw_vector(f.normal, origin=center, mx=mxw, color=(1, 0, 0), modal=False)

            co = f.verts[0].co
            coords = [center, co]

            draw_line(coords, mx=mxw, color=(1, 1, 0), modal=False)

        context.area.tag_redraw()

        return {'FINISHED'}

class DebugHUD(bpy.types.Operator):
    bl_idname = "machin3.debug_hud"
    bl_label = "MACHIN3: Debug HUD"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(name="Method", items=fuse_method_items, default="FUSE")
    handlemethod: EnumProperty(name="Unchamfer Method", items=handle_method_items, default="FACE")
    segments: IntProperty(name="Segments", default=6, min=0, max=30)
    tension: FloatProperty(name="Tension", default=0.7, min=0.01, max=4, step=0.1)
    tension_preset: EnumProperty(name="Tension Presets", items=tension_preset_items, default="CUSTOM")
    average: BoolProperty(name="Average Tension", default=False)
    force_projected_loop: BoolProperty(name="Force Projected Loop", default=False)
    width: FloatProperty(name="Width (experimental)", default=0.0, step=0.1)
    passthrough: BoolProperty(default=False)
    allowmodalwidth: BoolProperty(default=False)
    allowmodaltension: BoolProperty(default=False)
    def draw(self, context):
        layout = self.layout
        column = layout.column()

        row = column.row()
        row.prop(self, "method", expand=True)
        column.separator()

        if self.method == "Debug HUDE":
            row = column.row()
            row.prop(self, "handlemethod", expand=True)
            column.separator()

        column.prop(self, "segments")
        column.prop(self, "tension")
        row = column.row()
        row.prop(self, "tension_preset", expand=True)

        if self.method == "FUSE":
            column.prop(self, "force_projected_loop")

            column.separator()
            column.prop(self, "width")

    def draw_HUD(self, context):
        if context.area == self.area:

            draw_init(self)

            draw_title(self, "Debug HUD")

            draw_prop(self, "Method", self.method, offset=0, hint="SHIFT scroll UP/DOWN,")
            if self.method == "FUSE":
                draw_prop(self, "Handles", self.handlemethod, offset=18, hint="CTRL scroll UP/DOWN")
            self.offset += 10

            draw_prop(self, "Segments", self.segments, offset=18, hint="scroll UP/DOWN")
            draw_prop(self, "Tension", self.tension, offset=18, decimal=2, active=self.allowmodaltension, hint="move UP/DOWN, toggle T, presets Z/Y, X, C, V")

            if self.method == "FUSE":
                draw_prop(self, "Projected Loops", self.force_projected_loop, offset=18, hint="toggle P")

                self.offset += 10

                draw_prop(self, "Width", self.width, offset=18, decimal=3, active=self.allowmodalwidth, hint="move LEFT/RIGHT, toggle W, reset ALT + W")
                self.offset += 10

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)

        events = ['WHEELUPMOUSE', 'UP_ARROW', 'ONE', 'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO', 'R', 'S', 'F', 'Y', 'Z', 'X', 'C', 'V', 'W', 'T', 'A', 'P']

        if any([self.allowmodalwidth, self.allowmodaltension]):
            events.append('MOUSEMOVE')

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalwidth:
                        divisor = 100 if event.shift else 1 if event.ctrl else 10

                        delta_x = event.mouse_x - self.last_mouse_x
                        delta_width = delta_x / divisor

                        self.width += delta_width

                    if self.allowmodaltension:
                        divisor = 1000 if event.shift else 10 if event.ctrl else 100

                        delta_y = event.mouse_y - self.last_mouse_y
                        delta_tension = delta_y / divisor

                        self.tension_preset = "CUSTOM"
                        self.tension += delta_tension

            elif event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE'} and event.value == 'PRESS':
                if event.shift:
                    self.method = step_enum(self.method, fuse_method_items, 1)
                elif event.ctrl:
                    self.handlemethod = step_enum(self.handlemethod, handle_method_items, 1)
                else:
                    self.segments += 1

            elif event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO'} and event.value == 'PRESS':
                if event.shift:
                    self.method = step_enum(self.method, fuse_method_items, -1)
                elif event.ctrl:
                    self.handlemethod = step_enum(self.handlemethod, handle_method_items, -1)
                else:
                    self.segments -= 1

            elif (event.type == 'Y' or event.type == 'Z') and event.value == "PRESS":
                self.tension_preset = "0.55"

            elif event.type == 'X' and event.value == "PRESS":
                self.tension_preset = "0.7"

            elif event.type == 'C' and event.value == "PRESS":
                self.tension_preset = "1"

            elif event.type == 'V' and event.value == "PRESS":
                self.tension_preset = "1.33"

            elif event.type == 'W' and event.value == "PRESS":
                if event.alt:
                    self.allowmodalwidth = False
                    self.width = 0
                else:
                    self.allowmodalwidth = not self.allowmodalwidth

            elif event.type == 'T' and event.value == "PRESS":
                self.allowmodaltension = not self.allowmodaltension

            elif event.type == 'P' and event.value == "PRESS":
                self.force_projected_loop = not self.force_projected_loop

        elif event.type in {'MIDDLEMOUSE'}:
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

    def invoke(self, context, event):
        init_cursor(self, event)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class GetSides(bpy.types.Operator):
    bl_idname = "machin3.get_sides"
    bl_label = "MACHIN3: Get Sides"
    bl_options = {'REGISTER', 'UNDO'}

    sideselection = EnumProperty(name="Side", items=side_selection_items, default="A")
    sharp = BoolProperty(default=False)
    debuginit = BoolProperty(default=True)

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.prop(self, "sideselection", expand=True)

    def execute(self, context):
        active = context.active_object

        try:
            self.main(active)
        except Exception as e:
            output_traceback(self, e)

        return {'FINISHED'}

    def main(self, active, modal=False):
        debug = False

        if debug:
            m3.clear()
            if self.debuginit:
                m3.debug_idx()
                self.debuginit = False

        mesh = active.data

        m3.set_mode("OBJECT")

        if modal:
            self.initbm.to_mesh(active.data)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        verts = [v for v in bm.verts if v.select]
        edges = [e for e in bm.edges if e.select]

        if any([not e.smooth for e in edges]):
            self.sharp = True

        sideA, sideB, cyclic, err = get_sides(bm, verts, edges, debug=debug)

        if sideA and sideB:
            print("cyclic:", cyclic)

            if self.sideselection == "A":
                for sA in sideA:
                    if sA["edges"]:
                        sA["edges"][0].select = True

            else:
                for sB in sideB:
                    if sB["edges"]:
                        sB["edges"][0].select = True

            bm.to_mesh(mesh)
            m3.set_mode("EDIT")

            return True
        else:
            popup_message(err[0], title=err[1])
            m3.set_mode("EDIT")

            return False

        bm.to_mesh(mesh)
        m3.set_mode("EDIT")

        return True

class DrawTimer(bpy.types.Operator):
    bl_idname = "machin3.draw_timer"
    bl_label = "Draw Timer"
    bl_options = {'REGISTER'}

    countdown = FloatProperty(name="Countdown (s)", default=2)
    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            alpha = self.countdown / self.time
            title = "Draw Timer"
            subtitle = "%.*fs" % (1, self.countdown)
            subtitleoffset = 200

            HUDcolor = m3.MM_prefs().modal_hud_color

            blf.position(self.font_id, self.HUDx - 7, self.HUDy, 0)
            blf.size(self.font_id, 20)
            blf.draw(self.font_id, "• " + title)

            if subtitle:
                blf.position(self.font_id, self.HUDx - 7 + subtitleoffset, self.HUDy, 0)
                blf.size(self.font_id, 15)
                blf.draw(self.font_id, subtitle)

            draw_end()

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            self.mouse_x = event.mouse_x
            self.mouse_y = event.mouse_y

        if self.countdown < 0:

            context.window_manager.event_timer_remove(self.TIMER)

            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
            return {'FINISHED'}

        if event.type == 'TIMER':
            self.countdown -= 0.1

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        self.time = self.countdown

        self.mouse_x = self.init_mouse_x = self.fixed_mouse_x = event.mouse_x
        self.mouse_y = self.init_mouse_y = self.fixed_mouse_y = event.mouse_y

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.TIMER = context.window_manager.event_timer_add(0.1, context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class DrawStash(bpy.types.Operator):
    bl_idname = "machin3.draw_stash"
    bl_label = "MACHIN3: Draw Stash"
    bl_options = {'REGISTER', 'UNDO'}

    xray = BoolProperty(name="X-Ray", default=False)
    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.stash.obj:
                mesh = self.stash.obj.data

                offset = sum([d for d in self.active.dimensions]) / 3 * 0.001

                edgewidth = 2
                edgecolor = (1.0, 1.0, 1.0, 0.75)

                for edge in mesh.edges:
                    v1 = mesh.vertices[edge.vertices[0]]
                    v2 = mesh.vertices[edge.vertices[1]]

                    v1co = v1.co + v1.normal * offset + self.active.location
                    v2co = v2.co + v2.normal * offset + self.active.location

                draw_end()

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Draw Stash")

            draw_prop(self, "Stash", self.stash.index, key="scroll UP/DOWN")
            self.offset += 10

            if self.stash.obj:
                draw_prop(self, "X-Ray", self.xray, offset=18, key="toggle X")
            else:
                draw_prop(self, "INVALID", "Stash Object Not Found", offset=18, HUDcolor=(1, 0, 0))

            draw_end()

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            self.mouse_x = event.mouse_x
            self.mouse_y = event.mouse_y

        if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE'} and event.value == 'PRESS':
            self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", 1)

        elif event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO'} and event.value == 'PRESS':
            self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", -1)

        if self.stash.obj:
            if event.type == 'X' and event.value == 'PRESS':
                self.xray = not self.xray

        if event.type in {'MIDDLEMOUSE'}:
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:

            bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.active = context.active_object

        if self.active.MM.stashes:
            self.stash = self.active.MM.stashes[self.active.MM.active_stash_idx]

            self.mouse_x = self.init_mouse_x = self.fixed_mouse_x = event.mouse_x
            self.mouse_y = self.init_mouse_y = self.fixed_mouse_y = event.mouse_y

            self.area = context.area
            self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
            self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            print("%s has no stashes" % (self.active.name))
            return {'CANCELLED'}

class VertexInfo(bpy.types.Operator):
    bl_idname = "machin3.vertex_info"
    bl_label = "MACHIN3: Vertex Info"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = context.active_object

        bm = bmesh.new()
        bm.from_mesh(active.data)
        bm.verts.ensure_lookup_table()

        verts = [v for v in bm.verts if v.select]

        for v in verts:
            print("vert:", v)

            print("loops:")
            for l in v.link_loops:
                print(" •", l)

            print("edges:")
            for e in v.link_edges:
                print(" •", e)

        return {'FINISHED'}

class RayCast(bpy.types.Operator):
    bl_idname = "machin3.raycast"
    bl_label = "Raycast"
    bl_options = {'REGISTER', 'UNDO'}

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            self.mouse_x = event.mouse_x
            self.mouse_y = event.mouse_y

        elif event.type == "LEFTMOUSE" and event.value == 'PRESS':
            m3.clear()

            print("mouse:", self.mouse_x, self.mouse_y)

            coord = (self.mouse_x, self.mouse_y)
            obj, coords, normal, face_idx = cast_ray(context, coord, exclude_objs=[context.active_object])

            print("object:", obj)
            print("coords:", coords)
            print("normal:", normal)
            print("face_idx:", face_idx)

        elif event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        elif event.type in {'SPACE'}:
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

class GetLoopsHandles(bpy.types.Operator):
    bl_idname = "machin3.loops_or_handles"
    bl_label = "MACHIN3: Loops or Handles"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Create rounded Bevels from Chamfers"

    loops_or_handles = EnumProperty(name="Get Loops or Handles", items=[('LOOPS', "Loops", ""),
                                                                        ('HANDLES', "Handles", "")], default="LOOPS")
    handlemethod = EnumProperty(name="Unchamfer Method", items=handle_method_items, default="FACE")
    tension = FloatProperty(name="Tension", default=1, min=0.01, max=4, step=0.1)
    average = BoolProperty(name="Average Tension", default=False)
    force_projected = BoolProperty(name="Force Projected Loops", default=False)
    reverse = BoolProperty(name="Reverse", default=False)
    cyclic = BoolProperty(name="Cyclic", default=False)
    single = BoolProperty(name="Single", default=False)

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        row = column.row()
        row.prop(self, "loops_or_handles", expand=True)
        column.separator()

        row = column.row()
        row.prop(self, "handlemethod", expand=True)
        column.separator()

        column.prop(self, "tension")

        if self.handlemethod == "FACE":
            column.prop(self, "average")

        column.separator()
        column.prop(self, "force_projected")

        if self.single:
            column.separator()
            column.prop(self, "reverse")

    def execute(self, context):
        active = context.active_object

        self.main(active)

        return {'FINISHED'}

    def main(self, active):
        debug = True

        if debug:
            m3.clear()
            m3.debug_idx()

        m3.set_mode("OBJECT")

        bm = bmesh.new()
        bm.from_mesh(active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        mg = build_mesh_graph(bm, debug=debug)
        verts = [v for v in bm.verts if v.select]
        faces = [f for f in bm.faces if f.select]

        if len(faces) == 1:
            self.single = True
        else:
            self.single = False

        ret = get_2_rails(bm, mg, verts, faces, self.reverse, debug=debug)

        if ret:
            rails, self.cyclic = ret

            sweeps = init_sweeps(bm, active, rails, debug=debug)

            get_loops(bm, faces, sweeps, force_projected=self.force_projected, debug=debug)

            for f in faces:
                f.select = False

            if self.loops_or_handles == "HANDLES":
                if self.handlemethod == "FACE":
                    create_face_intersection_handles(bm, sweeps, tension=self.tension, average=self.average, debug=debug)
                elif self.handlemethod == "LOOP":
                    create_loop_intersection_handles(bm, sweeps, self.tension, debug=debug)

        bm.to_mesh(active.data)

        m3.set_mode("EDIT")

        if self.loops_or_handles == "HANDLES":
            m3.set_mode("VERT")
            m3.unselect_all("MESH")

        return False

    def clean_up(self, bm, sweeps, faces, magicloop=True, initialfaces=True, debug=False):
        if magicloop:
            magic_loops = []

            for sweep in sweeps:
                for idx, lt in enumerate(sweep["loop_types"]):
                    if lt in ["MAGIC", "PROJECTED"]:
                        magic_loops.append(sweep["loops"][idx])

            magic_loop_ids = [str(l.index) for l in magic_loops]

            bmesh.ops.delete(bm, geom=magic_loops, context=2)

            if debug:
                print()
                print("Removed magic and projected loops:", ", ".join(magic_loop_ids))

        if initialfaces:
            face_ids = [str(f.index) for f in faces]

            bmesh.ops.delete(bm, geom=faces, context=5)

            if debug:
                print()
                print("Removed faces:", ", ".join(face_ids))

        if not debug:
            for v in bm.verts:
                v.select = False

            bm.select_flush(False)

class GetFacesLinkedToVerts(bpy.types.Operator):
    bl_idname = "machin3.get_faces_linked_to_verts"
    bl_label = "MACHIN3: Get Faces Linked to Verts"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = context.active_object
        m3.debug_idx()

        m3.set_mode("OBJECT")

        bm = bmesh.new()
        bm.from_mesh(active.data)
        bm.normal_update()

        verts = [v for v in bm.verts if v.select]

        for v in verts:
            print(v)
            for f in v.link_faces:
                print(f)
            print()

        bm.to_mesh(active.data)

        m3.set_mode("EDIT")

        return {'FINISHED'}
