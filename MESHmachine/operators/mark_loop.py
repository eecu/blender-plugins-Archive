import bpy
from bpy.props import BoolProperty
import bmesh

class MarkLoop(bpy.types.Operator):
    bl_idname = "machin3.mark_loop"
    bl_label = "MACHIN3: Mark Loop"
    bl_description = "Mark/Unmark edges for preferential treatement by Fuse/Refuse"
    bl_options = {'REGISTER', 'UNDO'}

    clear: BoolProperty(name="Clear", default=False)
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, "clear")

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            return len([e for e in bm.edges if e.select]) > 0

    def execute(self, context):
        bpy.ops.mesh.mark_freestyle_edge(clear=self.clear)

        return {'FINISHED'}
