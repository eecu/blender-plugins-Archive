import bpy
from bpy.props import BoolProperty
from uuid import uuid4
from .. utils.object import parent, get_object_tree
from .. utils.system import printd

class BooleanDuplicate(bpy.types.Operator):
    bl_idname = "machin3.boolean_duplicate"
    bl_label = "MACHIN3: Boolean Duplicate"
    bl_description = "Duplicate Boolean Objects with their Cutters\nALT: Instance the Object and Cutter Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    instance: BoolProperty(name="Instance", default=False)
    @classmethod
    def poll(cls, context):
        return [obj for obj in context.selected_objects if any(mod.type == 'BOOLEAN' and mod.object for mod in obj.modifiers)]

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        column.prop(self, 'instance', toggle=True)

    def invoke(self, context, event):
        self.instance = event.alt
        return self.execute(context)

    def execute(self, context):
        debug = True
        debug = False

        view = context.space_data

        sel = [obj for obj in context.selected_objects if any(mod.type == 'BOOLEAN' and mod.object for mod in obj.modifiers)]

        if debug:
            print()
            print("selected objects with boolean mods:", [obj.name for obj in sel])

        sel_trees = set(sel)

        for obj in sel:

            if debug:
                print(obj.name)

            obj_tree = []
            get_object_tree(obj, obj_tree, mod_objects=True, debug=False)

            obj_tree = [obj for obj in obj_tree if obj.name in context.view_layer.objects]

            if debug:
                print(" tree:", [ob.name for ob in obj_tree])

            sel_trees.update(obj_tree)
            
        originals = {str(uuid4()): (obj, obj.visible_get()) for obj in sel_trees}

        bpy.ops.object.select_all(action='DESELECT')

        for dup_hash, (obj, visible) in originals.items():
            if debug:
                print(dup_hash, obj.name, visible)

            obj.MM.dup_hash = dup_hash

            if not visible:
                if view.local_view and not obj.local_view_get(view):
                    obj.local_view_set(view, True)

                obj.hide_set(False)

            obj.select_set(True)

        bpy.ops.object.duplicate(linked=self.instance)

        for dup in context.selected_objects:
            orig, visible = originals[dup.MM.dup_hash]

            if debug:
                print(orig.name, " > ", dup.name)

            orig.MM.dup_hash = ''
            dup.MM.dup_hash = ''

            orig.hide_set(not visible)

            if orig.parent in sel_trees:
                dup.hide_set(not visible)

        return {'FINISHED'}
