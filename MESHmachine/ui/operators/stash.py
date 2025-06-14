import bpy
from bpy.props import IntProperty
from ... utils.stash import clear_stashes, swap_stash

class RemoveStash(bpy.types.Operator):
    bl_idname = "machin3.remove_stash"
    bl_label = "MACHIN3: Remove Stash"
    bl_options = {'REGISTER', 'UNDO'}

    idx: IntProperty(name="Stash Index", default=0)
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.MM.stashes

    @classmethod
    def description(cls, context, properties):
        active = context.active_object
        return f"Remove Stash '{active.MM.stashes[properties.idx].name}'"

    def execute(self, context):
        active = context.active_object

        if self.idx < len(active.MM.stashes):
            stash = active.MM.stashes[self.idx]
            clear_stashes(active, stashes=[stash])

            active.select_set(True)

        return {'FINISHED'}

class SwapStash(bpy.types.Operator):
    bl_idname = "machin3.swap_stash"
    bl_label = "MACHIN3: Swap Stash"
    bl_options = {'REGISTER', 'UNDO'}

    idx: IntProperty(name="Stash Index", default=0)
    @classmethod
    def poll(cls, context):
        if context.mode in ['OBJECT', 'EDIT_MESH']:
            return context.active_object and context.active_object.MM.stashes

    @classmethod
    def description(cls, context, properties):
        active = context.active_object
        return f"Swap Active Object and Stash '{active.MM.stashes[properties.idx].name}'"

    def execute(self, context):
        swapped = swap_stash(context, context.active_object, self.idx, debug=False)

        return {'FINISHED'} if swapped else {'CANCELLED'}

class SweepStashes(bpy.types.Operator):
    bl_idname = "machin3.sweep_stashes"
    bl_label = "MACHIN3: Sweep Stashes"
    bl_description = "Sweep up stash objects, that became visible aber appending objects from other blend files"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return [obj for obj in context.scene.objects if obj.MM.isstashobj]

    def execute(self, context):
        stashobjs = [obj for obj in context.scene.objects if obj.MM.isstashobj]

        for obj in stashobjs:
            obj.use_fake_user = True

            for col in obj.users_collection:
                col.objects.unlink(obj)

        return {'FINISHED'}
