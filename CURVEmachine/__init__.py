bl_info = {
    "name": "CURVEmachine",
    "author": "MACHIN3 CGB3D",
    "version": (1, 3, 0),
    "blender": (3, 6, 0),
    "location": "Edit Curve Mode Menu: Y key",
    "revision": "463e79b5c63d1eb5689c16506894353986b56df7",
    "description": "The missing (POLY + NURBS) Curve essentials.",
    "warning": "",
    "doc_url": "",
    "tracker_url": "https://machin3.io/CURVEmachine/docs",
    "category": "Curve"}

import bpy
from typing import Tuple
import os
from . handlers import depsgraph_update_post
from . ui.menus import add_object_buttons, context_menu
from . utils.registration import get_core, get_ops, get_prefs, get_path
from . utils.registration import register_classes, unregister_classes, register_keymaps, unregister_keymaps, register_icons, unregister_icons
from . utils.system import verify_update, install_update
from time import time
from .zh.translations import unregister_translation_dict, register_translation_dict

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

        headers = {'User-Agent': f"{bl_info['name']}/{'.'.join([str(v) for v in bl_info.get('version')[:3]])} Blender/{'.'.join([str(v) for v in bpy.app.version])} ({platform.uname()[0]}; {platform.uname()[2]}; {platform.uname()[4]}; {machine})"}
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

        msg = [f"version: {'.'.join(str(v) for v in bl_info['version'][:3])}",
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
                print(f" comparing stored {bl_info['name']} version:", version, "with bl_info['version']:", bl_info['version'][:3])

            if version != bl_info['version'][:3]:
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
    global classes, keymaps, icons

    core_classlists, core_keylists = get_core()
    core_classes = register_classes(core_classlists)

    ops_classlists, ops_keylists = get_ops()

    classes = register_classes(ops_classlists) + core_classes

    bpy.types.VIEW3D_MT_curve_add.prepend(add_object_buttons)
    bpy.types.VIEW3D_MT_edit_curve_context_menu.prepend(context_menu)

    keymaps = register_keymaps(core_keylists + ops_keylists)

    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

    icons = register_icons()

    if get_prefs().registration_debug:
        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}")

    update_check()

    verify_update()
    if bpy.context.preferences.view.use_translate_interface and bpy.context.preferences.view.language.startswith('zh'):
        register_translation_dict()

def unregister():
    global classes, keymaps, icons

    debug = get_prefs().registration_debug

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

    unregister_keymaps(keymaps)

    bpy.types.VIEW3D_MT_curve_add.remove(add_object_buttons)
    bpy.types.VIEW3D_MT_edit_curve_context_menu.remove(context_menu)

    unregister_classes(classes)

    unregister_icons(icons)

    if debug:
        print(f"Unregistered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}")

    install_update()
    unregister_translation_dict()