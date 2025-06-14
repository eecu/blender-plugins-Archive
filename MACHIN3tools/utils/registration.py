import bpy
from bpy.utils import register_class, unregister_class, previews

import os

from .. msgbus import gp_annotation_tint_change, object_name_change, group_color_change, asset_empty_display_size_change

from .. registration import classes as classesdict
from .. registration import keys as keysdict

def get_path():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def get_name():
    return os.path.basename(get_path())

def get_prefs():
    return bpy.context.preferences.addons[get_name()].preferences

def get_pretty_version(version):
    return '.'.join([str(v) for v in version])

def get_addon(addon, debug=False):
    import addon_utils

    for mod in addon_utils.modules():
        name = mod.bl_info["name"]
        version = mod.bl_info.get("version", None)
        foldername = mod.__name__
        path = mod.__file__
        enabled = addon_utils.check(foldername)[1]

        if name == addon:
            if debug:
                print(name)
                print("  enabled:", enabled)
                print("  folder name:", foldername)
                print("  version:", version)
                print("  path:", path)
                print()

            return enabled, foldername, version, path
    return False, None, None, None

def get_addon_prefs(addon):
    _, foldername, _, _ = get_addon(addon)
    return bpy.context.preferences.addons.get(foldername).preferences

def enable_addon(context, name, debug=False):

    enabled, foldername, version, path = get_addon(name)

    if debug:
        print()
        print("enabled:", enabled)
        print("foldername:", foldername)
        print("version:", version)
        print("path:", path)

    if enabled:
        print(f"INFO: Addon {name}/{foldername} ({version}) is enabled already, installed at '{path}'")
        return True, None

    else:

        if foldername:
            if debug:
                print(f"  Enabling {name} now!")

            try:
                bpy.ops.preferences.addon_enable(module=foldername)

            except:
                print(f"WARNING: Failed to enable addon {name} at '{path}'")
                return False, [f"Failed to enable addon {name} at '{path}'", "Try Restarting Blender!"]

            enabled, foldername, version, path = get_addon(name)

            if enabled:
                print(f"INFO: Success! {name}/{foldername} ({version}) is now enabled, installed at '{path}'")
                return True, None

            else:
                print(f"WARNING: Failed to enable {name}/{foldername} ({version}), at '{path}'")
                return False, [f"Failed to enable {name}/{foldername} ({version}), at '{path}'"]

        else:

            if not context.preferences.system.use_online_access:
                print("INFO: Activating online access")
                context.preferences.system.use_online_access = True

            repo = context.preferences.extensions.repos.get('extensions.blender.org')

            if repo:
                print("INFO: Found Blender extensions repo")

                if not repo.enabled:
                    if debug:
                        print(" Enabling")

                    repo.enabled = True

                repo_index = list(context.preferences.extensions.repos).index(repo)

                if debug:
                    print(" Syncing, repo_index:", repo_index)

                bpy.ops.extensions.repo_sync(repo_index=repo_index)

                if debug:
                    print("  Finished Sync")

                print(f"INFO: Attempting to install {name} from repo")
                pkd_id = name.lower().replace(' ', '_')

                try:
                    bpy.ops.extensions.package_install(repo_index=repo_index, pkg_id=pkd_id)

                except:
                    enabled, foldername, version, path = get_addon(name)

                    if debug:
                        print()
                        print("enabled:", enabled)
                        print("foldername:", foldername)
                        print("version:", version)
                        print("path:", path)

                    print(f"WARNING: Failed to enable addon {name}, installed from repo at '{path}'")
                    return False, [f"Failed to enable addon {name}, installed from repo at '{path}'", "Try restarting Blender!"]

                enabled, foldername, version, path = get_addon(name)

                if debug:
                    print()
                    print("enabled:", enabled)
                    print("foldername:", foldername)
                    print("version:", version)
                    print("path:", path)

                if enabled:
                    print(f"INFO: Success! {name}/{foldername} ({version}) is now enabled and installed at '{path}'")
                    return True, None

                else:
                    print(f"WARNING: Failed to enable {name}/{foldername} ({version}), at '{path}'")

                    addonstr = f"Failed to enable {name}"

                    if foldername:
                        addonstr += f"/{foldername}"

                    if version:
                        addonstr += f" ({version})"

                    if path:
                        addonstr += f", at '{path}'"

                    msg = [addonstr]

                    if not path:
                        msg.append("No Internet connection?")

                    return False, msg

            else:
                print("WARNING: Could not find Blender extensions repo")
                return False, ["Could not find Blender extensions repo", "Impossibru!"]

    return False, None

def register_classes(classlists, debug=False):
    from .. import MACHIN3toolsManager as M3

    classes = []

    for classlist in classlists:
        for fr, imps in classlist:
            impline = f"from .. {fr} import {', '.join([i[0] for i in imps])}"
            classline = f"classes.extend([{', '.join([i[0] for i in imps])}])"

            exec(impline)
            exec(classline)

    for c in classes:
        if debug:
            print("REGISTERING", c)

        register_class(c)

        if 'operators' in c.__module__:
            if c.bl_idname in M3.get_core_operator_idnames():
                continue

            if 'ui.operators' in c.__module__:
                M3.props['operators']['pies'] += 1

            else:
                M3.props['operators']['tools'] += 1

    if debug:
        print(M3.props)

    return classes

def unregister_classes(classes, debug=False):
    from .. import MACHIN3toolsManager as M3

    for c in classes:
        if debug:
            print("UN-REGISTERING", c)

        unregister_class(c)

        if 'operators' in c.__module__:

            if 'operators' in c.__module__:
                if c.bl_idname in M3.get_core_operator_idnames():
                    continue

                if 'ui.operators' in c.__module__:
                    M3.props['operators']['pies'] -= 1

                else:
                    M3.props['operators']['tools'] -= 1

    if debug:
        print(M3.props)

def get_classes(classlist):
    classes = []

    for fr, imps in classlist:
        if "operators" in fr:
            type = "OT"
        elif "pies" in fr or "menus" in fr:
            type = "MT"

        for imp in imps:
            idname = imp[1]
            rna_name = "MACHIN3_%s_%s" % (type, idname)

            c = getattr(bpy.types, rna_name, False)

            if c:
                classes.append(c)

    return classes

def register_keymaps(keylists):
    from .. import MACHIN3toolsManager as M3

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    keymaps = []

    if kc:
        for keylist in keylists:
            for item in keylist:
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

                            keymaps.append((km, kmi))

                            if idname in ['wm.call_menu_pie', 'machin3.save_versioned_startup_file', 'machin3.call_machin3tools_pie']:
                                M3.props['keymaps']['pies'] += 1

                            else:
                                M3.props['keymaps']['tools'] += 1

    else:
        print("WARNING: Keyconfig not available, skipping MACHIN3tools keymaps")

    return keymaps

def unregister_keymaps(keymaps):
    from .. import MACHIN3toolsManager as M3

    for km, kmi in keymaps:

        if kmi.idname in ['wm.call_menu_pie', 'machin3.save_versioned_startup_file', 'machin3.call_machin3tools_pie']:
            M3.props['keymaps']['pies'] -= 1

        else:
            M3.props['keymaps']['tools'] -= 1

        km.keymap_items.remove(kmi)

def get_keymaps(keylist):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    keymaps = []

    for item in keylist:
        keymap = item.get("keymap")

        if keymap:
            km = kc.keymaps.get(keymap)

            if km:
                idname = item.get("idname")

                for kmi in km.keymap_items:
                    if kmi.idname == idname:
                        properties = item.get("properties")

                        if properties:
                            if all([getattr(kmi.properties, name, None) == value for name, value in properties]):
                                keymaps.append((km, kmi))

                        else:
                            keymaps.append((km, kmi))

    return keymaps

def register_icons():
    path = os.path.join(get_prefs().path, "icons")
    icons = previews.new()

    for i in sorted(os.listdir(path)):
        if i.endswith(".png"):
            iconname = i[:-4]
            filepath = os.path.join(path, i)

            icons.load(iconname, filepath, 'IMAGE')

    return icons

def unregister_icons(icons):
    previews.remove(icons)

def register_msgbus(owner):
    if get_prefs().activate_group_tools:
        bpy.msgbus.subscribe_rna(key=(bpy.types.Object, 'color'), owner=owner, args=(bpy.context, ), notify=group_color_change)
        bpy.msgbus.subscribe_rna(key=(bpy.types.Object, 'name'), owner=owner, args=(bpy.context, ), notify=object_name_change)

    if get_prefs().activate_tools_pie and bpy.app.version >= (4, 3, 0):
        bpy.msgbus.subscribe_rna(key=(bpy.types.GreasePencilLayer, 'tint_color'), owner=owner, args=(bpy.context, ), notify=gp_annotation_tint_change)

    if get_prefs().activate_assetbrowser_tools:
        bpy.msgbus.subscribe_rna(key=(bpy.types.Object, 'empty_display_size'), owner=owner, args=(bpy.context, ), notify=asset_empty_display_size_change)

def unregister_msgbus(owner):
    bpy.msgbus.clear_by_owner(owner)

def reload_msgbus():
    from .. import owner

    unregister_msgbus(owner)
    register_msgbus(owner)

def activate(self, register, tool):
    debug=True
    debug=False

    name = tool.replace("_", " ").title()

    if register:
        classlist, keylist, _ = eval("get_%s()" % (tool))

        classes = register_classes(classlist, debug=debug)

        from .. import classes as startup_classes

        for c in classes:
            if c not in startup_classes:
                startup_classes.append(c)

        keymaps = register_keymaps(keylist)

        from .. import keymaps as startup_keymaps
        for k in keymaps:
            if k not in startup_keymaps:
                startup_keymaps.append(k)

        if get_prefs().registration_debug:
            if classes:
                print("Registered MACHIN3tools' %s" % (name))

        classlist.clear()
        keylist.clear()

    else:

        keylist = keysdict.get(tool.upper())

        if keylist:
            keymaps = get_keymaps(keylist)

            from .. import keymaps as startup_keymaps
            for k in keymaps:
                if k in startup_keymaps:
                    startup_keymaps.remove(k)

            unregister_keymaps(keymaps)

        classlist = classesdict[tool.upper()]

        classes = get_classes(classlist)

        from .. import classes as startup_classes

        for c in classes:
            if c in startup_classes:
                startup_classes.remove(c)

        unregister_classes(classes, debug=debug)

        if get_prefs().registration_debug:
            if classes:
                print("Unregistered MACHIN3tools' %s" % (name))

def get_core():
    return [classesdict["CORE"]]

def get_tools():
    classlists = []
    keylists = []
    count = 0

    classlists, keylists, count = get_smart_vert(classlists, keylists, count)

    classlists, keylists, count = get_smart_edge(classlists, keylists, count)

    classlists, keylists, count = get_smart_face(classlists, keylists, count)

    classlists, keylists, count = get_clean_up(classlists, keylists, count)

    classlists, keylists, count = get_clipping_toggle(classlists, keylists, count)

    classlists, keylists, count = get_focus(classlists, keylists, count)

    classlists, keylists, count = get_mirror(classlists, keylists, count)

    classlists, keylists, count = get_align(classlists, keylists, count)

    classlists, keylists, count = get_apply(classlists, keylists, count)

    classlists, keylists, count = get_select(classlists, keylists, count)

    classlists, keylists, count = get_mesh_cut(classlists, keylists, count)

    classlists, keylists, count = get_surface_slide(classlists, keylists, count)

    classlists, keylists, count = get_assetbrowser(classlists, keylists, count)

    classlists, keylists, count = get_filebrowser(classlists, keylists, count)

    classlists, keylists, count = get_smart_drive(classlists, keylists, count)

    classlists, keylists, count = get_unity(classlists, keylists, count)

    classlists, keylists, count = get_material_picker(classlists, keylists, count)

    classlists, keylists, count = get_group(classlists, keylists, count)

    classlists, keylists, count = get_region(classlists, keylists, count)

    classlists, keylists, count = get_thread(classlists, keylists, count)

    classlists, keylists, count = get_smooth(classlists, keylists, count)

    classlists, keylists, count = get_edge_constraint(classlists, keylists, count)

    classlists, keylists, count = get_extrude(classlists, keylists, count)

    classlists, keylists, count = get_render(classlists, keylists, count)

    classlists, keylists, count = get_customize(classlists, keylists, count)

    return classlists, keylists, count

def get_pie_menus():
    classlists = []
    keylists = []
    count = 0

    classlists, keylists, count = get_modes_pie(classlists, keylists, count)

    classlists, keylists, count = get_save_pie(classlists, keylists, count)

    classlists, keylists, count = get_shading_pie(classlists, keylists, count)

    classlists, keylists, count = get_views_pie(classlists, keylists, count)

    classlists, keylists, count = get_align_pie(classlists, keylists, count)

    classlists, keylists, count = get_cursor_pie(classlists, keylists, count)

    classlists, keylists, count = get_transform_pie(classlists, keylists, count)

    classlists, keylists, count = get_snapping_pie(classlists, keylists, count)

    classlists, keylists, count = get_collections_pie(classlists, keylists, count)

    classlists, keylists, count = get_workspace_pie(classlists, keylists, count)

    classlists, keylists, count = get_tools_pie(classlists, keylists, count)

    return classlists, keylists, count

def get_smart_vert(classlists=[], keylists=[], count=0):
    if get_prefs().activate_smart_vert:

        classlists.append(classesdict["SMART_VERT"])
        keylists.append(keysdict["SMART_VERT"])
        count +=1

    return classlists, keylists, count

def get_smart_edge(classlists=[], keylists=[], count=0):
    if get_prefs().activate_smart_edge:

        classlists.append(classesdict["SMART_EDGE"])
        keylists.append(keysdict["SMART_EDGE"])
        count +=1

    return classlists, keylists, count

def get_smart_face(classlists=[], keylists=[], count=0):
    if get_prefs().activate_smart_face:
        classlists.append(classesdict["SMART_FACE"])
        keylists.append(keysdict["SMART_FACE"])
        count +=1

    return classlists, keylists, count

def get_clean_up(classlists=[], keylists=[], count=0):
    if get_prefs().activate_clean_up:
        classlists.append(classesdict["CLEAN_UP"])
        keylists.append(keysdict["CLEAN_UP"])
        count +=1

    return classlists, keylists, count

def get_clipping_toggle(classlists=[], keylists=[], count=0):
    if get_prefs().activate_clipping_toggle:
        classlists.append(classesdict["CLIPPING_TOGGLE"])
        keylists.append(keysdict["CLIPPING_TOGGLE"])
        count +=1

    return classlists, keylists, count

def get_focus(classlists=[], keylists=[], count=0):
    if get_prefs().activate_focus:
        classlists.append(classesdict["FOCUS"])
        keylists.append(keysdict["FOCUS"])
        count +=1

    return classlists, keylists, count

def get_mirror(classlists=[], keylists=[], count=0):
    if get_prefs().activate_mirror:
        classlists.append(classesdict["MIRROR"])
        keylists.append(keysdict["MIRROR"])
        count +=1

    return classlists, keylists, count

def get_align(classlists=[], keylists=[], count=0):
    if get_prefs().activate_align:
        classlists.append(classesdict["ALIGN"])
        keylists.append(keysdict["ALIGN"])
        count +=1

    return classlists, keylists, count

def get_apply(classlists=[], keylists=[], count=0):
    if get_prefs().activate_apply:
        classlists.append(classesdict["APPLY"])
        count +=1

    return classlists, keylists, count

def get_select(classlists=[], keylists=[], count=0):
    if get_prefs().activate_select:
        classlists.append(classesdict["SELECT"])
        keylists.append(keysdict["SELECT"])
        count +=1

    return classlists, keylists, count

def get_mesh_cut(classlists=[], keylists=[], count=0):
    if get_prefs().activate_mesh_cut:
        classlists.append(classesdict["MESH_CUT"])
        count +=1

    return classlists, keylists, count

def get_surface_slide(classlists=[], keylists=[], count=0):
    if get_prefs().activate_surface_slide:
        classlists.append(classesdict["SURFACE_SLIDE"])
        count +=1

    return classlists, keylists, count

def get_filebrowser(classlists=[], keylists=[], count=0):
    if get_prefs().activate_filebrowser_tools:
        classlists.append(classesdict["FILEBROWSER"])
        keylists.append(keysdict["FILEBROWSER"])
        count +=1

    return classlists, keylists, count

def get_assetbrowser(classlists=[], keylists=[], count=0):
    if get_prefs().activate_assetbrowser_tools:
        classlists.append(classesdict["ASSETBROWSER"])
        keylists.append(keysdict["ASSETBROWSER"])
        count +=1

    return classlists, keylists, count

def get_smart_drive(classlists=[], keylists=[], count=0):
    if get_prefs().activate_smart_drive:
        classlists.append(classesdict["SMART_DRIVE"])
        count +=1

    return classlists, keylists, count

def get_unity(classlists=[], keylists=[], count=0):
    if get_prefs().activate_unity:
        classlists.append(classesdict["UNITY"])
        count +=1

    return classlists, keylists, count

def get_material_picker(classlists=[], keylists=[], count=0):
    if get_prefs().activate_material_picker:
        classlists.append(classesdict["MATERIAL_PICKER"])
        keylists.append(keysdict["MATERIAL_PICKER"])
        count +=1

    return classlists, keylists, count

def get_group(classlists=[], keylists=[], count=0):
    if get_prefs().activate_group_tools:
        classlists.append(classesdict["GROUP"])
        keylists.append(keysdict["GROUP"])
        count +=1

    return classlists, keylists, count

def get_region(classlists=[], keylists=[], count=0):
    if get_prefs().activate_region:
        classlists.append(classesdict["REGION"])
        keylists.append(keysdict["REGION"])
        count +=1

    return classlists, keylists, count

def get_thread(classlists=[], keylists=[], count=0):
    if get_prefs().activate_thread:
        classlists.append(classesdict["THREAD"])
        count +=1

    return classlists, keylists, count

def get_smooth(classlists=[], keylists=[], count=0):
    if get_prefs().activate_smooth:
        classlists.append(classesdict["SMOOTH"])
        keylists.append(keysdict["SMOOTH"])
        count +=1

    return classlists, keylists, count

def get_edge_constraint(classlists=[], keylists=[], count=0):
    if get_prefs().activate_edge_constraint:
        classlists.append(classesdict["EDGE_CONSTRAINT"])
        keylists.append(keysdict["EDGE_CONSTRAINT"])
        count +=1
    return classlists, keylists, count

def get_extrude(classlists=[], keylists=[], count=0):
    if get_prefs().activate_extrude:
        classlists.append(classesdict["EXTRUDE"])
        count +=2

    return classlists, keylists, count

def get_render(classlists=[], keylists=[], count=0):
    if get_prefs().activate_render:
        classlists.append(classesdict["RENDER"])
        keylists.append(keysdict["RENDER"])
        count +=1

    return classlists, keylists, count

def get_customize(classlists=[], keylists=[], count=0):
    if get_prefs().activate_customize:
        classlists.append(classesdict["CUSTOMIZE"])
        count += 1

    return classlists, keylists, count

def get_modes_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_modes_pie:
        classlists.append(classesdict["MODES_PIE"])
        keylists.append(keysdict["MODES_PIE"])
        count += 1

    return classlists, keylists, count

def get_save_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_save_pie:
        classlists.append(classesdict["SAVE_PIE"])
        keylists.append(keysdict["SAVE_PIE"])
        count += 1

    return classlists, keylists, count

def get_shading_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_shading_pie:
        classlists.append(classesdict["SHADING_PIE"])
        keylists.append(keysdict["SHADING_PIE"])
        count += 1

    return classlists, keylists, count

def get_views_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_views_pie:

        classlists.append(classesdict["VIEWS_PIE"])
        keylists.append(keysdict["VIEWS_PIE"])
        count += 1

    return classlists, keylists, count

def get_align_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_align_pie:
        classlists.append(classesdict["ALIGN_PIE"])
        keylists.append(keysdict["ALIGN_PIE"])
        count += 1

    return classlists, keylists, count

def get_cursor_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_cursor_pie:
        classlists.append(classesdict["CURSOR_PIE"])
        keylists.append(keysdict["CURSOR_PIE"])
        count += 1

    return classlists, keylists, count

def get_transform_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_transform_pie:
        classlists.append(classesdict["TRANSFORM_PIE"])
        keylists.append(keysdict["TRANSFORM_PIE"])
        count += 1

    return classlists, keylists, count

def get_snapping_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_snapping_pie:
        classlists.append(classesdict["SNAPPING_PIE"])
        keylists.append(keysdict["SNAPPING_PIE"])
        count += 1

    return classlists, keylists, count

def get_collections_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_collections_pie:
        classlists.append(classesdict["COLLECTIONS_PIE"])
        keylists.append(keysdict["COLLECTIONS_PIE"])
        count += 1

    return classlists, keylists, count

def get_workspace_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_workspace_pie:
        classlists.append(classesdict["WORKSPACE_PIE"])
        keylists.append(keysdict["WORKSPACE_PIE"])
        count += 1

    return classlists, keylists, count

def get_tools_pie(classlists=[], keylists=[], count=0):
    if get_prefs().activate_tools_pie:
        classlists.append(classesdict["TOOLS_PIE"])
        keylists.append(keysdict["TOOLS_PIE"])
        count += 1

    return classlists, keylists, count
