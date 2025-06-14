import bpy

class MACHIN3toolsDebug(bpy.types.Operator):
    bl_idname = "machin3.machin3tools_debug"
    bl_label = "MACHIN3: MACHIN3tools Debug"
    bl_description = "MACHIN3tools Debug"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return False

    def execute(self, context):
        return {'FINISHED'}
