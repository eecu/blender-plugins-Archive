import bpy
from bpy.props import FloatProperty, StringProperty, FloatVectorProperty, BoolProperty, IntProperty
from mathutils import Vector
from ... utils.draw import draw_label
from ... utils.ui import finish_modal_handlers, get_scale, init_modal_handlers, set_countdown, get_timer_progress

class DrawLabel(bpy.types.Operator):
    bl_idname = "machin3.draw_label"
    bl_label = "MACHIN3: Draw Label"
    bl_description = ""
    bl_options = {'INTERNAL'}

    text: StringProperty(name="Text to draw the HUD", default='Text')
    size: FloatProperty(name="Text Size", default=12)
    coords: FloatVectorProperty(name='Screen Coordinates', size=2, default=(100, 100))
    center: BoolProperty(name='Center', default=True)
    color: FloatVectorProperty(name='Screen Coordinates', size=3, default=(1, 1, 1))
    alpha: FloatProperty(name="Alpha", default=0.5, min=0.1, max=1)
    move_y: IntProperty(name="Move Up or Down", default=0)
    time: FloatProperty(name="", default=1, min=0.1)
    cancel: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'VIEW_3D'

    def draw_HUD(self, context):
        try:
            if context.area == self.area:
                prog = get_timer_progress(self)
                alpha = prog * self.alpha

                coords = Vector(self.coords)

                if self.move_y:
                    coords += Vector((0, self.move_y * (1 - prog) * get_scale(context)))

                draw_label(context, title=self.text, coords=coords, center=self.center, size=self.size, color=self.color, alpha=alpha)

        except ReferenceError:
            pass

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        else:
            self.finish(context)
            return {'FINISHED'}

        if self.cancel:
            pass

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        finish_modal_handlers(self)

    def execute(self, context):
        init_modal_handlers(self, context, hud=True, timer=True, time_step=0.01 if self.move_y else 0.1)
        return {'RUNNING_MODAL'}
