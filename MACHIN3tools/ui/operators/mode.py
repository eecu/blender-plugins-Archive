import bpy
from bpy.props import StringProperty
from ... utils.registration import get_prefs
from ... utils.tools import get_active_tool, get_tools_from_context
from ... utils.view import set_xray, reset_xray

user_cavity = True

class EditMode(bpy.types.Operator):
    bl_idname = "machin3.edit_mode"
    bl_label = "Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    toggled_object = False

    @classmethod
    def poll(cls, context):
        if context.mode in ['OBJECT', 'EDIT_MESH']:
            active = context.active_object

            if active and active.override_library:
                if active.override_library:
                    cls.poll_message_set("You can't change modes on objects with a Library Override")

            return active and not active.override_library

    @classmethod
    def description(cls, context, properties):
        return f"Switch to {'Object' if context.mode == 'EDIT_MESH' else 'Edit'} Mode"

    def execute(self, context):
        global user_cavity

        shading = context.space_data.shading
        toggle_cavity = get_prefs().toggle_cavity
        toggle_xray = get_prefs().toggle_xray
        sync_tools = get_prefs().sync_tools

        active_tool = active_tool.idname if sync_tools and (active_tool := get_active_tool(context)) else None

        if context.mode == "OBJECT":
            if toggle_xray:
                set_xray(context)

            bpy.ops.object.mode_set(mode="EDIT")

            if toggle_cavity:
                user_cavity = shading.show_cavity
                shading.show_cavity = False

            if active_tool and active_tool in get_tools_from_context(context):
                bpy.ops.wm.tool_set_by_id(name=active_tool)

            self.toggled_object = False

        elif context.mode == "EDIT_MESH":
            if toggle_xray:
                reset_xray(context)

            bpy.ops.object.mode_set(mode="OBJECT")

            if toggle_cavity and user_cavity:
                shading.show_cavity = True
                user_cavity = True

            if active_tool and active_tool in get_tools_from_context(context):
                bpy.ops.wm.tool_set_by_id(name=active_tool)

            self.toggled_object = True

        return {'FINISHED'}

class MeshMode(bpy.types.Operator):
    bl_idname = "machin3.mesh_mode"
    bl_label = "Mesh Mode"
    bl_options = {'REGISTER', 'UNDO'}

    mode: StringProperty()

    @classmethod
    def poll(cls, context):
        if context.mode in ['OBJECT', 'EDIT_MESH', 'SCULPT', 'PAINT_TEXTURE', 'PAINT_WEIGHT', 'PAINT_VERTEX', 'PARTICLE']:
            active = context.active_object

            if active and active.override_library:
                if active.override_library:
                    cls.poll_message_set("You can't change modes on objects with a Library Override")

            return active and not active.override_library

    @classmethod
    def description(cls, context, properties):
        mode = properties.mode

        isvert = tuple(context.scene.tool_settings.mesh_select_mode) == (True, False, False)
        isedge = tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False)
        isface = tuple(context.scene.tool_settings.mesh_select_mode) == (False, False, True)

        desc = f"{mode.capitalize()} Select"

        if context.mode == 'EDIT_MESH':
            if not (mode == 'VERT' and isvert or mode == 'EDGE' and isedge or mode == 'FACE' and isface):
                desc += "\nSHIFT: Extend Selection"

            if isvert and mode != 'VERT' or isedge and mode != 'EDGE':
                desc += '\n   or'

                if mode == 'VERT':
                    desc += "\nCTRL: Contract Selection"
                else:
                    desc += "\nCTRL: Expand Selection"

            elif isface and mode != 'FACE':
                desc += '\n   or'
                desc += "\nCTRL: Contract Selection"

        return desc

    def invoke(self, context, event):
        global user_cavity

        shading = context.space_data.shading
        toggle_cavity = get_prefs().toggle_cavity
        toggle_xray = get_prefs().toggle_xray

        if context.mode in ['OBJECT', 'SCULPT', 'PAINT_TEXTURE', 'PAINT_WEIGHT', 'PAINT_VERTEX', 'PARTICLE']:
            if toggle_xray:
                set_xray(context)

            active_tool = active_tool.idname if get_prefs().sync_tools and (active_tool := get_active_tool(context)) else None

            bpy.ops.object.mode_set(mode="EDIT")

            if toggle_cavity:
                user_cavity = shading.show_cavity
                shading.show_cavity = False

            if active_tool and active_tool in get_tools_from_context(context):
                bpy.ops.wm.tool_set_by_id(name=active_tool)

        bpy.ops.mesh.select_mode(use_extend=event.shift, use_expand=event.ctrl, type=self.mode)
        return {'FINISHED'}

class ImageMode(bpy.types.Operator):
    bl_idname = "machin3.image_mode"
    bl_label = "MACHIN3: Image Mode"
    bl_options = {'REGISTER'}

    mode: StringProperty()

    def execute(self, context):
        view = context.space_data
        active = context.active_object

        toolsettings = context.scene.tool_settings
        view.mode = self.mode

        if self.mode == "UV" and active:
            if active.mode == "OBJECT":
                uvs = active.data.uv_layers

                if not uvs:
                    uvs.new()

                bpy.ops.object.mode_set(mode="EDIT")

                if not toolsettings.use_uv_select_sync:
                    bpy.ops.mesh.select_all(action="SELECT")

        return {'FINISHED'}

class UVMode(bpy.types.Operator):
    bl_idname = "machin3.uv_mode"
    bl_label = "MACHIN3: UV Mode"
    bl_options = {'REGISTER'}

    mode: StringProperty()

    def execute(self, context):
        toolsettings = context.scene.tool_settings
        view = context.space_data

        if view.mode != "UV":
            view.mode = "UV"

        if toolsettings.use_uv_select_sync:
            bpy.ops.mesh.select_mode(type=self.mode.replace("VERTEX", "VERT"))

        else:
            toolsettings.uv_select_mode = self.mode

        return {'FINISHED'}
