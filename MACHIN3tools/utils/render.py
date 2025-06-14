from typing import Tuple
import bpy
import os
from . view import get_shading_type
from . world import get_world_output

def get_render_engine(context):
    return context.scene.render.engine

def set_render_engine(context, engine):
    context.scene.render.engine = engine

def is_eevee(context):
    return context.scene.render.engine in ['BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT']

def is_eevee_view(context):
    return (shading_type := get_shading_type(context)) == 'MATERIAL' or (shading_type == 'RENDERED' and is_eevee(context))

def set_eevee(context):
    context.scene.render.engine = 'BLENDER_EEVEE_NEXT'

def get_user_presets():
    path = os.path.join(bpy.utils.user_resource('SCRIPTS'), 'presets', 'eevee', 'raytracing')

    if os.path.exists(path):
        return [f[:-3] for f in sorted(os.listdir(path)) if f.endswith('.py')]

def is_cycles(context):
    return context.scene.render.engine == 'CYCLES'

def is_cycles_view(context):
    return get_shading_type(context) == 'RENDERED' and is_cycles(context)

def set_cycles(context):
    context.scene.render.engine = 'CYCLES'

def get_device(context):
    return context.scene.cycles.device

def set_device(context, device='GPU'):
    context.scene.cycles.device = device

def is_volume(context, simple=True, debug=False) -> Tuple[bool, dict]:
    view = context.space_data
    shading = view.shading

    use_world = (shading.type == 'MATERIAL' and shading.use_scene_world) or (shading.type == 'RENDERED' and shading.use_scene_world_render)
    output = get_world_output(context.scene.world) if context.scene.world else None
    has_world_volume = bool(output.inputs[1].links) if output else False
    is_world_volume_muted = output.inputs[1].links[0].from_node.mute if has_world_volume else False

    is_world_volume = use_world and has_world_volume and not is_world_volume_muted

    if debug:
        print("\nworld")
        print("        use world:", use_world)
        print(" has world volume:", has_world_volume)
        print("         is muted:", is_world_volume_muted)
        print("  is world volume:", is_world_volume)

    volume_objects = [obj for obj in context.view_layer.objects if obj.type == 'VOLUME' if not obj.hide_get()]

    has_object_volume = bool(volume_objects)
    is_object_volume = view.show_object_viewport_volume and has_object_volume

    if debug:
        print("\nobjects")
        print(" volume objects:", volume_objects)
        print(" has object volume:", has_object_volume)
        print(" is object volume:", is_object_volume)

    is_volume = is_world_volume or is_object_volume

    if debug:
        print("\nis volume:", is_volume)

    if simple:
        return is_volume

    else:
        data = {'is_volume': is_volume,

                'is_world_volume': is_world_volume,
                'is_object_volume': is_object_volume,

                'use_world': shading.type if use_world else False,
                'world_volume': output.inputs[1].links[0].from_node if has_world_volume else None,

                'show_volume': view.show_object_viewport_volume,
                'volume_objects': volume_objects}

        return data
