import bpy
from bpy.props import BoolProperty
from .. utils.stash import create_stash
from .. utils.object import flatten, parent
from .. utils.mesh import unhide_deselect
from .. utils.modifier import apply_mod
from .. utils.ui import popup_message

class BooleanApply(bpy.types.Operator):
    bl_idname = "machin3.boolean_apply"
    bl_label = "MACHIN3: Boolean Apply"
    bl_description = 'Apply all Boolean Modifiers, and stash the Cutters'
    bl_options = {'REGISTER', 'UNDO'}

    stash_original: BoolProperty(name="Stash Original", default=True)
    stash_operants: BoolProperty(name="Stash Operants", default=True)
    apply_all: BoolProperty(name="Apply All Mods Selected Objects", description="Apply All Modifiers on Selected Objects", default=False)
    apply_all_stash_original: BoolProperty(name="Apply Stash Mods", description="Apply Mods on Original Stash", default=False)
    apply_all_stash_operants: BoolProperty(name="Apply Stashes Mods", description="Apply Mods on Operant Stashes", default=True)
    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        row = column.row(align=True)
        row.prop(self, "stash_original", toggle=True)
        row.prop(self, "stash_operants", toggle=True)

        row = column.row(align=True)
        r = row.row(align=True)
        r.active = self.stash_original
        r.prop(self, "apply_all_stash_original", text="Apply Mods", toggle=True)

        r = row.row(align=True)
        r.active = self.stash_operants
        r.prop(self, "apply_all_stash_operants", text="Apply Mods", toggle=True)

        row = column.row(align=True)
        row.prop(self, "apply_all", toggle=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        active = context.active_object
        objs = [obj for obj in context.selected_objects if any(mod.type == 'BOOLEAN' and mod.object for mod in obj.modifiers)]

        if not objs:
            popup_message("No Boolean Mods found on Selected Objects")
            return {'CANCELLED'}

        for obj in objs:
            booleans = [(mod, mod.object) for mod in obj.modifiers if mod.type == "BOOLEAN" and mod.object and mod.show_viewport]
            others = [mod for mod in obj.modifiers if mod.type != 'BOOLEAN']

            if booleans:
                dg = context.evaluated_depsgraph_get()

                if self.stash_original:

                    for mod, _ in booleans:
                        mod.show_viewport = False

                    dg.update()

                    obj.MM.stashname = "Boolean"
                    stash = create_stash(obj, obj, dg=dg if self.apply_all_stash_original else None)
                    obj.MM.stashname = ""

                    for mod, _ in booleans:
                        mod.show_viewport = True

                    dg.update()

                if self.stash_operants:
                    for mod, modobj in booleans:
                        obj.MM.stashname = f"{mod.operation.title()}"
                        create_stash(obj, modobj, dg=dg if self.apply_all_stash_operants else None)

                    obj.MM.stashname = ""

                if obj.data.users > 1:
                    obj.data = obj.data.copy()

                if self.apply_all:
                    flatten(obj, dg)

                else:
                    for mod, _ in booleans:
                        context.view_layer.objects.active = obj
                        apply_mod(mod.name)

                unhide_deselect(obj.data)

                remove = set()

                for mod, modobj in booleans:

                    other_booleans = [mod for ob in bpy.data.objects for mod in ob.modifiers if mod.type == 'BOOLEAN' and mod.object == modobj]

                    if other_booleans:
                        continue

                    else:
                        remove.add(modobj)

                for ob in remove:

                    for child in ob.children_recursive:
                        parent(child, obj)

                    if ob.data.users > 1:
                        bpy.data.objects.remove(ob, do_unlink=True)

                    else:
                        bpy.data.meshes.remove(ob.data, do_unlink=True)

        if active:
            context.view_layer.objects.active = active

        return {'FINISHED'}
