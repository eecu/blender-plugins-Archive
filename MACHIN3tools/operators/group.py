import bpy
from bpy.props import EnumProperty, BoolProperty, StringProperty, IntProperty
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

from mathutils import Vector, Matrix, Quaternion
from mathutils.geometry import intersect_line_plane

from math import radians, degrees

from .. utils.collection import get_collection_depth
from .. utils.draw import draw_cross_3d, draw_fading_label, draw_init, draw_multi_label, draw_point, draw_vector, draw_label, get_text_dimensions, draw_circle, draw_mesh_wire
from .. utils.group import ensure_internal_index_group_name, get_group_base_name, group, is_inception_pose, process_group_poses, retrieve_group_pose, set_group_pose, set_unique_group_name, ungroup, get_group_matrix, select_group_children, get_child_depth, clean_up_groups, fade_group_sizes, prettify_group_pose_names, get_pose_batches, get_batch_pose_name, get_group_hierarchy, get_remove_poses
from .. utils.math import average_locations, dynamic_format, compare_quat
from .. utils.mesh import get_coords, get_eval_mesh
from .. utils.modifier import get_mods_as_dict, add_mods_from_dict
from .. utils.object import get_eval_bbox, parent, unparent, compensate_children
from .. utils.registration import get_prefs
from .. utils.ui import draw_status_item, draw_status_item_precision, finish_modal_handlers, force_ui_update, get_mouse_pos, ignore_events, init_modal_handlers, init_status, finish_status, navigation_passthrough, scroll, scroll_up
from .. utils.view import ensure_visibility, get_view_origin_and_dir, get_location_2d, is_local_view, restore_visibility, visible_get
from .. utils.workspace import is_outliner

from .. items import group_location_items, axis_items, axis_vector_mappings, ctrl, axis_color_mappings, axis_index_mapping
from .. colors import red, blue, green, yellow, white, normal

ungroupable_batches = None

class Group(bpy.types.Operator):
    bl_idname = "machin3.group"
    bl_label = "MACHIN3: Group"
    bl_description = "Group Objects by Parenting them to an Empty"
    bl_options = {'REGISTER', 'UNDO'}

    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            sel = [obj for obj in context.selected_objects]

            if len(sel) == 1:
                obj = sel[0]
                parent = obj.parent

                if parent:
                    booleans = [mod for mod in parent.modifiers if mod.type == 'BOOLEAN' and mod.object == obj]
                    if booleans:
                        return False
            return True

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.label(text="Location")
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.label(text="Rotation")
        row.prop(self, 'rotation', expand=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        context.evaluated_depsgraph_get()

        groupable = {obj for obj in context.selected_objects if (obj.parent and obj.parent.M3.is_group_empty) or not obj.parent}

        if any(col.library for obj in groupable for col in obj.users_collection):
            draw_fading_label(context, text="You can't group objects that are in a Linked Collection!", x=self.HUD_x, y=self.HUD_y, color=red, time=get_prefs().HUD_fade_group * 2)
            return {'CANCELLED'}

        if groupable:
            ungroupable = [obj for obj in context.selected_objects if obj.parent and not obj.parent.M3.is_group_empty and obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']]

            self.group(context, groupable, ungroupable, debug=False)

            global ungroupable_batches
            ungroupable_batches = []

            if ungroupable:
                dg = context.evaluated_depsgraph_get()

                for obj in ungroupable:
                    mx = obj.matrix_world

                    mesh = get_eval_mesh(dg, obj, data_block=False)
                    batch = get_coords(mesh, mx=mx, indices=True)

                    bbox = get_eval_bbox(obj)
                    loc2d = get_location_2d(context, mx @ average_locations(bbox), default='OFF_SCREEN')
                    ungroupable_batches.append((loc2d, batch))
                    del mesh

                bpy.ops.machin3.draw_ungroupable()

            return {'FINISHED'}

        text = ["ℹℹ Illegal Selection ℹℹ",
                "You can't create a group from a selection of Objects, that are parented to something other than group empties"]

        draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=[yellow, white], alpha=0.75, time=get_prefs().HUD_fade_group * 4, delay=1)
        return {'CANCELLED'}

    def group(self, context, objects, ungroupable, debug=False):
        grouped = {obj for obj in objects if obj.parent and obj.parent.M3.is_group_empty}

        selected_empties = {obj for obj in objects if obj.M3.is_group_empty}

        if debug:
            print()
            print("               sel: ", [obj.name for obj in objects])
            print("           grouped: ", [obj.name for obj in grouped])
            print("  selected empties: ", [obj.name for obj in selected_empties])

        if grouped == objects:

            unselected_empties = {obj.parent for obj in objects if obj not in selected_empties and obj.parent and obj.parent.M3.is_group_empty and obj.parent not in selected_empties}

            top_level = {obj for obj in selected_empties | unselected_empties if obj.parent not in selected_empties | unselected_empties}

            if debug:
                print("unselected empties:", [obj.name for obj in unselected_empties])
                print("         top level:", [obj.name for obj in top_level])

            if len(top_level) == 1:
                new_parent = top_level.pop()

            else:
                parent_groups = {obj.parent for obj in top_level}

                if debug:
                    print("     parent_groups:", [obj.name if obj else None for obj in parent_groups])

                new_parent = parent_groups.pop() if len(parent_groups) == 1 else None

        else:
            new_parent = None

        if debug:
            print("        new parent:", new_parent.name if new_parent else None)
            print(20 * "-")

        ungrouped = {obj for obj in objects - grouped if obj not in selected_empties}

        top_level = {obj for obj in selected_empties if obj.parent not in selected_empties}

        grouped = {obj for obj in grouped if obj not in selected_empties and obj.parent not in selected_empties}

        if len(top_level) == 1 and new_parent in top_level:
            new_parent = list(top_level)[0].parent

            if debug:
                print("updated parent", new_parent.name)

        if debug:
            print("     top level:", [obj.name for obj in top_level])
            print("       grouped:", [obj.name for obj in grouped])
            print("     ungrouped:", [obj.name for obj in ungrouped])

        for obj in top_level | grouped:
            unparent(obj)

        empty = group(context, top_level | grouped | ungrouped, location=self.location, rotation=self.rotation)

        if new_parent:
            parent(empty, new_parent)
            empty.M3.is_group_object = True

        clean_up_groups(context)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        process_group_poses(empty)

        text = [f"{'Sub' if new_parent else 'Root'} Goup: {empty.name}"]
        color = [green if new_parent else yellow]
        time = get_prefs().HUD_fade_group
        alpha = 0.75

        if ungroupable:
            text.append(f"{len(ungroupable)}/{len(objects) + len(ungroupable)} Objects could not be grouped")
            color.append(yellow)
            time = get_prefs().HUD_fade_group * 4
            alpha = 1

        draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=color, alpha=alpha, time=time)

class Groupify(bpy.types.Operator):
    bl_idname = "machin3.groupify"
    bl_label = "MACHIN3: Groupify"
    bl_description = "Turn any Empty Hierarchy into Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children]

    def execute(self, context):
        all_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children]

        empties = [e for e in all_empties if e.parent not in all_empties]

        self.groupify(empties)

        top_empties = clean_up_groups(context)

        for empty in top_empties:
            process_group_poses(empty)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        return {'FINISHED'}

    def groupify(self, objects):
        for obj in objects:

            if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children:
                obj.M3.is_group_empty = True
                obj.M3.is_group_object = True if obj.parent and obj.parent.M3.is_group_empty else False
                obj.show_in_front = True
                obj.empty_display_type = 'CUBE'
                obj.empty_display_size = get_prefs().group_tools_size
                obj.show_name = True

                if get_prefs().group_tools_auto_name:
                    set_unique_group_name(obj)

                set_group_pose(obj, name='Inception')

                self.groupify(obj.children)

            else:
                obj.M3.is_group_object = True

ungrouped_child_locations = None
ungrouped_child_batches = None

class UnGroup(bpy.types.Operator):
    bl_idname = "machin3.ungroup"
    bl_label = "MACHIN3: Un-Group"
    bl_options = {'REGISTER', 'UNDO'}

    ungroup_all_selected: BoolProperty(name="Un-Group all Selected Groups", default=False)
    ungroup_entire_hierarchy: BoolProperty(name="Un-Group entire Hierarchy down", default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode

    @classmethod
    def description(cls, context, properties):
        if context.scene.M3.group_recursive_select and context.scene.M3.group_select:
            return "Un-Group selected top-level Groups\nALT: Un-Group all selected Groups"
        else:
            return "Un-Group selected top-level Groups\nALT: Un-Group all selected Groups\nCTRL: Un-Group entire Hierarchy down"

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row(align=True)
        row.label(text="Un-Group")
        row.prop(self, 'ungroup_all_selected', text='All Selected', toggle=True)
        row.prop(self, 'ungroup_entire_hierarchy', text='Entire Hierarchy', toggle=True)

    def invoke(self, context, event):
        self.ungroup_all_selected = event.alt
        self.ungroup_entire_hierarchy = event.ctrl

        return self.execute(context)

    def execute(self, context):
        global ungrouped_child_locations, ungrouped_child_batches

        dg = context.evaluated_depsgraph_get()

        empties = self.get_group_empties(context)

        if empties:

            ungrouped_child_locations, ungrouped_child_batches, ungrouped_count = self.ungroup(empties, depsgraph=dg)#

            top_empties = clean_up_groups(context)

            for empty in top_empties:
                process_group_poses(empty)

            if get_prefs().group_tools_fade_sizes:
                fade_group_sizes(context, init=True)

            text = [f"Removed {ungrouped_count} Groups"]
            color = [red]
            alpha = [1]

            if ungrouped_child_locations:
                text.append(f"with {len(ungrouped_child_locations)} Sub-Groups")
                color.append(yellow)
                alpha.append(0.3)

            if ungrouped_child_batches:
                text.append(f"{'and' if ungrouped_child_locations else 'with'} {len(ungrouped_child_batches)} Group Objects")
                color.append(yellow)
                alpha.append(0.3)

            time_extension = bool(ungrouped_child_locations) + bool(ungrouped_child_batches)
            draw_fading_label(context, text=text, color=color, alpha=alpha, move_y=20 + 10 * time_extension, time=2 + time_extension)

            bpy.ops.machin3.draw_ungroup()

            return {'FINISHED'}
        return {'CANCELLED'}

    def get_group_empties(self, context):
        all_empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]

        if self.ungroup_all_selected:
            return all_empties

        else:
            return [e for e in all_empties if e.parent not in all_empties]

    def collect_entire_hierarchy(self, empties):
        for e in empties:
            children = [obj for obj in e.children if obj.M3.is_group_empty]

            for c in children:
                self.empties.add(c)

                self.collect_entire_hierarchy([c])

    def ungroup(self, empties, depsgraph):
        if self.ungroup_entire_hierarchy:
            self.empties = set(empties)

            self.collect_entire_hierarchy(empties)

        else:
            self.empties = empties

        empty_locations = []
        object_batches = []

        ungrouped_count = len(self.empties)

        for empty in self.empties:
            locations, batches = ungroup(empty, depsgraph=depsgraph)

            empty_locations.extend(locations)
            object_batches.extend(batches)

        return empty_locations, object_batches, ungrouped_count

class Select(bpy.types.Operator):
    bl_idname = "machin3.select_group"
    bl_label = "MACHIN3: Select Group"
    bl_description = "Select Group\nCTRL: Select entire Group Hierarchy down"
    bl_options = {'REGISTER', 'UNDO'}

    recursive: BoolProperty(name="Recursive Selection", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.M3.is_group_empty or obj.M3.is_group_object]

    @classmethod
    def description(cls, context, properties):
        if not context.scene.M3.group_recursive_select or is_local_view():
            return "Select Groups of the current Selection\nCTRL: Select entire Group Hierarchy down"

        else:
            return "Select entire Group Hierarchies down"

    def draw(self, context):
        layout = self.layout

        if is_local_view() or not context.scene.M3.group_recursive_select:
            column = layout.column()
            column.prop(self, "recursive", toggle=True)

    def invoke(self, context, event):
        if is_local_view() or not context.scene.M3.group_recursive_select:
            self.recursive = event.ctrl

        else:
            self.recursive = context.scene.M3.group_recursive_select
        return self.execute(context)

    def execute(self, context):
        clean_up_groups(context)

        empties = {obj for obj in context.selected_objects if obj.M3.is_group_empty}
        objects = [obj for obj in context.selected_objects if obj.M3.is_group_object and obj not in empties]

        for obj in objects:
            if obj.parent and obj.parent.M3.is_group_empty:
                empties.add(obj.parent)

        ensure_visibility(context, empties, scene=False, select=True)

        children = [obj for group in empties for obj in group.children_recursive if obj.M3.is_group_object] if self.recursive else [obj for group in empties for obj in group.children if obj.M3.is_group_object]

        ensure_visibility(context, children, scene=False, select=False)

        for e in empties:
            if len(empties) == 1:
                context.view_layer.objects.active = e

            select_group_children(context.view_layer, e, recursive=self.recursive or context.scene.M3.group_recursive_select)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        return {'FINISHED'}

class Duplicate(bpy.types.Operator):
    bl_idname = "machin3.duplicate_group"
    bl_label = "MACHIN3: duplicate_group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.M3.is_group_empty]

    @classmethod
    def description(cls, context, properties):
        if context.scene.M3.group_recursive_select:
            return "Duplicate entire Group Hierarchies down\nALT: Create Instances"
        else:
            return "Duplicate Top Level Groups\nALT: Create Instances\nCTRL: Duplicate entire Group Hierarchies down"

    def invoke(self, context, event):
        empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]

        bpy.ops.object.select_all(action='DESELECT')

        for e in empties:
            e.select_set(True)
            select_group_children(context.view_layer, e, recursive=event.ctrl or context.scene.M3.group_recursive_select)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        bpy.ops.object.duplicate_move_linked('INVOKE_DEFAULT') if event.alt else bpy.ops.object.duplicate_move('INVOKE_DEFAULT')

        return {'FINISHED'}

class Add(bpy.types.Operator):
    bl_idname = "machin3.add_to_group"
    bl_label = "MACHIN3: Add to Group"
    bl_description = "Add Selection to Group"
    bl_options = {'REGISTER', 'UNDO'}

    realign_group_empty: BoolProperty(name="Re-Align Group Empty", default=False)
    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    add_mirror: BoolProperty(name="Add Mirror Modifiers, if there are common ones among the existing Group's objects, that are missing from the new Objects", default=True)
    is_mirror: BoolProperty()

    add_color: BoolProperty(name="Add Object Color, from Group's Empty", default=True)
    is_color: BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, 'realign_group_empty', toggle=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'rotation', expand=True)

        row = column.row(align=True)

        if self.is_color:
            row.prop(self, 'add_color', text="Add Color", toggle=True)

        if self.is_mirror:
            row.prop(self, 'add_mirror', text="Add Mirror", toggle=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        debug = False

        active_group = context.active_object if context.active_object and context.active_object.M3.is_group_empty and context.active_object.select_get() else None

        if not active_group:

            active_group = context.active_object.parent if context.active_object and context.active_object.M3.is_group_object and context.active_object.select_get() else None

            if not active_group:
                return {'CANCELLED'}

        objects = [obj for obj in context.selected_objects if obj != active_group and obj not in active_group.children and (not obj.parent or (obj.parent and obj.parent.M3.is_group_empty and not obj.parent.select_get()))]

        if debug:
            print("active group", active_group.name)
            print("     addable", [obj.name for obj in objects])

        if objects:

            children = [c for c in active_group.children if c.M3.is_group_object and c.type == 'MESH' and c.name in context.view_layer.objects]

            self.is_mirror = any(obj for obj in children for mod in obj.modifiers if mod.type == 'MIRROR')

            self.is_color = any(obj.type == 'MESH' for obj in objects)

            for obj in objects:
                if obj.parent:
                    unparent(obj)

                parent(obj, active_group)

                obj.M3.is_group_object = True

                if obj.type == 'MESH':

                    if children and self.add_mirror:
                        self.mirror(obj, active_group, children)

                    if self.add_color:
                        obj.color = active_group.color

            if self.realign_group_empty:

                gmx = get_group_matrix(context, [c for c in active_group.children], self.location, self.rotation)

                compensate_children(active_group, active_group.matrix_world, gmx)

                active_group.matrix_world = gmx

            clean_up_groups(context)

            process_group_poses(active_group)

            if get_prefs().group_tools_fade_sizes:
                fade_group_sizes(context, init=True)

            text = f"Added {len(objects)} objects to group '{active_group.name}'"
            draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=green, time=get_prefs().HUD_fade_group)

            return {'FINISHED'}
        return {'CANCELLED'}

    def mirror(self, obj, active_group, children):
        all_mirrors = {}

        for c in children:
            if c.M3.is_group_object and not c.M3.is_group_empty and c.type == 'MESH':
                mirrors = get_mods_as_dict(c, types=['MIRROR'], skip_show_expanded=True)

                if mirrors:
                    all_mirrors[c] = mirrors

        if all_mirrors and len(all_mirrors) == len(children):

            obj_props = [props for props in get_mods_as_dict(obj, types=['MIRROR'], skip_show_expanded=True).values()]

            if len(all_mirrors) == 1:

                common_props = [props for props in next(iter(all_mirrors.values())).values() if props not in obj_props]

            else:
                common_props = []

                for c, mirrors in all_mirrors.items():
                    others = [obj for obj in all_mirrors if obj != c]

                    for name, props in mirrors.items():
                        if all(props in all_mirrors[o].values() for o in others) and props not in common_props:
                            if props not in obj_props:
                                common_props.append(props)

            if common_props:
                common_mirrors = {f"Mirror{'.' + str(idx).zfill(3) if idx else ''}": props for idx, props in enumerate(common_props)}

                add_mods_from_dict(obj, common_mirrors)

class Remove(bpy.types.Operator):
    bl_idname = "machin3.remove_from_group"
    bl_label = "MACHIN3: Remove from Group"
    bl_description = "Remove Selection from Group"
    bl_options = {'REGISTER', 'UNDO'}

    realign_group_empty: BoolProperty(name="Re-Align Group Empty", default=False)
    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return True

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, 'realign_group_empty', toggle=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'rotation', expand=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        debug = False

        all_group_objects = [obj for obj in context.selected_objects if obj.M3.is_group_object]

        group_objects = [obj for obj in all_group_objects if obj.parent not in all_group_objects]

        if debug:
            print()
            print("all group objects", [obj.name for obj in all_group_objects])
            print("    group objects", [obj.name for obj in group_objects])

        if group_objects:

            empties = set()

            for obj in group_objects:
                empties.add(obj.parent)

                unparent(obj)
                obj.M3.is_group_object = False

            if self.realign_group_empty:
                for e in empties:
                    children = [c for c in e.children]

                    if children:
                        gmx = get_group_matrix(context, children, self.location, self.rotation)

                        compensate_children(e, e.matrix_world, gmx)

                        e.matrix_world = gmx

            top_empties = clean_up_groups(context)

            for empty in top_empties:
                process_group_poses(empty)

            text = f"Removed {len(group_objects)} objects from their group"
            draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=red, time=get_prefs().HUD_fade_group)

            return {'FINISHED'}
        return {'CANCELLED'}

class ToggleGroupMode(bpy.types.Operator):
    bl_idname = "machin3.toggle_outliner_group_mode"
    bl_label = "MACHIN3: Toggle Outliner Group Mode"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_outliner(context)

    def execute(self, context):
        area = context.area
        space = area.spaces[0]

        init_state = context.workspace.get('outliner_group_mode_toggle', False)

        if init_state:

            for name, prop in init_state.items():

                if name == 'M3':
                    for n, p in prop.items():
                        setattr(context.scene.M3, n, p)

                elif name == 'VISIBILITY':
                    for groupname, vis in prop.items():
                        if group := bpy.data.objects.get(groupname):
                            del vis['select']
                            restore_visibility(group, vis)

                        else:
                            print(f"WARNING: Couldn't find group empty {groupname}, skipped restoring visibility",)

                else:
                    setattr(space, name, prop)

            del init_state['M3']
            del context.workspace['outliner_group_mode_toggle']

            clean_up_groups(context)

        else:
            groups = [(obj, visible_get(obj)) for obj in context.view_layer.objects if obj.M3.is_group_empty]

            if groups:
                ensure_internal_index_group_name([obj for obj, _ in groups])

                init_state = {
                    'display_mode': space.display_mode,

                    'show_restrict_column_enable': space.show_restrict_column_enable,
                    'show_restrict_column_select': space.show_restrict_column_select,
                    'show_restrict_column_hide': space.show_restrict_column_hide,
                    'show_restrict_column_viewport': space.show_restrict_column_viewport,
                    'show_restrict_column_render': space.show_restrict_column_render,
                    'show_restrict_column_holdout': space.show_restrict_column_holdout,
                    'show_restrict_column_indirect_only': space.show_restrict_column_indirect_only,

                    'use_sort_alpha': space.use_sort_alpha,
                    'use_sync_select': space.use_sync_select,
                    'show_mode_column': space.show_mode_column,

                    'use_filter_complete': space.use_filter_complete,
                    'use_filter_case_sensitive': space.use_filter_case_sensitive,

                    'use_filter_view_layers': space.use_filter_view_layers,
                    'use_filter_collection': space.use_filter_collection,
                    'use_filter_object_mesh': space.use_filter_object_mesh,
                    'use_filter_object_content': space.use_filter_object_content,
                    'use_filter_object_armature': space.use_filter_object_armature,
                    'use_filter_object_light': space.use_filter_object_light,
                    'use_filter_object_camera': space.use_filter_object_camera,
                    'use_filter_object_others': space.use_filter_object_others,
                    'use_filter_object_grease_pencil': space.use_filter_object_grease_pencil,
                    'use_filter_object_empty': space.use_filter_object_empty,
                    'use_filter_children': space.use_filter_children,

                    'filter_state': space.filter_state,
                    'filter_text': space.filter_text,

                    'M3': {
                        'group_select': context.scene.M3.group_select,
                        'group_recursive_select': context.scene.M3.group_recursive_select,
                        'group_hide': context.scene.M3.group_hide,
                        'show_group_gizmos': context.scene.M3.show_group_gizmos,
                        'draw_group_relations': context.scene.M3.draw_group_relations
                    },

                    'VISIBILITY': {obj.name: vis for obj, vis in groups}
                }

                context.workspace['outliner_group_mode_toggle'] = init_state

                ensure_visibility(context, [obj for obj, vis in groups if not vis['visible']])

                if space.display_mode != 'VIEW_LAYER':
                    space.display_mode = 'VIEW_LAYER'

                space.show_restrict_column_enable = False
                space.show_restrict_column_select = True
                space.show_restrict_column_hide = True
                space.show_restrict_column_viewport = False
                space.show_restrict_column_render = False
                space.show_restrict_column_holdout = False
                space.show_restrict_column_indirect_only = False

                space.use_sort_alpha = True
                space.use_sync_select = True
                space.show_mode_column = True

                space.use_filter_complete = True
                space.use_filter_case_sensitive = True

                space.use_filter_view_layers = False
                space.use_filter_collection = False
                space.use_filter_object_mesh = False
                space.use_filter_object_content = False
                space.use_filter_object_armature = False
                space.use_filter_object_light = False
                space.use_filter_object_camera = False
                space.use_filter_object_others = False
                space.use_filter_object_grease_pencil = False
                space.use_filter_object_empty = True

                space.use_filter_children = True

                space.filter_state = 'ALL'

                if get_prefs().group_tools_auto_name:

                    empties = {obj for obj in context.view_layer.objects if obj.type == 'EMPTY'}
                    groups = {obj for obj in empties if obj.M3.is_group_empty}

                    if empties - groups:

                        has_prefix = False
                        has_suffix = False

                        for obj in groups:
                            prefix, basename, suffix = get_group_base_name(obj.name, debug=False)

                            if has_prefix is False and prefix:
                                has_prefix = True

                            if has_suffix is False and suffix:
                                has_suffix = True

                        if has_suffix and (suffix := get_prefs().group_tools_suffix) and has_prefix and (prefix := get_prefs().group_tools_prefix):
                            space.filter_text = f"{prefix}*{suffix}"

                        elif has_suffix and (suffix := get_prefs().group_tools_suffix):
                            space.filter_text = f"*{suffix}"

                        elif has_prefix and (prefix := get_prefs().group_tools_prefix):
                            space.filter_text = f"{prefix}*"

                if get_prefs().group_tools_group_mode_disable_auto_select:
                    context.scene.M3.group_select = False

                if get_prefs().group_tools_group_mode_disable_recursive_select:
                    context.scene.M3.group_recursive_select = False

                if get_prefs().group_tools_group_mode_disable_group_hide:
                    context.scene.M3.group_hide = False

                if True:
                    if get_prefs().group_tools_group_mode_disable_group_gizmos:
                        context.scene.M3.show_group_gizmos = False

                if get_prefs().group_tools_group_mode_enable_group_draw_relations:
                    context.scene.M3.draw_group_relations = True

            else:
                print("WARNING: Can't toggle Outliner into Group Mode, as there aren't any group objects!")

        return {'FINISHED'}

class ExpandOutliner(bpy.types.Operator):
    bl_idname = "machin3.expand_outliner"
    bl_label = "MACHIN3: Expand Outliner"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        bpy.ops.outliner.show_hierarchy()

        depth = get_collection_depth(self, [context.scene.collection], init=True)

        for i in range(depth):
            bpy.ops.outliner.show_one_level(open=True)

        return {'FINISHED'}

class CollapseOutliner(bpy.types.Operator):
    bl_idname = "machin3.collapse_outliner"
    bl_label = "MACHIN3: Collapse Outliner"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        col_depth = get_collection_depth(self, [context.scene.collection], init=True)

        child_depth = get_child_depth(self, [obj for obj in context.scene.objects if obj.children], init=True)

        for i in range(max(col_depth, child_depth) + 2):
            bpy.ops.outliner.show_one_level(open=False)

        return {'FINISHED'}

class ToggleChildren(bpy.types.Operator):
    bl_idname = "machin3.toggle_outliner_children"
    bl_label = "MACHIN3: Toggle Outliner Children"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        area = context.area
        space = area.spaces[0]

        space.use_filter_children = not space.use_filter_children
        return {'FINISHED'}

def draw_transform_group(op):
    def draw(self, context):
        layout = self.layout

        pose = op.poseCOL[op.pidx - 1]  if op.pidx > 0 else None

        row = layout.row(align=True)

        row.label(text="Transform Group")

        if op.pidx == 0 or pose.remove:
            draw_status_item(row, key='LMB', text="Finish")

        else:
            draw_status_item(row, key='LMB', text="Recall Pose + Finish")
            draw_status_item(row, key='SPACE', text="Finish")

        draw_status_item(row, key='RMB', text="Cancel")

        draw_status_item(row, key='G', text="Select Group Empty + Finish", gap=1)

        draw_status_item(row, key='Q', text="Setup Group Gizmos", gap=1)

        draw_status_item(row, active=op.is_angle_snapping, key='CTRL', text="5° Angle Snap", gap=10)

        if op.poseCOL:
            prop = pose.name if pose else 'None'

            draw_status_item(row, key='MMB_SCROLL', text="Pose", prop=prop, gap=1)

            if op.pidx > 0:
                draw_status_item(row, key=['ALT', 'MMB_SCROLL'], text="Preview Alpha", prop=dynamic_format(op.empty.M3.group_pose_alpha, 0), gap=1)

        draw_status_item(row, key='S', text="Set Pose + Finish", gap=2)

        if op.pidx > 0:
            draw_status_item(row, active=pose.remove, key='X', text="Remove Pose", gap=2)

        if op.poseCOL:
            draw_status_item(row, active=all(p.remove for p in op.poseCOL), key=['SHIFT', 'X'], text="Remove All Poses", gap=1)

    return draw

class TransformGroup(bpy.types.Operator):
    bl_idname = "machin3.transform_group"
    bl_label = "MACHIN3: Transform Group"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Group Empty Name")
    axis: EnumProperty(name="Rotation Axis", items=axis_items, default='X')
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode

    @classmethod
    def description(cls, context, properties):
        return f"Rotate Group '{properties.name}' around its {properties.axis} Axis"

    def draw_HUD(self, context):
        if self.area == context.area:
            draw_init(self)

            color = axis_color_mappings[self.axis]
            draw_vector(self.mouse_pos.resized(3) - self.group_location_2d.resized(3), origin=self.group_location_2d.resized(3), color=color, fade=True)

            prefix, basename, suffix = get_group_base_name(self.empty.name, remove_index=False)

            stack_dims = Vector((0, 0))

            if prefix:
                stack_dims = draw_label(context, title=prefix, coords=Vector((self.HUD_x, self.HUD_y)), center=False, size=10, alpha=0.3)

            stack_dims += draw_label(context, title=basename, coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), center=False, color=yellow)

            if suffix:
                draw_label(context, title=suffix, coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), center=False, size=10, alpha=0.3)

            self.offset += 18

            stack_dims = draw_label(context, title="Rotate ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False)
            stack_dims += draw_label(context, title="around ", coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), offset=self.offset, center=False, size=10, alpha=0.5)
            draw_label(context, title=self.axis, coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), offset=self.offset, center=False, color=axis_color_mappings[self.axis])

            self.offset += 18
            stack_dims = draw_label(context, title="Angle: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

            angle = dynamic_format(self.HUD_angle, decimal_offset=0 if self.is_angle_snapping else 2)
            color = yellow if self.is_angle_snapping else white
            alpha = 1 if self.pidx == 0 else 0.5
            stack_dims += draw_label(context, title=f"{angle}° ", coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)

            if self.is_angle_snapping:
                draw_label(context, title="Snapping", coords=Vector((self.HUD_x+ stack_dims.x, self.HUD_y)), offset=self.offset, center=False, color=yellow, alpha=alpha)

            self.offset += 24
            stack_dims = draw_label(context, title="Pose: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

            max_dim = max([get_text_dimensions(context, f"{name}  ").x for name in self.poses])

            pose_axes_differ = len(set(pose.axis for pose in self.poseCOL if pose.axis)) > 1

            if self.pidx > 0:
                alpha_dims = draw_label(context, title="Alpha: ", coords=Vector((self.HUD_x + stack_dims.x + max_dim, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)
                draw_label(context, title=dynamic_format(self.empty.M3.group_pose_alpha, 0), coords=Vector((self.HUD_x + stack_dims.x + max_dim + alpha_dims.x, self.HUD_y)), offset=self.offset, center=False)

            for idx, name in enumerate(self.poses):

                if idx > 0:
                    self.offset += 18

                    pose = self.poseCOL[idx - 1]
                    color = red if pose.remove else green if name == 'Inception' else yellow if name == 'LegacyPose' else blue

                else:
                    color = white

                alpha, size = (1, 12) if idx == self.pidx else (0.5, 10)

                if idx == 0:
                    draw_label(context, title=name, coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), offset=self.offset, center=False, size=size, color=color, alpha=alpha)

                elif idx == self.pidx:
                    pose_emoji = '❌ ' if pose.remove else '🏃'
                    offset_x = get_text_dimensions(context, f"{pose_emoji}").x

                    draw_label(context, title=f"{pose_emoji}{name}", coords=Vector((self.HUD_x + stack_dims.x - offset_x, self.HUD_y)), offset=self.offset, center=False, size=size, color=color, alpha=alpha)

                else:
                    draw_label(context, title=name, coords=Vector((self.HUD_x + stack_dims.x, self.HUD_y)), offset=self.offset, center=False, size=size, color=color, alpha=alpha)

                if idx > 0 and pose.axis:

                    axis_dim = Vector((0, 0))

                    if pose_axes_differ:
                        color = red if pose.axis == 'X' else green if pose.axis == 'Y' else blue
                        axis_dim = draw_label(context, title=f"{pose.axis} ", coords=Vector((self.HUD_x + stack_dims.x + max_dim, self.HUD_y)), offset=self.offset, center=False, size=size, color=color, alpha=alpha)

                    draw_label(context, title=f"{dynamic_format(pose.angle, decimal_offset=1)}°", coords=Vector((self.HUD_x + stack_dims.x + max_dim + axis_dim.x, self.HUD_y)), offset=self.offset, center=False, size=size, alpha=alpha)

    def draw_VIEW3D(self, context):
        if self.area == context.area:

            if self.pidx > 0:
                selected_pose = self.poseCOL[self.pidx - 1]
                alpha = self.empty.M3.group_pose_alpha

                for pose, batches in self.pose_batche_coords.items():

                    if batches:
                        color = red if pose.remove else green if pose.name == 'Inception' else yellow if pose.name == 'LegacyPose' else blue

                        if pose == selected_pose:
                            for batch in batches:

                                if isinstance(batch[0], Matrix):
                                    mx, length = batch
                                    draw_cross_3d(Vector(), mx=mx, length=length, color=normal)

                                else:
                                    draw_mesh_wire(batch, color=color, alpha=alpha)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

        self.is_angle_snapping = event.ctrl

        events = ['MOUSEMOVE', 'S', 'X', 'A', 'K', *ctrl, 'G', 'Q']

        if event.type in events or scroll(event):

            if event.type in ['MOUSEMOVE', *ctrl]:

                rotation = self.get_rotation(context)

                self.empty.matrix_world = Matrix.LocRotScale(self.init_location, rotation, self.init_scale)

            elif self.poseCOL and scroll(event):

                if event.alt and self.pidx > 0:
                    alpha = self.empty.M3.group_pose_alpha

                    if scroll_up(event):
                        if alpha <= 0.1:
                            alpha += 0.01

                        else:
                            alpha += 0.1

                    else:
                        if alpha <= 0.11:
                            alpha -= 0.01

                        else:
                            alpha -= 0.1

                    alpha = min(max(alpha, 0.01), 1)

                    for e in self.empties:
                        e.M3.avoid_update = True
                        e.M3.group_pose_alpha = alpha

                else:

                    if scroll_up(event):
                        self.pidx -= 1

                    else:
                        self.pidx += 1

                    if self.pidx < 0:
                        self.pidx = len(self.poses) - 1

                    elif self.pidx >= len(self.poses):
                        self.pidx = 0

                if not self.pose_batche_coords[self.poseCOL[self.pidx - 1]]:
                    get_pose_batches(context, self.empty, pose := self.poseCOL[self.pidx - 1], self.pose_batche_coords[pose], children=self.group_children, dg=self.dg)

                force_ui_update(context)

            elif event.type in ['S', 'X', 'A', 'K'] and event.value == 'PRESS':

                if event.type == 'S':
                    self.finish()

                    set_group_pose(self.empty)

                    location = self.empty.matrix_world.to_translation()
                    bpy.ops.machin3.draw_group_rest_pose(location=location, size=self.gizmo_size, time=1, alpha=0.2, reverse=False)

                    self.is_setting_rest_pose = True

                    self.auto_keyframe(context)

                    return {'FINISHED'}

                elif event.type == 'X':

                    if event.shift:
                        state = not self.poseCOL[0].remove

                        for pose in self.poseCOL:
                            pose.remove = state

                    elif self.pidx > 0:
                        pose = self.poseCOL[self.pidx - 1]
                        pose.remove = not pose.remove

                elif event.type == 'A':

                    state = not self.poseCOL[0].remove

                    for pose in self.poseCOL:
                        pose.remove = state

                force_ui_update(context)

            elif event.type == 'G' and event.value == 'PRESS':
                self.empty.matrix_world = Matrix.LocRotScale(self.init_location, self.init_rotation, self.init_scale)

                self.finish()

                bpy.ops.object.select_all(action='DESELECT')
                self.empty.select_set(True)
                context.view_layer.objects.active = self.empty

                return {'FINISHED'}

            elif event.type == 'Q' and event.value == 'PRESS':
                self.empty.matrix_world = Matrix.LocRotScale(self.init_location, self.init_rotation, self.init_scale)

                self.finish()

                bpy.ops.object.select_all(action='DESELECT')
                self.empty.select_set(True)
                context.view_layer.objects.active = self.empty

                bpy.ops.machin3.setup_group_gizmos('INVOKE_DEFAULT')

                return {'FINISHED'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()

            remove_poses = [pose for pose in self.poseCOL if pose.remove]
            recall_pose = self.poseCOL[self.pidx - 1] if self.pidx > 0 else None

            if recall_pose and recall_pose not in remove_poses and event.type == 'LEFTMOUSE':

                self.empty.M3.group_pose_IDX = self.pidx - 1

                retrieve_group_pose(self.empty)

                location = self.empty.matrix_world.to_translation()
                bpy.ops.machin3.draw_group_rest_pose(location=location, size=self.gizmo_size, time=1, alpha=0.2, reverse=True)

                self.is_recalling_rest_pose = True

            if remove_poses:
                remaining = [(pose.name, pose.mx.copy(), pose.uuid, pose.batch, pose.batchlinked, pose.axis, pose.angle) for pose in self.poseCOL if not pose.remove]

                is_inception_removal = any(is_inception_pose(p) for p in remove_poses)
                print("is inception removal:", is_inception_removal)

                self.empty.M3.group_pose_COL.clear()

                for idx, (name, mx, uuid, batch, batchlinked, axis, angle) in enumerate(remaining):
                    pose = self.empty.M3.group_pose_COL.add()
                    pose.index = idx

                    pose.avoid_update = True
                    pose.name = name

                    pose.mx = mx
                    pose.uuid = uuid
                    pose.batch = batch
                    pose.batchlinked = batchlinked

                    if not is_inception_removal:
                        pose.axis = axis
                        pose.angle = angle

                process_group_poses(self.empty)

                self.empty.M3.group_pose_IDX = 0 if remaining else -1

                prettify_group_pose_names(self.empty.M3.group_pose_COL)

            self.auto_keyframe(context)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.empty.matrix_world = Matrix.LocRotScale(self.init_location, self.init_rotation, self.init_scale)

            self.finish()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        finish_modal_handlers(self)

        finish_status(self)

    def invoke(self, context, event):
        self.gzm_grp = context.gizmo_group

        self.empty = bpy.data.objects.get(self.name)

        if self.empty and self.gzm_grp:

            get_mouse_pos(self, context, event)

            self.HUD_angle = 0
            self.is_angle_snapping = False

            self.empty_dir = None

            self.axis_direction = axis_vector_mappings[self.axis]
            self.init_rotation_intersect = None

            self.init_mx = self.empty.matrix_world.copy()
            self.init_location, self.init_rotation, self.init_scale = self.init_mx.decompose()

            self.group_location_2d = get_location_2d(context, self.init_location)

            self.is_setting_rest_pose = False
            self.is_recalling_rest_pose = False

            self.empties = get_group_hierarchy(self.empty, up=True)

            self.gzm, self.others = self.get_gizmos(self.gzm_grp)

            self.gizmo_size = self.gzm.scale_basis

            self.init_poses(context)

            get_mouse_pos(self, context, event)

            init_status(self, context, func=draw_transform_group(self))

            force_ui_update(context)

            init_modal_handlers(self, context, hud=True, view3d=True)
            return {'RUNNING_MODAL'}

        return {'CANCELLED'}

    def get_gizmos(self, gzm_group):
        active_gzm = None
        other_gizmos = []

        if gzm_group:
            for gzm in gzm_group.gizmos:
                if gzm.is_modal:
                    active_gzm = gzm

                else:
                    other_gizmos.append(gzm)

        return active_gzm, other_gizmos

    def init_poses(self, context):
        self.dg = context.evaluated_depsgraph_get()

        self.poseCOL = self.empty.M3.group_pose_COL
        self.poses = ['None']

        self.pidx = 0

        self.pose_batche_coords = {}

        self.group_children = [obj for obj in self.empty.children_recursive if obj.name in context.view_layer.objects and obj.visible_get()]

        for idx, pose in enumerate(self.poseCOL):
            self.poses.append(pose.name)

            pose.remove = False

            if self.pidx == 0 and pose.name not in ['Inception', 'LegacyPose'] and compare_quat(pose.mx.to_quaternion(), self.empty.matrix_local.to_quaternion(), precision=5, debug=False):
                self.pidx = idx + 1

            self.pose_batche_coords[pose] = []

        if self.pidx > 0:
            get_pose_batches(context, self.empty, pose := self.poseCOL[self.pidx - 1], self.pose_batche_coords[pose], children=self.group_children, dg=self.dg)

    def get_rotation(self, context):
        mx = self.empty.matrix_world

        self.view_origin = region_2d_to_origin_3d(context.region, context.region_data, self.mouse_pos)
        self.view_dir = region_2d_to_vector_3d(context.region, context.region_data, self.mouse_pos)

        self.empty_origin = mx.to_translation()

        if self.empty_dir is None:
            self.empty_dir = (mx.to_quaternion() @ self.axis_direction)

        i = intersect_line_plane(self.view_origin, self.view_origin + self.view_dir, self.empty_origin, self.empty_dir)

        if i:

            if not self.init_rotation_intersect:
                self.init_rotation_intersect = i
                return self.init_rotation

            else:
                v1 = self.init_rotation_intersect - self.empty_origin
                v2 = i - self.empty_origin

                deltarot = v1.rotation_difference(v2).normalized()

                angle = v1.angle(v2)

                if self.is_angle_snapping:
                    step = 5

                    dangle = degrees(angle)
                    mod = dangle % step

                    angle = radians(dangle + (step - mod)) if mod >= (step / 2) else radians(dangle - mod)

                    deltarot = Quaternion(deltarot.axis, angle)

                rotation = (deltarot @ self.init_rotation).normalized()

                dot = round(self.empty_dir.dot(deltarot.axis))

                self.HUD_angle = dot * degrees(angle)

                return rotation
            return self.init_rotation

    def auto_keyframe(self, context, init=False):

        return

        scene = context.scene

        self.empty.rotation_mode = 'QUATERNION'

        if init and not scene.tool_settings.use_keyframe_insert_auto:
            scene.tool_settings.use_keyframe_insert_auto = True

        if scene.tool_settings.use_keyframe_insert_auto:
            frame = scene.frame_current
            data_path = 'rotation_quaternion'

            self.empty.keyframe_insert(data_path=data_path, frame=frame)

            print("INFO: Auto-keyed rotation of", self.empty.name, "at frame", frame)

class BakeGroupGizmoSize(bpy.types.Operator):
    bl_idname = "machin3.bake_group_gizmo_size"
    bl_label = "MACHIN3: Bake Group Gizmo Size"
    bl_description = "Set Global Size to 1, and compensate each Group's Size accordingly."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.M3.group_gizmo_size != 1

    def execute(self, context):
        gizmo_size = context.scene.M3.group_gizmo_size
        divider = 1 / gizmo_size

        group_empties = [obj for obj in bpy.data.objects if obj.type == 'EMPTY' and obj.M3.is_group_empty]

        for obj in group_empties:
            obj.M3.group_gizmo_size /= divider

        context.scene.M3.group_gizmo_size = 1
        return {'FINISHED'}

def draw_setup_group_gizmos_status(op):
    def draw(self, context):
        decimal_offset = 2 if op.empty.M3.group_gizmo_size > 1 else 1
        m3 = op.empty.M3

        layout = self.layout

        row = layout.row(align=True)

        row.label(text="Setup Group Gizmos")

        draw_status_item(row, key='LMB', text="Confirm")
        draw_status_item(row, key='RMB', text="Cancel")

        draw_status_item_precision(row, fine=op.is_shift, coarse=op.is_ctrl, gap=10)

        draw_status_item(row, key='MMB_SCROLL', text="Adjust Size", prop=dynamic_format(m3.group_gizmo_size, decimal_offset=decimal_offset), gap=1)

        draw_status_item(row, key='TAB', text="Toggle Axis Gizmo based on View", prop=op.aligned_axis, gap=2)

        draw_status_item(row, text="Axis Gizmos:")
        draw_status_item(row, active=m3.show_group_x_rotation, key='X')
        draw_status_item(row, active=m3.show_group_y_rotation, key='Y')
        draw_status_item(row, active=m3.show_group_z_rotation, key='Z')

        draw_status_item(row, key='A', text="Toggle All", gap=2)

        draw_status_item(row, active=op.lock_axes, key='R', text="Lock Axes without Gizmos", gap=2)
        draw_status_item(row, active=m3.show_group_gizmo, key='S', text=f"Show Gizmos{'s' if len(op.axes) > 1 else ''}", gap=2)

    return draw

class SetupGroupGizmos(bpy.types.Operator):
    bl_idname = "machin3.setup_group_gizmos"
    bl_label = "MACHIN3: Setup Group Gizmos"
    bl_description = "Setup Group Gizmos"
    bl_options = {'REGISTER', 'UNDO'}

    lock_axes: BoolProperty(name="Lock Rotational Axes without Gizmos", default=True)
    passthrough = None

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            active = context.active_object
            return active and active.M3.is_group_empty

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def draw_HUD(self, context):
        if self.area == context.area:
            draw_init(self)

            prefix, basename, suffix = get_group_base_name(self.empty.name, remove_index=False)

            dims = Vector((0, 0))

            if prefix:
                dims = draw_label(context, title=prefix, coords=Vector((self.HUD_x, self.HUD_y)), center=False, size=10, alpha=0.3)

            dims += draw_label(context, title=basename, coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False, color=yellow)

            if suffix:
                draw_label(context, title=suffix, coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False, size=10, alpha=0.3)

            self.offset += 18
            alpha = 1 if self.empty.M3.show_group_gizmo else 0.25
            dims = draw_label(context, title="Setup Group Gizmos ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=alpha)

            if not self.empty.M3.show_group_gizmo:
                draw_label(context, title=" Disabled", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, size=10, alpha=0.5)

            self.offset += 18

            axes = self.axes.copy()

            if self.aligned_axis not in axes:
                axes.append(self.aligned_axis)
                axes.sort()

            labels = [
                ("Axes: ", 12, white, 0.5)
            ]

            for axis in axes:
                if axis == self.aligned_axis and not getattr(self.empty.M3, f"show_group_{axis.lower()}_rotation"):
                    labels.append((f"{axis} ", 12, white, 0.3))
                else:
                    labels.append((f"{axis} ", 12, axis_color_mappings[axis], 1))

            draw_multi_label(self, context, labels)

            self.offset += 18

            dims = draw_label(context, title="Size: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

            decimal_offset = 1 if self.empty.M3.group_gizmo_size > 1 else 0

            if self.is_shift:
                decimal_offset += 1
            elif self.is_ctrl:
                decimal_offset -= 1

            dims += draw_label(context, title=f"{dynamic_format(self.empty.M3.group_gizmo_size, decimal_offset=decimal_offset)} ", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False)

            if self.is_shift or self.is_ctrl:
                dims += draw_label(context, title="🔍 " if self.is_shift else "💪 ", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

            if context.scene.M3.group_gizmo_size != 1:
                dims += draw_label(context, title=" ⚠", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, size=20, color=yellow)
                draw_label(context, title=f" Global: {dynamic_format(context.scene.M3.group_gizmo_size, 1)}", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, alpha=0.25)

            if self.lock_axes:
                self.offset += 18

                dims = draw_label(context, title="Lock Rotational Axes ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=yellow)
                draw_label(context, title="(those without Gizmos)", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, size=10, alpha=0.25)

    def draw_VIEW3D(self, context):
        if context.area == self.area:

            scale = context.preferences.system.ui_scale
            size = self.empty.M3.group_gizmo_size * context.scene.M3.group_gizmo_size * (self.empty.empty_display_size / 0.2) * (sum(self.gmx.to_scale()) / 3)

            axes = [axis.capitalize() for axis in ['x', 'y', 'z'] if getattr(self.empty.M3, f"show_group_{axis}_rotation")]

            if self.aligned_axis in axes:
                color = red if self.aligned_axis == 'X' else green if self.aligned_axis == 'Y' else blue
                alpha, width = 0.3, 5

            else:
                color, alpha, width = white, 0.03, 10

            radius = size * scale

            draw_circle(loc=self.gloc, rot=self.aligned_rot, radius=radius, segments=100, width=width, color=color, alpha=alpha)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

        self.is_shift = event.shift
        self.is_ctrl = event.ctrl

        events = ['MOUSEMOVE', 'A', 'X', 'Y', 'Z', 'T', 'TAB', 'S', 'D', 'R', 'L']

        if event.type in events or scroll(event):
            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.aligned_axis, self.aligned_rot = self.get_group_axis_aligned_with_view(context, debug=False)
                    self.passthrough = False

            elif scroll(event):
                if scroll_up(event):
                    self.empty.M3.group_gizmo_size += 0.01 if self.is_shift else 1 if self.is_ctrl else 0.1
                else:
                    self.empty.M3.group_gizmo_size -= 0.01 if self.is_shift else 1 if self.is_ctrl else 0.1

            if event.type == 'A' and event.value == 'PRESS':
                axes = [getattr(self.empty.M3, f"show_group_{axis}_rotation") for axis in ['x', 'y', 'z']]

                if all(axes):
                    for axis in ['x', 'y', 'z']:
                        self.empty.M3.avoid_update = False
                        setattr(self.empty.M3, f"show_group_{axis}_rotation", False)

                else:
                    for axis in ['x', 'y', 'z']:
                        if not getattr(self.empty.M3, f"show_group_{axis}_rotation"):
                            self.empty.M3.avoid_update = False
                            setattr(self.empty.M3, f"show_group_{axis}_rotation", True)

                self.get_enabled_axes()

                self.set_axes_locks()

            elif event.type in ['X', 'Y', 'Z', 'TAB', 'T'] and event.value == 'PRESS':

                if event.type == 'X':
                    axis = 'X'

                elif event.type == 'Y':
                    axis = 'Y'

                elif event.type == 'Z':
                    axis = 'Z'

                elif event.type in ['TAB', 'T'] and event.value == 'PRESS':
                    axis = self.aligned_axis

                self.empty.M3.avoid_update = True
                setattr(self.empty.M3, f"show_group_{axis.lower()}_rotation", not getattr(self.empty.M3, f"show_group_{axis.lower()}_rotation"))

                self.get_enabled_axes()

                self.set_axes_locks()

            elif event.type in ['S', 'D'] and event.value == 'PRESS':
                self.empty.M3.show_group_gizmo = not self.empty.M3.show_group_gizmo

            elif event.type in ['R', 'L'] and event.value == 'PRESS':
                self.lock_axes = not self.lock_axes

                self.set_axes_locks()

            force_ui_update(context)

        if navigation_passthrough(event, alt=True, wheel=False):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE'] and event.value == 'PRESS':
            self.finish(context)

            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            self.finish(context)

            self.restore_initial_state(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        finish_modal_handlers(self)

        finish_status(self)

    def invoke(self, context, event):
        self.empty = context.active_object
        self.gmx = self.empty.matrix_world
        self.gloc = self.gmx.to_translation()

        self.fetch_initial_state(context)

        self.aligned_axis, self.aligned_rot = self.get_group_axis_aligned_with_view(context, debug=False)

        if not context.scene.M3.show_group_gizmos:
            context.scene.M3.avoid_update = True
            context.scene.M3.show_group_gizmos = True

        if not self.empty.M3.show_group_gizmo:
            self.empty.M3.avoid_update = True
            self.empty.M3.show_group_gizmo = True

            if not any([getattr(self.empty.M3, f"show_group_{axis}_rotation") for axis in ['x', 'y', 'z']]):

                self.empty.M3.avoid_update = True
                setattr(self.empty.M3, f"show_group_{self.aligned_axis.lower()}_rotation", True)

        self.get_enabled_axes()

        self.set_axes_locks()

        force_ui_update(context)

        self.is_shift = event.shift
        self.is_ctrl = event.ctrl

        get_mouse_pos(self, context, event)

        init_status(self, context, func=draw_setup_group_gizmos_status(self))

        init_modal_handlers(self, context, hud=True, view3d=True)
        return {'RUNNING_MODAL'}

    def fetch_initial_state(self, context):
        self.init_props = {'show_group_gizmos': context.scene.M3.show_group_gizmos,
                           'show_group_gizmo': self.empty.M3.show_group_gizmo,

                           'show_group_x_rotation': self.empty.M3.show_group_x_rotation,
                           'show_group_y_rotation': self.empty.M3.show_group_y_rotation,
                           'show_group_z_rotation': self.empty.M3.show_group_z_rotation,

                           'lock_rotation_x': self.empty.lock_rotation[0],
                           'lock_rotation_y': self.empty.lock_rotation[1],
                           'lock_rotation_z': self.empty.lock_rotation[2],

                           'group_gizmo_size': self.empty.M3.group_gizmo_size}

    def get_enabled_axes(self):
        self.axes = [axis.capitalize() for axis in ['x', 'y', 'z'] if getattr(self.empty.M3, f"show_group_{axis}_rotation")]

    def set_axes_locks(self):
        for idx, (axis, _, _) in enumerate(axis_items):
            if self.lock_axes:
                self.empty.lock_rotation[idx] = self.empty.M3.show_group_gizmo and axis not in self.axes

            else:
                self.empty.lock_rotation[idx] = False

    def restore_initial_state(self, context):
        for prop, state in self.init_props.items():
            if prop == 'show_group_gizmos':
                context.scene.M3.avoid_update = True
                setattr(context.scene.M3, prop, state)

            elif 'lock_rotation_' in prop:
                axis = prop.replace('lock_rotation_', '').capitalize()
                self.empty.lock_rotation[axis_index_mapping[axis]] = state

            else:
                self.empty.M3.avoid_update = True
                setattr(self.empty.M3, prop, state)

    def get_group_axis_aligned_with_view(self, context, debug=False):
        view_center = Vector((context.region.width / 2, context.region.height / 2))

        view_origin, view_dir = get_view_origin_and_dir(context, view_center)

        if debug:
            draw_point(view_origin, modal=False)
            draw_vector(view_dir, origin=view_origin, modal=False)

        axes = []

        group_loc, group_rot, _ = self.gmx.decompose()
        group_up = group_rot @ Vector((0, 0, 1))

        for axis in ['X', 'Y', 'Z']:
            group_axis_dir = group_rot @ axis_vector_mappings[axis]

            if debug:
                draw_vector(group_axis_dir, origin=group_loc, modal=False)

            dot = group_axis_dir.dot(view_dir)

            axis_rot = group_axis_dir.rotation_difference(group_up) @ group_rot

            axes.append((axis, axis_rot, dot))

            if debug:
                print(axis, dot)

        aligned = max(axes, key=lambda x: abs(x[2]))

        if debug:
            print("aligned axis:", aligned[0])
            print("aligned rotation:", aligned[1])

        return aligned[0], aligned[1]

class SetGroupPose(bpy.types.Operator):
    bl_idname = "machin3.set_group_pose"
    bl_label = "MACHIN3: Set Group Pose"
    bl_description = "Set Group Pose"
    bl_options = {'REGISTER', 'UNDO'}

    batch: BoolProperty(name="Batch Pose", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return active and active.type == 'EMPTY' and active.M3.is_group_empty

    @classmethod
    def description(cls, context, properties):
        active = context.active_object

        if properties.batch:
            return f"Create linked Batch Poses for {active.name} and all Group Empties under it"

        else:
            return f"Create new Pose based on {active.name}'s current Rotation"

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def execute(self, context):
        active = context.active_object

        if self.batch:
            group_empties = get_group_hierarchy(active, up=False)

            if group_empties:

                name = get_batch_pose_name(group_empties)

                uuid = set_group_pose(active, name=name, batch=True)

                for obj in group_empties:
                    if obj != active:
                        set_group_pose(obj, name=name, uuid=uuid, batch=True)

            else:
                return {'CANCELLED'}

        else:
            set_group_pose(active)

        return {'FINISHED'}

class UpdateGroupPose(bpy.types.Operator):
    bl_idname = "machin3.update_group_pose"
    bl_label = "MACHIN3: Update Group Pose"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(name="Index", default=-1)
    is_batch: BoolProperty(name="Batch Retrieval", default=False)
    update_up: BoolProperty(name="Update Up", description="Update Poses Up the Hierarchy too", default=False)
    update_unlinked: BoolProperty(name="Update Unlinked", description="Update Poses, that have been unlinked too", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return active and active.type == 'EMPTY' and active.M3.is_group_empty and (poseCOL := active.M3.group_pose_COL) and 0 <= active.M3.group_pose_IDX < len(poseCOL)

    @classmethod
    def description(cls, context, properties):
        if properties.index == -1:
            return "Update active Pose from current Group Empty's Rotation"
        else:
            if active := context.active_object:
                poseCOL = active.M3.group_pose_COL

                if properties.index >= 0 and properties.index < len(poseCOL):
                    pose = poseCOL[properties.index]
                    return f"Update Pose '{pose.name}' from current Group Empty's Rotation"
        return "Invalid"

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if self.is_batch:
            row = column.row(align=True)

            row.prop(self, 'update_up', toggle=True)
            row.prop(self, 'update_unlinked', toggle=True)

    def invoke(self, context, event):
        active = context.active_object
        poseCOL = active.M3.group_pose_COL
        pose = poseCOL[active.M3.group_pose_IDX]

        self.is_batch = pose.batch
        return self.execute(context)

    def execute(self, context):
        active = context.active_object
        poseCOL = active.M3.group_pose_COL

        pose = poseCOL[active.M3.group_pose_IDX] if self.index == -1 else poseCOL[self.index]

        pose.mx = active.matrix_local

        if is_inception_pose(pose):
            for pose in active.M3.group_pose_COL:
                if pose.axis:
                    pose.axis = ''

        elif pose.axis:
            pose.axis = ''

        pose = poseCOL[active.M3.group_pose_IDX] if self.index == -1 else poseCOL[self.index]
        uuid = pose.uuid

        if pose.batch and pose.batchlinked:
            group_empties = get_group_hierarchy(active, up=self.update_up)

            for empty in group_empties:
                if empty != active:

                    batch_poses = [p for p in empty.M3.group_pose_COL if p.batch and p.uuid == uuid]

                    if batch_poses:
                        batch_pose = batch_poses[0]

                        if self.update_unlinked or batch_pose.batchlinked:
                            batch_pose.mx = empty.matrix_local

                            if batch_pose.axis:
                                batch_pose.axis = ''

                            if is_inception_pose(batch_pose):
                                for p in empty.M3.group_pose_COL:
                                    if p.axis:
                                        p.axis = ''

                            elif batch_pose.axis:
                                batch_pose.axis = ''

        process_group_poses(active, debug=False)

        force_ui_update(context)

        return {'FINISHED'}

class RetrieveGroupPose(bpy.types.Operator):
    bl_idname = "machin3.retrieve_group_pose"
    bl_label = "MACHIN3: Retrieve Group Pose"
    bl_description = "Retrieve Selected Group Pose"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    is_batch = BoolProperty(name="Batch Retrieval", default=False)
    retrieve_up: BoolProperty(name="Retrieve Up", description="Retrieve Poses Up the Hierarchy too", default=False)
    retrieve_unlinked: BoolProperty(name="Retrieve Unlinked", description="Retrieve Poses, that have been unlinked too", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return active and active.type == 'EMPTY' and active.M3.is_group_empty and active.M3.group_pose_COL

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if self.is_batch:
            row = column.row(align=True)

            row.prop(self, 'retrieve_up', toggle=True)
            row.prop(self, 'retrieve_unlinked', toggle=True)

    def invoke(self, context, event):
        active = context.active_object

        if 0 <= self.index < len(active.M3.group_pose_COL):
            pose = active.M3.group_pose_COL[self.index]

            self.is_batch = pose.batch
            return self.execute(context)
        return {'CANCELLED'}

    def execute(self, context):
        context.evaluated_depsgraph_get()

        active = context.active_object
        poseCOL = active.M3.group_pose_COL

        pose = poseCOL[self.index]

        if pose.batch and pose.batchlinked:

            uuid = pose.uuid

            group_empties = get_group_hierarchy(active, up=self.retrieve_up)

            for empty in group_empties:

                for p in empty.M3.group_pose_COL:
                    if p.uuid == uuid and p.batch and (self.retrieve_unlinked or p.batchlinked):
                        retrieve_group_pose(empty, index=p.index)
                        break

        else:
            retrieve_group_pose(active, index=self.index)

        if active.M3.draw_active_group_pose:
            active.M3.group_pose_COL[active.M3.group_pose_IDX].forced_preview_update = True

        return {'FINISHED'}

class SortGroupPose(bpy.types.Operator):
    bl_idname = "machin3.sort_group_pose"
    bl_label = "MACHIN3: Sort Group Pose"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty()
    index: IntProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return active and active.type == 'EMPTY' and active.M3.is_group_empty and len(active.M3.group_pose_COL) > 1

    @classmethod
    def description(cls, context, properties):
        return f"Move Selected Goup Pose {properties.direction.title()}"

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def execute(self, context):
        active = context.active_object
        poseCOL = active.M3.group_pose_COL

        if self.direction == 'UP' and self.index > 0:
            new_idx = self.index - 1

        elif self.direction == 'DOWN' and self.index < len(poseCOL) - 1:
            new_idx = self.index + 1

        else:
            return {'CANCELLED'}

        poseCOL.move(self.index, new_idx)

        active.M3.group_pose_IDX = new_idx

        prettify_group_pose_names(poseCOL)

        return {'FINISHED'}

class RemoveGroupPose(bpy.types.Operator):
    bl_idname = "machin3.remove_group_pose"
    bl_label = "MACHIN3: Remove Group Pose"
    bl_description = "Remove Group Pose"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty()

    def update_remove_poses(self, context):
        active = context.active_object
        poseCOL = active.M3.group_pose_COL

        if poseCOL and 0 <= self.index < len(poseCOL):
            pose = active.M3.group_pose_COL[self.index]
            uuid = pose.uuid

            get_remove_poses(self, active, uuid)

    is_batch = BoolProperty(name="Batch Retrieval", default=False)
    remove_batch: BoolProperty(name="Remove related Batch Poses", description="Remove all related Batch Poses in the Group Hierarchy", default=True, update=update_remove_poses)
    remove_up: BoolProperty(name="Remove Up", description="Remove Batch Poses further Up the Hierarchy too", default=False, update=update_remove_poses)
    remove_unlinked: BoolProperty(name="Remove Disconnected", description="Remove Batch Poses, that have been unlinked too", default=False, update=update_remove_poses)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return active and active.type == 'EMPTY' and active.M3.is_group_empty and active.M3.group_pose_COL

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if self.is_batch:
            column.prop(self, 'remove_batch', toggle=True)

            row = column.row(align=True)
            row.enabled = self.remove_batch
            row.prop(self, 'remove_up', toggle=True)
            row.prop(self, 'remove_unlinked', toggle=True)

            column.separator()
            column.label(text="Batch Poses to be Removed:")

            for is_active_empty, objname, posename, linked in self.remove_poses:
                row = column.row(align=False)

                r = row.row()
                r.active = is_active_empty
                r.label(text='', icon='SPHERE' if is_active_empty else 'CUBE')

                s = row.split(factor=0.4)

                row = s.row(align=True)
                row.alignment = 'LEFT'

                prefix, basename, suffix = objname

                if prefix:
                    r = row.row(align=True)
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text=prefix)

                row.label(text=basename)

                if suffix:
                    r = row.row(align=True)
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text=suffix)

                s.label(text=posename, icon='LINKED' if linked else 'UNLINKED')

    def invoke(self, context, event):
        self.remove_batch = True

        active = context.active_object

        if 0 <= self.index < len(active.M3.group_pose_COL):
            pose = active.M3.group_pose_COL[self.index]

            self.is_batch = pose.batch

            if self.is_batch:

                uuid = pose.uuid

                get_remove_poses(self, active, uuid)

                return context.window_manager.invoke_props_dialog(self, width=300)
            return self.execute(context)

        return {'CANCELLED'}

    def execute(self, context):
        active = context.active_object
        poseCOL = active.M3.group_pose_COL

        if self.is_batch and self.remove_batch:
            pose = poseCOL[self.index]

            for obj, idx in get_remove_poses(self, active, pose.uuid):
                obj.M3.group_pose_COL.remove(idx)

                if obj.M3.group_pose_COL:
                    if idx < obj.M3.group_pose_IDX or obj.M3.group_pose_IDX >= len(obj.M3.group_pose_COL):
                        obj.M3.group_pose_IDX -= 1
                else:
                    obj.M3.group_pose_IDX = -1

                prettify_group_pose_names(obj.M3.group_pose_COL)

        else:
            poseCOL.remove(self.index)

            if poseCOL:
                if self.index < active.M3.group_pose_IDX or active.M3.group_pose_IDX >= len(poseCOL):
                    active.M3.group_pose_IDX -= 1
            else:
                active.M3.group_pose_IDX = -1

            prettify_group_pose_names(poseCOL)

        process_group_poses(active)

        if active.M3.draw_active_group_pose or self.is_batch:
            force_ui_update(context, active=active)

        return {'FINISHED'}
