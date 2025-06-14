import bpy
from bpy.props import StringProperty
from ... utils.registration import get_prefs

class CallMeshMachineMenu(bpy.types.Operator):
    bl_idname = "machin3.call_mesh_machine_menu"
    bl_label = "MACHIN3: Call MESHmachine Menu"
    bl_options = {'REGISTER', 'UNDO'}

    idname: StringProperty()

    def invoke(self, context, event):
        if context.mode in ['OBJECT', 'EDIT_MESH']:

            if context.mode == 'OBJECT':
                wm = context.window_manager

                if get_prefs().plugmode == "NONE":
                    get_prefs().plugmode = "INSERT"
                    get_prefs().plugremovemode = False

                wm.plug_mousepos = (event.mouse_region_x, event.mouse_region_y)

            bpy.ops.wm.call_menu(name='MACHIN3_MT_%s' % (self.idname))
            return {'FINISHED'}
        return {'PASS_THROUGH'}
