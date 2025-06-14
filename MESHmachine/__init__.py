bl_info = {
    "name": "MESHmachine",
    "author": "MACHIN3",
    "version": (0, 16, 0),
    "blender": (3, 6, 0),
    "location": "Object and Edit Mode Menu: Y key, MACHIN3 N Panel",
    "revision": "77fa6a4129a61aa3ec3755cc30c8648e4f020d0f",
    "description": "The missing essentials.",
    "warning": "",
    "doc_url": "https://machin3.io/MESHmachine/docs",
    "tracker_url": "https://machin3.io/MESHmachine/docs/faq/#get-support",
    "category": "Mesh"}

def reload_modules(name):
    import os
    import importlib

    dbg = False

    from . import registration, items, colors

    for module in [registration, items, colors]:
        importlib.reload(module)

    utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

    for module in utils_modules:
        impline = "from . utils import %s" % (module)

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
from bpy.props import PointerProperty, IntVectorProperty
from typing import Tuple
import os
from . properties import MeshSceneProperties, MeshObjectProperties
from . handlers import load_post, depsgraph_update_post
from . utils.registration import get_core, get_menus, get_path, get_tools, get_prefs, register_classes, unregister_classes, register_keymaps, unregister_keymaps
from . utils.registration import register_plugs, unregister_plugs, register_lockedlib, unregister_lockedlib, register_icons, unregister_icons
from . utils.registration import register_msgbus, unregister_msgbus
from . utils.system import verify_update, install_update
from . ui.menus import context_menu
from time import time

def update_check():
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
            print("initiating update check for version", bl_info['version'])

        import platform
        import hashlib
        from . modules.requests_futures.sessions import FuturesSession

        machine = hashlib.sha1(platform.node().encode('utf-8')).hexdigest()[0:7]

        headers = {'User-Agent': f"{bl_info['name']}/{'.'.join([str(v) for v in bl_info.get('version')])} Blender/{'.'.join([str(v) for v in bpy.app.version])} ({platform.uname()[0]}; {platform.uname()[2]}; {platform.uname()[4]}; {machine})"}
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

        msg = [f"version: {'.'.join(str(v) for v in bl_info['version'])}",
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
            lines = [l[:-1] for l in f.readlines()]

        if len(lines) == 3:
            version_str = lines[0].replace('version: ', '')
            update_time_str = lines[1].replace('update time: ', '')
            update_available_str = lines[2].replace('update available: ', '')

            if debug:
                print(" fetched update available:", update_available_str)
                print(" fetched update time:", update_time_str)

            try:
                version = tuple(int(v) for v in version_str.split('.'))
            except:
                version = None

            try:
                update_time = float(update_time_str)
            except:
                update_time = None

            try:
                update_available = True if update_available_str == 'True' else False if update_available_str == 'False' else None
            except:
                update_available = None

            if version is not None and update_time is not None and update_available is not None:
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
                print(f" comparing stored {bl_info['name']} version:", version, "with bl_info['version']:", bl_info['version'])

            if version != bl_info['version']:
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

    core_classes = register_classes(get_core())

    bpy.types.Scene.MM = PointerProperty(type=MeshSceneProperties)
    bpy.types.Object.MM = PointerProperty(type=MeshObjectProperties)

    bpy.types.WindowManager.plug_mousepos = IntVectorProperty(name="Mouse Position for Plug Insertion", size=2)

    plugs = register_plugs()
    register_lockedlib()

    menu_classlists, menu_keylists = get_menus()
    tool_classlists, tool_keylists = get_tools()

    classes = register_classes(menu_classlists + tool_classlists) + core_classes
    keymaps = register_keymaps(menu_keylists + tool_keylists)

    bpy.types.VIEW3D_MT_object_context_menu.prepend(context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(context_menu)

    icons = register_icons()

    owner = object()
    register_msgbus(owner)

    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

    if get_prefs().registration_debug:
        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])} with {len(plugs)} plug libraries")

        for lib in plugs:
            print(" • plug library: %s" % (lib))

    update_check()

    verify_update()

def unregister():
    global classes, keymaps, icons

    debug = get_prefs().registration_debug
    keep_assets = get_prefs().update_keep_assets

    from . handlers import stashesHUD, stashesVIEW3D

    if stashesHUD and "RNA_HANDLE_REMOVED" not in str(stashesHUD):
        bpy.types.SpaceView3D.draw_handler_remove(stashesHUD, 'WINDOW')

    if stashesVIEW3D and "RNA_HANDLE_REMOVED" not in str(stashesVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(stashesVIEW3D, 'WINDOW')

    bpy.app.handlers.load_post.remove(load_post)
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

    unregister_msgbus(owner)

    unregister_plugs()
    unregister_lockedlib()

    unregister_keymaps(keymaps)

    unregister_icons(icons)

    del bpy.types.Scene.MM
    del bpy.types.Object.MM

    del bpy.types.Scene.userpluglibs
    del bpy.types.WindowManager.newplugidx

    del bpy.types.WindowManager.plug_mousepos

    bpy.types.VIEW3D_MT_object_context_menu.remove(context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(context_menu)

    unregister_classes(classes)

    if debug:
        print(f"Unregistered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}")

    install_update(keep_assets=keep_assets)
    #H360ru
