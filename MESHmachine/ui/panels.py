import bpy
import os
from .. utils.registration import get_path, get_prefs
from .. import bl_info

class PanelMESHmachine(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_mesh_machine"
    bl_label = "MESHmachine %s" % ('.'.join([str(v) for v in bl_info['version']]))
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MACHIN3"
    bl_order = 10

    @classmethod
    def poll(cls, context):
        return get_prefs().show_sidebar_panel

    def draw_header(self, context):
        layout = self.layout

        mm = context.scene.MM

        row = layout.row(align=True)
        row.prop(mm, "register_panel_help", text="", icon="QUESTION")

    def draw(self, context):
        layout = self.layout

        mm = context.scene.MM
        active = context.active_object
        sweep = [obj for obj in context.scene.objects if obj.MM.isstashobj]

        box = layout.box()
        column = box.column()

        row = column.split(factor=0.33)
        row.label(text="Plug Align")
        r = row.row()
        r.prop(mm, "align_mode", expand=True)

        if active and active.MM.stashes:
            box = layout.box()
            column = box.column()
            column.label(text=f"{active.name} {'(' + active.MM.stashname + ')' if active.MM.stashname else ''}")

            column.template_list("MACHIN3_UL_stashes", "", active.MM, "stashes", active.MM, "active_stash_idx", rows=max(len(active.MM.stashes), 1))

        if sweep:
            box = layout.box()
            column = box.column()

            row = column.row()
            row.scale_y = 1.2
            row.operator('machin3.sweep_stashes', text='Sweep Stashes')

class PanelHelp(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_help_mesh_machine"
    bl_label = "MESHmachine Help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MACHIN3"
    bl_order = 11

    @classmethod
    def poll(cls, context):
        return get_prefs().show_sidebar_panel and context.scene.MM.register_panel_help

    def draw(self, context):
        layout = self.layout

        resources_path = os.path.join(get_path(), "resources")
        example_tutorial_path = os.path.join(resources_path, "Example_Tutorial.blend")
        example_plugged_path = os.path.join(resources_path, "Example_Plugged.blend")

        box = layout.box()
        box.label(text="Help")

        b = box.box()
        b.label(text="Documentation")
        column = b.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="Local", icon='FILE_BACKUP').url = "file://" + os.path.join(get_path(), "docs", "index.html")
        row.operator("wm.url_open", text="Online", icon='FILE_BLEND').url = "https://machin3.io/MESHmachine/docs"

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="FAQ", icon='QUESTION').url = "https://machin3.io/MESHmachine/docs/faq"
        row.operator("wm.url_open", text="Youtube", icon='FILE_MOVIE').url = "https://www.youtube.com/watch?v=i68jOGMEUV8&list=PLcEiZ9GDvSdXR9kd4O6cdQN_6i0LOe5lw"

        b = box.box()
        b.label(text="Support")
        column = b.column()

        row = column.row()
        row.scale_y = 1.5
        row.operator("machin3.get_meshmachine_support", text="Get Support", icon='GREASEPENCIL')

        b = box.box()
        b.label(text="Examples")
        column = b.column()

        if bpy.data.is_dirty:
            column.label(text="Your current file is not saved!", icon="ERROR")
            column.label(text="Unsaved changes will be lost,", icon="BLANK1")
            column.label(text="if you load the following example.", icon="BLANK1")

        row = column.row(align=True)
        row.operator_context = 'EXEC_DEFAULT'
        row.scale_y = 1.5

        op = row.operator("wm.open_mainfile", text="Tutorial", icon="FILE_FOLDER")
        op.filepath=example_tutorial_path
        op.load_ui = True

        op = row.operator("wm.open_mainfile", text="Plugged", icon="FILE_FOLDER")
        op.filepath=example_plugged_path
        op.load_ui = True

        b = box.box()
        b.label(text="Plug Resources")
        column = b.column()

        row = column.row()
        row.scale_y = 1.2
        row.operator("wm.url_open", text="Plug Packs", icon='RENDER_RESULT').url = "https://machin3.io/MESHmachine/docs/plug_resources"

        b = box.box()
        b.label(text="Discuss")
        column = b.column()

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="Blender Artists", icon="COMMUNITY").url = "https://blenderartists.org/t/meshmachine/1102529"

        b = box.box()
        b.label(text="Follow Development")
        column = b.column()
        column.label(text='Twitter')

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("wm.url_open", text="@machin3io").url = "https://twitter.com/machin3io"
        row.operator("wm.url_open", text="#MESHmachine").url = "https://twitter.com/search?q=(%23MESHmachine)%20(from%3Amachin3io)&src=typed_query&f=live"

        column.label(text='Youtube')
        row = column.row()
        row.scale_y = 1.2
        row.operator("wm.url_open", text="MACHIN3").url = "https://www.youtube.com/c/MACHIN3"
