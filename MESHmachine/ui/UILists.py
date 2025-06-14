import bpy
from .. utils.ui import get_icon

class PlugLibsUIList(bpy.types.UIList):
    bl_idname = "MACHIN3_UL_plug_libs"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        isvisibleicon = "HIDE_OFF" if item.isvisible else "HIDE_ON"
        islockedicon = "LOCKED" if item.islocked else "BLANK1"

        split = layout.split(factor=0.7)

        row = split.row()
        row.label(text=item.name)
        row = split.row()
        row.prop(item, "isvisible", text="", icon=isvisibleicon, emboss=False)
        row.prop(item, "islocked", text="", icon=islockedicon, emboss=False)

class StashesUIList(bpy.types.UIList):
    bl_idname = "MACHIN3_UL_stashes"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        emboss = False

        isactive = data.active_stash_idx == index

        draw_stash_icon = "HIDE_OFF" if context.scene.MM.draw_active_stash else "HIDE_ON"

        row = layout.split(factor=0.05)
        row.prop(context.scene.MM, "draw_active_stash", text='', icon=draw_stash_icon, emboss=emboss) if isactive and item.obj else row.separator()

        row = row.split(factor=0.6)
        row.prop(item, "name", emboss=False, text="")

        row = row.split(factor=0.33)
        row.prop(context.scene.MM, "draw_active_stash_xray", text='', icon='XRAY', emboss=True) if isactive and context.scene.MM.draw_active_stash and item.obj else row.separator()

        row = row.split(factor=0.5)
        if item.obj:
            row.operator('machin3.swap_stash', text='', icon_value=get_icon('refresh'), emboss=emboss).idx = item.index
        else:
            row.label(text='', icon='ERROR')

        row.operator('machin3.remove_stash', text='', icon_value=get_icon('cancel' if isactive else 'cancel_grey'), emboss=emboss).idx = item.index
