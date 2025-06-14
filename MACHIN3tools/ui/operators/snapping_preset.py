import bpy
from bpy.props import StringProperty, BoolProperty

from ... utils.draw import draw_fading_label
from ... utils.registration import get_prefs
from ... utils.snap import get_sorted_snap_elements
from ... utils.ui import get_mouse_pos

from ... colors import white, yellow, blue

class SetSnappingPreset(bpy.types.Operator):
    bl_idname = "machin3.set_snapping_preset"
    bl_label = "MACHIN3: Set Snapping Preset"
    bl_description = "Set Snapping Preset"
    bl_options = {'REGISTER', 'UNDO'}

    additive: BoolProperty(name="Additive Snap Elements", default=False)
    element: StringProperty(name="Snap Element")
    target: StringProperty(name="Snap Target")
    align_rotation: BoolProperty(name="Align Rotation")

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        column = layout.column()
        ts = context.scene.tool_settings

        column.label(text=f"Elements: {', '.join(e for e in ts.snap_elements)}")
        column.label(text=f"Target: {self.target}")

        if self.element not in ['INCREMENT', 'VOLUME']:
            column.label(text=f"Align Rotation: {self.align_rotation}")

    @classmethod
    def description(cls, context, properties):
        desc = "Set Snapping Preset"

        if properties.element == 'VERTEX':
            desc += "\n  VERTEX"

        elif properties.element == 'EDGE':
            desc += "\n  EDGE"

        elif properties.element == 'FACE' and properties.align_rotation:
            desc += "\n  FACE + Align Rotation"

        elif properties.element == 'FACE_NEAREST':
            desc += "\n  FACE_NEAREST"

        elif properties.element in ['INCREMENT', 'GRID']:
            desc += "\n  GRID"

        elif properties.element == 'VOLUME':
            desc += "\n  VOLUME"

        desc += "\n\nALT: Set Snap Element additively"
        return desc

    def invoke(self, context, event):
        self.additive = event.alt

        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        ts = context.scene.tool_settings

        if self.additive:
            ts.snap_elements |= {self.element}

        else:
            ts.snap_elements = {self.element}

        if self.element == 'INCREMENT':
            ts.use_snap_grid_absolute = True

        elif self.element == 'VOLUME':
            pass

        else:
            ts.snap_target = self.target
            ts.use_snap_align_rotation = self.align_rotation

        text = ["Additive Snapping" if self.additive else "Snapping"]
        color = [yellow if self.additive else white, white]
        alpha = [1 if self.additive else 0.7, 1]

        text.append(ts.snap_target + " | " + " + ".join(get_sorted_snap_elements(ts, title=False)))

        if ts.use_snap_align_rotation:
            text.append("Align Rotation")
            color.append(blue)

        if get_prefs().snap_draw_HUD:
            time = 2 if self.additive else 1
            draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, center=False, color=color, alpha=alpha, move_y=10 * time, time=time)
        return {'FINISHED'}
