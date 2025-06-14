import bpy
import os
from bpy.app.handlers import persistent
from time import time

from . utils.application import delay_execution, set_prop_safe
from . utils.asset import validate_assetbrowser_bookmarks
from . utils.draw import draw_axes_VIEW3D, draw_focus_HUD, draw_group_relations_VIEW3D, draw_surface_slide_HUD, draw_screen_cast_HUD, draw_group_poses_VIEW3D, draw_assembly_edit_HUD
from . utils.group import get_group_relation_coords, get_pose_batches, process_group_poses, select_group_children, set_group_pose, set_pose_uuid
from . utils.light import adjust_lights_for_rendering, get_area_light_poll
from . utils.math import compare_quat
from . utils.object import get_active_object, get_view_layer_objects, get_visible_objects
from . utils.registration import get_prefs, reload_msgbus
from . utils.system import get_temp_dir
from . utils.view import sync_light_visibility

global_debug = False

axesVIEW3D = None
prev_axes_objects = []

def manage_axes_VIEW3D():
    global global_debug, axesVIEW3D, prev_axes_objects

    debug = global_debug

    scene = getattr(bpy.context, 'scene', None)

    if scene:

        if debug:
            print("  axes VIEW3D")

        if axesVIEW3D and "RNA_HANDLE_REMOVED" in str(axesVIEW3D):
            axesVIEW3D = None

        axes_objects = [obj for obj in get_visible_objects(bpy.context) if obj.M3.draw_axes]

        active = get_active_object(bpy.context)

        if scene.M3.draw_active_axes and active and active not in axes_objects:
            axes_objects.append(active)

        if scene.M3.draw_cursor_axes:
            axes_objects.append('CURSOR')

        if axes_objects:
            if debug:
                print("   axes objects present:", [obj if obj == 'CURSOR' else obj.name for obj in axes_objects])

            if axes_objects != prev_axes_objects:
                if debug:
                    print("   axes objects changed")

                prev_axes_objects = axes_objects

                if axesVIEW3D:
                    if debug:
                        print("   removing previous draw handler")

                    bpy.types.SpaceView3D.draw_handler_remove(axesVIEW3D, 'WINDOW')

                if debug:
                    print("   adding new draw handler")
                axesVIEW3D = bpy.types.SpaceView3D.draw_handler_add(draw_axes_VIEW3D, (bpy.context, axes_objects), 'WINDOW', 'POST_VIEW')

        elif axesVIEW3D:
            bpy.types.SpaceView3D.draw_handler_remove(axesVIEW3D, 'WINDOW')

            if debug:
                print("   removing old draw handler")

            axesVIEW3D = None
            prev_axes_objects = []

focusHUD = None

def manage_focus_HUD():
    global global_debug, focusHUD

    debug = global_debug

    scene = getattr(bpy.context, 'scene', None)

    if scene:

        if debug:
            print("  focus HUD")

        if focusHUD and "RNA_HANDLE_REMOVED" in str(focusHUD):
            focusHUD = None

        history = scene.M3.focus_history

        if history:
            if not focusHUD:
                if debug:
                    print("   adding new draw handler")

                focusHUD = bpy.types.SpaceView3D.draw_handler_add(draw_focus_HUD, (bpy.context, (1, 1, 1), 1, 2), 'WINDOW', 'POST_PIXEL')

        elif focusHUD:
            if debug:
                print("   removing old draw handler")

            bpy.types.SpaceView3D.draw_handler_remove(focusHUD, 'WINDOW')
            focusHUD = None

surfaceslideHUD = None

def manage_surface_slide_HUD():
    global global_debug, surfaceslideHUD

    debug = global_debug

    if debug:
        print("  surface slide HUD")

    if surfaceslideHUD and "RNA_HANDLE_REMOVED" in str(surfaceslideHUD):
        surfaceslideHUD = None

    active = get_active_object(bpy.context)

    if active:
        surfaceslide = [mod for mod in active.modifiers if mod.type == 'SHRINKWRAP' and 'SurfaceSlide' in mod.name]

        if surfaceslide and not surfaceslideHUD:
            if debug:
                print("   adding new draw handler")

            surfaceslideHUD = bpy.types.SpaceView3D.draw_handler_add(draw_surface_slide_HUD, (bpy.context, (0, 1, 0), 1, 2), 'WINDOW', 'POST_PIXEL')

        elif surfaceslideHUD and not surfaceslide:
            if debug:
                print("   removing old draw handler")

            bpy.types.SpaceView3D.draw_handler_remove(surfaceslideHUD, 'WINDOW')
            surfaceslideHUD = None

screencastHUD = None

def manage_screen_cast_HUD():
    global global_debug, screencastHUD

    debug = global_debug

    if debug:
        print("  screen cast HUD")

    wm = bpy.context.window_manager

    if screencastHUD and "RNA_HANDLE_REMOVED" in str(screencastHUD):
        screencastHUD = None

    if getattr(wm, 'M3_screen_cast', False):
        if not screencastHUD:
            if debug:
                print("   adding new draw handler")

            screencastHUD = bpy.types.SpaceView3D.draw_handler_add(draw_screen_cast_HUD, (bpy.context, ), 'WINDOW', 'POST_PIXEL')

    elif screencastHUD:
        if debug:
            print("   removing old draw handler")

        bpy.types.SpaceView3D.draw_handler_remove(screencastHUD, 'WINDOW')
        screencastHUD = None

def manage_group():
    global global_debug

    debug = global_debug

    if debug:
        print("  group management")

    C = bpy.context
    scene = getattr(C, 'scene', None)
    m3 = scene.M3

    if scene and C.mode == 'OBJECT':
        active = active if (active := get_active_object(C)) and active.M3.is_group_empty and active.select_get() and not active.library else None

        if m3.group_select and active:
            if debug:
                print("   auto-selecting")

            select_group_children(C.view_layer, active, recursive=m3.group_recursive_select)

        if active:
            if debug:
                print("   storing user-set empty size")

            if round(active.empty_display_size, 4) != 0.0001 and active.empty_display_size != active.M3.group_size:
                set_prop_safe(active.M3, 'group_size', active.empty_display_size)

        if (visible := get_visible_objects(C)):

            group_empties = [obj for obj in visible if obj.M3.is_group_empty and not obj.library]

            if m3.group_hide:
                if debug:
                    print("   hiding/unhiding")

                selected = [obj for obj in group_empties if obj.select_get()]
                unselected = [obj for obj in group_empties if not obj.select_get()]

                if selected:
                    for group in selected:
                        if not group.show_name:
                            set_prop_safe(group, 'show_name', True)

                        if group.empty_display_size != group.M3.group_size:
                            set_prop_safe(group, 'empty_display_size', group.M3.group_size)

                if unselected:
                    for group in unselected:
                        if group.show_name:
                            set_prop_safe(group, 'show_name', False)

                        if round(group.empty_display_size, 4) != 0.0001:
                            set_prop_safe(group.M3, 'group_size', group.empty_display_size)

                            set_prop_safe(group, 'empty_display_size', 0.0001)

            for group in group_empties:
                if group == active:
                    if not group.empty_display_type == 'SPHERE':
                        if debug:
                            print("   setting active group display type to SPHERE")

                        set_prop_safe(group, 'empty_display_type', 'SPHERE')

                elif group.empty_display_type == 'SPHERE':
                    if debug:
                        print("   setting inactive group display type to CUBE")

                    set_prop_safe(group, 'empty_display_type', 'CUBE')

def manage_legacy_group_poses():
    global global_debug

    debug = global_debug

    if debug:
        print("  legacy group poses")

    legacy_group_empties = [obj for obj in bpy.data.objects if obj.type == 'EMPTY' and obj.M3.is_group_empty and not obj.M3.group_pose_COL]

    if legacy_group_empties:
        for empty in legacy_group_empties:

            if debug:
                print(f"   legacy group: {empty.name}")

            else:
                print(f"INFO: Updating group {empty.name}'s legacy rest pose to new multi-pose format")

            empty.M3.group_pose_IDX = 0

            pose = empty.M3.group_pose_COL.add()
            pose.index = 0

            legacy_mx = empty.matrix_parent_inverse @ empty.M3.group_rest_pose

            pose.mx = legacy_mx

            pose.avoid_update = True
            pose.name = "Inception"

            set_pose_uuid(pose)

            if not compare_quat(legacy_mx.to_quaternion(), empty.matrix_local.to_quaternion(), precision=5):
                set_group_pose(empty, name='LegacyPose')

    for empty in legacy_group_empties:
        if not empty.parent:
            process_group_poses(empty)

groupposesVIEW3D = None
olddrawn = None

def manage_group_poses_VIEW3D():
    global global_debug, groupposesVIEW3D, olddrawn

    debug = global_debug

    if debug:
        print("  group poses VIEW3D")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        if groupposesVIEW3D and "RNA_HANDLE_REMOVED" in str(groupposesVIEW3D):
            groupposesVIEW3D = None

        active = active if (active := get_active_object(bpy.context)) and active.select_get() and active.type == 'EMPTY' and active.M3.is_group_empty and active.M3.group_pose_COL else None
        pose = active.M3.group_pose_COL[active.M3.group_pose_IDX] if active else None

        if active and active.M3.draw_active_group_pose and pose:

            if not groupposesVIEW3D or (active, active.M3.group_pose_IDX, active.M3.group_pose_alpha, pose.uuid, pose.index, pose.batch, pose.batchlinked, pose.mx, pose.forced_preview_update) != olddrawn:
                if pose.forced_preview_update:
                    pose.forced_preview_update = False

                olddrawn = (active, active.M3.group_pose_IDX, active.M3.group_pose_alpha, pose.uuid, pose.index, pose.batch, pose.batchlinked, pose.mx.copy(), pose.forced_preview_update)

                if debug:
                    if not groupposesVIEW3D:
                        print("   adding VIEW3D handler")
                    else:
                        print("   re-creating VIEW3D handler because active, pose preview alpha, pose uuid, pose index, mx, batch of batchlinked props")

                if groupposesVIEW3D:
                    bpy.types.SpaceView3D.draw_handler_remove(groupposesVIEW3D, 'WINDOW')

                batches = []
                get_pose_batches(bpy.context, active, pose, batches, preview_batch_poses=True)

                groupposesVIEW3D = bpy.types.SpaceView3D.draw_handler_add(draw_group_poses_VIEW3D, (pose, batches, active.M3.group_pose_alpha, ), 'WINDOW', 'POST_VIEW')

        elif groupposesVIEW3D:
            if debug:
                print("   removing VIEW3D handler because there's no active, or drawing is disabled")

            bpy.types.SpaceView3D.draw_handler_remove(groupposesVIEW3D, 'WINDOW')
            groupposesVIEW3D = None

grouprelationsVIEW3D = None
prev_relation_states = None

def manage_group_relations_VIEW3D():
    global global_debug, grouprelationsVIEW3D, prev_relation_states

    debug = global_debug
    debug = False

    C = bpy.context
    scene = getattr(C, 'scene', None)

    if scene:
        m3 = scene.M3

        if debug:
            print()
            print("  group relations VIEW3D")

        if grouprelationsVIEW3D and "RNA_HANDLE_REMOVED" in str(grouprelationsVIEW3D):
            grouprelationsVIEW3D = None

        active = active if (active := get_active_object(C)) and active.M3.is_group_empty else None

        if m3.draw_group_relations_active_only:
            other_groups = []

        else:
            other_groups = [obj for obj in get_view_layer_objects(C) if obj.M3.is_group_empty and obj != active]

        if m3.draw_group_relations and (active or other_groups):
            if debug:
                print("   active group present:", bool(active))
                print("   other groups present:", bool(other_groups))

            states = [
                m3.draw_group_relations_active_only,
                m3.draw_group_relations_objects,
                (active, active.parent, *active.children, active.matrix_world.to_translation(), *[(c.matrix_world.to_translation(), c.visible_get()) for c in active.children if not c.M3.is_group_empty and c.M3.is_group_object]) if active else None,
                *[(obj, obj.visible_get(), obj.parent, *obj.children, obj.matrix_world.to_translation(), *[(c.matrix_world.to_translation(), c.visible_get()) for c in obj.children if not c.M3.is_group_empty and c.M3.is_group_object]) for obj in other_groups]
            ]

            if states != prev_relation_states:
                if debug:
                    print("    states have changed:")

                prev_relation_states = states

                if grouprelationsVIEW3D:
                    if debug:
                        print("     removing previous draw handler")

                    bpy.types.SpaceView3D.draw_handler_remove(grouprelationsVIEW3D, 'WINDOW')

                if debug:
                    print("    adding new draw handler")

                grouprelationsVIEW3D = bpy.types.SpaceView3D.draw_handler_add(draw_group_relations_VIEW3D, (C, *get_group_relation_coords(C, active, other_groups)), 'WINDOW', 'POST_VIEW')

        elif grouprelationsVIEW3D:
            bpy.types.SpaceView3D.draw_handler_remove(grouprelationsVIEW3D, 'WINDOW')

            if debug:
                print("   removing old draw handler")

            grouprelationsVIEW3D = None
            prev_relation_states = None

        if m3.draw_group_relations and C.workspace.get('outliner_group_mode_toggle', None):

            groups = [obj for obj in C.selected_objects if obj.M3.is_group_empty]

            for group in groups:
                if group.parent and group.parent.M3.is_group_empty and not group.M3.is_group_object:
                    group.M3.is_group_object = True
                    print(f"INFO: {group.name} is now a group object, because it was manually parented to {group.parent.name}")

                elif group.M3.is_group_object and (not group.parent or group.parent and not group.parent.M3.is_group_empty):
                    group.M3.is_group_object = False

                    if group.parent:
                        print(f"INFO: {group.name} is no longer a group object, because it's parent {group.parent.name} is not a group empty")

                    else:
                        print(f"INFO: {group.name} is no longer a group object, because it doesn't have any parent")

            if len(groups) == 1 and (active := C.active_object) and active not in groups and active.M3.is_group_empty:
                C.view_layer.objects.active = groups[0]
                print(f"INFO: Made {groups[0].name} the active group")

def manage_lights_decrease_and_visibility_sync():
    global global_debug

    debug = global_debug

    if debug:
        print("  light decrease and visibility sync")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        m3 = scene.M3
        p = get_prefs()

        if p.activate_render and p.activate_shading_pie and p.render_adjust_lights_on_render and get_area_light_poll() and m3.adjust_lights_on_render:
            if scene.render.engine == 'CYCLES':
                last = m3.adjust_lights_on_render_last
                divider = m3.adjust_lights_on_render_divider

                if last in ['NONE', 'INCREASE'] and divider > 1:
                    if debug:
                        print("   decreasing lights for cycles when starting render")

                    m3.adjust_lights_on_render_last = 'DECREASE'
                    m3.is_light_decreased_by_handler = True

                    adjust_lights_for_rendering(mode='DECREASE', debug=debug)

        if p.activate_render and p.render_sync_light_visibility:
            if debug:
                print("   light visibility syncing")

            sync_light_visibility(scene)

def manage_lights_increase():
    global global_debug

    debug = global_debug

    if debug:
        print("  light increase")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        m3 = scene.M3
        p = get_prefs()

        if p.activate_render and p.activate_shading_pie and p.render_adjust_lights_on_render and get_area_light_poll() and m3.adjust_lights_on_render:
            if scene.render.engine == 'CYCLES':
                last = m3.adjust_lights_on_render_last

                if last == 'DECREASE' and m3.is_light_decreased_by_handler:
                    if debug:
                        print("   increasing lights for cycles when finshing/aborting render")

                    m3.adjust_lights_on_render_last = 'INCREASE'
                    m3.is_light_decreased_by_handler = False

                    adjust_lights_for_rendering(mode='INCREASE', debug=debug)

def pre_undo_save():
    global global_debug

    debug = global_debug

    if debug:
        print("  undo save")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        m3 = scene.M3

        if m3.use_undo_save:
            global last_active_operator

            C = bpy.context

            if debug:
                print("   active operator:", C.active_operator)

            first_redo = False

            if m3.use_redo_save and C.active_operator:
                if last_active_operator != C.active_operator:
                    last_active_operator = C.active_operator
                    first_redo = True

            if C.active_operator is None or first_redo:
                temp_dir = get_temp_dir(bpy.context)

                if temp_dir:
                    if debug:
                        if first_redo:
                            print("    saving before first redo")
                        else:
                            print("    saving before undoing")

                    filepath = bpy.data.filepath

                    if filepath:
                        filename = os.path.basename(filepath)
                    else:
                        filename = "startup.blend"

                    name, ext = os.path.splitext(filename)
                    filepath = os.path.join(temp_dir, name + '_undosave' + ext)

                    if debug:
                        print("     to temp folder:", filepath)

                    if debug:
                        start = time()

                    bpy.ops.wm.save_as_mainfile(filepath=filepath, check_existing=True, copy=True, compress=True)

                    if debug:
                        print("     save time:", time() - start)

assemblyeditHUD = None

def manage_assembly_edit_HUD():
    global global_debug, assemblyeditHUD

    debug = global_debug
    debug = False

    scene = getattr(bpy.context, 'scene', None)

    if scene:

        if debug:
            print("  asset browser edit scene HUD")

        if assemblyeditHUD and "RNA_HANDLE_REMOVED" in str(assemblyeditHUD):
            assemblyeditHUD = None

        if scene.M3.is_assembly_edit_scene:
            if not assemblyeditHUD:
                if debug:
                    print("   adding new draw handler")

                assemblyeditHUD = bpy.types.SpaceView3D.draw_handler_add(draw_assembly_edit_HUD, (bpy.context, (1, 0, 0), 0.3, 4), 'WINDOW', 'POST_PIXEL')

        elif assemblyeditHUD:
            if debug:
                print("   removing old draw handler")

            bpy.types.SpaceView3D.draw_handler_remove(assemblyeditHUD, 'WINDOW')
            assemblyeditHUD = None

def manage_assetbrowser_bookmarks():
    global global_debug

    debug = global_debug

    if debug:
        print("  assetbrowser bookmarks")

    validate_assetbrowser_bookmarks()

def fix_empty_display_type():
    global global_debug

    debug = global_debug

    if debug:
        print("  fix empty display types")

        empty_display_type = [obj for obj in get_visible_objects(bpy.context) if not obj.display_type]

        for obj in empty_display_type:
            display_type = 'WIRE' if obj.hide_render or not obj.visible_camera else 'TEXTURED'
            obj.display_type = display_type
            print(f"INFO: Restored {obj.name}'s display type to {display_type}")

@persistent
def load_post(none):
    global global_debug

    if global_debug:
        print()
        print("MACHIN3tools load post handler:")
        print(" reloading msgbus")

    p = get_prefs()

    if p.activate_group_tools or p.activate_tools_pie or p.activate_assetbrowser_tools:
        reload_msgbus()

    if p.activate_group_tools:
        if global_debug:
            print(" managing legacy group poses")

        delay_execution(manage_legacy_group_poses)

    if p.activate_assetbrowser_tools:
        if global_debug:
            print(" managing assetbrowser bookmarks")

        delay_execution(manage_assetbrowser_bookmarks)

    if p.activate_shading_pie:
        if global_debug:
            print(" fix empty display_types")

        delay_execution(fix_empty_display_type)

last_active_operator = None

@persistent
def undo_pre(scene):
    global global_debug

    if global_debug:
        print()
        print("MACHIN3tools undo pre handler:")

    p = get_prefs()

    if p.activate_save_pie and p.save_pie_use_undo_save:
        if global_debug:
            print(" managing pre undo save")

        delay_execution(pre_undo_save)

@persistent
def render_start(scene):
    global global_debug

    if global_debug:
        print()
        print("MACHIN3tools render start handler:")

    p = get_prefs()

    if p.activate_render and (p.render_adjust_lights_on_render or p.render_enforce_hide_render):
        if global_debug:
            print(" managing light decrease and light visibility sync")

        delay_execution(manage_lights_decrease_and_visibility_sync)

@persistent
def render_end(scene):
    global global_debug

    if global_debug:
        print()
        print("MACHIN3tools render cancel or complete handler:")

    p = get_prefs()

    if p.activate_render and p.render_adjust_lights_on_render:
        if global_debug:
            print(" managing light increase")

        delay_execution(manage_lights_increase)

@persistent
def depsgraph_update_post(scene):
    global global_debug

    if global_debug:
        print()
        print("MACHIN3tools depsgraph update post handler:")

    p = get_prefs()

    if p.activate_shading_pie:
        if global_debug:
            print(" managing axes HUD")

        delay_execution(manage_axes_VIEW3D)

    if p.activate_focus:
        if global_debug:
            print(" managing focus HUD")

        delay_execution(manage_focus_HUD)

    if p.activate_assetbrowser_tools:
        if global_debug:
            print(" managing assembly edit HUD")

        delay_execution(manage_assembly_edit_HUD)

    if p.activate_surface_slide:
        if global_debug:
            print(" managing surface slide HUD")

        delay_execution(manage_surface_slide_HUD)

    if p.activate_save_pie and p.show_screencast:
        if global_debug:
            print(" managing screen cast HUD")

        delay_execution(manage_screen_cast_HUD)

    if p.activate_group_tools:
        if global_debug:
            print(" managing group")

        delay_execution(manage_group)

        if global_debug:
            print(" managing group poses VIEW3D")

        delay_execution(manage_group_poses_VIEW3D)

        if global_debug:
            print(" managing group relations VIEW3D")

        delay_execution(manage_group_relations_VIEW3D)
