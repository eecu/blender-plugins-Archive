import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix
from uuid import uuid4
from . utils.application import delay_execution
from . utils.draw import draw_stashes_HUD, draw_stashes_VIEW3D
from . utils.math import flatten_matrix
from . utils.mesh import get_coords
from . utils.object import get_active_object, get_visible_objects
from . utils.stash import get_version_as_tuple
from . utils.registration import reload_msgbus
from . import bl_info

global_debug = False

stashesHUD = None
oldactive = None
oldstasheslen = 0
oldinvalidstasheslen = 0

def manage_stashes_HUD():
    global global_debug, stashesHUD, oldactive, oldstasheslen, oldinvalidstasheslen

    debug = global_debug
    debug = False

    if debug:
        print("  stashes HUD")

    if stashesHUD and "RNA_HANDLE_REMOVED" in str(stashesHUD):
        stashesHUD = None

    active = get_active_object(bpy.context)

    if active:
        stasheslen = len(active.MM.stashes)
        invalidstasheslen = len([stash for stash in active.MM.stashes if not stash.obj])

        if not stashesHUD:
            oldactive = active
            oldstasheslen = stasheslen
            oldinvalidstasheslen = invalidstasheslen

            if debug:
                print("   adding HUD handler")

            stashesHUD = bpy.types.SpaceView3D.draw_handler_add(draw_stashes_HUD, (bpy.context, stasheslen, invalidstasheslen), 'WINDOW', 'POST_PIXEL')

        if active != oldactive or stasheslen != oldstasheslen or invalidstasheslen != oldinvalidstasheslen:
            oldactive = active
            oldstasheslen = stasheslen
            oldinvalidstasheslen = invalidstasheslen

            if debug:
                print("   re-creating HUD handler because active, number of (invalid) stashes have changed")

            bpy.types.SpaceView3D.draw_handler_remove(stashesHUD, 'WINDOW')
            stashesHUD = bpy.types.SpaceView3D.draw_handler_add(draw_stashes_HUD, (bpy.context, stasheslen, invalidstasheslen), 'WINDOW', 'POST_PIXEL')

    elif stashesHUD:
        if debug:
            print("   removing HUD handler because there's no active")

        bpy.types.SpaceView3D.draw_handler_remove(stashesHUD, 'WINDOW')
        stashesHUD = None

stashesVIEW3D = None
oldstashuuid = None

def manage_stashes_VIEW3D():
    global global_debug, stashesVIEW3D, oldstashuuid

    debug = global_debug
    debug = False

    if debug:
        print("  stashes VIEW3D")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        if stashesVIEW3D and "RNA_HANDLE_REMOVED" in str(stashesVIEW3D):
            stashesVIEW3D = None

        active = active if (active := get_active_object(bpy.context)) and active.MM.stashes else None
        stash = active.MM.stashes[active.MM.active_stash_idx] if active and active.MM.stashes[active.MM.active_stash_idx].obj else None

        if scene.MM.draw_active_stash and stash:
            if not stashesVIEW3D:
                oldstashuuid = stash.uuid

                if debug:
                    print("   adding VIEW3D handler")

                batch = get_coords(stash.obj.data, mx=active.matrix_world, offset=0.002, indices=True)
                stashesVIEW3D = bpy.types.SpaceView3D.draw_handler_add(draw_stashes_VIEW3D, (scene, batch, ), 'WINDOW', 'POST_VIEW')

            if oldstashuuid != stash.uuid:
                oldstashuuid = stash.uuid

                if debug:
                    print("   re-creating VIEW3D handler because stash has changed")

                batch = get_coords(stash.obj.data, mx=active.matrix_world, offset=0.002, indices=True)
                bpy.types.SpaceView3D.draw_handler_remove(stashesVIEW3D, 'WINDOW')
                stashesVIEW3D = bpy.types.SpaceView3D.draw_handler_add(draw_stashes_VIEW3D, (scene, batch, ), 'WINDOW', 'POST_VIEW')

        elif stashesVIEW3D:
            if debug:
                print("   removing VIEW3D handler because there's no active, no stashes, no stash obj or drawing is disabled")

            bpy.types.SpaceView3D.draw_handler_remove(stashesVIEW3D, 'WINDOW')
            stashesVIEW3D = None

was_asset_drop_cleanup_executed = False

def manage_asset_drop_cleanup():
    global global_debug, was_asset_drop_cleanup_executed

    debug = global_debug
    debug = False

    if debug:
        print("  MM asset drop management")

    if was_asset_drop_cleanup_executed:
        if debug:
            print("   skipping second (duplicate) run")

        was_asset_drop_cleanup_executed = False
        return

    if debug:
        print("   checking for asset drop cleanup")

    C = bpy.context

    if C.mode == 'OBJECT':
        operators = C.window_manager.operators
        active = active if (active := get_active_object(C)) and active.type == 'EMPTY' and active.instance_collection and active.instance_type == 'COLLECTION' else None

        if active and operators:
            lastop = operators[-1]

            if lastop.bl_idname == 'OBJECT_OT_transform_to_mouse':
                if debug:
                    print()
                    print("    asset drop detected!")

                visible = get_visible_objects(C)

                for obj in visible:
                    if obj.MM.isstashobj:
                        if debug:
                            print("     stash object:", obj.name)

                        for col in obj.users_collection:
                            if debug:
                                print(f"      unlinking from {col.name}")

                            col.objects.unlink(obj)

            was_asset_drop_cleanup_executed = True

def manage_legacy_stashes():
    global global_debug

    debug = global_debug
    debug = False

    if debug:
        print("  update legacy stashes")

    scene = getattr(bpy.context, 'scene', None)

    if scene:
        objects = [obj for obj in bpy.data.objects if obj.MM.stashes]
        version = '.'.join([str(v) for v in bl_info['version']])

        revision = bl_info.get("revision")

        if revision and not scene.MM.revision:
            scene.MM.revision = revision

    for obj in objects:
        updateable = [stash for stash in obj.MM.stashes if get_version_as_tuple(stash.version) < (0, 7)]

        if updateable:
            if debug:
                print(f"   Updating {obj.name}'s stashes to version {version}")

            for stash in updateable:
                stash.version = version
                stash.uuid = str(uuid4())

                if stash.obj:
                    stash.obj.MM.stashuuid = stash.uuid

                    deltamx = stash.obj.MM.stashtargetmx.inverted_safe() @ stash.obj.MM.stashmx

                    if deltamx == Matrix():
                        stash.self_stash = True

                    stash.obj.MM.stashdeltamx = flatten_matrix(deltamx)
                    stash.obj.MM.stashorphanmx = flatten_matrix(stash.obj.MM.stashtargetmx)

                    stash.obj.MM.stashmx.identity()
                    stash.obj.MM.stashtargetmx.identity()

@persistent
def load_post(none):
    global global_debug

    if global_debug:
        print()
        print("MESHmachine load post handler:")
        print(" reloading msgbus")

    reload_msgbus()

    if global_debug:
        print(" managing legacy stash update")

    delay_execution(manage_legacy_stashes)

@persistent
def depsgraph_update_post(scene):
    global global_debug

    if global_debug:
        print()
        print("MESHmachine depsgraph update post handler:")

    if global_debug:
        print(" managing stashes HUD")

    delay_execution(manage_stashes_HUD)

    if global_debug:
        print(" managing stashes VIEW3D")

    delay_execution(manage_stashes_VIEW3D)

    if global_debug:
        print(" managing asset drop cleanup")

    delay_execution(manage_asset_drop_cleanup)
