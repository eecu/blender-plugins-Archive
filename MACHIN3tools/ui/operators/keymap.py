import bpy
from ... utils.ui import get_user_keymap_items, kmi_to_string

class ResetKeymaps(bpy.types.Operator):
    bl_idname = "machin3.reset_machin3tools_keymaps"
    bl_label = "MACHIN3: Reset MACHIN3tools Keymaps"
    bl_description = "This will undo all MACHIN3tools Keymap changes you have done" 
    bl_options = {'REGISTER'}

    def execute(self, context):
        modified, _ = get_user_keymap_items(context)

        if modified:
            for km, kmi in modified:
                km.restore_item_to_default(kmi)
                print(f"INFO: Modified keymap item: '{kmi_to_string(kmi, compact=True)}, active: {kmi.active}' has been restored to default")
        return {'FINISHED'}

class RestoreKeymaps(bpy.types.Operator):
    bl_idname = "machin3.restore_machin3tools_keymaps"
    bl_label = "MACHIN3: Restore missing MACHIN3tools Keymaps"
    bl_description = "This will restore all MACHIN3tools Keymappings, that have been removed" 
    bl_options = {'REGISTER'}

    def execute(self, context):
        _, missing = get_user_keymap_items(context)

        if missing:
            wm = bpy.context.window_manager
            kc = wm.keyconfigs.addon  # NOTE: even though the keymap has been removed from the user keyconfig, we have to re-add it here from the addon keymap, which then seems to restore it in the user keyconfig too

            for item in missing:
                keymap = item.get("keymap")
                space_type = item.get("space_type", "EMPTY")

                if keymap:
                    km = kc.keymaps.get(keymap)

                    if not km:
                        km = kc.keymaps.new(name=keymap, space_type=space_type)

                    if km:
                        idname = item.get("idname")
                        type = item.get("type")
                        value = item.get("value")

                        shift = item.get("shift", False)
                        ctrl = item.get("ctrl", False)
                        alt = item.get("alt", False)

                        kmi = km.keymap_items.new(idname, type, value, shift=shift, ctrl=ctrl, alt=alt)

                        if kmi:
                            properties = item.get("properties")

                            if properties:
                                for name, value in properties:
                                    setattr(kmi.properties, name, value)

                            active = item.get("active", True)
                            kmi.active = active

                        print(f"INFO: Missing keymap item: '{kmi_to_string(kmi, compact=True)}, active: {kmi.active}' has been re-created")

        return {'FINISHED'}
