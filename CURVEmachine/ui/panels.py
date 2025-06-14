import bpy
from .. import bl_info
from .. utils.ui import get_icon
from .. utils.registration import get_prefs

class PanelCURVEmachine(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_curve_machine"
    bl_label = "CURVEmachine %s" % ('.'.join([str(v) for v in bl_info['version']]))
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MACHIN3"
    bl_order = 30

    @classmethod
    def poll(cls, context):
        return get_prefs().show_sidebar_panel

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        column.operator('machin3.get_curvemachine_support', text='Get Support', icon='GREASEPENCIL')
        column.operator("wm.url_open", text='Documentation', icon='INFO').url = 'https://machin3.io/CURVEmachine/docs'
