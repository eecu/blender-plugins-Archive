import bpy
from bpy.utils import register_class, unregister_class, previews
import os
import addon_utils
from .. registration import keys as keysdict
from .. registration import classes as classesdict

def get_path():
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def get_name():
    try:
        return os.path.basename(get_path())
    except:
        return "CURVEmachine"

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
        print("WARNING: Keyconfig not availabe, skipping CURVEmachine keymaps")

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

def get_core():
    classlists = []
    keylists = []

    classlists.append(classesdict["CORE"])
    classlists.append(classesdict["MENU"])

    keylists.append(keysdict["MENU"])

    return classlists, keylists

def get_ops():
    classlists = []
    keylists = []

    classlists.append(classesdict["ADD"])

    classlists.append(classesdict["BLEND"])
    keylists.append(keysdict["BLEND"])

    classlists.append(classesdict["KNIFE"])
    keylists.append(keysdict["KNIFE"])

    classlists.append(classesdict["MERGE"])
    keylists.append(keysdict["MERGE"])

    classlists.append(classesdict["REBUILD"])

    classlists.append(classesdict["SYMMETRIZE"])
    keylists.append(keysdict["SYMMETRIZE"])

    classlists.append(classesdict["TRANSFORM"])
    keylists.append(keysdict["TRANSFORM"])

    return classlists, keylists
