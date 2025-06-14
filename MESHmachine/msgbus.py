import bpy

def active_object_change():
    if bpy.context.scene.MM.draw_active_stash:
        wm = bpy.context.window_manager
        lastop = wm.operators[-1] if wm.operators else None

        if not (lastop and lastop.bl_idname == 'MACHIN3_OT_swap_stash'):
            bpy.context.scene.MM.draw_active_stash = False
