import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty
import bmesh
from .. utils.tool import flatten_verts, flatten_faces
from .. utils.draw import draw_lines, draw_points
from .. utils.developer import output_traceback
from .. utils.ui import draw_init, draw_title, draw_prop, init_cursor, wrap_cursor, update_HUD_location
from .. utils.ui import init_status, finish_status
from .. utils.property import step_enum
from .. items import flatten_mode_items

class Flatten(bpy.types.Operator):
    bl_idname = "machin3.flatten"
    bl_label = "MACHIN3: Flatten"
    bl_description = "Flatten Polygon(s) along Edges or Normal"
    bl_options = {'REGISTER', 'UNDO'}

    flatten_mode: EnumProperty(name="Mode", items=flatten_mode_items, default="EDGE")
    dissolve: BoolProperty(name="Dissolve", default=True)
    face_mode: BoolProperty(name="Face Mode", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)

            if tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True):
                return bm.faces.active and len([f for f in bm.faces if f.select])

            else:
                verts = [v for v in bm.verts if v.select]
                vert_faces = [{f for f in v.link_faces} for v in verts if v.link_faces]

                if len(verts) == len(vert_faces) == 3:
                    return len(vert_faces[0].intersection(vert_faces[1], vert_faces[2])) == 1

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.prop(self, "flatten_mode", expand=True)

        if self.face_mode:
            column.prop(self, "dissolve")

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            subtitle = "Face mode" if self.face_mode else "Vert mode"

            draw_title(self, "Flatten", subtitle=subtitle, subtitleoffset=125)

            draw_prop(self, "Flatten Along", self.flatten_mode, hint="scroll UP/DOWN")
            if self.face_mode:
                draw_prop(self, "Dissolve", self.dissolve, offset=18, hint="toggle D")

    def draw_VIEW3D(self, context):
        if context.scene.MM.debug and self.coords:
            draw_lines(self.coords, mx=self.active.matrix_world, color=(0.5, 0.5, 1) if self.flatten_mode == "NORMAL" else (0.1, 0.4, 1))
            draw_points([self.coords[idx] for idx in range(0, len(self.coords), 2)], mx=self.active.matrix_world)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'ONE', 'TWO', 'D']

        if event.type in events:

            if event.type in ['WHEELUPMOUSE', 'ONE'] and event.value == "PRESS":
                self.flatten_mode = step_enum(self.flatten_mode, flatten_mode_items, 1)

            elif event.type in ['WHEELDOWNMOUSE', 'TWO'] and event.value == "PRESS":
                self.flatten_mode = step_enum(self.flatten_mode, flatten_mode_items, -1)

            elif event.type == 'D' and event.value == "PRESS":
                self.dissolve = not self.dissolve

            try:
                ret = self.main(self.active, modal=True)

                if ret is False:
                    self.finish()
                    return {'FINISHED'}
            except Exception as e:
                self.finish()

                output_traceback(self, e)
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish()

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

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

        self.coords = []

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        init_cursor(self, event)

        try:
            self.ret = self.main(self.active, modal=True)
            if not self.ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'Flatten')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

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

        bm = bmesh.new()
        bm.from_mesh(active.data)

        bm.normal_update()
        bm.verts.ensure_lookup_table()

        verts = [v for v in bm.verts if v.select]
        edges = [e for e in bm.edges if e.select]
        faces = [f for f in bm.faces if f.select]

        if len(faces) > 1:
            self.face_mode = True
            self.coords = flatten_faces(bm, edges, self.flatten_mode, self.dissolve, debug=debug)
        else:
            self.face_mode = False
            self.coords = flatten_verts(bm, verts, self.flatten_mode, debug=debug)

        bm.normal_update()
        bm.to_mesh(active.data)

        bpy.ops.object.mode_set(mode='EDIT')
        return True
