import os
import bpy
from bpy.props import StringProperty
from .. utils.ui import popup_message
from .. utils.registration import reload_plug_libraries
from .. utils.append import append_collection
from .. utils.registration import get_prefs, set_new_plug_index
from .. utils.collection import create_plug_collections
from .. utils.plug import align, clear_drivers
from .. utils.scene import setup_surface_snapping
from .. utils.object import update_local_view
from .. utils.modifier import get_auto_smooth, remove_mod

class Insert(bpy.types.Operator):
    bl_idname = "machin3.insert_plug"
    bl_label = "Insert Plug"
    bl_description = "Insert Plug"
    bl_options = {'REGISTER', 'UNDO'}

    library: StringProperty()
    plug: StringProperty()

    def execute(self, context):
        scene = context.scene

        assetspath = get_prefs().assetspath
        blendpath = os.path.join(assetspath, self.library, "blends", self.plug + ".blend")

        col = append_collection(blendpath, self.plug)

        if col:
            _, plcol = create_plug_collections(scene, self.library)

            handle = None
            empties = []
            others = []

            for obj in col.objects:
                plcol.objects.link(obj)

                if obj.hide_viewport:
                    obj.hide_viewport = False
                    obj.hide_set(True)

                if obj.MM.isplughandle:
                    handle = obj

                    handle.display_type = 'BOUNDS'

                elif obj.MM.isplugdeformer or obj.MM.isplugoccluder:
                    obj.hide_set(True)

                elif obj.MM.isplug or obj.MM.isplugsubset:
                    obj.show_in_front = get_prefs().plugxraypreview

                elif obj.type == "EMPTY":
                    obj.show_in_front = True
                    empties.append(obj)

                else:
                    others.append(obj)
                    obj.hide_set(True)

                if bpy.app.version >= (4, 1, 0):
                    mod = get_auto_smooth(obj)

                    if mod:
                        remove_mod(mod)

            clear_drivers(others)

            if handle:
                dg = context.evaluated_depsgraph_get()

                bpy.ops.object.select_all(action='DESELECT')
                handle.select_set(True)
                context.view_layer.objects.active = handle

                align(scene, dg, handle, empties)

                setup_surface_snapping(scene)

            else:
                popup_message("The Imported Plug doesn't not contain a valid Plug Handle.")

            update_local_view(context.space_data, [(obj, True) for obj in col.objects])

            bpy.data.collections.remove(col, do_unlink=True)

        return {"FINISHED"}

class Remove(bpy.types.Operator):
    bl_idname = "machin3.remove_plug"
    bl_label = "Remove Plug"
    bl_options = {'REGISTER'}

    library: StringProperty()
    plug: StringProperty()

    def draw(self, context):
        layout = self.layout

        layout.label(text="This removes the plug '%s' from library '%s'!" % (self.plug, self.library), icon='ERROR')
        layout.label(text="Removing a plug deletes it from the hard drive, this cannot be undone!")

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def execute(self, context):
        print("\nRemoving plug '%s' from library '%s'" % (self.plug, self.library))

        path = get_prefs().assetspath

        iconpath = os.path.join(path, self.library, "icons", self.plug + ".png")
        blendbasepath = os.path.join(path, self.library, "blends")
        blendpaths = [os.path.join(path, self.library, "blends", blend) for blend in sorted(os.listdir(blendbasepath)) if self.plug + ".blend" in blend]

        for path in blendpaths:
            print(" • Deleting plug blend '%s' from disk" % path)
            if os.path.exists(path):
                os.remove(path)

        print(" • Deleting plug icon '%s' from disk" % iconpath)
        if os.path.exists(iconpath):
            os.remove(iconpath)

        plugs = [f[:-4] for f in sorted(os.listdir(os.path.dirname(iconpath))) if f.endswith('.png')]
        default = plugs[-1] if plugs else None
        reload_plug_libraries(library=self.library, default=default)
        set_new_plug_index(self, context)

        return {'FINISHED'}
