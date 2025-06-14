import bpy
from bpy.props import FloatProperty, BoolProperty, IntProperty
from ... utils.mesh import get_coords
from ... utils.draw import draw_points
from ... utils.registration import get_prefs
from ... utils.ui import init_timer_modal, set_countdown, get_timer_progress
from ... colors import normal, white, red

class DrawSymmetrize(bpy.types.Operator):
    bl_idname = "machin3.draw_symmetrize"
    bl_label = "MACHIN3: Draw Symmetrize"

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=0.3, min=0.1, max=1)
    normal_offset = 0.002

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha * (10 if self.remove else 1)

            draw_points(self.coords, indices=self.indices, color=self.color, size=6, alpha=alpha, xray=False)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        else:
            self.finish(context)
            return {'FINISHED'}

        if self.countdown < 0:
            self.finish(context)

            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        context.window_manager.event_timer_remove(self.TIMER)
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

    def execute(self, context):
        active = context.active_object
        mx = active.matrix_world
        offset = sum([d for d in active.dimensions]) / 3 * self.normal_offset

        from .. symmetrize import vert_ids, custom_normals, remove

        self.indices = vert_ids
        self.color = red if remove else normal if custom_normals else white
        self.remove = remove

        self.coords = get_coords(active.data, mx=mx, offset=offset)

        init_timer_modal(self)

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.05, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
