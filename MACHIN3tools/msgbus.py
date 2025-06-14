import bpy

from . utils import registration as r
from . utils.application import is_context_safe
from . utils.group import set_unique_group_name

def object_name_change(context):
    if is_context_safe(context):
        active = context.active_object#

        if active:

            if active.M3.is_group_empty and r.get_prefs().group_tools_auto_name:
                set_unique_group_name(active)

def group_color_change(context):
    if is_context_safe(context):
        active = context.active_object

        if active and active.M3.is_group_empty:
            objects = [obj for obj in active.children if obj.M3.is_group_object and not obj.M3.is_group_empty]

            for obj in objects:
                obj.color = active.color

def gp_annotation_tint_change(context):
    if is_context_safe(context):
        active = context.active_object

        gp = active if active and active.type == 'GREASEPENCIL' else None

        if gp:
            tint_color = gp.data.layers.active.tint_color

            active.color = (*tint_color, 1)

            mat = active.data.materials.get('NoteMaterial')
            if mat:
                mat.grease_pencil.color = (*tint_color, 1)

def asset_empty_display_size_change(context):
    if is_context_safe(context):
        active = context.active_object

        if active and not active.M3.is_group_empty:

            from . utils.object import is_instance_collection

            icol = active.instance_collection

            instances = [obj for obj in bpy.data.objects if obj != active and not obj.library and (col := is_instance_collection(obj)) and col == icol]

            for obj in instances:
                obj.empty_display_size = active.empty_display_size
