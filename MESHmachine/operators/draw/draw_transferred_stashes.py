import bpy
from bpy.props import FloatProperty
from ... utils.mesh import get_coords
from ... utils.draw import draw_mesh_wire
from ... utils.registration import get_prefs
from ... utils.ui import init_timer_modal, set_countdown, get_timer_progress

class DrawTransferredStashes(bpy.types.Operator):
    bl_idname = "machin3.draw_transferred_stashes"
    bl_label = "MACHIN3: Draw Transferred Stashes"

    time: FloatProperty(name="Time (s)", default=1.5)
    alpha: FloatProperty(name="Alpha", default=0.3, min=0.1, max=1)
    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha

            for batch in self.batches:
                draw_mesh_wire(batch, alpha=alpha)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        else:
            context.window_manager.event_timer_remove(self.TIMER)

            bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
            return {'FINISHED'}

        if self.countdown < 0:

            context.window_manager.event_timer_remove(self.TIMER)

            bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def execute(self, context):
        active = context.active_object
        mx = active.matrix_world

        from .. stash import transferred_stash_meshes

        self.batches = []
        for mesh in transferred_stash_meshes:
            self.batches.append(get_coords(mesh, mx=mx, indices=True))

        init_timer_modal(self)

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.05, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
