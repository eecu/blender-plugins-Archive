import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_location_3d, region_2d_to_origin_3d, region_2d_to_vector_3d

from mathutils import Matrix, Vector

from typing import Tuple, Union

from .. colors import green, red

def get_shading_type(context):
    return context.space_data.shading.type

def set_xray(context):
    x = (context.scene.M3.pass_through, context.scene.M3.show_edit_mesh_wire)
    shading = context.space_data.shading

    shading.show_xray = True if any(x) else False

    if context.scene.M3.show_edit_mesh_wire:
        shading.xray_alpha = 0.1

    elif context.scene.M3.pass_through:
        shading.xray_alpha = 1 if context.active_object and context.active_object.type == "MESH" else 0.5

def reset_xray(context):
    shading = context.space_data.shading

    shading.show_xray = False
    shading.xray_alpha = 0.5

def update_local_view(space_data, states):
    if space_data.local_view:
        for obj, local in states:
            if obj:
                obj.local_view_set(space_data, local)

def reset_viewport(context, disable_toolbar=False):
    for screen in context.workspace.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        r3d = space.region_3d

                        r3d.view_distance = 10
                        r3d.view_matrix = Matrix(((1, 0, 0, 0),
                                                  (0, 0.2, 1, -1),
                                                  (0, -1, 0.2, -10),
                                                  (0, 0, 0, 1)))

                        if disable_toolbar:
                            space.show_region_toolbar = False

def sync_light_visibility(scene):

    for view_layer in scene.view_layers:
        lights = [obj for obj in view_layer.objects if obj.type == 'LIGHT']

        for light in lights:
            hidden = light.hide_get(view_layer=view_layer)

            if light.hide_render != hidden:
                light.hide_render = hidden

def get_loc_2d(context, loc):
    loc_2d = location_3d_to_region_2d(context.region, context.region_data, loc)
    return loc_2d if loc_2d else Vector((-1000, -1000))

def get_view_origin_and_dir(context, coord=None) -> Tuple[Vector, Vector]:
    if not coord:
        coord = Vector((context.region.width / 2, context.region.height / 2))

    view_origin = region_2d_to_origin_3d(context.region, context.region_data, coord)
    view_dir = region_2d_to_vector_3d(context.region, context.region_data, coord)

    return view_origin, view_dir

def is_local_view():
    view = bpy.context.space_data

    if view and view.type == 'VIEW_3D':
        return bool(view.local_view)

def is_object_in_local_view(dg, obj):
    view = bpy.context.space_data

    if view and view.type == 'VIEW_3D':
        return bool(view.local_view) and obj.evaluated_get(dg).local_view_get(view)

def add_obj_to_local_view(obj:Union[bpy.types.Object, list, set]):
    view = bpy.context.space_data

    if view and view.type == 'VIEW_3D' and view.local_view:
        objects = obj if type(obj) in [list, set] else [obj]

        for obj in objects:
            obj.local_view_set(view, True)

def remove_obj_from_local_view(obj:Union[bpy.types.Object, list, set]):
    view = bpy.context.space_data

    if view and view.type == 'VIEW_3D' and view.local_view:
        objects = obj if type(obj) in [list, set] else [obj]

        for obj in objects:
            obj.local_view_set(view, False)

def visible_get(obj, depsgraph=None, ray_visibility=False, debug=False) -> dict:
    vis = {'visible': obj.visible_get(),

           'scene': is_obj_in_scene(obj),
           'viewlayer': is_obj_on_viewlayer(obj),
           'visible_collection': is_obj_in_visible_collection(obj),

           'local_view': None if not is_local_view() else is_object_in_local_view(depsgraph, obj) if depsgraph else False,   # None if local view is not used, otherwise check if obj is in local view IF the dg is passed in, otherwise set to False - the distinction beteed None and False is useful
           'hide': obj.hide_get(),                                                                                           # but could still be useful for debugging (when dg would be passed in)
           'hide_viewport': obj.hide_viewport,
           'hide_render': obj.hide_render,                                                                                   # NOTE: hide_render is only relevant for camera rendering, not for viewport rendering, nor basic viewport display

           'select': obj.select_get(),                                                                                       # get the selection state too actually, while at it, useful for restore_visibility()

           'meta': None}

    if ray_visibility:                                                                                                       # NOTE: ray visibility on the other hand, does affect viewport rendering, even eevee/material shading
        vis['visible_ray'] = {'visible_camera': obj.visible_camera,
                              'visible_diffuse': obj.visible_diffuse,
                              'visible_glossy': obj.visible_glossy,
                              'visible_transmission': obj.visible_transmission,
                              'visible_volume_scatter': obj.visible_volume_scatter,
                              'visible_shadow': obj.visible_shadow}

    if not vis['visible']:
        if vis['scene']:
            if vis['viewlayer']:
                if vis['visible_collection']:

                    if vis['local_view'] in [True, None]:

                        if not vis['hide_viewport']:

                            if vis['hide']:
                                vis['meta'] = 'HIDE'

                        else:
                            vis['meta'] = 'HIDE_VIEWPORT'

                    else:
                        vis['meta'] = 'LOCAL_VIEW'

                else:
                    vis['meta'] = 'HIDDEN_COLLECTION'

            else:
                vis['meta'] = 'VIEWLAYER'

        else:
            vis['meta'] = 'SCENE'

    if debug:
        print("", obj.name, "✔" if vis['visible'] else "❌", vis['meta'] if not vis['visible'] else '')

    return vis

def is_obj_in_scene(obj):
    return obj.name in bpy.context.scene.objects

def is_obj_on_viewlayer(obj):
    return obj.name in bpy.context.view_layer.objects

def is_obj_in_visible_collection(obj):
    from . collection import is_collection_visible
    return any(is_collection_visible(col) for col in obj.users_collection)

def ensure_visibility(context, obj: Union[bpy.types.Object, list[bpy.types.Object], set[bpy.types.Object]], scene=True, viewlayer=True, hidden_collection=True, local_view=True, unhide=True, unhide_viewport=True, select=False, debug=False):

    objects = obj if type(obj) in [list, set] else [obj]

    if debug:
        print()

        for obj in objects:
            vis = visible_get(obj, debug=False)
            print(obj.name, "✔" if vis['visible'] else "❌", vis['meta'] if not vis['visible'] else '')

    for obj in objects:

        is_in_scene = is_obj_in_scene(obj)
        is_on_viewlayer = is_obj_on_viewlayer(obj)
        is_in_visible_collection = is_obj_in_visible_collection(obj)

        if scene and not is_in_scene:
            context.scene.collection.objects.link(obj)
            obj.select_set(False)

            is_in_scene = True
            is_on_viewlayer = True
            is_in_visible_collection = True#

            if debug:
                print(" added", obj.name, "to scene")

        if viewlayer and is_in_scene and not is_on_viewlayer:
            context.scene.collection.objects.link(obj)
            obj.select_set(False)

            is_in_scene = True
            is_on_viewlayer = True
            is_in_visible_collection = True

            if debug:
                print(" added", obj.name, "to viewlayer")

        if hidden_collection and is_in_scene and is_on_viewlayer and not is_in_visible_collection:
            context.scene.collection.objects.link(obj)
            obj.select_set(False)

            is_in_scene = True
            is_on_viewlayer = True
            is_in_visible_collection = True

            if debug:
                print(" added", obj.name, "to visible collection")

        if local_view:
            add_obj_to_local_view(objects)

            if debug and is_local_view():
                print(" ensured", obj.name, "is in local view")

        if unhide:
            if obj.hide_get():
                obj.hide_set(False)

        if unhide_viewport:
            if obj.hide_viewport:
                obj.hide_viewport = False

        if select:
            if obj.visible_get():
                obj.select_set(True)

def restore_visibility(obj, data:dict):
    if is_obj_on_viewlayer(obj):

        if (state := data.get('select')) and state != obj.select_get():
            obj.select_set(state)

        if (state := data.get('hide')) and state != obj.hide_get():
            obj.hide_set(state)

    if (state := data.get('hide_viewport')) and state != obj.hide_viewport:
        obj.hide_viewport = state

    if is_local_view() and (state := data.get('local_view')) is not None:
        if state:
            remove_obj_from_local_view(obj)
        else:
            add_obj_to_local_view(obj)

    if (meta := data.get('meta')) and meta in ['SCENE', 'VIEWLAYER', 'HIDDEN_COLLECTION']:
        mcol = bpy.context.scene.collection

        if obj.name in mcol.objects:
            mcol.objects.unlink(obj)

def get_location_2d(context, co3d, default=(0, 0), debug=False):
    if default == 'OFF_SCREEN':
        default = Vector((-1000, -1000))
    co2d = Vector(round(i) for i in location_3d_to_region_2d(context.region, context.region_data, co3d, default=default))
    if debug:
        print(tuple(co3d), "is", tuple(co2d))

    return co2d

def get_view_bbox(context, bbox, margin=0, border_gap=0, debug=False):
    from . ui import get_scale

    scale = get_scale(context)
    gap = border_gap * scale

    coords = []

    for co in bbox:
        coords.append(get_location_2d(context, co, default=Vector((context.region.width / 2, context.region.height / 2))))
    xmin = round(min(context.region.width - gap, max(gap, min(coords, key=lambda x: x[0])[0] - margin)))
    xmax = round(min(context.region.width - gap, max(gap, max(coords, key=lambda x: x[0])[0] + margin)))

    ymin = round(min(context.region.height - gap, max(gap, min(coords, key=lambda x: x[1])[1] - margin)))
    ymax = round(min(context.region.height - gap, max(gap, max(coords, key=lambda x: x[1])[1] + margin)))

    bbox = [Vector((xmin, ymin)), Vector((xmax, ymin)), Vector((xmax, ymax)), Vector((xmin, ymax))]

    if debug:
        print(bbox)

        from . draw import draw_line

        line_coords = [co.resized(3) for co in bbox + [bbox[0]]]
        draw_line(line_coords, screen=True, modal=False)

    return bbox

def set_view_focal_point(location, context=None, space=None, region=None, debug=False):
    if debug:
        from . draw import draw_point

        draw_point(location, color=red, modal=False)

    if context and not (space and region):
        space = context.space_data
        region = context.region

    if space and region:

        r3d = space.region_3d
        r3d.update()

        try:
            center = Vector((region.width / 2, region.height / 2))
            focal_point = region_2d_to_location_3d(region, r3d, center, location)

            if debug:
                draw_point(focal_point, color=green, modal=False)

        except:
            focal_point = location

            if debug:
                draw_point(focal_point, color=red, modal=False)

        if debug:
            if context:
                context.area.tag_redraw()

            print("focal location:", r3d.view_location)
            print("view distance:", r3d.view_distance)

            print("view location:", r3d.view_matrix.decompose()[0])

        if r3d.view_perspective == 'ORTHO':
            r3d.view_location = focal_point

        elif r3d.view_perspective == 'PERSP':

            init_loc = r3d.view_matrix.decompose()[0]

            r3d.view_location = focal_point

            r3d.update()

            new_loc = r3d.view_matrix.decompose()[0]

            r3d.view_distance -= (init_loc - new_loc).length
