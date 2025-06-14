import bpy

class MakeUnique(bpy.types.Operator):
    bl_idname = "machin3.make_unique"
    bl_label = "MACHIN3: Make Unique"
    bl_description = "Make Instanced Mesh Objects Unique incl. any Instanced Boolean Operators"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if obj.data and obj.data.users > 1]

    def execute(self, context):
        instances = [obj for obj in context.selected_objects if obj.data and obj.data.users > 1]

        for obj in instances:

            obj.data = obj.data.copy()

            booleans = [mod for mod in obj.modifiers if mod.type == 'BOOLEAN' and mod.object and mod.object.data.users > 1]

            for mod in booleans:
                mod.object.data = mod.object.data.copy()

        return {'FINISHED'}
