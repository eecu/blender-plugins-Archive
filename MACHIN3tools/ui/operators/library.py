import bpy

from ... utils.data import get_pretty_linked_data
from ... utils.draw import draw_fading_label
from ... utils.object import is_linked_object
from ... utils.system import abspath

class ReloadAllLibraries(bpy.types.Operator):
    bl_idname = "machin3.reload_all_libraries"
    bl_label = "MACHIN3: Reload All Libraries"
    bl_description = "Reload Libraries"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
           return bpy.data.libraries

    def execute(self, context):
        text = []

        for lib in (libs := bpy.data.libraries):
            lib.reload()
            msg = f"Reloaded Library '{lib.name.replace('.blend', '')}' from: {abspath(lib.filepath)}"
            text.append(msg)
            print("INFO:", msg)

        draw_fading_label(context, text=text, move_y=30 + 10 * len(libs), time=3 + len(libs))
        return {'FINISHED'}

class ReloadActivesLibraries(bpy.types.Operator):
    bl_idname = "machin3.reload_actives_libraries"
    bl_label = "MACHIN3: Reload Active's Libraries"
    bl_description = "Reload Active's Libraries"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and bpy.data.libraries:
            active = context.active_object
            if active:
                return is_linked_object(active)

    @classmethod
    def description(cls, context, properties):
        active = context.active_object
        linked = is_linked_object(active, recursive=True)
        pretty_linked = get_pretty_linked_data(linked, active)

        lib_count = len({id.library for id in linked})
        linked_limit = 50

        keep_main = not all('MAIN_' in id[0] for id in pretty_linked)

        desc = f"Reload Active Object's Librar{'ies' if lib_count > 1 else 'y'}"
        desc += f"\n\nObject links {len(linked)} data blocks (recursively) from {lib_count} librar{'ies' if lib_count > 1 else 'y'}"

        current = None

        for type, _, data, count in pretty_linked[:linked_limit]:
            if type != current:
                current = type

                if 'MAIN_' in type and not keep_main:
                    desc += f"\n\n{type.replace('MAIN_', '').title().replace('_', ' ')}"

                else:
                    desc += f"\n\n{type.title().replace('_', ' ')}"

            desc += f"\n • {data.name}"

        if left := pretty_linked[linked_limit:]:
            desc += "\n ..."
            desc += f"\n\n and {len(left)} more"

        return desc

    def execute(self, context):
        active = context.active_object

        linked = is_linked_object(active)

        libs = {lnk.library for lnk in linked}

        text = []

        for lib in libs:
            lib.reload()
            text.append(f"Reloaded Library '{lib.name.replace('.blend', '')}' from: {abspath(lib.filepath)}")

        draw_fading_label(context, text=text, move_y=30 + 10 * len(libs), time=3 + len(libs))
        return {'FINISHED'}
