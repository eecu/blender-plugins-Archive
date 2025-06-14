import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.utils import register_class, unregister_class, previews
import os
import addon_utils
from . system import get_new_directory_index
from .. registration import keys as keysdict
from .. registration import classes as classesdict
from .. msgbus import active_object_change

def get_path():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def get_name():
    return os.path.basename(get_path())

def get_prefs():
    return bpy.context.preferences.addons[get_name()].preferences

def get_addon(addon, debug=False):
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

    enabled, foldername, version, path = get_addon('LoopTools')#

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

            enabled, foldername, version, path = get_addon('LoopTools')

            if enabled:
                print(f"INFO: Success! {name}/{foldername} ({version}) is now enabled, installed at '{path}'")
                return True, None

            else:
                print(f"WARNING: Failed to enable {name}/{foldername} ({version}), at '{path}'")
                return False, [f"Failed to enable {name}/{foldername} ({version}), at '{path}'"]

        elif bpy.app.version >= (4, 2, 0):

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

        else:
            print(f"WARNING: Addon {name} could not be found on disk")
            return False, ["Addon {name} could not be found on disk"]

    return False, None

def register_classes(classlists, debug=False):
    classes = []

    for classlist in classlists:
        for fr, imps in classlist:
            impline = "from ..%s import %s" % (fr, ", ".join([i[0] for i in imps]))
            classline = "classes.extend([%s])" % (", ".join([i[0] for i in imps]))

            exec(impline)
            exec(classline)

    for c in classes:
        if debug:
            print("REGISTERING", c)

        register_class(c)

    return classes

def unregister_classes(classes, debug=False):
    for c in classes:
        if debug:
            print("UN-REGISTERING", c)

        unregister_class(c)

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
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    keymaps = []

    if kc:
        for keylist in keylists:
            for item in keylist:
                keymap = item.get("keymap")
                space_type = item.get("space_type", "EMPTY")

                if keymap:
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

                            keymaps.append((km, kmi))
    else:
        print("WARNING: Keyconfig not availabe, skipping MESHmachine keymaps")

    return keymaps

def unregister_keymaps(keymaps):
    for km, kmi in keymaps:
        km.keymap_items.remove(kmi)

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
    bpy.msgbus.subscribe_rna(key=(bpy.types.LayerObjects, 'active'), owner=owner, args=(), notify=active_object_change)

def unregister_msgbus(owner):
    bpy.msgbus.clear_by_owner(owner)

def reload_msgbus():
    from .. import owner

    unregister_msgbus(owner)
    register_msgbus(owner)

def get_core():
    return [classesdict["CORE"]]

def get_menus():
    classlists = []
    keylists = []

    classlists.append(classesdict["MENU"])
    keylists.append(keysdict["MENU"])

    classlists.append(classesdict["PANEL"])

    return classlists, keylists

def get_panels(getall=False):
    classlists = []

    if not getall:
        mm = bpy.context.scene.MM

    if getall or mm.register_panel_help:
        classlists.append(classesdict["PANEL_HELP"])

    return classlists

def get_tools():
    classlists = []
    keylists = []

    classlists.append(classesdict["FUSE"])
    classlists.append(classesdict["CHANGEWIDTH"])
    classlists.append(classesdict["FLATTEN"])

    classlists.append(classesdict["UNFUSE"])
    classlists.append(classesdict["REFUSE"])
    classlists.append(classesdict["UNCHAMFER"])
    classlists.append(classesdict["UNBEVEL"])
    classlists.append(classesdict["UNFUCK"])

    classlists.append(classesdict["TURNCORNER"])
    classlists.append(classesdict["QUADCORNER"])

    classlists.append(classesdict["MARKLOOP"])

    classlists.append(classesdict["BOOLEANCLEANUP"])
    classlists.append(classesdict["CHAMFER"])
    classlists.append(classesdict["OFFSET"])
    classlists.append(classesdict["OFFSETCUT"])

    classlists.append(classesdict["STASHES"])

    classlists.append(classesdict["CONFORM"])

    classlists.append(classesdict["NORMALS"])

    classlists.append(classesdict["SYMMETRIZE"])
    keylists.append(keysdict["SYMMETRIZE"])

    classlists.append(classesdict["REALMIRROR"])

    classlists.append(classesdict["SELECT"])
    keylists.append(keysdict["SELECT"])

    classlists.append(classesdict["INSERTREMOVE"])
    classlists.append(classesdict["PLUG"])
    classlists.append(classesdict["CREATE"])
    classlists.append(classesdict["VALIDATE"])

    classlists.append(classesdict["LOOPTOOLS"])

    classlists.append(classesdict["QUICKPATCH"])

    classlists.append(classesdict["BOOLEAN"])

    classlists.append(classesdict["WEDGE"])

    classlists.append(classesdict["DEBUG"])

    return classlists, keylists

def context_menu(self, context):
    self.layout.menu("MACHIN3_MT_mesh_machine_context")
    self.layout.separator()

def add_context_menus():
    if get_prefs().show_in_object_context_menu:
        bpy.types.VIEW3D_MT_object_context_menu.prepend(context_menu)

    if get_prefs().show_in_mesh_context_menu:
        bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(context_menu)

def remove_context_menus():
    bpy.types.VIEW3D_MT_object_context_menu.remove(context_menu)

    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(context_menu)

plugs = {}

def register_plugs(library="ALL", default=None, reloading=False):
    assetspath = get_prefs().assetspath

    savedlibs = [lib.name for lib in get_prefs().pluglibsCOL]
    for idx, lib in enumerate(savedlibs):
        if not os.path.exists(os.path.join(assetspath, lib)):
            get_prefs().pluglibsCOL.remove(idx)

            print(" ! WARNNING: plug library '%s' can no longer be found! Save your preferences!" % lib)

    pluglibs = []

    if library == "ALL":
        for idx, f in enumerate(sorted(os.listdir(assetspath))):
            if os.path.isdir(os.path.join(assetspath, f)):
                pluglibs.append(f)

                if f not in get_prefs().pluglibsCOL:
                    item = get_prefs().pluglibsCOL.add()
                    item.name = f

                if os.path.exists(os.path.join(assetspath, f, ".islocked")):
                    get_prefs().pluglibsCOL[f].islocked = True

        get_prefs().pluglibsIDX = len(pluglibs) - 1

        unlockedlibs = sorted([(lib.name, lib.name, "") for lib in get_prefs().pluglibsCOL if not lib.islocked], reverse=False)
        enum = EnumProperty(name="User Plug Libraries", items=unlockedlibs, update=set_new_plug_index, default=unlockedlibs[-1][0] if unlockedlibs else None)
        setattr(bpy.types.Scene, "userpluglibs", enum)
        setattr(bpy.types.WindowManager, "newplugidx", StringProperty(name="User Plug Library Index"))

    else:
        pluglibs = [library]

    global plugs

    for folder in pluglibs:
        plugs[folder] = previews.new()
        load_library_preview_icons(plugs[folder], os.path.join(assetspath, folder, "icons"))
        items = get_library_preview_items(plugs[folder])

        setattr(bpy.types.WindowManager, "pluglib_" + folder, EnumProperty(items=items, update=insert_or_remove_plug(folder), default=default))
        if reloading:
            if folder in savedlibs:
                print(" • reloaded plug library: %s" % (folder))
            else:
                print(" • loaded new plug library: %s" % (folder))

    return plugs

def unregister_plugs(library="ALL"):
    global plugs

    if library == "ALL":
        pluglibs = list(plugs.keys())
    else:
        pluglibs = [library]

    for libname in pluglibs:
        delattr(bpy.types.WindowManager, "pluglib_" + libname)
        previews.remove(plugs[libname])

        del plugs[libname]

        if get_prefs().registration_debug:
            print(" • unloaded plug library: %s" % (libname))

def insert_or_remove_plug(folderstring):
    def function_template(self, context):
        if get_prefs().plugmode == "INSERT":
            bpy.ops.machin3.insert_plug(library=folderstring, plug=getattr(bpy.context.window_manager, "pluglib_" + folderstring))

        elif get_prefs().plugmode == "REMOVE":
            bpy.ops.machin3.remove_plug('INVOKE_DEFAULT', library=folderstring, plug=getattr(bpy.context.window_manager, "pluglib_" + folderstring))

    return function_template

def set_new_plug_index(self, context):
    assetspath = get_prefs().assetspath
    library = context.scene.userpluglibs
    plugpath = os.path.join(assetspath, library)

    idx = get_new_directory_index(plugpath)

    context.window_manager.newplugidx = get_new_directory_index(plugpath)

def load_library_preview_icons(preview_collection, dirpath):
    for f in sorted(os.listdir(dirpath)):
        if f.endswith(".png"):
            plugname = f[:-4]
            filepath = os.path.join(dirpath, f)
            preview_collection.load(plugname, filepath, 'IMAGE')

def get_library_preview_items(preview_collection):
    tuplelist = []
    for name, preview in sorted(preview_collection.items(), reverse=get_prefs().reverseplugsorting):
        tuplelist.append((name, name, "", preview.icon_id, preview.icon_id))
    return tuplelist

def reload_plug_libraries(library="ALL", default=None):
    lib = bpy.context.scene.userpluglibs

    if library == "ALL":
        unregister_plugs()
        register_plugs(reloading=True)
    else:
        unregister_plugs(library=library)
        register_plugs(library=library, default=default, reloading=True)
        if default:
            mode = get_prefs().plugmode
            get_prefs().plugmode = "NONE"
            setattr(bpy.context.window_manager, "pluglib_" + library, default)
            get_prefs().plugmode = mode

    if lib not in [lib[0] for lib in bpy.types.Scene.userpluglibs.keywords['items']]:
        firstlib = bpy.types.Scene.userpluglibs.keywords['items'][0][0]
        setattr(bpy.context.scene, "userpluglibs", firstlib)

locked = None

def register_lockedlib():
    global locked

    locked = previews.new()

    lockedpath = os.path.join(get_path(), "resources", 'locked.png')
    assert os.path.exists(lockedpath), "%s not found" % lockedpath

    preview = locked.load("LOCKED", lockedpath, 'IMAGE')
    items = [("LOCKED", "LOCKED", "LIBRARY is LOCKED", preview.icon_id, preview.icon_id)]

    enum = EnumProperty(items=items)
    setattr(bpy.types.WindowManager, "lockedpluglib", enum)

def unregister_lockedlib():
    global locked

    delattr(bpy.types.WindowManager, "lockedpluglib")
    previews.remove(locked)
