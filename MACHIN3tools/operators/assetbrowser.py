import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty

from bpy_extras.view3d_utils import region_2d_to_location_3d
from mathutils import Quaternion, Vector, Matrix

import numpy as np
import os

from .. utils.asset import set_asset_catalog_id, set_asset_name, set_asset_tags, set_asset_meta_data, get_asset_ids, get_asset_library_reference, is_local_assembly_asset, set_asset_catalog, set_asset_library_reference, update_asset_catalogs, get_assetbrowser_bookmarks, get_catalogs_from_asset_libraries, get_libref_and_catalog, set_assetbrowser_bookmarks, validate_libref_and_catalog, get_display_size_from_area
from .. utils.collection import duplicate_collection, get_assets_collection, get_collection_objects, get_scene_collections, set_collection_visibility
from .. utils.data import get_id_data_type, get_pretty_linked_data
from .. utils.draw import draw_fading_label, draw_points, draw_point, get_text_dimensions
from .. utils.math import average_locations, create_coords_bbox, create_rotation_matrix_from_vectors, get_loc_matrix, get_sca_matrix
from .. utils.modifier import get_mod_obj, remote_boolean_poll, remove_mod
from .. utils.object import clear_rotation, get_active_object, get_eval_bbox, get_object_tree, get_parent, has_decal_backup, has_stashes, is_decal, is_decal_backup, is_instance_collection, is_linked_object, is_stash_object, remove_obj, duplicate_objects, unparent
from .. utils.registration import get_path, get_prefs
from .. utils.render import is_cycles_view
from .. utils.scene import create_scene, ensure_compositor_nodes
from .. utils.system import printd
from .. utils.ui import force_ui_update, get_icon, popup_message
from .. utils.view import add_obj_to_local_view, ensure_visibility, get_view_bbox, get_view_origin_and_dir, is_local_view, is_obj_in_scene
from .. utils.workspace import get_3dview, get_3dview_area, is_3dview

from .. import MACHIN3toolsManager as M3

from .. items import create_assembly_asset_empty_location_items, create_assembly_asset_include_items, asset_browser_bookmark_props, id_data_types
from .. colors import white, yellow, blue, green, red

class CreateAssemblyAsset(bpy.types.Operator):
    bl_idname = "machin3.create_assembly_asset"
    bl_label = "MACHIN3: Create Assembly Asset"
    bl_description = "Create Assembly Asset from the selected Objects"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Asset Name", default="AssemblyAsset")
    tags: StringProperty(name="Asset Tags", default="", description="Comma separated list of tags")
    add_meta: BoolProperty(name="Set Meta Data", default=True, description="Set Meta Data like Author, Copyright and License.\n\nConfigure these in the MACHIN3tools addon prefs.")
    def update_duplicate(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if not self.duplicate and self.include == 'SELECTION':
            if self.all_objects_count != self.sel_objects_count:
                self.avoid_update = True
                self.include = 'HIERARCHY'

    duplicate: BoolProperty(name="Duplicate Asset Objects", description="Duplication ensures the Asset Objects become fully independent, and the Objects in the initial Selection remain ontouched.\n\nDuplication supports Assembly Creaton from parts of a Hierarchy, and removal of potential Decal Backups and Stash Objects.\nDisabling Duplication forces Assembly Creation of the entire Hierarchy.", default=True, update=update_duplicate)
    def update_include(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.include == 'SELECTION' and not self.duplicate:
            if self.all_objects_count != self.sel_objects_count:
                self.avoid_update = True
                self.include = 'HIERARCHY'

    include: EnumProperty(name="Include Asset Objects", items=create_assembly_asset_include_items, description="Chose the Scope of the Asset Objects", default='HIERARCHY', update=update_include)
    keep_decal_backups: BoolProperty(name="keep Decal Backups", default=True)
    keep_stash_objects: BoolProperty(name="keep Stash Objects", default=True)
    location: EnumProperty(name="Empty Location", items=create_assembly_asset_empty_location_items, description="Location of Asset's Empty", default='AVGFLOOR')
    drop_asset_into_scene: BoolProperty(name="Drop Asset into Scene", description="Drop the Asset into the Scene immedeately\nIf disabled, the asset will appear in the Assetbrowser's 'Current File' library only", default=False)
    render_thumbnail: BoolProperty(name="Render Thumbnail", default=True)
    has_meta: BoolProperty()

    sel_objects_count: IntProperty()
    all_objects_count: IntProperty()

    avoid_update: BoolProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
           if not context.scene.M3.is_assembly_edit_scene:
               return bool(context.selected_objects)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Asset Info")

        column = box.column(align=True)

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Name')

        row = split.row(align=True)
        row.prop(self, 'name', text='')

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Catalog')

        row = split.row(align=True)
        row.prop(context.window_manager, 'M3_asset_catalogs', text='')

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Tags')

        row = split.row(align=True)
        row.prop(self, 'tags', text='')

        if self.has_meta:
            split = column.split(factor=0.25, align=True)
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            row.active = False
            row.label(text='Meta Data')

            row = split.row(align=True)
            row.prop(self, 'add_meta', text="Fill in meta data" if self.add_meta else "Leave empty", toggle=True)

        if get_prefs().assetbrowser_tools_use_originals:
            box = layout.box()
            box.label(text="Asset Creation")

            column = box.column(align=True)

            split = column.split(factor=0.25, align=True)
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            row.active = False
            row.label(text='Duplicate')

            row = split.row(align=True)
            text = "Create Asset as Copy" if self.duplicate else "Create Asset from Originals"
            row.prop(self, 'duplicate', text=text, toggle=True)

            if not self.duplicate:
                column.separator()

                row = column.row()
                row.alignment = 'RIGHT'
                row.label(text="Note, duplication is highly recommended", icon='INFO')
                column.separator()

        if self.all_objects_count or self.sel_object_count:
            objects_count, decal_backup_count, stash_object_count = self.get_object_counts()

            box = layout.box()

            row = box.row()
            row.label(text="Asset Scope")

            r = row.row()
            rr = r.row(align=True)
            rr.alignment = 'RIGHT'
            rr.active = False
            rr.label(text="Assembly Objects:")

            rr = r.row(align=True)
            rr.alignment = 'RIGHT'
            rr.label(text=str(objects_count))

            column = box.column(align=True)

            if self.include == 'SELECTION' and self.unselected_group_children_count:
                row = column.row()
                row.alignment = 'RIGHT'
                row.label(text=f"There are {self.unselected_group_children_count} unselected group objects!", icon='INFO')
                column.separator()

            split = column.split(factor=0.25, align=True)
            row = split.row(align=True)
            row.active = False
            row.alignment = 'RIGHT'
            row.label(text="Include")

            row = split.row(align=True)
            row.prop(self, 'include', expand=True)

            if self.duplicate:

                if decal_backup_count:
                    split = column.split(factor=0.25, align=True)
                    row = split.row(align=True)
                    row.active = False
                    row.alignment = 'RIGHT'
                    row.label(text="Decal Backups")

                    row = split.row(align=True)
                    row.prop(self, 'keep_decal_backups', text=f"Keep ({decal_backup_count})" if self.keep_decal_backups else "Discard All", toggle=True)

                if stash_object_count:
                    split = column.split(factor=0.25, align=True)
                    row = split.row(align=True)
                    row.active = False
                    row.alignment = 'RIGHT'
                    row.label(text="Stash Objects")

                    row = split.row(align=True)
                    row.prop(self, 'keep_stash_objects', text=f"Keep ({stash_object_count})" if self.keep_stash_objects else "Discard All", toggle=True)

        box = layout.box()
        box.label(text="Asset Empty")
        column = box.column(align=True)

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.active = False
        row.alignment = 'RIGHT'
        row.label(text="Position")

        row = split.row(align=True)
        row.prop(self, 'location', expand=True)

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.active = False
        row.alignment = 'RIGHT'
        row.label(text="Scene")

        row = split.row(align=True)
        row.prop(self, 'drop_asset_into_scene', toggle=True)

    def invoke(self, context, event):
        update_asset_catalogs(self, context)
        debug = False

        if debug:
            import time
            start = time.time()

        all_objects = self.get_assembly_asset_objects(context, include='HIERARCHY')

        self.all_objects_count = len(all_objects)
        self.all_decal_backup_count = len([obj for obj in all_objects if is_decal_backup(obj)])
        self.all_stash_object_count = len([obj for obj in all_objects if is_stash_object(obj)])

        if debug:
            print("\nobjects (all):", self.all_objects_count)
            print(" decal backups:", self.all_decal_backup_count)
            print(" stash objects:", self.all_stash_object_count)

        sel_objects = self.get_assembly_asset_objects(context, include='SELECTION')

        self.sel_objects_count = len(sel_objects)
        self.sel_decal_backup_count = len([obj for obj in sel_objects if is_decal_backup(obj)])
        self.sel_stash_object_count = len([obj for obj in sel_objects if is_stash_object(obj)])

        if debug:
            print("\nobjects (selected):", self.sel_objects_count)
            print(" decal backups:", self.sel_decal_backup_count)
            print(" stash objects:", self.sel_stash_object_count)

        group_children = set()

        for obj in sel_objects:
            if obj.M3.is_group_empty:
                group_children.update(obj.children_recursive)

        self.unselected_group_children_count = len(group_children - sel_objects)

        if debug:
            print("\nunselected group children:", self.unselected_group_children_count)

            print("\ntook:", time.time() - start, "seconds")
            return {'FINISHED'}

        if not get_prefs().assetbrowser_tools_use_originals and not self.duplicate:
            self.duplicate = True

        if self.include == 'SELECTION' and not self.duplicate:
            if self.all_objects_count != self.sel_objects_count:
                self.avoid_update = True
                self.include = 'HIERARCHY'

        self.has_meta = any([getattr(get_prefs(), f"assetbrowser_tools_meta_{meta}") for meta in ['author', 'copyright', 'license']])

        return context.window_manager.invoke_props_dialog(self, width=350)

    def execute(self, context):
        name = self.name.strip()

        if name:
            print(f"\nINFO: Creating Assembly Asset from {self.include} of {'duplicated' if self.duplicate else 'original'} objects: {name}")

            objects = self.get_assembly_asset_objects(context, include=self.include)

            loc = self.get_empty_location(context, objects, debug=False)

            if self.duplicate:
                duplicates = duplicate_objects(context, objects)

                for obj, data in duplicates.items():

                    obj.M3.hide = data['vis']['hide'] or not (data['vis']['viewlayer'] and data['vis']['visible_collection'])

                    obj.M3.hide_viewport = data['vis']['hide_viewport']

                _, decal_backup_count, stash_object_count = self.get_object_counts()

                if decal_backup_count and not self.keep_decal_backups:
                    print(f"WARNING: Skipping {decal_backup_count} Decal Backups")
                    self.delete_decal_backups(duplicates)

                if stash_object_count and not self.keep_stash_objects:
                    print(f"WARNING: Skipping {stash_object_count} Stash Objects")
                    self.delete_stashes(duplicates)

                if self.include == 'SELECTION':
                    self.process_selection(duplicates)

                empty, empty_cols = self.create_assembly_asset_as_copy(context, name, duplicates, loc)

            else:
                empty, empty_cols = self.create_assembly_asset_from_originals(context, name, objects, loc)

            set_asset_tags(empty, self.tags)

            if self.has_meta and self.add_meta:
                set_asset_meta_data(empty)

            self.switch_asset_browser_to_LOCAL(context, empty)

            asset_bbox, asset_dimensions = self.get_asset_bbox(duplicates if self.duplicate else objects)

            empty.empty_display_size = min(asset_dimensions) * 0.7

            if asset_bbox and self.render_thumbnail:
                self.create_asset_thumbnail(context, empty, asset_bbox)

            self.finalize(context, loc, empty, empty_cols, asset_dimensions)

            if not asset_bbox:
                draw_fading_label(context, text="Could not create Asset Thumbnail from current Selection of Objects", color=red, move_y=30, time=3)

            return {'FINISHED'}

        else:
            popup_message("The chosen asset name can't be nothing", title="Illegal Name")
            return {'CANCELLED'}

    def get_object_counts(self):
        if self.include == 'HIERARCHY':
            objects_count = self.all_objects_count
            decal_backup_count = self.all_decal_backup_count
            stash_object_count = self.all_stash_object_count

        else:
            objects_count = self.sel_objects_count
            decal_backup_count = self.sel_decal_backup_count
            stash_object_count = self.sel_stash_object_count

        return objects_count, decal_backup_count, stash_object_count

    def get_assembly_asset_objects(self, context, include='HIERARCHY'):
        def get_entire_hierarchy(context, objects):
            for obj in context.selected_objects:
                if obj not in objects:
                    tops = get_parent(obj, recursive=True, debug=True)
                    top = tops[-1] if tops else obj

                    obj_tree = [top]
                    get_object_tree(top, obj_tree, mod_objects=True, find_disabled_mods=False, include_hidden=['VIEWLAYER', 'COLLECTION'], force_stash_objects=True, force_decal_backups=True, debug=False)

                    objects.update(obj_tree)

        def get_selected_objects_and_their_children(context, objects):
            sel = context.selected_objects

            objects.update(sel)

            for obj in sel:

                children = [ob for ob in obj.children_recursive if not obj.M3.is_group_empty and is_obj_in_scene(ob)]
                objects.update(children)

            decal_backups = set()
            stash_objects = set()

            for obj in objects:
                if has_stashes(obj):
                    for stash in obj.MM.stashes:
                        if stash.obj:
                            stash_objects.add(stash.obj)

                if has_decal_backup(obj):
                    if obj.DM.decalbackup:
                        decal_backups.add(obj.DM.decalbackup)

            objects |= decal_backups
            objects |= stash_objects

        objects = set()

        if include == 'HIERARCHY':
            get_entire_hierarchy(context, objects)

        elif include == 'SELECTION':
            get_selected_objects_and_their_children(context, objects)

        return objects

    def get_empty_location(self, context, objects, debug=False):
        if self.location in ['AVG', 'AVGFLOOR']:

            location_objs = [obj for obj in objects if obj.visible_get() and not obj.parent and not is_decal(obj) and obj.display_type not in ['WIRE', 'BOUNDS', '']]

            if not location_objs:
                location_objs = [obj for obj in context.selected_objects]

            loc = average_locations([obj.matrix_world.decompose()[0] for obj in location_objs])
            color = yellow

            if self.location == 'AVGFLOOR':
                loc.z = 0
                color = green

        elif self.location == 'CURSOR':
            loc = context.scene.cursor.location
            color = blue

        else:
            loc = Vector((0, 0, 0))
            color = white

        if debug:
            draw_point(loc, color=color, modal=False)
            context.area.tag_redraw()

        return loc

    def delete_decal_backups(self, objects, debug=False):

        if debug:
            print()
            print(len(objects))

        decals_with_backups = [obj for obj in objects if is_decal(obj) and has_decal_backup(obj)]

        for decal in decals_with_backups:
            decal.DM.decalbackup = None

        decal_backups = {obj for obj in objects if is_decal_backup(obj)}

        for obj in decal_backups:
            del objects[obj]

            if debug:
                print(" removing decal backup:", obj.name)

        bpy.data.batch_remove(decal_backups)

        if debug:
            print(len(objects))

    def delete_stashes(self, objects, debug=False):

        if debug:
            print()
            print(len(objects))

        objs_with_stashes = [obj for obj in objects if has_stashes(obj)]

        for obj in objs_with_stashes:
            obj.MM.stashes.clear()

        stash_objects = [obj for obj in objects if is_stash_object(obj)]

        for obj in stash_objects:
            del objects[obj]

            if debug:
                print(" removing stash object:", obj.name)

        bpy.data.batch_remove(stash_objects)

        if debug:
            print(len(objects))

    def process_selection(self, duplicates, debug=False):
        for obj in duplicates:

            if obj.parent and obj.parent not in duplicates:
                if debug:
                    print("", obj.name, "is a new root object")

                unparent(obj)

            if obj.M3.is_group_empty and not obj.children:
                if debug:
                    print("", obj.name, "is a group anchor")

                obj.M3.is_group_empty = False
                obj.M3.is_group_anchor = True

                obj.empty_display_size = obj.M3.group_size

                obj.empty_display_type = 'PLAIN_AXES'

                if (suffix := get_prefs().group_tools_suffix) and suffix in obj.name:
                    obj.name = obj.name.replace(suffix, '_anchor')
                else:
                    obj.name += "_anchor"

            if obj.modifiers and (mods := [(mod, modobj) for mod in obj.modifiers if (modobj := get_mod_obj(mod))]):
                for mod, modobj in mods:
                    if modobj not in duplicates:
                        if debug:
                            print(f" {obj.name}'s mod {mod.name}'s mod object {modobj.name} is not among duplicated asset objects, removing mod")

                        remove_mod(mod)

    def finalize(self, context, loc, empty, empty_cols, asset_dimensions):
        if self.drop_asset_into_scene:
            empty = empty.copy()

            empty.location = loc

            for col in empty_cols:
                col.objects.link(empty)

            context.evaluated_depsgraph_get()

            context.view_layer.objects.active = empty

            if asset_dimensions:
                self.offset_asset_empty_towards_view(context, empty, asset_dimensions)

    def create_assembly_asset_as_copy(self, context, name, objects, loc):
        master_col = context.scene.collection

        main_asset_col = get_assets_collection(context)

        scene_collections = get_scene_collections(context)

        if not (data := scene_collections[main_asset_col])['visible']:
            if data['hidden']:
                data['layer_collections'][0].hide_viewport = False

            if data['excluded']:
                data['layer_collections'][0].exclude = False

        asset_col = bpy.data.collections.new(f"_{name}")
        asset_col.M3.is_asset_collection = True
        asset_col.color_tag = 'COLOR_02'

        main_asset_col.children.link(asset_col)

        object_cols = {col for obj in objects for col in obj.users_collection}

        empty_cols = [col for col in object_cols if all(ob.name in col.objects for ob in objects)]

        if not empty_cols:
            empty_cols = [master_col]

        for obj in objects:
            for col in obj.users_collection:
                if col in object_cols:
                    col.objects.unlink(obj)

        for obj in objects:
            if is_decal_backup(obj) or is_stash_object(obj):
                continue

            asset_col.objects.link(obj)

            if obj.display_type in ['WIRE', 'BOUNDS'] or (obj.type == 'EMPTY' and not obj.instance_collection):

                if obj.M3.is_group_empty:
                    if obj.parent:
                        obj.hide_viewport = True

                    else:
                        obj.hide_viewport = False
                        obj.empty_display_type = 'SPHERE'
                        obj.empty_display_size = obj.M3.group_size  # set their size too, to negate hide_empties behavior

                elif obj.M3.is_group_anchor:
                    obj.hide_viewport = False

                else:
                    obj.hide_set(True)

                    obj.hide_viewport = True

        empty = bpy.data.objects.new(name, object_data=None)
        empty.instance_collection = asset_col
        empty.instance_type = 'COLLECTION'

        empty.M3.asset_version = "1.2"

        asset_col.instance_offset = loc

        empty.asset_mark()

        set_asset_catalog(self, empty)

        scene_collections[main_asset_col]['layer_collections'][0].exclude = True

        return empty, empty_cols

    def create_assembly_asset_from_originals(self, context, name, objects, loc):
        master_col = context.scene.collection

        main_asset_col = get_assets_collection(context)

        scene_collections = get_scene_collections(context)

        if not (data := scene_collections[main_asset_col])['visible']:
            if data['hidden']:
                data['layer_collections'][0].hide_viewport = False

            if data['excluded']:
                data['layer_collections'][0].exclude = False

        asset_col = bpy.data.collections.new(f"_{name}")
        asset_col.M3.is_asset_collection = True
        asset_col.color_tag = 'COLOR_02'

        main_asset_col.children.link(asset_col)

        object_cols = {col for obj in objects for col in obj.users_collection}

        empty_cols = [col for col in object_cols if all(ob.name in col.objects for ob in objects)]

        if not empty_cols:
            empty_cols = [master_col]

        for obj in objects:
            if is_decal_backup(obj) or is_stash_object(obj):
                continue

            asset_col.objects.link(obj)

            if obj.display_type in ['WIRE', 'BOUNDS'] or (obj.type == 'EMPTY' and not obj.instance_collection and not obj.M3.is_group_empty):
                obj.hide_set(True)

                obj.hide_viewport = True

                obj.M3.hide = True
                obj.M3.hide_viewport = True

        empty = bpy.data.objects.new(name, object_data=None)
        empty.instance_collection = asset_col
        empty.instance_type = 'COLLECTION'

        empty.M3.asset_version = "1.2"

        asset_col.instance_offset = loc

        empty.asset_mark()

        set_asset_catalog(self, empty)

        scene_collections[main_asset_col]['layer_collections'][0].exclude = True

        return empty, empty_cols

    def switch_asset_browser_to_LOCAL(self, context, asset):
        asset_browsers = [area for screen in context.workspace.screens for area in screen.areas if area.type == 'FILE_BROWSER' and area.ui_type == 'ASSETS']

        if len(asset_browsers) == 1:
            for space in asset_browsers[0].spaces:
                if space.type == 'FILE_BROWSER':
                    if get_asset_library_reference(space.params) != 'LOCAL':
                        set_asset_library_reference(space.params, 'LOCAL')

                    space.show_region_tool_props = True

                    set_asset_catalog_id(space.params, 'ALL')

                    space.activate_asset_by_id(asset, deferred=True)

    def get_asset_bbox(self, objects, debug=False):
        coords = []

        bbox_objects = [obj for obj in objects if not is_decal(obj) and not is_decal_backup(obj) and not is_stash_object(obj)]

        for obj in bbox_objects:

            bbox = [obj.matrix_world @ co for co in get_eval_bbox(obj)]

            if bbox:
                coords.extend(bbox)

        if coords:
            bbox, _, dimensions = create_coords_bbox(coords)

            if debug:
                draw_points(coords, color=yellow, modal=False)
                draw_points(bbox, color=blue, modal=False)

            return bbox, dimensions
        return None, None

    def offset_asset_empty_towards_view(self, context, empty, asset_dimensions):
        mx = empty.matrix_world

        axes = [('X', mx.to_quaternion() @ Vector((1, 0, 0))),
                ('X', mx.to_quaternion() @ Vector((-1, 0, 0))),
                ('Y', mx.to_quaternion() @ Vector((0, 1, 0))),
                ('Y', mx.to_quaternion() @ Vector((0, -1, 0)))]

        _, view_dir = get_view_origin_and_dir(context)

        aligned = []

        for label, axis in axes:
            aligned.append((label, axis, axis.dot(view_dir)))

        label, axis = min(aligned, key=lambda x: x[2])[:2]

        amount = asset_dimensions[0] if label == 'X' else asset_dimensions[1]
        empty.matrix_world @= get_loc_matrix(axis * amount * 1.1)

    def create_asset_thumbnail(self, context, obj, bbox, show_overlays=False):
        def get_square_view_bbox(debug=False):
            render_bbox = get_view_bbox(context, bbox, margin=20, border_gap=0, debug=False)

            if debug:
                print("render bbox:", render_bbox)

            render_bbox_width = (render_bbox[1] - render_bbox[0]).length
            render_bbox_height = (render_bbox[2] - render_bbox[1]).length

            if debug:
                print("  bbox width:", render_bbox_width)
                print(" bbox height:", render_bbox_height)

            if render_bbox_width > render_bbox_height:
                delta = int((render_bbox_width - render_bbox_height) / 2)

                xmin = render_bbox[0].x
                xmax = render_bbox[1].x

                ymin = max(min(render_bbox[1].y - delta, region_height), 0)
                ymax = max(min(render_bbox[2].y + delta, region_height), 0)

                square_bbox = [Vector((xmin, ymin)), Vector((xmax, ymin)), Vector((xmax, ymax)), Vector((xmin, ymax))]

            elif render_bbox_width < render_bbox_height:
                delta = int((render_bbox_height - render_bbox_width) / 2)

                xmin = max(min(render_bbox[0].x - delta, region_width), 0)
                xmax = max(min(render_bbox[1].x + delta, region_width), 0)

                ymin = render_bbox[1].y
                ymax = render_bbox[2].y

                square_bbox = [Vector((xmin, ymin)), Vector((xmax, ymin)), Vector((xmax, ymax)), Vector((xmin, ymax))]

            else:
                square_bbox = render_bbox

            square_bbox_width = (square_bbox[1] - square_bbox[0]).length
            square_bbox_height = (square_bbox[2] - square_bbox[1]).length

            if debug:
                print("square bbox:", square_bbox)
                print(" square bbox width:", square_bbox_width)
                print("square bbox height:", square_bbox_height)

            return square_bbox, (int(square_bbox_width), int(square_bbox_height))

        def render_viewport():
            view = context.space_data
            cam = context.scene.camera
            render = context.scene.render

            is_cam_view = cam and view.region_3d.view_perspective == 'CAMERA'
            is_forced_cam = False
            is_cycles = is_cycles_view(context)

            initial = {'resolution_x': render.resolution_x,
                       'resolution_y': render.resolution_y,
                       'resolution_percentage': render.resolution_percentage,
                       'file_format': render.image_settings.file_format,
                       'show_overlays': view.overlay.show_overlays}

            if is_cam_view:
                initial['lens'] = cam.data.lens

            if is_cycles:
                cycles = context.scene.cycles

                settings = { 'use_adaptive_sampling': cycles.use_adaptive_sampling,
                             'adaptive_threshold': cycles.adaptive_threshold,
                             'samples': cycles.samples,
                             'use_denoising': cycles.use_denoising,
                             'denoising_input_passes': cycles.denoising_input_passes,
                             'denoising_prefilter': cycles.denoising_prefilter,
                             'denoising_quality': cycles.denoising_quality,
                             'denoising_use_gpu': cycles.denoising_use_gpu}

                initial['cycles'] = settings

                if not is_cam_view:

                    initial['camera'] = context.scene.camera

                    initial['active'] = context.active_object
                    initial['selected'] = context.selected_objects

                    bpy.ops.object.camera_add()

                    cam = context.active_object
                    context.scene.camera = cam

                    bpy.ops.view3d.camera_to_view()

                    cam.data.lens = view.lens
                    cam.data.sensor_width = 72

                    is_cam_view = True
                    is_forced_cam = True

            if is_cam_view and not is_forced_cam:
                init_resolution_ratio = render.resolution_x / render.resolution_y
                region_ratio = region_width / region_height
                factor = init_resolution_ratio / region_ratio

                if round(factor) > 1:
                    factor = region_ratio

            render.resolution_x = region_width
            render.resolution_y = region_height
            render.resolution_percentage = 100
            render.image_settings.file_format = 'PNG'
            view.overlay.show_overlays = show_overlays

            if is_cycles:
                 cycles.use_adaptive_sampling = True
                 cycles.adaptive_threshold = 0.1
                 cycles.samples = 4
                 cycles.use_denoising = True
                 cycles.denoising_input_passes = 'RGB'
                 cycles.denoising_prefilter = 'FAST'
                 cycles.denoising_quality = 'FAST'
                 cycles.denoising_use_gpu = True

            if is_cam_view and not is_forced_cam:
                cam.data.lens *= factor

            if is_cycles_view(context):
                bpy.ops.render.render(write_still=False)

            else:
                bpy.ops.render.opengl()

            result = bpy.data.images.get('Render Result')

            if result:
                filepath = os.path.join(get_path(), 'resources', 'asset_thumbnail_render.png')
                result.save_render(filepath=filepath)

            context.scene.render.resolution_x = initial['resolution_x']
            context.scene.render.resolution_y = initial['resolution_y']
            context.scene.render.resolution_percentage = initial['resolution_percentage']
            context.scene.render.image_settings.file_format = initial['file_format']
            view.overlay.show_overlays = initial['show_overlays']

            if is_cycles:
                cycles.use_adaptive_sampling = initial['cycles']['use_adaptive_sampling']
                cycles.adaptive_threshold = initial['cycles']['adaptive_threshold']
                cycles.samples = initial['cycles']['samples']
                cycles.use_denoising = initial['cycles']['use_denoising']
                cycles.denoising_input_passes = initial['cycles']['denoising_input_passes']
                cycles.denoising_prefiltert = initial['cycles']['denoising_prefilter']
                cycles.denoising_quality = initial['cycles']['denoising_quality']
                cycles.denoising_use_gpu = initial['cycles']['denoising_use_gpu']

            if is_forced_cam:
                bpy.data.cameras.remove(cam.data, do_unlink=True)

                if cam := initial['camera']:
                    context.scene.camera = cam

                if active := initial['active']:
                    context.view_layer.objects.active = active

                for obj in initial['selected']:
                    obj.select_set(True)

            if is_cam_view and not is_forced_cam:
                cam.data.lens = initial['lens']

            if result:
                 image = bpy.data.images.load(filepath=filepath)
                 return image

        def crop_image(image, crop_box, dimensions, debug=False):
            width, height = dimensions

            pixels = np.array(image.pixels[:])

            pixels = pixels.reshape((region_height, region_width, 4))

            left = int(crop_box[0].x)
            right = int(crop_box[1].x)
            top = int(crop_box[1].y)
            bottom = int(crop_box[2].y)

            cropped_pixels = pixels[top:bottom, left:right, :]

            cropped = bpy.data.images.new("Cropped Asset Render", width=width, height=height)

            try:
                cropped.pixels[:] = cropped_pixels.flatten()         # see CodeMaX below, the difference here is minor though, but extreme for the image_pixels_float

            except Exception as e:
                print("something failed ugh here already actually")
                print(e)

                print("cropped pixels")
                print(cropped_pixels)

            if debug:
                print("cropped width:", width)
                print("cropped height:", height)

            scale_factor = max(width, height) / 256

            if scale_factor > 1:
                if debug:
                    print("scale down by:", scale_factor)

                cropped.scale(int(width / scale_factor), int(height / scale_factor))

            return cropped

        region_width = context.region.width
        region_height = context.region.height

        square_bbox, cropped_dimensions = get_square_view_bbox(debug=False)

        if image := render_viewport():
            cropped = crop_image(image, square_bbox, cropped_dimensions)

            obj.preview_ensure()
            obj.preview.image_size = cropped.size

            try:
                obj.preview.image_pixels_float[:] = cropped.pixels   # CodeManX is a legend, see https://blender.stackexchange.com/a/3678/33919
            except Exception as e:
                print("something failed ugh")
                print(e)

                print("cropped pixels")
                print(cropped.pixels)

            os.unlink(image.filepath)

            bpy.data.images.remove(image, do_unlink=True)
            bpy.data.images.remove(cropped, do_unlink=True)

class CreateAssemblyVariant(bpy.types.Operator):
    bl_idname = "machin3.create_assembly_variant"
    bl_label = "MACHIN3: Create Assembly Variant"
    bl_options = {'REGISTER', 'UNDO'}

    link_object_data: BoolProperty(name="Link Object Data", default=False)
    @classmethod
    def poll(cls, context):
        active = context.active_object
        return bool(active and active.select_get() and is_instance_collection(active))

    @classmethod
    def description(cls, context, propertes):
        desc = "Create a new Variant of the selected Assembly\nThis duplicates the Instance Collection structure and contents, creating an independent Assembly."
        desc += "\n\nALT: Link Object Data during Duplication"
        return desc

    def invoke(self, context, event):
        self.link_object_data = event.alt
        return self.execute(context)

    def execute(self, context):
        active = context.active_object
        icol = is_instance_collection(active)

        assembly_objects = get_collection_objects(icol)

        dup_icol, dup_map = duplicate_collection(icol)

        duplicated = duplicate_objects(context, assembly_objects, linked=self.link_object_data)

        reverse_map = {data['original']: dup for dup, data in duplicated.items()}

        for dup in duplicated:
            for col in dup.users_collection:
                col.objects.unlink(dup)

        for dup_col, col_data in dup_map.items():
            objects = col_data['objects']

            for orig in objects:
                dup_col.objects.link(reverse_map[orig])

        active.instance_collection = dup_icol

        context.view_layer.objects.active = active
        active.select_set(True)
        return {'FINISHED'}

class TurnAssemblyIntoAsset(bpy.types.Operator):
    bl_idname = "machin3.turn_assembly_into_asset"
    bl_label = "MACHIN3: Turn Assembly into Asset"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Asset Name", default="AssemblyAsset")
    tags: StringProperty(name="Asset Tags", default="", description="Comma separated list of tags")
    add_meta: BoolProperty(name="Set Meta Data", default=True, description="Set Meta Data like Author, Copyright and License.\n\nConfigure these in the MACHIN3tools addon prefs.")
    skip_meta: BoolProperty(name="Skip adding Meta Data", default=False)
    has_meta: BoolProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and context.area:
            active = context.active_object
            return bool(active and is_instance_collection(active) and not is_local_assembly_asset(active) and not is_linked_object(active))

    @classmethod
    def description(cls, context, propertes):
        desc = "Turn selected Assembly into Local Asset"
        desc += "\nThis adds a thumbnail and allows your to drop it from the Asset Browser"
        desc += "\nIt also allows you set a unified name, assign a catalog, add tags and meta data"
        desc += "\n\nALT: Just mark the asset as such, and add the thumbnail"
        desc += "\nNote, you can always change the name, add tags, pick a catalog and add meta data later"
        return desc

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Asset Info")

        column = box.column(align=True)

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Name')

        row = split.row(align=True)
        row.prop(self, 'name', text='')

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Catalog')

        row = split.row(align=True)
        row.prop(context.window_manager, 'M3_asset_catalogs', text='')

        split = column.split(factor=0.25, align=True)
        row = split.row(align=True)
        row.alignment = 'RIGHT'
        row.active = False
        row.label(text='Tags')

        row = split.row(align=True)
        row.prop(self, 'tags', text='')

        if self.has_meta:
            split = column.split(factor=0.25, align=True)
            row = split.row(align=True)
            row.alignment = 'RIGHT'
            row.active = False
            row.label(text='Meta Data')

            row = split.row(align=True)
            row.prop(self, 'add_meta', text="Fill in meta data" if self.add_meta else "Leave empty", toggle=True)

    def invoke(self, context, event):
        self.skip_meta = event.alt

        if self.skip_meta:
            return self.execute(context)

        update_asset_catalogs(self, context)

        self.has_meta = any([getattr(get_prefs(), f"assetbrowser_tools_meta_{meta}") for meta in ['author', 'copyright', 'license']])

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        active = context.active_object
        icol = is_instance_collection(active)

        icol.M3.is_asset_collection = True
        icol.color_tag = 'COLOR_02'

        empty = bpy.data.objects.new(active.name, object_data=None)
        empty.instance_collection = icol
        empty.instance_type = 'COLLECTION'

        empty.empty_display_size = active.empty_display_size
        empty.asset_mark()

        empty.M3.asset_version = "1.2"

        if (scale := active.matrix_world.to_scale()) != Vector((1, 1, 1)):
            empty.matrix_world = Matrix.LocRotScale(Vector(), Quaternion(), scale)

        main_asset_col = get_assets_collection(context)

        main_asset_col.children.link(icol)

        if not self.skip_meta:

            set_asset_name(empty, self.name)

            set_asset_catalog(self, empty)

            set_asset_tags(empty, self.tags)

            if self.has_meta and self.add_meta:
                set_asset_meta_data(empty)

        CreateAssemblyAsset.switch_asset_browser_to_LOCAL(self, context, empty)

        bpy.ops.machin3.update_asset_thumbnail()

        return {'FINISHED'}

class UpdateAssetThumbnail(bpy.types.Operator):
    bl_idname = "machin3.update_asset_thumbnail"
    bl_label = "MACHIN3: Update Asset Thumbnail"
    bl_options = {'REGISTER', 'UNDO'}

    show_overlays: BoolProperty(name="Show Overlays", default=False)
    if True:
        setup_bbox_helper: BoolProperty(name="Setup Asset Thumbnail Helper Gizmo", description="This BBox Gizmo is used to fine-tune the framing of the Asset's Thumbnail", default=False)
        is_prop_invoke: BoolProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and context.area:
            if context.area.type == 'FILE_BROWSER' and context.area.ui_type == 'ASSETS':
                if get_3dview_area(context) and context.selected_objects:
                    active, id_type, local_id = get_asset_ids(context)
                    return active and id_type in ['OBJECT', 'MATERIAL', 'COLLECTION', 'ACTION', 'NODETREE'] and local_id

            elif context.area.type == 'VIEW_3D':
                active = context.active_object
                return bool(active and is_local_assembly_asset(active))

    @classmethod
    def description(cls, context, properties):
        desc = "Update the Asset Thumbnail via a Viewport Render of the Active Object"
        desc += "\nALT: Render Overlays too"
        desc += "\nCTRL: Setup and View-Align Thumbnail Helper, to fine-tune Thumbnail Framing"
        return desc

    def invoke(self, context, event):
        self.show_overlays = event.alt
        self.setup_bbox_helper = event.ctrl
        return self.execute(context)

    def execute(self, context):
        is_3d_view = context.area.type == 'VIEW_3D'

        if is_3d_view:

            active = context.active_object
            local_id = is_local_assembly_asset(active)

            sel = [active]

            if True and self.is_prop_invoke:
                area, region, region_data, _ = get_3dview(context)
            else:
                area, region, region_data = context.area, context.region, context.region_data

        else:
            _, _, local_id = get_asset_ids(context)

            sel = [obj for obj in context.selected_objects]

            area, region, region_data, _ = get_3dview(context)

        obj = sel[0]

        asset_bbox, asset_dimensions = CreateAssemblyAsset.get_asset_bbox(self, sel, debug=False)

        if asset_bbox or (True and obj.M3.use_asset_thumbnail_helper):

            if True and self.setup_bbox_helper:

                bbox_center = average_locations(asset_bbox)

                with context.temp_override(area=area, region=region, region_data=region_data):
                    view_origin, view_dir = get_view_origin_and_dir(context)

                    center = Vector((context.region.width / 2, context.region.height / 2))
                    offset = center + Vector((100, 0))

                    try:
                        center_3d = region_2d_to_location_3d(context.region, context.region_data, center, bbox_center)
                        offset_3d = region_2d_to_location_3d(context.region, context.region_data, offset, bbox_center)
                    except Exception as e:
                        print(f"WARNING: Could not create Asset Thumbnail Helper View Matrix because: {e}")
                        return {'CANCELLED'}

                normal = - view_dir.normalized()
                tangent = (offset_3d - center_3d).normalized()
                binormal = normal.cross(tangent)

                rotmx = create_rotation_matrix_from_vectors(tangent, binormal, normal)

                obj.M3.asset_thumbnail_helper_location_offset = bbox_center - obj.matrix_world.to_translation()
                obj.M3.asset_thumbnail_helper_rotation = rotmx.to_quaternion()

                scale = obj.M3.asset_thumbnail_helper_matrix.to_scale()

                if any(s <= 0 for s in scale) or (scale.x == 1 and scale.y == 1) or scale.z != 1:

                    with context.temp_override(area=area, region=region, region_data=region_data):
                        try:
                            view_bbox = get_view_bbox(context, asset_bbox)

                            view_bbox_3d = [region_2d_to_location_3d(context.region, context.region_data, co, bbox_center) for co in view_bbox]

                        except Exception as e:
                            print(f"WARNING: Could not create Asset Thumbnail Helper View Matrix because: {e}")
                            return {'CANCELLED'}

                    width = (view_bbox_3d[1] - view_bbox_3d[0]).length
                    height = (view_bbox_3d[3] - view_bbox_3d[0]).length

                    helper_matrix = get_sca_matrix(obj.matrix_world.to_scale()).inverted_safe() @ get_sca_matrix(Vector((width, height, 1)))

                    helper_matrix[2][2] = 1

                    obj.M3.asset_thumbnail_helper_matrix = helper_matrix

                if not obj.M3.use_asset_thumbnail_helper:
                    obj.M3.use_asset_thumbnail_helper = True

                force_ui_update(context)
                return {'FINISHED'}

            else:

                if True and obj.M3.use_asset_thumbnail_helper:
                    loc, rot, sca = obj.matrix_world.decompose()

                    gzm_mx = Matrix.LocRotScale(loc + obj.M3.asset_thumbnail_helper_location_offset, obj.M3.asset_thumbnail_helper_rotation, sca) @ obj.M3.asset_thumbnail_helper_matrix

                    asset_bbox = [
                        gzm_mx @ Vector((-0.5, -0.5, 0)),
                        gzm_mx @ Vector((0.5, -0.5, 0)),
                        gzm_mx @ Vector((0.5, 0.5, 0)),
                        gzm_mx @ Vector((-0.5, 0.5, 0))
                    ]

                with context.temp_override(area=area, region=region, region_data=region_data):
                    CreateAssemblyAsset.create_asset_thumbnail(self, context, local_id, asset_bbox, show_overlays=self.show_overlays)

                if not is_3d_view:
                    context.space_data.activate_asset_by_id(local_id, deferred=True)
                context.area.tag_redraw()
                return {'FINISHED'}

        else:
            if is_3d_view:
                draw_fading_label(context, text=["Could not create Asset Thumbnail from current Selection of Objects", "Asset Bounding Box was not created"], color=[red, yellow], move_y=40, time=4)

            else:
                with context.temp_override(area=area, region=region, region_data=region_data):
                    draw_fading_label(context, text=["Could not create Asset Thumbnail from current Selection of Objects", "Asset Bounding Box was not created"], color=[red, yellow], move_y=40, time=4)

            return {'CANCELLED'}
        return {'FINISHED'}

class RemoveAssemblyAsset(bpy.types.Operator):
    bl_idname = "machin3.remove_assembly_asset"
    bl_label = "MACHIN3: Remove Assembly Asset"
    bl_options = {'REGISTER', 'UNDO'}

    remove_asset: BoolProperty(name="Remove entire Local Asset")

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if is_instance_collection(obj)]

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        column.label(text="This will remove the entire asset from the .blend file!", icon_value=get_icon('error'))
        column.label(text="It will no longer be available in the asset browser after this operation.", icon='BLANK1')
        column.label(text="If the asset was created without duplication, then the original objects will also be removed!", icon='BLANK1')

    @classmethod
    def description(cls, context, properties):
        if properties.remove_asset:
            return "Remove entire Local Assembly Asset from the file.\nCareful, this removes it from the Asset Browser too!"
        else:
            return "Remove Assembly Object from current scene/view layer, if it's marked as an asset it will remain accessible from the Asset Browser!.\nIf its instance collection has no other users, remove it and the contained objects too"

    def invoke(self, context, event):
        if self.remove_asset:
            return context.window_manager.invoke_props_dialog(self, width=550)

        return self.execute(context)

    def execute(self, context):
        draw_legacy_message = False

        assemblies = {obj for obj in context.selected_objects if is_instance_collection(obj)}

        asset_originals = {obj for obj in assemblies if obj.asset_data}

        if not self.remove_asset:
            assemblies -= asset_originals

        asset_cols = set(obj.instance_collection for obj in assemblies if not obj.library)

        if self.remove_asset:
            other_assemblies = [obj for obj in bpy.data.objects if obj not in assemblies and is_instance_collection(obj) and obj.instance_collection in asset_cols]

        legacy_offset_map = {}

        for obj in assemblies:
            if not obj.instance_collection.M3.is_asset_collection:
                legacy_offset_map[obj.instance_collection] = obj.matrix_world.copy()

        for obj in assemblies:
            bpy.data.objects.remove(obj, do_unlink=True)

        if self.remove_asset:
            for obj in other_assemblies:
                bpy.data.objects.remove(obj, do_unlink=True)

        for col in asset_cols:

            if not col.users_dupli_group:

                if col.M3.is_asset_collection:
                    for obj in col.objects:
                        remove_obj(obj)

                else:
                    ensure_visibility(context, list(col.objects), select=True)

                    for obj in col.objects:
                        if not obj.parent:
                            obj.matrix_world = legacy_offset_map[col] @ obj.matrix_world

                    draw_legacy_message = True

                bpy.data.collections.remove(col, do_unlink=True)

        if not self.remove_asset and asset_originals:
            for obj in asset_originals:
                for col in obj.users_collection:
                    col.objects.unlink(obj)

        main_asset_col = get_assets_collection(context, create=False)

        if main_asset_col and not (main_asset_col.children or main_asset_col.objects):
            bpy.data.collections.remove(main_asset_col, do_unlink=True)

        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        if draw_legacy_message:
            draw_fading_label(context, text=["Legacy Asset Objects have been disassembled, but not removed automatically!", "This is because MACHIN3tools can't be sure they aren't the original objects", "Please remove manually, if desired"], color=[yellow, white], move_y=60, time=6)

        return {'FINISHED'}

class DisassembleAssembly(bpy.types.Operator):
    bl_idname = "machin3.disassemble_assembly"
    bl_label = "MACHIN3: Disassemble Assembly"
    bl_description = "Make Assembly Objects (Instance Collection) accessible"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if is_instance_collection(obj)]

    def execute(self, context):
        assemblies = [obj for obj in context.selected_objects if is_instance_collection(obj)]

        MakeIDLocal.make_obj_data_icol_local(self, context)

        objects = []
        failed = []

        for obj in assemblies:
            disassembled = self.disassemble_assembly(context, obj)

            if disassembled:
                objects.extend(disassembled)
            else:
                failed.append(f"Failed to disassemble '{obj.name}', is it in a linked collection only?")

        groups = [obj for obj in objects if obj.M3.is_group_empty]

        for obj in groups:
            if obj.hide_viewport:
                print(f"INFO: revealing Group Empty '{obj.name}' on all viewlayers")
                obj.hide_viewport = False

            if obj.hide_get():
                print(f"INFO: unhiding Group Empty '{obj.name}'")
                obj.hide_set(False)

        root_objects = [obj for obj in objects if not get_parent(obj)]

        if root_objects:
            context.view_layer.objects.active = root_objects[0]
            root_objects[0].select_set(True)

        if M3.get_addon('DECALmachine'):
            decals = [obj for obj in objects if is_decal(obj)]
            DM = M3.addons['decalmachine']['module']

            for obj in decals:
                DM.utils.collection.sort_into_collections(context, obj, purge=False)

        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        if failed:
            draw_fading_label(context, text=failed, color=red, move_y=30 + 10 * len(failed), time=3 + len(failed))
        return {'FINISHED'}

    def disassemble_assembly(self, context, empty):
        mx = empty.matrix_world.copy()
        cols = [col for col in empty.users_collection if not col.library]

        if not cols:
            return []

        assembly_col = empty.instance_collection
        assembly_objects = get_collection_objects(assembly_col)

        if [obj for obj in assembly_col.users_dupli_group if obj != empty]:
            print(f"\nINFO: Disassembling duplicated objects from instance collection {assembly_col.name}")
            objects = duplicate_objects(context, assembly_objects, debug=False)   # NOTE: also ensures visibility on local view and takes care of visibility states including hide_viewport

        else:
            print(f"\nINFO: Disassembling original objects from instance collection {assembly_col.name}")
            objects = assembly_objects

        for obj in objects:
            for col in obj.users_collection:
                col.objects.unlink(obj)

        for obj in objects:
            for col in cols:
                col.objects.link(obj)

        for obj in objects:
            obj.hide_set(obj.M3.hide)
            obj.hide_viewport = obj.M3.hide_viewport

        for obj in objects:
            if not obj.parent:
                offsetmx = get_loc_matrix(assembly_col.instance_offset)
                obj.matrix_world = mx @ offsetmx.inverted_safe() @ obj.matrix_world

        if any(obj.rigid_body for obj in objects):
            if not context.scene.rigidbody_world:
                bpy.ops.rigidbody.world_add()

            for obj in objects:
                if obj.rigid_body:

                    with context.temp_override(object=obj):
                        bpy.ops.rigidbody.object_add(type=obj.rigid_body.type)

            bpy.ops.ptcache.bake_all(bake=True)

        bpy.data.objects.remove(empty, do_unlink=True)

        return objects

class MakeIDLocal(bpy.types.Operator):
    bl_idname = "machin3.make_id_local"
    bl_label = "MACHIN3: Make IDs Local"
    bl_options = {'REGISTER', 'UNDO'}

    force: BoolProperty(name="Force Making Everything Local")
    make_collections_local: BoolProperty(name="Make Collections Local")

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.selected_objects if is_linked_object(obj)]

    @classmethod
    def description(cls, context, properties):
        all_linked = []
        pretty_linked = []

        for obj in context.selected_objects:
            all_linked.extend(linked := is_linked_object(obj))

            if linked:
                pretty_linked.append(get_pretty_linked_data(linked, obj))

        lib_count = len({id.library for id in all_linked})
        linked_limit = int(50 / len(pretty_linked))

        if all_linked and not any(obj.library for obj in context.selected_objects):
            desc = "Make Object Data, including Instance Collections local"

        else:
            desc = "Make Selected Linked Objects local"
            desc += "\nSHIFT: make Object Data, including Instance Collections local too"

        linked_collections = {col for obj in context.selected_objects for col in obj.users_collection if col.library}
        linked_empties = {obj for obj in bpy.data.objects if obj.library and (icol := is_instance_collection(obj)) and icol in linked_collections}

        if linked_collections and not linked_empties:
            desc += "\nALT: Make Collection Containing Linked objects local too"

        desc += f"\n\nSelection links {len(all_linked)} data blocks (top level) from {lib_count} librar{'ies' if lib_count > 1 else 'y'}"

        for idx, linked in enumerate(pretty_linked):
            current = None

            keep_main = not all('MAIN_' in id[0] for id in linked)

            for type, _, data, count in linked[:linked_limit]:
                if type != current:
                    spacer = "_________________________________________________________________________\n" if idx and current is None else ""
                    current = type

                    if 'MAIN_' in type and not keep_main:
                        desc += f"\n\n{spacer}{type.replace('MAIN_', '').title().replace('_', ' ')}"

                    else:
                        desc += f"\n\n{spacer}{type.title().replace('_', ' ')}"

                desc += f"\n • {data.name}"

            if left := linked[linked_limit:]:
                desc += "\n ..."
                desc += f"\n\n and {len(left)} more"

        return desc

    def draw(self, context):
        _layout = self.layout

    def invoke(self, context, event):
        self.force = event.shift
        self.make_collections_local = event.alt
        return self.execute(context)

    def execute(self, context):
        linked_collections = {col for obj in context.selected_objects for col in obj.users_collection if col.library}

        linked_empties = {obj for obj in bpy.data.objects if obj.library and (icol := is_instance_collection(obj)) and icol in linked_collections}

        if linked_empties:
            text = [
                "The Selected Objects are contained in a linked Collection, which itself is referenced by a linked Empty (Instance Collection)!",
                "To make the Objects local, you have to make the Empty instancing the Collection local first!"]

            draw_fading_label(context, text=text, color=[red, yellow], move_y=50, time=5)
            return {'CANCELLED'}

        elif linked_collections:
            if self.make_collections_local:
                for col in linked_collections:
                    col.make_local()
                    print(f"INFO: Made collection '{col.name}' local")

            else:
                text = [
                    "The Selected Objects are contained in Linked Collections!",
                    "To make the Objects local, you have to make the Collection the Object are contaiend in local first.",
                    "You can run the Make Local tool again with the ALT key pressed to do that"
                ]

                draw_fading_label(context, text=text, color=[yellow, yellow, green], move_y=50, time=5)
                return {'CANCELLED'}

        if any(obj.library for obj in context.selected_objects) and not self.force:
            bpy.ops.object.make_local(type="SELECT_OBJECT")

        else:
            self.make_obj_data_icol_local(context)

        return {'FINISHED'}

    def make_obj_data_icol_local(self, context):
        debug = False

        objects = []
        collections = []

        bpy.ops.object.make_local(type="SELECT_OBDATA")

        for obj in context.selected_objects:
            if linked := is_linked_object(obj):
                for id in linked:
                    if get_id_data_type(id) == 'COLLECTION':
                        collections.append(id)

                    elif get_id_data_type(id) in ['OBJECT', 'EMPTY']:
                        objects.append(id)

                        if has_decal_backup(id):
                            if debug:
                                print("", id.name, "collecting decal backup too")

                            objects.append(id.DM.decalbackup)

                        if has_stashes(id):
                            if debug:
                                print("", id.name, "collecting stash objects too")

                            for stash in id.MM.stashes:
                                if stash.obj:
                                    objects.append(stash.obj)

        for col in collections:
            col.make_local(clear_proxy=True, clear_liboverride=True, clear_asset_data=True)

        if objects:
            with context.temp_override(selected_objects=objects):
                bpy.ops.object.make_local(type="SELECT_OBDATA")

class SetAssemblyOrigin(bpy.types.Operator):
    bl_idname = "machin3.set_assembly_origin"
    bl_label = "MACHIN3: Set Assembly Origin"
    bl_options = {'REGISTER', 'UNDO'}

    source: StringProperty(name="Source of Origin")

    location: BoolProperty(name="Location", default=True)
    if True:
        rotation: BoolProperty(name="Rotation", default=True)
    relative_to_original: BoolProperty(name="Relative to Original", description="Set Origin based relative to location of Objects within Instance Collection", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            if active and active.select_get():
                if icol := is_instance_collection(active):
                    if icol.library:
                        cls.poll_message_set("You can't change the Origin of an Assembly with a linked Instance Collection")

                    else:
                        return True

    @classmethod
    def description(cls, context, properties):
        if properties.source == 'CURSOR':
            desc = "Set Asset Collection Offset from Cursor"

        elif properties.source == 'OBJECT':
            desc = "Set Asset Collection Offset from Object\nNOTE: Select the Offset Object first, then the Assembly Asset Object"
        else:
            return ""

        if True:
            desc += "\n\nALT: Only Set Location"
            desc += "\nCTRL: Only Set Rotation"

        desc += "\n\nSHIFT: Set Relative to the Original Objects within the Instance Collection"

        return desc

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        if True:
            row = column.row(align=True)
            row.prop(self, 'location', toggle=True)
            row.prop(self, 'rotation', toggle=True)

        column.prop(self, 'relative_to_original', toggle=True)

    def invoke(self, context, event):
        if True:
            if event.alt:
                self.location = True
                self.rotation = False

            elif event.ctrl:
                self.location = False
                self.rotation = True
            else:
                self.location = True
                self.rotation = True

        self.relative_to_original = event.shift

        return self.execute(context)

    def execute(self, context):
        _dg = context.evaluated_depsgraph_get()

        active = get_active_object(context)

        sel = [obj for obj in context.selected_objects if obj != active]

        if self.source == 'OBJECT':

            if len(sel) != 1:
                draw_fading_label(context, text=["Illegal Selection", "Select a single Source Object first, then the Assembly Asset as the Active"], color=[yellow, white], move_y=30, time=3)
                return {'CANCELLED'}

            source_mx = sel[0].matrix_world

        elif self.source == 'CURSOR':
            source_mx = context.scene.cursor.matrix
        else:
            return {'CANCELLED'}

        active_loc, active_rot, active_sca = active.matrix_world.decompose()

        icol = active.instance_collection
        icol_offset = icol.instance_offset.copy()

        assemblies = [obj for obj in bpy.data.objects if (col := is_instance_collection(obj)) and col == icol]

        if True:
            rootobjs = [obj for obj in get_collection_objects(icol) if not obj.parent] if self.rotation else []

            if any(obj.library for obj in rootobjs):
                text = [
                    "Some root objects within the Instance Collection are linked!",
                    "This prevents Rotating and Assembly Origin, because for that the Objects within the Instance Collection have to be transformed.",
                    "NOTE: You can still set just the Origin's Location via ALT!"
                ]

                draw_fading_label(context, text=text, color=[red, yellow, green], move_y=40, time=4)
                return {'CANCELLED'}

        if self.location:

            source_loc = source_mx.to_translation()

            if self.relative_to_original:
                delta = source_loc - icol_offset

            else:

                delta = active.matrix_world.inverted().to_3x3() @ (source_loc - active_loc)

            icol.instance_offset += delta

            for obj in assemblies:
                omx = obj.matrix_world
                loc, rot, sca = omx.decompose()

                obj.matrix_world = Matrix.LocRotScale(loc + omx.to_3x3() @ delta, rot, sca)

        if True and self.rotation:

            delta_rot = source_mx.to_quaternion().rotation_difference(active.matrix_world.to_quaternion())

            icol_offset = icol.instance_offset.copy()

            for obj in rootobjs:
                rmx = obj.matrix_world

                obj.matrix_world = get_loc_matrix(icol_offset) @ delta_rot.to_matrix().to_4x4() @ get_loc_matrix(icol_offset).inverted_safe() @ rmx

            for obj in assemblies:
                loc, rot, sca = obj.matrix_world.decompose()

                obj.matrix_world = Matrix.LocRotScale(loc, rot @ delta_rot.inverted(), sca)

        return {'FINISHED'}

class ResetAssemblyOrigin(bpy.types.Operator):
    bl_idname = "machin3.reset_assembly_origin"
    bl_label = "MACHIN3: Reset Assembly Origin"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object

            if active and active.select_get():
                if icol := is_instance_collection(active):
                    if icol.library:
                        cls.poll_message_set("You can't Reset the Origin of an Assembly with a linked Instance Collection")

                    else:
                        return True

    @classmethod
    def description(cls, context, properties):
        return "Zero out Assembly Asset's Instance Collection Offset, and compensate contained Objects' Locations within the collection.\nThis ensures the Assembly's Origin sits in the World Origin."

    def draw(self, context):
        _layout = self.layout

    def execute(self, context):
        _dg = context.evaluated_depsgraph_get()

        active = get_active_object(context)
        icol = active.instance_collection

        rootobjs = [obj for obj in get_collection_objects(icol) if not obj.parent]

        if any(obj.library for obj in rootobjs):
            text = [
                "Some root objects within the Instance Collection are linked!",
                "This prevents adjusting their location to compensate for the Instance Offset Reset"
            ]

            draw_fading_label(context, text=text, color=[red, yellow], move_y=40, time=4)
            return {'CANCELLED'}

        icol_offset = icol.instance_offset.copy()
        icol.instance_offset.zero()

        for obj in rootobjs:
            obj.matrix_world.translation -= icol_offset

        return {'FINISHED'}

class EditAssembly(bpy.types.Operator):
    bl_idname = "machin3.edit_assembly"
    bl_label = "MACHIN3: Edit Assembly"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active = context.active_object
        return bool(active and active.select_get() and is_instance_collection(active))

    @classmethod
    def description(cls, context, properties):
        if is_local_assembly_asset(context.active_object):
            return "Edit Assembly Asset"
        else:
            return "Edit Assembly (Instance Collection)"

    def draw(self, context):
        _layout = self.layout

    def execute(self, context):
        r3d = context.space_data.region_3d

        active = context.active_object
        icol = active.instance_collection

        cmx = context.scene.cursor.matrix

        delta_mx = active.matrix_world @ get_loc_matrix(icol.instance_offset).inverted_safe()

        edit_scene = create_scene(context, f"Edit Assembly {icol.name}", inherit=True)

        edit_scene.node_tree.nodes.clear()
        edit_scene.use_nodes = False

        edit_scene.use_fake_user = True

        edit_scene.collection.children.link(icol)

        edit_scene.M3.is_assembly_edit_scene = True

        edit_scene.M3.assembly_edit_init_scene = context.scene
        edit_scene.M3.assembly_edit_collection = icol
        edit_scene.M3.assembly_edit_delta_view_mx = delta_mx

        context.window.scene = edit_scene

        assembly_objects = get_collection_objects(icol)

        if is_local_view():
            add_obj_to_local_view(assembly_objects)

        r3d.view_location = delta_mx.inverted_safe() @ r3d.view_location
        r3d.view_rotation = delta_mx.inverted_safe().to_quaternion() @ r3d.view_rotation
        r3d.view_distance = (get_sca_matrix(delta_mx.inverted_safe().to_scale()) @ Vector((0, 0, r3d.view_distance))).z

        edit_scene.cursor.matrix = delta_mx.inverted_safe() @ cmx

        for col, data in get_scene_collections(context, debug=False).items():
            if not data['visible']:
                for lcol in data['layer_collections']:
                    lcol.hide_viewport = False
                    lcol.exclude = False
                    break

        groups = [obj for obj in assembly_objects if obj.M3.is_group_empty or obj.M3.is_group_anchor]

        for obj in groups:
            if obj.hide_viewport:
                obj.hide_viewport = False

            if obj.hide_get():
                obj.hide_set(False)

        if active := context.active_object:
            active.select_set(True)

        else:
            rootobjs = [obj for obj in assembly_objects if not obj.parent]

            if rootobjs:
                if selected := [obj for obj in rootobjs if obj.select_get()]:
                    context.view_layer.objects.active = selected[0]

                else:
                    context.view_layer.objects.active = rootobjs[0]
                    rootobjs[0].select_set(True)

        return {'FINISHED'}

class FinishAssemblyEdit(bpy.types.Operator):
    bl_idname = "machin3.finish_assembly_edit"
    bl_label = "MACHIN3: Finish Assembly Edit"
    bl_options = {'REGISTER', 'UNDO'}

    is_topbar_invoke: BoolProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            m3 = context.scene.M3
            return m3.is_assembly_edit_scene and m3.assembly_edit_collection and m3.assembly_edit_init_scene

    @classmethod
    def description(cls, context, properties):
        return "Finish Editing Assembly"

    def draw(self, context):
        _layout = self.layout

    def execute(self, context):
        r3d = None
        view_mx = None

        if self.is_topbar_invoke:
            _, _, r3d, space = get_3dview(context)

        else:
            space = context.space_data
            r3d = space.region_3d

        if r3d:
            view_mx = r3d.view_matrix

        edit_scene = context.scene
        m3 = edit_scene.M3

        assembly_col = m3.assembly_edit_collection
        init_scene = m3.assembly_edit_init_scene
        delta_mx = m3.assembly_edit_delta_view_mx.copy()

        cmx = edit_scene.cursor.matrix

        if assembly_col.library:
            outsiders = None
            print("WARNING: assembly collection is linked, and can't be modified!")

        else:
            assembly_objects = get_collection_objects(assembly_col)
            outsiders = set(edit_scene.objects) - assembly_objects

            for obj in outsiders:
                print(f"INFO: moving outsider '{obj.name}' to assembly collection '{assembly_col.name}'")

                for col in obj.users_collection:
                    if not col.library:
                        col.objects.unlink(obj)

                assembly_col.objects.link(obj)

            wire_objects = self.get_hide_wire_objects(context, assembly_col)

            for obj in wire_objects:

                if obj.M3.is_group_empty:
                    if obj.parent:
                        obj.hide_viewport = True

                    else:

                        obj.hide_viewport = False
                        obj.empty_display_type = 'SPHERE'
                        obj.empty_display_size = obj.M3.group_size  # set their size too, to negate hide_empties behavior

                        if obj.hide_get():
                            obj.hide_set(False)

                elif obj.M3.is_group_anchor:

                    obj.hide_viewport = False

                    if obj.hide_get():
                        obj.hide_set(False)

                else:

                    if not obj.hide_viewport:
                        obj.hide_viewport = True

                    if not obj.M3.hide:
                        obj.M3.hide = True

                    if obj.hide_get():
                        obj.hide_set(False)

            for obj in get_collection_objects(assembly_col):
                    if obj not in wire_objects and obj.hide_viewport and not obj.M3.hide:
                        obj.M3.hide = True

        context.window.scene = init_scene

        if r3d and view_mx:
            r3d.view_location = delta_mx @ r3d.view_location
            r3d.view_rotation = delta_mx.to_quaternion() @ r3d.view_rotation
            r3d.view_distance = (get_sca_matrix(delta_mx.to_scale()) @ Vector((0, 0, r3d.view_distance))).z

        init_scene.cursor.matrix = delta_mx @ cmx

        if outsiders:
            bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=False)

        edit_scene.use_fake_user = False
        bpy.data.scenes.remove(edit_scene)
        return {'FINISHED'}

    def get_hide_wire_objects(self, context, collection):
        wire_objects = {obj for obj in get_collection_objects(collection) if (obj.type == 'EMPTY' and not obj.instance_collection) or obj.display_type in ['', 'WIRE', 'BOUNDS']}

        root_wire_objs = {obj for obj in wire_objects if not obj.type == 'EMPTY' and not obj.parent and not remote_boolean_poll(context, obj) and obj.children}

        root_wire_children = set()

        for obj in root_wire_objs:
            for c in obj.children_recursive:
                if c in wire_objects:
                    root_wire_children.add(c)

        skip_hiding = root_wire_objs | root_wire_children

        return wire_objects - skip_hiding

class AssetBrowserBookmark(bpy.types.Operator):
    bl_idname = "machin3.assetbrowser_bookmark"
    bl_label = "MACHIN3: Assetbrowser Bookmark"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(name="Index", default=1, min=0, max=10)
    save_bookmark: BoolProperty(name="Save Bookmark", default=False)
    clear_bookmark: BoolProperty(name="Clear Bookmark", default=False)
    @classmethod
    def poll(cls, context):
        if context.area:
            return context.area.type == 'FILE_BROWSER' and context.area.ui_type == 'ASSETS'

    @classmethod
    def description(cls, context, properties):
        idx = str(properties.index)
        desc = f"Bookmark: {idx}"

        if idx == '0':
            desc += "\n Library: Current File"
            return desc

        bookmarks = get_assetbrowser_bookmarks(force=True)
        bookmark = bookmarks[idx]

        libref, _, catalog = get_libref_and_catalog(context, bookmark=bookmark)

        if catalog:
            if libref == 'ALL':
                desc += f"\n Library: ALL ({libref})"
            else:
                desc += f"\n Library: {libref}"

            desc += f"\n Catalog: {catalog['catalog']}"

        elif libref:
            desc += f"\n Library: {libref}"

        else:
            desc += "\n None"

        if catalog:
            desc += "\n\nClick: Jump to this Bookmark's Library and Catalog"
        else:
            desc += "\n"

        desc += "\nSHIFT: Save the current Library and Catalog on this Bookmark"

        if catalog:
            desc += "\nCTRL: Remove the stored Bookmark"

        return desc

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def invoke(self, context, event):
        self.save_bookmark = event.shift
        self.clear_bookmark = event.ctrl

        space = context.space_data
        catalogs = get_catalogs_from_asset_libraries(context, debug=False)
        bookmarks = get_assetbrowser_bookmarks(force=True)

        if self.save_bookmark:
            libref = get_asset_library_reference(space.params)
            catalog_id = space.params.catalog_id
            display_size = space.params.display_size
            display_type = space.params.display_type

            if catalog_id in catalogs:
                bookmark = {'libref': libref,
                            'catalog_id': catalog_id,
                            'display_size': display_size,
                            'display_type': display_type,
                            'valid': True}

                bookmarks[str(self.index)] = bookmark

                set_assetbrowser_bookmarks(bookmarks)

                if getattr(context.window_manager, 'M3_screen_cast', False):
                    force_ui_update(context)

            else:
                print("  WARNING: no catalog found under this id! Reload the blend file? Restart Blender?")
                return {'CANCELLED'}

        elif self.clear_bookmark:
            bookmark = bookmarks.get(str(self.index), None)

            if bookmark:

                bookmarks[str(self.index)] = {key: None for key in asset_browser_bookmark_props}

                set_assetbrowser_bookmarks(bookmarks)

                if getattr(context.window_manager, 'M3_screen_cast', False):
                    force_ui_update(context)

            else:
                print(f" WARNING: no bookmark found for {self.index}. This should not happen! Reload the blend file.")
                return {'CANCELLED'}

        else:

            if self.index == 0:
                set_asset_library_reference(space.params, 'LOCAL')

                set_asset_catalog_id(space.params, 'ALL')

                space.params.display_size = get_display_size_from_area(context)

            else:
                bookmark = bookmarks.get(str(self.index), None)

                if bookmark:
                    libref = bookmark.get('libref', None)
                    catalog_id = bookmark.get('catalog_id', None)
                    display_size = bookmark.get('display_size', None)
                    display_type = bookmark.get('display_type', None)
                    valid = bookmark.get('valid', None)

                    if libref and catalog_id:

                        if validate_libref_and_catalog(context, libref, catalog_id):
                            params = space.params

                            set_asset_library_reference(params, libref)
                            params.catalog_id = catalog_id
                            params.display_size = display_size
                            params.display_type = display_type

                            if not valid:
                                bookmark['valid'] = True

                                set_assetbrowser_bookmarks(bookmarks)

                        else:
                            bookmark['valid'] = False

                            set_assetbrowser_bookmarks(bookmarks)

                else:
                    print(f" WARNING: no bookmark found for {self.index}. This should not happen! Reload the blend file.")
                    return {'CANCELLED'}

        return {'FINISHED'}

class CleanOutNonAssets(bpy.types.Operator):
    bl_idname = "machin3.clean_out_non_assets"
    bl_label = "MACHIN3: Clean Out Non-Assets"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'OBJECT' and is_3dview(context)

    @classmethod
    def description(cls, context, properties):
        desc = "Clean out non-asset data blocks from .blend file!"
        desc += "\nThis keeps only the assets (and related data-blocks), for efficient storage within a library."
        desc += "\nNOTE: Fake user data is also kept!"
        return desc

    def execute(self, context):
        debug = False

        assets, fake_users, init_id_count = self.get_assets_and_fake_users(debug=debug)

        _scene = create_scene(context, "_Scene", inherit=True)

        _scene.node_tree.nodes.clear()
        _scene.use_nodes = False

        _scene.use_fake_user = True

        context.window.scene = _scene

        remove_scenes = [scene for scene in bpy.data.scenes if not scene.asset_data and scene != _scene]

        for scene in remove_scenes:
            bpy.data.scenes.remove(scene)

        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        if M3.get_addon('MESHmachine'):
            invalid = {obj for obj in bpy.data.objects if is_stash_object(obj) and obj.type != 'MESH'}
            orphans = {obj for obj in bpy.data.objects if is_stash_object(obj) and obj.use_fake_user and obj.users == 1 and obj.type == 'MESH'}

            for obj in invalid | orphans:
                bpy.data.objects.remove(obj)

            if invalid or orphans:
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        if M3.get_addon('DECALmachine'):
            dm = M3.addons['decalmachine']['module']

            backup_count, joined_count, decal_count = dm.utils.decal.remove_decal_orphans(debug=True)

            if backup_count or joined_count or decal_count:
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

            backup_count, joined_count, decal_count = dm.utils.decal.remove_decal_orphans(debug=True)

            if backup_count or joined_count or decal_count:
                bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

        assets, fake_users, cleaned_id_count = self.get_assets_and_fake_users(debug=debug)

        _scene.name = "Assets"

        if bpy.data.worlds:
            _scene.world = bpy.data.worlds[0]
        else:
            _scene.world = bpy.data.worlds.new("World")

        assembly_cols = [col for col in bpy.data.collections if col.M3.is_asset_collection]

        if assembly_cols:
            assemblies_col = get_assets_collection(context, name='_Assemblies', color_tag='COLOR_04', create=True, exclude=False)

            for col in assembly_cols:
                assemblies_col.children.link(col)

                set_collection_visibility(context, col, exclude=True, hide_viewport=False)

                if col.color_tag == 'NONE':
                    col.color_tag = 'COLOR_02'

        asset_objs = [obj for obj in bpy.data.objects if obj.asset_data and obj.M3.asset_version != "1.0" and not is_obj_in_scene(obj)]

        if asset_objs:
            if not assembly_cols:
                assemblies_col = get_assets_collection(context, create=True, exclude=False)

            for obj in asset_objs:
                assemblies_col.objects.link(obj)

        context.evaluated_depsgraph_get()

        distribute = sorted([(obj, get_eval_bbox(obj, advanced=True)) for obj in asset_objs if not obj.parent and obj.location == Vector()], key=lambda x: - x[1][2].x)

        if distribute:
            clear_rotation([obj for obj, _ in distribute])

            offset_x = 0

            gap = sum(bbox[2][0] for _, bbox in distribute) / len(distribute) / 5

            for idx, (obj, (bbox, _, dims)) in enumerate(distribute):
                mx = obj.matrix_world

                if idx:
                    prev_obj = distribute[idx - 1][0]
                    prev_mx = prev_obj.matrix_world
                    prev_bbox = distribute[idx - 1][1][0]

                    prev_right_d = (get_sca_matrix(prev_mx.to_scale()) @ prev_bbox[1]).x
                    current_left_d = -(get_sca_matrix(mx.to_scale()) @ bbox[0]).x

                    location = Vector((offset_x + prev_right_d + current_left_d + gap, 0, 0))

                    obj.location = location

                    offset_x = location.x

        asset_cols = [col for col in bpy.data.collections if not col.M3.is_asset_collection and col.asset_data]

        if asset_cols:
            assets_col = get_assets_collection(context, name='_Assets', color_tag='NONE', create=True, exclude=False)

            for col in asset_cols:
                assets_col.children.link(col)

                set_collection_visibility(context, col, exclude=True, hide_viewport=False)

        user_asset_objs = [obj for obj in bpy.data.objects if obj.asset_data and obj.M3.asset_version == "1.0" and not is_obj_in_scene(obj)]

        if user_asset_objs:
            if not asset_cols:
                assets_col = get_assets_collection(context, name='_Assets', color_tag='NONE', create=True, exclude=False)

            icols = [icol for obj in user_asset_objs if (icol := is_instance_collection(obj)) and icol not in asset_cols]

            for icol in icols:
                assets_col.children.link(icol)

                set_collection_visibility(context, icol, exclude=True, hide_viewport=False)

            for obj in user_asset_objs:
                assets_col.objects.link(obj)

        fake_user_cols = [col for col in bpy.data.collections if not col.M3.is_asset_collection and not col.asset_data and col.use_fake_user]

        if fake_user_cols:
            fake_users_col = get_assets_collection(context, name='_FakeUsers', color_tag='NONE', create=True, exclude=False)

            for col in fake_user_cols:
                fake_users_col.children.link(col)

                set_collection_visibility(context, col, exclude=True, hide_viewport=False)

        fake_user_objects = {obj for obj in bpy.data.objects if not obj.asset_data and obj.use_fake_user and not is_obj_in_scene(obj)}

        if fake_user_objects:
            if not fake_user_cols:
                fake_users_col = get_assets_collection(context, name='_FakeUsers', color_tag='NONE', create=True, exclude=False)

            decal_backups = {obj for obj in fake_user_objects if is_decal_backup(obj)}
            stash_objs = {obj for obj in fake_user_objects if is_stash_object(obj)}

            if decal_backups:
                decal_backups_col = bpy.data.collections.new('_DecalBackups')
                fake_users_col.children.link(decal_backups_col)

                set_collection_visibility(context, decal_backups_col, exclude=True, hide_viewport=False)

                for obj in decal_backups:
                    decal_backups_col.objects.link(obj)

            if stash_objs:
                stash_objs_col = bpy.data.collections.new('_StashObjects')
                fake_users_col.children.link(stash_objs_col)

                set_collection_visibility(context, stash_objs_col, exclude=True, hide_viewport=False)

                for obj in stash_objs:
                    stash_objs_col.objects.link(obj)

            for obj in fake_user_objects - decal_backups - stash_objs:
                fake_users_col.objects.link(obj)

        _scene.use_fake_user = False

        ensure_compositor_nodes(_scene)

        self.draw_stats(context, assets, fake_users, init_id_count, cleaned_id_count)

        return {'FINISHED'}

    def get_assets_and_fake_users(self, debug=False):
        assets = {}
        fake_user = {}
        total_count = 0

        for name in id_data_types:
            id_collection = getattr(bpy.data, name, None)

            if id_collection:
                total_count += len(id_collection)

                for id in id_collection:
                    data_type = get_id_data_type(id)

                    if not id.library:

                        if id.asset_data:
                            if data_type in assets:
                                assets[data_type].add(id)
                            else:
                                assets[data_type] = {id}

                        elif id.use_fake_user:

                            if data_type in ['BRUSH', 'PALETTE']:
                                id.use_fake_user = False
                                continue

                            if data_type in fake_user:
                                fake_user[data_type].add(id)
                            else:
                                fake_user[data_type] = {id}

        if debug:
            if assets:
                printd(assets, name="assets")

            if fake_user:
                printd(fake_user, name="fake user")

            print("total ids seen:", total_count)

        return assets, fake_user, total_count

    def draw_stats(self, context, assets, fake_users, init_count, cleaned_count):
        assets_count = sum(len(ids) for ids in assets.values())
        fake_users_count = sum(len(ids) for ids in fake_users.values())

        limit_assets_hud = assets_count > 10
        limit_fake_users_hud = fake_users_count > 10

        assets_text = []
        assets_color = []
        assets_alpha = []

        fake_user_text = []
        fake_user_color = []
        fake_user_alpha = []

        if assets:
            msg = "Kept the following Asset IDs"
            print(f"\nINFO: {msg}")

            assets_text.append(msg)
            assets_color.append(green)
            assets_alpha.append(1)

            for type, ids in assets.items():
                print("", type)

                if limit_assets_hud:
                    assets_text.append(f" {len(ids)} x {type} ")
                else:
                    assets_text.append(f" {type}")

                assets_color.append(white)
                assets_alpha.append(0.3)

                for id in ids:
                    print(f"  • {id.name}")

                    if not limit_assets_hud:
                        assets_text.append(f"  • {id.name}")
                        assets_color.append(white)
                        assets_alpha.append(0.5)

                    if type == 'EMPTY' and id.instance_collection:
                        print(f"    with the instance collection {id.instance_collection.name}")

                        if not limit_assets_hud:
                            assets_text.append(f"    with the instance collection {id.instance_collection.name}")
                            assets_color.append(white)
                            assets_alpha.append(0.3)

        if fake_users:
            msg = "Kept the following Fake User IDs"
            print(f"\nINFO: {msg}")

            fake_user_text.append(msg)
            fake_user_color.append(blue)
            fake_user_alpha.append(1)

            for type, ids in fake_users.items():
                print("", type)

                if limit_fake_users_hud:
                    fake_user_text.append(f" {len(ids)} x {type}")
                else:
                    fake_user_text.append(f" {type}")

                fake_user_color.append(white)
                fake_user_alpha.append(0.3)

                for id in ids:
                    print(f"  • {id.name}")

                    if not limit_fake_users_hud:
                        fake_user_text.append(f"  • {id.name}")
                        fake_user_color.append(white)
                        fake_user_alpha.append(0.5)

                    if type == 'EMPTY' and id.instance_collection:
                        print(f"    with the instance collection {id.instance_collection.name}")

                        if not limit_fake_users_hud:
                            fake_user_text.append(f"    with the instance collection {id.instance_collection.name}")
                            fake_user_color.append(white)
                            fake_user_alpha.append(0.3)

        if assets_text and fake_user_text:
            max_dim = max([get_text_dimensions(context, text, size=12).x for text in assets_text])
            left_x = int((context.region.width / 2) - max_dim - 50)
            right_x = int((context.region.width / 2) + 50)

            if assets_text:
                draw_fading_label(context, text=assets_text, x=left_x, y=200, center=False, color=assets_color, alpha=assets_alpha, move_y=20, time=2)

            if fake_user_text:
                draw_fading_label(context, text=fake_user_text, x=right_x, y=200, center=False, color=fake_user_color, alpha=fake_user_alpha, move_y=20, time=2)

        elif assets_text or fake_user_text:
            text, color, alpha = (assets_text, assets_color, assets_alpha) if assets_text else (fake_user_text, fake_user_color, fake_user_alpha)

            x = (context.region.width / 2) - (get_text_dimensions(context, text=text[0], size=12).x / 2)
            draw_fading_label(context, text=text, x=x, y=200, center=False, color=color, alpha=alpha, move_y=20, time=2)

        if delta := (init_count - cleaned_count):
            msg = f"Removed {delta} non-asset data blocks"
            print(f"INFO: {msg}")

            draw_fading_label(context, text=f"{msg}", y=150, color=yellow, alpha=1, move_y=30, time=3)

        else:
            msg ="INFO: Nothing to remove. The file already contains only assets and related data blocks!"
            print(f"INFO {msg}")

            draw_fading_label(context, text=f"✔ {msg}", y=150, color=green, alpha=1, move_y=50, time=5)
