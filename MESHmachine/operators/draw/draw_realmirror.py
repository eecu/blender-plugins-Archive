import bpy
from bpy.props import FloatProperty
from ... utils.mesh import get_coords
from ... utils.draw import draw_points
from ... utils.registration import get_prefs
from ... colors import normal, white
from ... utils.ui import init_timer_modal, set_countdown, get_timer_progress

class DrawRealMirror(bpy.types.Operator):
    bl_idname = "machin3.draw_realmirror"
    bl_label = "MACHIN3: Draw RealMirror"

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=0.3, min=0.1, max=1)
    normal_offset = 0.002

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha

            for coords, color in self.batches:
                draw_points(coords, color=color, alpha=alpha)

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
        from .. real_mirror import mirrored, custom_normals

        self.batches = []

        for obj, cn in zip(mirrored, custom_normals):
            offset = sum([d for d in obj.dimensions]) / 3 * self.normal_offset
            coords = get_coords(obj.data, mx=obj.matrix_world, offset=offset)
            color = normal if cn else white
            self.batches.append((coords, color))

        init_timer_modal(self)

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.05, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
