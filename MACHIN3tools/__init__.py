bl_info = {
    "name": "MACHIN3tools",
    "author": "MACHIN3, TitusLVR",
    "version": (1, 12, 0, "DeusEx"),
    "blender": (4, 2, 0),
    "location": "Everywhere",
    "revision": "ce4f695d532d4513337853af996e1a0d1e9cd442",
    "description": "Streamlining Blender 4.2+.",
    "warning": "",
    "doc_url": "https://machin3.io/MACHIN3tools/docs",
    "category": "3D View"}

def reload_modules(name):
    import os
    import importlib

    dbg = False

    from . import registration, items, colors

    for module in [registration, items, colors]:
        importlib.reload(module)

    utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

    for module in utils_modules:
        impline = f"from . utils import {module}"

        if dbg:
            print(f"reloading {name}.utils.{module}")

        exec(impline)
        importlib.reload(eval(module))

    from . import handlers

    if dbg:
        print("reloading", handlers.__name__)

    importlib.reload(handlers)

    modules = []

    for label in registration.classes:
        entries = registration.classes[label]
        for entry in entries:
            path = entry[0].split('.')
            module = path.pop(-1)

            if (path, module) not in modules:
                modules.append((path, module))

    for path, module in modules:
        if path:
            impline = f"from . {'.'.join(path)} import {module}"
        else:
            impline = f"from . import {module}"

        if dbg:
            print(f"reloading {name}.{'.'.join(path)}.{module}")

        exec(impline)
        importlib.reload(eval(module))

if 'bpy' in locals():
    reload_modules(bl_info['name'])

import bpy
from bpy.props import PointerProperty, BoolProperty, EnumProperty

import os
import importlib
from typing import Tuple

from . properties import M3SceneProperties, M3ObjectProperties, M3CollectionProperties
from . handlers import load_post, undo_pre, depsgraph_update_post, render_start, render_end

from . ui.menus import asset_browser_bookmark_buttons, asset_browser_metadata, object_context_menu, mesh_context_menu, face_context_menu, apply_transform_menu, add_object_buttons, material_pick_button, outliner_group_toggles, extrude_menu, group_origin_adjustment_toggle, render_menu, render_buttons, asset_browser_update_thumbnail

if True:
    from .ui.menus import finish_assembly_edit_button, edge_context_menu

from . utils.registration import get_addon, get_core, get_prefs, get_tools, get_pie_menus, get_path
from . utils.registration import register_classes, unregister_classes, register_keymaps, unregister_keymaps, register_icons, unregister_icons, register_msgbus, unregister_msgbus
from . utils.system import printd, verify_update, install_update

from time import time

def update_check():
    def get_version_as_string():
        return '.'.join(str(v) for v in bl_info['version'])

    def get_version_as_semver_string():
        version = [v for v in bl_info['version'] if v != "DeusEx"]

        if len(version) == 3:
            return ".".join([str(v) for v in version])

        else:
            sign = "-" if any(version[3] == rt for rt in ['alpha', 'beta', 'rc']) else "+"
            basever = ".".join([str(v) for v in version[:3]]) + f"{sign}{version[3]}"

            if version[4:]:
                tailver = ".".join(str(v) for v in version[4:])
                return f"{basever}.{tailver}"

            else:
                return basever

    def hook(resp, *args, **kwargs):
        if resp:
            if resp.text == 'true':
                get_prefs().update_available = True

            else:
                get_prefs().update_available = False

            if debug:
                print(" received response:", resp.text)

            write_update_check(update_path, time(), debug=debug)

    def init_update_check(debug=False):
        if debug:
            print()
            print("initiating update check for version", get_version_as_string(), "semver:", get_version_as_semver_string())

        import platform
        import hashlib
        from . modules.requests_futures.sessions import FuturesSession

        machine = hashlib.sha1(platform.node().encode('utf-8')).hexdigest()[0:7]

        headers = {'User-Agent': f"{bl_info['name']}/{get_version_as_semver_string()} Blender/{'.'.join([str(v) for v in bpy.app.version])} ({platform.uname()[0]}; {platform.uname()[2]}; {platform.uname()[4]}; {machine})"}
        session = FuturesSession()

        try:
            if debug:
                print(" sending update request")

            session.post("https://drum.machin3.io/update", data={'revision': bl_info['revision']}, headers=headers, hooks={'response': hook})
        except:
            pass

    def write_update_check(update_path, update_time, debug=False):
        if debug:
            print()
            print("writing update check data")

        update_available = get_prefs().update_available

        msg = [f"version: {get_version_as_string()}",
               f"update time: {update_time}",
               f"update available: {update_available}\n"]

        with open(update_path, mode='w') as f:
            f.write('\n'.join(m for m in msg))

        if debug:
            print(" written to", update_path)

        return update_time, update_available

    def read_update_check(update_path, debug=False) -> Tuple[bool, tuple, float, bool]:
        if debug:
            print()
            print(f"reading {bl_info['name']} update check data")

        with open(update_path) as f:
            lines = [line[:-1] for line in f.readlines()]

        if len(lines) == 3:
            version = lines[0].replace('version: ', '')
            update_time_str = lines[1].replace('update time: ', '')
            update_available_str = lines[2].replace('update available: ', '')

            if debug:
                print(" fetched version:", version)
                print(" fetched update available:", update_available_str)
                print(" fetched update time:", update_time_str)

            try:
                update_time = float(update_time_str)
            except:
                update_time = None

            try:
                update_available = True if update_available_str == 'True' else False if update_available_str == 'False' else None
            except:
                update_available = None

            if version and update_time is not None and update_available is not None:
                return True, version, update_time, update_available

        return False, None, None, None

    debug = False

    update_path = os.path.join(get_path(), 'update_check')

    if not os.path.exists(update_path):
        if debug:
            print(f"init {bl_info['name']} update check as file does not exist")

        init_update_check(debug=debug)

    else:
        valid, version, update_time, update_available = read_update_check(update_path, debug=debug)

        if valid:

            if debug:
                print(f" comparing stored {bl_info['name']} version:", version, "with bl_info['version']:", get_version_as_string())

            if version != get_version_as_string():
                if debug:
                    print(f"init {bl_info['name']} update check, as the versions differ due to user updating the addon since the last update check")

                init_update_check(debug=debug)
                return

            now = time()
            delta_time = now - update_time

            if debug:
                print(" comparing", now, "and", update_time)
                print("  delta time:", delta_time)

            if delta_time > 72000:
                if debug:
                    print(f"init {bl_info['name']} update check, as it has been over 20 hours since the last one")

                init_update_check(debug=debug)
                return

            if debug:
                print(f"no {bl_info['name']} update check required, setting update available prefs from stored file")

            get_prefs().update_available = update_available

        else:
            if debug:
                print(f"init {bl_info['name']} update check as fetched file is invalid")

            init_update_check(debug=debug)

def register():
    global classes, keymaps, icons, owner

    MACHIN3toolsManager.clear_registered_count()

    core_classes = register_classes(get_core())

    bpy.types.Scene.M3 = PointerProperty(type=M3SceneProperties)
    bpy.types.Object.M3 = PointerProperty(type=M3ObjectProperties)
    bpy.types.Collection.M3 = PointerProperty(type=M3CollectionProperties)

    bpy.types.WindowManager.M3_screen_cast = BoolProperty()
    bpy.types.WindowManager.M3_asset_catalogs = EnumProperty(items=[])

    tool_classlists, tool_keylists, tool_count = get_tools()
    pie_classlists, pie_keylists, pie_count = get_pie_menus()

    classes = register_classes(tool_classlists + pie_classlists) + core_classes
    keymaps = register_keymaps(tool_keylists + pie_keylists)

    bpy.types.VIEW3D_MT_object_context_menu.prepend(object_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(mesh_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(face_context_menu)

    if True:
        bpy.types.VIEW3D_MT_edit_mesh_edges.append(edge_context_menu)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.append(extrude_menu)
    bpy.types.VIEW3D_MT_mesh_add.prepend(add_object_buttons)
    bpy.types.VIEW3D_MT_object_apply.append(apply_transform_menu)

    bpy.types.VIEW3D_MT_editor_menus.append(material_pick_button)

    bpy.types.OUTLINER_HT_header.prepend(outliner_group_toggles)

    bpy.types.ASSETBROWSER_MT_editor_menus.append(asset_browser_bookmark_buttons)
    bpy.types.ASSETBROWSER_PT_metadata.prepend(asset_browser_metadata)
    bpy.types.ASSETBROWSER_PT_metadata_preview.append(asset_browser_update_thumbnail)

    if True:
        bpy.types.TOPBAR_HT_upper_bar.prepend(finish_assembly_edit_button)

    bpy.types.VIEW3D_PT_tools_object_options_transform.append(group_origin_adjustment_toggle)

    bpy.types.TOPBAR_MT_render.append(render_menu)
    bpy.types.DATA_PT_context_light.prepend(render_buttons)

    icons = register_icons()

    owner = object()
    register_msgbus(owner)

    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

    bpy.app.handlers.render_init.append(render_start)
    bpy.app.handlers.render_cancel.append(render_end)
    bpy.app.handlers.render_complete.append(render_end)

    bpy.app.handlers.undo_pre.append(undo_pre)

    MACHIN3toolsManager.clear_addons()

    if get_prefs().registration_debug:
        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])} with {tool_count} {'tool' if tool_count == 1 else 'tools'}, {pie_count} pie {'menu' if pie_count == 1 else 'menus'}")

    update_check()

    verify_update()

def unregister():
    global classes, keymaps, icons, owner

    debug = get_prefs().registration_debug

    bpy.app.handlers.load_post.remove(load_post)

    from . handlers import axesVIEW3D, focusHUD, surfaceslideHUD, screencastHUD, groupposesVIEW3D, grouprelationsVIEW3D, assemblyeditHUD

    if axesVIEW3D and "RNA_HANDLE_REMOVED" not in str(axesVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(axesVIEW3D, 'WINDOW')

    if focusHUD and "RNA_HANDLE_REMOVED" not in str(focusHUD):
        bpy.types.SpaceView3D.draw_handler_remove(focusHUD, 'WINDOW')

    if surfaceslideHUD and "RNA_HANDLE_REMOVED" not in str(surfaceslideHUD):
        bpy.types.SpaceView3D.draw_handler_remove(surfaceslideHUD, 'WINDOW')

    if screencastHUD and "RNA_HANDLE_REMOVED" not in str(screencastHUD):
        bpy.types.SpaceView3D.draw_handler_remove(screencastHUD, 'WINDOW')

    if groupposesVIEW3D and "RNA_HANDLE_REMOVED" not in str(groupposesVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(groupposesVIEW3D, 'WINDOW')

    if grouprelationsVIEW3D and "RNA_HANDLE_REMOVED" not in str(grouprelationsVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(grouprelationsVIEW3D, 'WINDOW')

    if assemblyeditHUD and "RNA_HANDLE_REMOVED" not in str(assemblyeditHUD):
        bpy.types.SpaceView3D.draw_handler_remove(assemblyeditHUD, 'WINDOW')

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

    bpy.app.handlers.render_init.remove(render_start)
    bpy.app.handlers.render_cancel.remove(render_end)
    bpy.app.handlers.render_complete.remove(render_end)

    bpy.app.handlers.undo_pre.remove(undo_pre)

    unregister_msgbus(owner)

    bpy.types.VIEW3D_MT_object_context_menu.remove(object_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(mesh_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(face_context_menu)

    if True:
        bpy.types.VIEW3D_MT_edit_mesh_edges.remove(edge_context_menu)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(extrude_menu)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_object_buttons)
    bpy.types.VIEW3D_MT_object_apply.remove(apply_transform_menu)
    bpy.types.VIEW3D_MT_editor_menus.remove(material_pick_button)

    bpy.types.OUTLINER_HT_header.remove(outliner_group_toggles)

    bpy.types.ASSETBROWSER_MT_editor_menus.remove(asset_browser_bookmark_buttons)
    bpy.types.ASSETBROWSER_PT_metadata.remove(asset_browser_metadata)
    bpy.types.ASSETBROWSER_PT_metadata_preview.remove(asset_browser_update_thumbnail)

    if True:
        bpy.types.TOPBAR_HT_upper_bar.remove(finish_assembly_edit_button)

    bpy.types.VIEW3D_PT_tools_object_options_transform.remove(group_origin_adjustment_toggle)

    bpy.types.TOPBAR_MT_render.remove(render_menu)
    bpy.types.DATA_PT_context_light.remove(render_buttons)

    unregister_keymaps(keymaps)
    unregister_classes(classes)

    del bpy.types.Scene.M3
    del bpy.types.Object.M3
    del bpy.types.Collection.M3

    del bpy.types.WindowManager.M3_screen_cast
    del bpy.types.WindowManager.M3_asset_catalogs

    unregister_icons(icons)

    if debug:
        print(f"Unregistered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}.")

    install_update()

class MACHIN3toolsManager:

    props = {
        'operators': {
            'tools': 0,
            'pies': 0
        },

        'keymaps': {
            'tools': 0,
            'pies': 0
        }

    }

    addons = {}
    defaults = []
    @classmethod
    def get_addon(cls, name='SomeAddon', version=False, debug=False):

        addon = cls.addons.setdefault(name.lower(), {'enabled': None, 'version': None, 'foldername': '', 'path': '', 'module': None})
        if addon['enabled'] is None:
            addon['enabled'],  addon['foldername'],  addon['version'],  addon['path'] = get_addon(name)

            if addon['enabled']:
                addon['module'] = importlib.import_module(addon['foldername'])

            if debug:
                printd(addon, name)

        return (addon['enabled'], addon['version']) if version else addon['enabled']

    @classmethod
    def clear_addons(cls):
        cls.addons.clear()

    @classmethod
    def clear_registered_count(cls):
        cls.props['operators']['tools'] = 0
        cls.props['operators']['pies'] = 0

        cls.props['keymaps']['tools'] = 0
        cls.props['keymaps']['pies'] = 0

    @classmethod
    def init_machin3_operator_idnames(cls):
        for addon in ['MACHIN3tools', 'DECALmachine', 'MESHmachine', 'CURVEmachine', 'HyperCursor', 'PUNCHit']:
            if cls.get_addon(addon) and 'idnames' not in cls.addons[addon.lower()]:
                module = cls.addons[addon.lower()]['module']
                classes = module.registration.classes

                idnames = []

                for imps in classes.values():
                    op_imps = [imp for imp in imps if 'operators' in imp[0] or 'macros' in imp[0]]
                    idnames.extend([f"machin3.{idname}" for _, cls in op_imps for _, idname in cls])

                cls.addons[addon.lower()]['idnames'] = idnames

    @classmethod
    def get_core_operator_idnames(cls):
        idnames = []

        for fr, imps in get_core()[0]:
            if 'operators' in fr:
                for name, idname in imps:
                    idnames.append(f"machin3.{idname}")

        return idnames

    @classmethod
    def init_operator_defaults(cls, bl_idname, properties, skip=None, debug=False):
        if bl_idname not in cls.defaults:
            if debug:
                print("\ngetting defaults for", bl_idname, "from addon prefs")
            cls.defaults.append(bl_idname)
            ignore = [
                "__doc__",
                "__module__",
                "__slots__",
                "bl_rna",
                "rna_type",
            ]

            if skip:
                props = [prop for prop in dir(properties) if prop not in ignore and prop not in skip]
            else:
                props = [prop for prop in dir(properties) if prop not in ignore]

            op = bl_idname.replace('MACHIN3_OT_', '')

            for prop in props:
                if debug:
                    print(" prop:", prop)

                if (default := getattr(get_prefs(), f"{op}_default_{prop}", None)) is not None:
                    if debug:
                        print("  prefs default:", default)
                        print("  op default:", getattr(properties, prop))
                    if default != getattr(properties, prop):
                        setattr(properties, prop, default)
        else:
            if debug:
                print("\ndefaults already set for", bl_idname)
