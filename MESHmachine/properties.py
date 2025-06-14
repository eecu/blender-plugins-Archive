import bpy
from bpy.props import StringProperty, IntProperty, PointerProperty, BoolProperty, CollectionProperty, FloatVectorProperty, EnumProperty
from mathutils import Matrix
from . utils.math import flatten_matrix
from . items import align_mode_items

class PlugLibsCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    isvisible: BoolProperty(default=True, description="Show in MESHmachine Menu")
    islocked: BoolProperty(default=False, description="Prevent Plug Creation. Requires Library Reload")

class PlugEmptiesCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    location: FloatVectorProperty(name="Location")

class PlugScalesCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    scale: FloatVectorProperty(name="Scale")
    empties: CollectionProperty(type=PlugEmptiesCollection)

class StashCollection(bpy.types.PropertyGroup):
    def update_name(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.obj:
            if self.name:
                self.obj.MM.stashname = self.name

            else:
                self.avoid_update = True
                self.name = f"stash_{self.index}"
                self.obj.MM.stashname = ''

    name: StringProperty(update=update_name)
    index: IntProperty()

    version: StringProperty(name="stash version", default='0.0.0')
    uuid: StringProperty(name="stash uuid")
    obj: PointerProperty(name="Stash Object", type=bpy.types.Object)

    self_stash: BoolProperty(name="Self Stash", default=False)
    flipped: BoolProperty(name="Flipped Normals", default=False)
    mark_delete: BoolProperty(default=False)
    avoid_update: BoolProperty()

class MeshSceneProperties(bpy.types.PropertyGroup):
    debug: BoolProperty(default=False)
    register_panel_help: BoolProperty(default=True)
    align_mode: EnumProperty(name="Align Mode", items=align_mode_items, default="RAYCAST", description="Insert Plug at Mouse or Cursor position")
    plugscales: CollectionProperty(type=PlugScalesCollection)

    def update_active_stash_drawing_batch(self, context):
        if self.draw_active_stash:
            from . import handlers
            handlers.oldstashuuid = None

    draw_active_stash: BoolProperty(name="Draw Active Stash in 3D View", default=False, update=update_active_stash_drawing_batch)
    draw_active_stash_xray: BoolProperty(name="Draw Active Stash in X-Ray", default=False, update=update_active_stash_drawing_batch)
    revision: StringProperty()

class MeshObjectProperties(bpy.types.PropertyGroup):

    stashes: CollectionProperty(type=StashCollection)
    active_stash_idx: IntProperty()

    stashuuid: StringProperty(name="stash uuid")
    isstashobj: BoolProperty(name="is stash object", default=False)
    stashdeltamx: FloatVectorProperty(name="Delta Matrix", subtype="MATRIX", size=16, default=flatten_matrix(Matrix()))
    stashorphanmx: FloatVectorProperty(name="Orphan Matrix", subtype="MATRIX", size=16, default=flatten_matrix(Matrix()))
    stashname: StringProperty(name="stash name")

    stashmx: FloatVectorProperty(name="Stash Matrix", subtype="MATRIX", size=16, default=flatten_matrix(Matrix()))
    stashtargetmx: FloatVectorProperty(name="Target Matrix", subtype="MATRIX", size=16, default=flatten_matrix(Matrix()))

    uuid: StringProperty(name="plug uuid")
    isplug: BoolProperty(name="is plug", default=False)
    isplughandle: BoolProperty(name="is plug handle", default=False)
    isplugdeformer: BoolProperty(name="is plug deformer", default=False)
    isplugsubset: BoolProperty(name="is plug subset", default=False)
    isplugoccluder: BoolProperty(name="is plug occluder", default=False)
    hasfillet: BoolProperty(name="has fillet", default=False)
    deformerprecision: IntProperty(name="Deformer Precision", default=4)
    usedeformer: BoolProperty(name="Use Deformer", default=False)
    forcesubsetdeform: BoolProperty(name="Force Subset Deform", default=False)
    plugcreator: StringProperty(name="Plug Creator")

    dup_hash: StringProperty(description="Hash to find associated duplicate, after running bpy.ops.object.duplicate()")
