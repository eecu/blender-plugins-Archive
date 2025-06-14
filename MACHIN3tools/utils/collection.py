import bpy

from . system import printd

from .. import MACHIN3toolsManager as M3

def get_groups_collection(scene):
    mcol = scene.collection

    gpcol = bpy.data.collections.get("Groups")

    if gpcol:
        if gpcol.name not in mcol.children:
            mcol.children.link(gpcol)

    else:
        gpcol = bpy.data.collections.new(name="Groups")
        mcol.children.link(gpcol)

    return gpcol

def get_assets_collection(context, name='_Assemblies', color_tag='COLOR_04', scene_collections=None, create=True, exclude=True, hide_viewport=None):
    if not scene_collections:
        scene_collections = get_scene_collections(context)

    asset_cols = [col for col in scene_collections if col.name.startswith(name)]

    if asset_cols:
        return asset_cols[0]

    elif create:
        acol = bpy.data.collections.new(name)
        acol.color_tag = color_tag
        context.scene.collection.children.link(acol)

        set_collection_visibility(context, acol, exclude=exclude, hide_viewport=hide_viewport)
        return acol

def set_collection_visibility(context, collection, exclude=None, hide_viewport=None):
    if exclude is not None or hide_viewport is not None:
        layer_col = context.view_layer.layer_collection.children.get(collection.name)

        if not layer_col:
            scene_collections = get_scene_collections(context)

            for col, data in scene_collections.items():
                if col == collection:
                    layer_col = data['layer_collections'][0]
                    break

        if layer_col:
            if exclude is not None:
                layer_col.exclude = exclude

            if hide_viewport is not None:
                layer_col.hide_viewport = hide_viewport

        else:
            print(f"WARNING: Could not set visibility for collection {collection.name}, as no layer collection could be found on the view layer")

def get_scene_collections(context, debug=False):
    layer_collections = []
    get_layer_collections_recursively(context.view_layer.layer_collection, layer_collections)

    collections = {}

    for lcol in layer_collections:
        if lcol.collection == context.scene.collection:
            continue

        if (col := lcol.collection) in collections:
            collections[col]['layer_collections'].append(lcol)

        else:
            collections[col] = {'layer_collections': [lcol]}

    for col, data in collections.items():

        data['excluded'] = all(lcol.exclude for lcol in data['layer_collections'])

        data['hidden'] = col.hide_viewport or all(lcol.hide_viewport for lcol in data['layer_collections'])

        data['visible'] = any(lcol.visible_get() for lcol in data['layer_collections'])

    if debug:
        printd(collections)

    return collections

def get_scene_collections_old(scene, ignore_decals=True):
    mcol = scene.collection

    scenecols = []
    seen = list(mcol.children)

    while seen:
        col = seen.pop(0)
        if col not in scenecols:
            if not (ignore_decals and M3.get_addon("DECALmachine") and (col.DM.isdecaltypecol or col.DM.isdecalparentcol)):
                scenecols.append(col)
        seen.extend(list(col.children))

    return scenecols

def get_collection_depth(self, collections, depth=0, init=False):
    if init or depth > self.depth:
        self.depth = depth

    for col in collections:
        if col.children:
            get_collection_depth(self, col.children, depth + 1, init=False)

    return self.depth

def get_layer_collections_recursively(lcol, layer_collections):
    layer_collections.append(lcol)

    for lc in lcol.children:
        get_layer_collections_recursively(lc, layer_collections)

def is_collection_visible(col):
    C = bpy.context

    if col == C.scene.collection:
        return True

    if col.hide_viewport:
        return False

    viewlayer = C.view_layer

    layer_collections = []
    get_layer_collections_recursively(viewlayer.layer_collection, layer_collections)

    instances = [lcol for lcol in layer_collections if lcol.collection == col]

    return any(lcol.visible_get() for lcol in instances)

def get_instance_collections_recursively(collections, col, depth=0):
    from . object import is_instance_collection

    if depth:
        if depth not in collections:
            collections[depth] = []

        collections[depth].append(col)

    for obj in col.objects:
        if icol := is_instance_collection(obj):
           get_instance_collections_recursively(collections, icol, depth + 1)

def get_active_collection(context):
    if layercol := context.view_layer.active_layer_collection:
        colname = layercol.name

        if colname:
            return bpy.data.collections.get(colname, None)

def copy_collection(collection):
    dup = bpy.data.collections.new(name=collection.name)

    dup.instance_offset = collection.instance_offset

    dup.hide_render = collection.hide_render
    dup.hide_viewport = collection.hide_viewport
    dup.hide_select = collection.hide_select

    dup.color_tag = collection.color_tag
    return dup

def duplicate_collection(collection, recursive=True, debug=False):
    def recursively_duplicate_collection(dup_map, collection):
        reverse_map = {data['original']: dup for dup, data in dup_map.items()}

        if collection in reverse_map:
            return reverse_map[collection]

        else:
            dup = copy_collection(collection)

            dup_map[dup] = {'original': collection, 'objects': [obj for obj in collection.objects]}

            for child in collection.children:
                dup_child = recursively_duplicate_collection(dup_map, child)

                dup.children.link(dup_child)

        return dup

    dup_map = {}

    dup = copy_collection(collection)

    dup_map[dup] = {'original': collection, 'objects': [obj for obj in collection.objects]}

    if recursive:
        for child_col in collection.children:
            dup_child = recursively_duplicate_collection(dup_map, child_col)
            dup.children.link(dup_child)

    if debug:
        printd(dup_map)

    return dup, dup_map

def get_collection_objects(collection):
    objects = set()
    sub_cols = set(collection.children_recursive)

    for col in {collection} | sub_cols:
        for obj in col.objects:
            objects.add(obj)

    return objects
