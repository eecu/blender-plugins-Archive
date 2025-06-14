import bpy
from .. utils.registration import get_prefs 
from .. utils.ui import get_keymap_item, get_icon
from .. import bl_info

class MenuCURVEmachine(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_curve_machine"
    bl_label = "CURVEmachine %s" % ('.'.join([str(v) for v in bl_info['version']]))

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE'

    def draw(self, context):
        draw_menu_edit_curve(self, context, context_menu=False)

def draw_menu_edit_curve(self, context, context_menu=False):
    layout = self.layout

    active = context.active_object
    curve = active.data
    active_spline = curve.splines.active

    has_tilt = len(set(point.tilt for point in active_spline.points)) - 1 if active_spline else 0
    has_radius = len(set(point.radius for point in active_spline.points)) - 1 if active_spline else 0
    has_geo = curve.bevel_depth or curve.extrude

    is_nurbs = active_spline.type == 'NURBS' if active_spline else False
    has_resolution_along = active_spline.type in ['NURBS', 'BEZIER'] if active_spline else False

    has_only_bezier = all(spline.type == 'BEZIER' for spline in curve.splines)

    show_delete = get_keymap_item('Curve', 'wm.call_menu', 'X', properties=[('name', 'MACHIN3_MT_curve_machine')]) and get_prefs().show_delete
    show_curve_split = get_keymap_item('Curve', 'wm.call_menu', 'Y', properties=[('name', 'MACHIN3_MT_curve_machine')]) and get_prefs().show_curve_split

    layout.operator_context = "INVOKE_DEFAULT"

    if get_prefs().update_available:
        layout.label(text="A new version is available!", icon_value=get_icon("refresh_green"))
        layout.separator()

    if has_only_bezier:
        layout.label(text="Limited BEZIER Support!", icon_value=get_icon("error"))
        layout.separator()

        layout.operator("curve.make_segment", text="Connect")

    else:

        layout.operator("machin3.bendulate", text="Blendulate")

        if has_tilt or has_radius:
            layout.operator("machin3.interpolate_points", text="Interpolate")

        layout.separator()

        layout.operator("machin3.slide_point", text="Slide")

        layout.operator("machin3.symmetrize_curve", text="Symmetrize")

        layout.separator()

        layout.operator("machin3.merge_to_last_point", text="Merge to Last")

        layout.operator("machin3.merge_to_center", text="Merge to Center")

        layout.operator("curve.make_segment", text="Connect")

        layout.separator()

        layout.operator("machin3.curve_knife", text="Knife")

        layout.separator()

        layout.operator("machin3.gap_shuffle", text="Gap Shuffle")

        layout.operator("machin3.reverse_spline", text="Reverse")

    if active_spline:

        layout.prop(active_spline, "use_cyclic_u", text="Cyclic")

        if is_nurbs:
            layout.prop(active_spline, "use_endpoint_u", text="Endpoint")

        if has_geo:
            layout.prop(active_spline, "use_smooth", text="Smooth")

    layout.separator()

    if curve.bevel_depth:
        layout.prop(curve, "use_fill_caps", text="Fill Caps")

    layout.prop(curve, "bevel_depth", text="Depth   ", icon_only=True, emboss=False)

    layout.prop(curve, "extrude", text="Extrude   ", icon_only=True, emboss=False)

    if curve.bevel_depth:
        text = 'Resolution Around   ' if has_resolution_along else 'Resolution   '
        layout.prop(curve, "bevel_resolution", text=text, icon_only=True, emboss=False)

    if has_resolution_along:
        layout.prop(active_spline, "resolution_u", text="Resolution Along   ", icon_only=True, emboss=False)

    if is_nurbs:
        layout.prop(active_spline, "order_u", text="Nurbs Order U   ", icon_only=True, emboss=False)

    layout.separator()

    layout.operator("machin3.convert_spline", text=f"Convert to {'POLY' if is_nurbs else 'NURBS'}")

    if not context_menu:
        if show_delete:
            layout.separator()
            layout.operator("wm.call_menu", text="(X) Delete").name = "VIEW3D_MT_edit_curve_delete"

        elif show_curve_split:
            layout.separator()
            layout.operator("curve.split", text="(Y) Split")

def add_object_buttons(self, context):
    if context.mode == 'OBJECT':
        self.layout.operator("machin3.add_single_point_poly_curve", text="Single Point Poly Curve", icon='DOT')

def context_menu(self, context):
    layout = self.layout

    if context.mode == "EDIT_CURVE" and get_prefs().show_in_curve_context_menu:
        layout.menu("MACHIN3_MT_curve_machine_context")
        layout.separator()

class MenuCURVEmachineContext(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_curve_machine_context"
    bl_label = "CURVEmachine"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE'

    def draw(self, context):
        draw_menu_edit_curve(self, context, context_menu=True)
