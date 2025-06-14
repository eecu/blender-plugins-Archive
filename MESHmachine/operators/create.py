import bpy
from bpy.props import BoolProperty, IntProperty, EnumProperty, StringProperty
import bmesh
from mathutils import Matrix
import os
from .. utils.bmesh import ensure_custom_data_layers
from .. utils.object import hide_render, parent
from .. utils.registration import set_new_plug_index, reload_plug_libraries, get_prefs, get_path
from .. utils.append import append_scene
from .. items import add_plug_to_library_mode_items, plug_prop_items
from uuid import uuid4

class Create(bpy.types.Operator):
    bl_idname = "machin3.create_plug"
    bl_label = "MACHIN3: Create Plug"
    bl_description = "Create Plug from mesh object(s)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            if active:
                sel = context.selected_objects
                return not any([obj.MM.isplug or obj.MM.isplughandle for obj in sel + [active]])

    def execute(self, context):
        plug = context.active_object
        others = [obj for obj in context.selected_objects if obj != plug]

        subsets = [obj for obj in others if obj.type == 'MESH']

        for obj in subsets:
            parent(obj, plug)

        hide_render([plug] + subsets, False)

        conform_vgroup = plug.vertex_groups.new(name="conform")

        plug.data.materials.clear()

        handle_mesh = bpy.data.meshes.new(name="%s_handle" % (plug.name))
        handle = bpy.data.objects.new(name=handle_mesh.name, object_data=handle_mesh)
        context.collection.objects.link(handle)

        hasfillet = self.prepare_plug(plug, handle, conform_vgroup)

        self.set_props(plug, handle, subsets, hasfillet)

        handle.matrix_world = plug.matrix_world

        parent(plug, handle)

        handle.display_type = 'BOUNDS'
        handle.show_in_front = True

        hide_render(handle, True)

        bpy.ops.object.select_all(action='DESELECT')
        handle.select_set(True)
        context.view_layer.objects.active = handle
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

    def set_props(self, plug, handle, subsets, hasfillet):
        uuid = str(uuid4())
        creator = get_prefs().plugcreator

        plug.MM.isplug = True
        plug.MM.uuid = uuid
        plug.MM.hasfillet = hasfillet
        plug.MM.plugcreator = creator

        handle.MM.isplughandle = True
        handle.MM.uuid = uuid
        handle.MM.plugcreator = creator

        for sub in subsets:
            sub.MM.isplugsubset = True
            sub.MM.uuid = uuid
            sub.MM.plugcreator = creator

    def prepare_plug(self, plug, handle, conform_vgroup):
        bm = bmesh.new()
        bm.from_mesh(plug.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        groups, bw, _ = ensure_custom_data_layers(bm)

        border_edges = []
        border_verts = []
        for e in bm.edges:
            if not e.is_manifold:
                e.smooth = True
                border_edges.append(e)
                border_verts.extend(e.verts)

        conform_verts = []
        edge_verts = []
        for e in border_edges:
            for v in e.verts:
                if v not in conform_verts:
                    conform_verts.append(v)
                    edge_verts.append(v)

                for e in v.link_edges:
                    if e not in border_edges:
                        conform_verts.append(e.other_vert(v))

        for v in conform_verts:
            v[groups][conform_vgroup.index] = 1

        inner_rail = []
        for e in bm.edges:
            if len([v for v in e.verts if v in conform_verts]) == 2:
                if len([v for v in e.verts if v in border_verts]) == 0:
                    inner_rail.append(e)

        hasfillet = True if all([e.smooth for e in inner_rail]) else False

        bm.to_mesh(plug.data)

        for v in edge_verts:
            for e in v.link_edges:
                if e not in border_edges:
                    other_v = e.other_vert(v)
                    offset_dir = other_v.co - v.co
                    v.co = v.co - offset_dir * 0.3

        bmesh.ops.dissolve_verts(bm, verts=[v for v in bm.verts if v not in conform_verts])

        for e in bm.edges:
            e.smooth = True
            e[bw] = 0

        for f in bm.faces:
            if len(f.verts) > 4:
                f.select_set(True)

            else:
                f.select_set(False)

        bm.to_mesh(handle.data)
        bm.clear()

        return hasfillet

class AddPlugToLibrary(bpy.types.Operator):
    bl_idname = "machin3.add_plug_to_library"
    bl_label = "MACHIN3: Add Plug To Library"
    bl_description = "Add selected Plug to Plug Library"

    addmode: EnumProperty(name="Add Mode", items=add_plug_to_library_mode_items, default="NEW")
    plugname: StringProperty(name="Name (optional)")

    showindicatorHUD: BoolProperty(name="Show Indicators", default=True)
    showindicatorFILLETorEDGE: BoolProperty(name="FILLET or EDGE", default=True)
    showindicatorHOOKorARRAY: BoolProperty(name="HOOK or ARRAY", default=True)
    showindicatorDEFORMER: BoolProperty(name="DEFORMER", default=True)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            if active:
                return active.MM.isplughandle

    def draw(self, context):
        wm = context.window_manager
        library = context.scene.userpluglibs
        scale = get_prefs().plugsinlibraryscale
        show_names = get_prefs().showplugnames

        layout = self.layout

        column = layout.column()

        row = column.row()
        row.label(text="Add Mode")
        row.prop(self, "addmode", expand=True)

        row = column.split(factor=0.33)
        row.label(text="Library")
        row.prop(context.scene, "userpluglibs", text="")

        if self.addmode == "NEW":
            row = column.split(factor=0.33)
            row.label(text="Name (optiona)")
            row.prop(self, "plugname", text="")

            if self.plugname:
                pathstr = library + " / blends / " + context.window_manager.newplugidx + "_" + self.plugname.replace(" ", "_") + ".blend"
            else:
                pathstr = library + " / blends / " + context.window_manager.newplugidx + ".blend"

        else:
            column.template_icon_view(wm, "pluglib_" + library, show_labels=show_names, scale=scale)

            plugname = getattr(wm, "pluglib_" + library)
            pathstr = library + " / blends / " + plugname + ".blend"

        row = column.split(factor=0.33)
        row.label(text="Path Preview")
        row.label(text=pathstr, icon="FILE_FOLDER")

        column.separator()
        column.prop(self, "showindicatorHUD")

        if self.showindicatorHUD:
            row = column.row()
            row.prop(self, "showindicatorFILLETorEDGE")
            row.prop(self, "showindicatorHOOKorARRAY")
            row.prop(self, "showindicatorDEFORMER")

    def invoke(self, context, event):
        set_new_plug_index(self, context)

        get_prefs().plugmode = "NONE"

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def execute(self, context):
        debug = False

        assetspath = get_prefs().assetspath
        library = context.scene.userpluglibs
        index = context.window_manager.newplugidx
        plugiconrenderblendpath = os.path.join(get_path(), "resources", "Templates.blend")

        if self.addmode == "NEW":
            if self.plugname:
                blendname = "%s_%s.blend" % (index, self.plugname.replace(" ", "_"))
                iconname = "%s_%s.png" % (index, self.plugname.replace(" ", "_"))
                plugname = "%s_%s" % (index, self.plugname.replace(" ", "_"))
            else:
                blendname = "%s.blend" % index
                iconname = "%s.png" % index
                plugname = "%s" % index
        else:
            wm = context.window_manager
            plugname = getattr(wm, "pluglib_" + library)
            blendname = "%s.blend" % plugname
            iconname = "%s.png" % plugname

        blendpath = os.path.join(assetspath, library, "blends", blendname)
        iconpath = os.path.join(assetspath, library, "icons", iconname)

        handle = context.active_object
        plugobjs, fillet, deformer, occluder, mods = self.get_plug_objs(handle, debug=debug)
        mx = handle.matrix_world.copy()

        scene = self.render_thumbnail(context, plugobjs, plugiconrenderblendpath, iconpath, fillet, deformer, mods)
        if not scene:
            return {'FINISHED'}

        self.save_blend(context, scene, plugobjs, plugname, blendpath)

        handle.matrix_world = mx
        bpy.ops.view3d.view_selected(use_all_regions=False)

        reload_plug_libraries(library=library, default=plugname)
        return {'FINISHED'}

    def get_plug_objs(self, handle, debug=False):
        plugobjects = [handle]
        plugmods = []
        fillet = False
        deformer = False
        occluder = False
        mods = None

        if handle.children:
            children = list(handle.children)

            while children:
                child = children[0]

                plugobjects.append(child)
                children.extend(list(child.children))

                if child.MM.isplug:
                    if child.MM.hasfillet:
                        fillet = True

                    hide_render(child, False)

                elif child.MM.isplugsubset:
                    hide_render(child, False)

                elif child.MM.isplugdeformer:
                    deformer = child
                    hide_render(child, True)

                elif child.MM.isplugoccluder:
                    occluder = child

                    hide_render(child, False)

                plugmods.extend([mod.type for mod in child.modifiers])

                children.pop(0)

        if "ARRAY" in plugmods:
            mods = "ARRAY"
        elif "HOOK" in plugmods:
            mods = "HOOK"

        if debug:
            print()
            print("plug objs:", plugobjects)
            print("fillet:", fillet)
            print("deformer:", deformer)
            print("occluder:", occluder)
            print("mods:", mods)

        return plugobjects, fillet, deformer, occluder, mods
    def render_thumbnail(self, context, plugobjs, iconrenderblendpath, iconpath, fillet, deformer, mods):
        scene = append_scene(iconrenderblendpath, "Thumbnail")
        context.window.scene = scene

        for obj in bpy.data.objects:
            if "demo" in obj.name:
                bpy.data.objects.remove(obj, do_unlink=True)

        made_local = False

        for col in scene.collection.children:
            if col.library:
                col.make_local()

                print(f"WARNING: Making linked collection '{col.name}' local!")

                made_local = True

            for obj in col.objects:
                if obj.library:
                    obj.make_local()

                    print(f"WARNING: Making linked object '{obj.name}' local!")

                    made_local = True

                    if obj.data and obj.data.library:
                        obj.data.make_local()

                        print(f"WARNING: Making linked data '{obj.data.name}' local!")

            for matname in ['base', 'HUD.black.transparent', 'HUD.blue', 'HUD.red', 'HUD.white', 'HUD.white.transparent']:
                mat = bpy.data.materials.get(matname)

                if mat.library:
                    mat.make_local()

                    made_local = True

                    print(f"WARNING: Making linked material '{mat.name}' local!")

        plugcol = bpy.data.collections.get('Plug')

        for obj in plugobjs:
            plugcol.objects.link(obj)

        handle = plugobjs[0]
        handle.matrix_world = Matrix()

        dg = context.evaluated_depsgraph_get()

        maxscale = 1.8
        handlemaxdim = max(handle.dimensions)

        handle.matrix_world = Matrix.Scale(maxscale / handlemaxdim, 4) @ handle.matrix_world
        dg.update()

        HUDlayer = scene.view_layers.get('HUD')
        bglayer = scene.view_layers.get('bg')
        Pluglayer = scene.view_layers.get('Plug')

        basemat = bpy.data.materials.get('base')

        if not basemat:
            print("WARNING: No basemat found!")

        if not Pluglayer.material_override:
            print(f"WARNING: Material Override is not set in view layer '{Pluglayer.name}'")
            Pluglayer.material_override = basemat

        if not bglayer.material_override:
            print(f"WARNING: Material Override is not set in view layer '{bglayer.name}'")
            bglayer.material_override = basemat

        context.window.view_layer = HUDlayer

        if self.showindicatorHUD:
            if self.showindicatorFILLETorEDGE:
                hudfillet = bpy.data.objects.get("HUD_FILLET")
                hudedge = bpy.data.objects.get("HUD_EDGE")
                if hudfillet and hudedge:
                    if fillet:
                        hudfillet.hide_render = False
                        hudfillet.hide_set(False)
                        hudedge.hide_render = True
                        hudedge.hide_set(True)
                    else:
                        hudfillet.hide_render = True
                        hudfillet.hide_set(True)
                        hudedge.hide_render = False
                        hudedge.hide_set(False)

            if self.showindicatorHOOKorARRAY:
                hudarray = bpy.data.objects.get("HUD_ARRAY")
                hudhook = bpy.data.objects.get("HUD_HOOK")
                if hudarray and hudhook:
                    if mods == "ARRAY":
                        hudarray.hide_render = False
                        hudarray.hide_set(False)
                        hudhook.hide_render = True
                        hudhook.hide_set(True)
                    elif mods == "HOOK":
                        hudarray.hide_render = True
                        hudarray.hide_set(True)
                        hudhook.hide_render = False
                        hudhook.hide_set(False)

            if self.showindicatorDEFORMER:
                huddeformer = bpy.data.objects.get("HUD_DEFORMER")
                if huddeformer:
                    if deformer:
                        huddeformer.hide_render = False
                        huddeformer.hide_set(False)
                        if deformer.MM.usedeformer:
                            mat = bpy.data.materials.get("HUD.white.transparent")
                            if mat:
                                huddeformer.material_slots[0].material = mat
        scene.render.filepath = iconpath

        scene.render.image_settings.file_format = 'PNG'

        context.window.view_layer = Pluglayer
        handle.select_set(True)
        bpy.ops.view3d.view_selected(use_all_regions=False)

        bpy.ops.render.render(write_still=True)

        print(" • Saved plug icon to '%s'" % (iconpath))

        for obj in scene.objects:
            if obj not in plugobjs:
                if obj.type == "CAMERA":
                    bpy.data.cameras.remove(obj.data, do_unlink=True)

                elif obj.type == "LIGHT":
                    bpy.data.lights.remove(obj.data, do_unlink=True)

                else:
                    bpy.data.objects.remove(obj, do_unlink=True)

        img = bpy.data.images.get('Render Result')
        if img:
            bpy.data.images.remove(img, do_unlink=True)

        for name in ['base', 'HUD.black.transparent', 'HUD.blue', 'HUD.red', 'HUD.white', 'HUD.white.transparent']:
            mat = bpy.data.materials.get(name)
            if mat:
                bpy.data.materials.remove(mat, do_unlink=True)

        for name in ['comp.blur', 'comp.combine', 'comp.passes']:
            group = bpy.data.node_groups.get(name)
            if group:
                bpy.data.node_groups.remove(group)

        world = bpy.data.worlds.get('ThumbnailWorld')
        if world:
            bpy.data.worlds.remove(world, do_unlink=True)

        for col in scene.collection.children:
            bpy.data.collections.remove(col, do_unlink=True)

        scene.view_layers.remove(HUDlayer)
        scene.view_layers.remove(bglayer)

        Pluglayer.name = 'View Layer'

        return scene

    def save_blend(self, context, scene, plugobjs, plugname, blendpath):
        mcol = scene.collection

        plugcol = bpy.data.collections.new(name=plugname)
        mcol.children.link(plugcol)

        handle = None

        for obj in plugobjs:
            plugcol.objects.link(obj)
            if not any([obj.MM.isplug, obj.MM.isplughandle, obj.MM.isplugsubset, obj.type == "EMPTY"]):
                obj.hide_set(True)

        scene.name = 'Plug Asset'

        handle = plugobjs[0]
        handle.matrix_world = Matrix()
        context.view_layer.objects.active = handle

        bpy.data.libraries.write(filepath=blendpath, datablocks={scene}, path_remap='RELATIVE_ALL')

        print(" • Saved plug blend to '%s'" % (blendpath))

        bpy.data.collections.remove(plugcol, do_unlink=True)

        bpy.data.scenes.remove(scene, do_unlink=True)

class SetPlugProps(bpy.types.Operator):
    bl_idname = "machin3.set_plug_props"
    bl_label = "MACHIN3: Set Plug Props"
    bl_description = "Set/Change Plug properties"
    bl_options = {'REGISTER', 'UNDO'}

    prop: EnumProperty(name="Property", items=plug_prop_items, default="NONE")
    hasfillet: BoolProperty(name="Has Fillet", default=False)
    deformerprecision: IntProperty(name="Deformer Precision", default=4)
    usedeformer: BoolProperty(name="Use Deformer", default=False)
    forcesubsetdeform: BoolProperty(name="Force Subset Deform", default=False)
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.prop(self, "prop", expand=True)
        if self.prop == "PLUG":
            column.prop(self, "hasfillet")

        if self.prop in ["PLUG", "SUBSET"]:
            if self.deformerprecision > 4:
                column.label(text="Careful, values above 4 are increasingly slow", icon="ERROR")

            column.prop(self, "deformerprecision")
        if self.prop == "SUBSET":
            column.prop(self, "forcesubsetdeform")
        if self.prop == "DEFORMER":
            column.prop(self, "usedeformer")
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and context.active_object:
            return len(context.selected_objects) == 1

    def invoke(self, context, event):
        active = context.active_object

        if active.MM.isplug:
            self.set_props(active, init=True, plug=True)
        elif active.MM.isplughandle:
            self.set_props(active, init=True, handle=True)
        elif active.MM.isplugsubset:
            self.set_props(active, init=True, subset=True)
        elif active.MM.isplugdeformer:
            self.set_props(active, init=True, deformer=True)
        elif active.MM.isplugoccluder:
            self.set_props(active, init=True, occluder=True)
        else:
            self.set_props(active, init=True)

        return {'FINISHED'}

    def execute(self, context):
        active = context.active_object

        if self.prop == "NONE":
            self.set_props(active)
        elif self.prop == "PLUG":
            self.set_props(active, plug=True)
        elif self.prop == "HANDLE":
            self.set_props(active, handle=True)
        elif self.prop == "SUBSET":
            self.set_props(active, subset=True)
        elif self.prop == "DEFORMER":
            self.set_props(active, deformer=True)
        elif self.prop == "OCCLUDER":
            self.set_props(active, occluder=True)

        return {'FINISHED'}

    def set_props(self, obj, init=False, plug=False, handle=False, subset=False, deformer=False, occluder=False):
        if init:
            if plug:
                self.prop = "PLUG"
                self.hasfillet = obj.MM.hasfillet
                self.deformerprecision = obj.MM.deformerprecision
            elif handle:
                self.prop = "HANDLE"
            elif deformer:
                self.prop = "DEFORMER"
                self.usedeformer = obj.MM.usedeformer
            elif subset:
                self.prop = "SUBSET"
                self.deformerprecision = obj.MM.deformerprecision
                self.forcesubsetdeform = obj.MM.forcesubsetdeform
            else:
                self.prop = "NONE"

        obj.MM.isplug = plug
        obj.MM.isplughandle = handle
        obj.MM.isplugsubset = subset
        obj.MM.isplugdeformer = deformer
        obj.MM.isplugoccluder = occluder

        if not init:
            if plug:
                obj.MM.hasfillet = self.hasfillet
                obj.MM.deformerprecision = self.deformerprecision
                hide_render(obj, False)

            if subset:
                obj.MM.deformerprecision = self.deformerprecision
                obj.MM.forcesubsetdeform = self.forcesubsetdeform
                hide_render(obj, False)

            if deformer:
                obj.name = obj.name.replace("handle", "deformer")
                obj.MM.usedeformer = self.usedeformer
                obj.show_in_front = False
                hide_render(obj, True)

            if occluder:
                obj.name = obj.name.replace("handle", "occluder")
                obj.show_all_edges = True
                obj.show_in_front = False
                obj.cycles.is_shadow_catcher = True
                hide_render(obj, False)

class ClearPlugProps(bpy.types.Operator):
    bl_idname = "machin3.clear_plug_props"
    bl_label = "MACHIN3: Clear Plug Properties"
    bl_description = "Clear Plug properties"
    bl_options = {'REGISTER', 'UNDO'}

    alsoclearvgroups: BoolProperty(name="Also Clear Vertex Groups", default=True)
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, "alsoclearvgroups")

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object

    def execute(self, context):
        sel = context.selected_objects

        for obj in sel:
            print("Clearing %s's plug properies" % (obj.name))

            if obj.MM.isplug:
                obj.MM.isplug = False
                print(" • cleared 'isplug' property")

                if self.alsoclearvgroups:
                    obj.vertex_groups.clear()
                    print(" • cleared plug object's vertex groups")

            if obj.MM.isplughandle:
                obj.MM.isplughandle = False
                print(" • cleared 'isplughandle' property")

            if obj.MM.isplugsubset:
                obj.MM.isplugsubset = False
                print(" • cleared 'isplugsubset' property")

            if obj.MM.isplugdeformer:
                obj.MM.isplugdeformer = False
                print(" • cleared 'isplugdeformer' property")
            if obj.MM.isplugoccluder:
                obj.MM.isplugoccluder = False
                print(" • cleared 'isplugoccluder' property")

            if obj.MM.deformerprecision != 4:
                obj.MM.deformerprecision = 4
                print(" • reset 'deformerprecision' property to 4")
            if obj.MM.usedeformer:
                obj.MM.usedeformer = False
                print(" • cleared 'usedeformer' property")
            if obj.MM.forcesubsetdeform:
                obj.MM.forcesubsetdeform = False
                print(" • cleared 'forcesubsetdeform' property")
        return {'FINISHED'}
