import bpy
import bmesh

from . bmesh import get_tri_coords

from . object import remove_obj
from . raycast import cast_scene_ray_from_mouse
from . view import is_local_view

from .. items import snap_element_items

class Snap:
    def log(self, *args, **kwargs):
        if self.debug:
            print(*args, **kwargs)

    debug = False

    depsgraph = None
    cache = None

    exclude = []
    exclude_wire = False
    alternative = []

    hit = None
    hitobj = None
    hitindex = None
    hitlocation = None
    hitnormal = None
    hitmx = None

    name = None
    hitface = None

    _edit_mesh_objs = []
    _modifiers = []

    def __init__(self, context, include=None, exclude=None, exclude_wire=False, force_exclude_wire=False, alternative=None, modifier_toggles=None, debug=False):
        self.debug = debug
        self.context = context

        self.log("\nInitialize Snapping")

        self._init_edit_mode()

        self._init_exclude(include, exclude, exclude_wire, force_exclude_wire)

        self._init_alternatives(alternative)

        self._init_modifier_toggles(modifier_toggles)

        self.depsgraph = context.evaluated_depsgraph_get()
        self.cache = SnapCache(debug=debug)

        self.hitface = None

        self.log()

    def finish(self):
        self.log("\nFinish Snapping")

        if self._modifiers:
            self._enable_modifiers()

        self._remove_alternatives()

        if self._toggled_modifiers:
            for mod, hostobj, modobj in self._toggled_modifiers:
                self.log(f"re-enabling {mod.name} ({mod.type}) modifier of {hostobj.name}")

                if mod.type == 'BOOLEAN' and not mod.object:
                    mod.object = modobj

                mod.show_viewport = True

            if self.context.active_object:
                if self.context.active_object.display_type != self._display_type:
                    self.log(f"restoring {self.context.active_object.name}'s display_type to {self._display_type}")
                    self.context.active_object.display_type = self._display_type

        self.cache.clear()

    def _init_edit_mode(self):
        if self.context.mode == 'EDIT_MESH':
            self._update_meshes()
            self._disable_modifiers()

    def _init_exclude(self, include, exclude, exclude_wire, force_exclude_wire):
        if include:
            self.exclude = [obj for obj in self.context.visible_objects if obj not in include]

        elif exclude:
            self.exclude = exclude

        else:
            self.exclude = []

        if is_local_view():
            hidden = [obj for obj in self.context.view_layer.objects if not obj.visible_get()]
            self.exclude += hidden

        self.exclude_wire = exclude_wire
        self.force_exclude_wire = force_exclude_wire

    def _init_alternatives(self, alternative):
        self.alternative = []

        if alternative:
            for obj in alternative:
                if obj not in self.exclude:
                    self.exclude.append(obj)

                dup = obj.copy()
                dup.data = obj.data.copy()
                self.context.scene.collection.objects.link(dup)
                dup.hide_set(True)

                self.alternative.append(dup)

                self.log(f" Created alternative object {dup.name} for {obj.name}")

    def _init_modifier_toggles(self, modifier_types):
        self._toggled_modifiers = []
        self._display_type = self.context.active_object.display_type if self.context.active_object else 'WIRE'

        if modifier_types:
            boolean_union = False

            for modtype in modifier_types:
                if modtype == 'BOOLEAN':
                    mods = [(mod, hostobj, mod.object if mod.type == 'BOOLEAN' else None) for hostobj in self.context.visible_objects for mod in hostobj.modifiers if mod.type == modtype and mod.object == self.context.active_object and mod.show_viewport]
                    boolean_union = any([mod.operation == 'UNION' for mod, _, _ in mods])

                    self._toggled_modifiers.extend(mods)

            if self.debug:
                print("boolean union?:", boolean_union)

        if self._toggled_modifiers:

            for mod, hostobj, _ in self._toggled_modifiers:
                self.log(f"disabling {mod.name} ({mod.type}) modifier of {hostobj.name}")
                mod.show_viewport = False

                if mod.type == 'BOOLEAN':
                    mod.object = None

            if 'BOOLEAN' in modifier_types and boolean_union and self._display_type in ['WIRE', 'BOUNDS']:
                self.log(f"changing {self.context.active_object.name}'s display_type, as its union boolean was temporarily disabled")

                if self.context.active_object:
                    self.context.active_object.display_type = 'TEXTURED'

    def _remove_alternatives(self):
        for obj in self.alternative:
            self.log(f" Removing alternave object {obj.name}")
            remove_obj(obj)

    def _update_meshes(self):
        self._edit_mesh_objs = [obj for obj in self.context.visible_objects if obj.mode == 'EDIT']

        for obj in self._edit_mesh_objs:
            obj.update_from_editmode()

    def _disable_modifiers(self):
        self._modifiers = [(obj, mod) for obj in self._edit_mesh_objs for mod in obj.modifiers if mod.show_viewport]

        for obj, mod in self._modifiers:
            self.log(f" Disabling {obj.name}'s {mod.name}")

            if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith('Smooth by Angle'):
                continue

            mod.show_viewport = False

    def _enable_modifiers(self):
        for obj, mod in self._modifiers:
            self.log(f" Re-enabling {obj.name}'s {mod.name}")

            if mod.type == 'NODES' and mod.node_group and mod.node_group.name.startswith('Smooth by Angle'):
                continue

            mod.show_viewport = True

    def _init_cache(self, obj):
        name = obj.name

        self.cache.objects[name] = obj

        mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(self.depsgraph), depsgraph=self.depsgraph)
        self.cache.meshes[name] = mesh

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        self.cache.bmeshes[name] = bm

        self.cache.loop_triangles[name] = bm.calc_loop_triangles()
        self.cache.tri_coords[name] = {}

    def get_hit(self, mousepos):
        self.hit, self.hitobj, self.hitindex, self.hitlocation, self.hitnormal, self.hitmx = cast_scene_ray_from_mouse(mousepos, self.depsgraph, exclude=self.exclude, exclude_wire=self.exclude_wire, force_exclude_wire=self.force_exclude_wire, unhide=self.alternative, cache=self.cache.hittable, debug=self.debug)

        if self.hit:
            name = self.hitobj.name

            if name not in self.cache.objects:
                self._init_cache(self.hitobj)

            if self.hitface is None or self.hitface.index != self.hitindex or name != self.name:
                self.log("Hitface changed to", self.hitindex)

                self.hitface = self.cache.bmeshes[name].faces[self.hitindex]

            if self.hitindex not in self.cache.tri_coords[name]:
                self.log("Adding tri coords for face index", self.hitindex)

                loop_triangles = self.cache.loop_triangles[name]
                tri_coords = get_tri_coords(loop_triangles, [self.hitface], mx=self.hitmx)

                self.cache.tri_coords[name][self.hitindex] = tri_coords

            self.name = name

class SnapCache:
    def log(self, *args, **kwargs):
        if self.debug:
            print(*args, **kwargs)

    debug = False

    hittable = {}

    objects = {}
    meshes = {}

    bmeshes = {}

    loop_triangles = {}
    tri_coords = {}

    def __init__(self, debug=False):
        self.debug = debug
        self.log(" Initialize SnappingCache")

        self.hittable = {}

        self.objects = {}
        self.meshes = {}

        self.bmeshes = {}

        self.loop_triangles = {}
        self.tri_coords = {}

    def clear(self):
        for name, mesh in self.meshes.items():
            self.log(f" Removing {name}'s temporary snapping mesh {mesh.name} with {len(mesh.polygons)} faces and {len(mesh.vertices)} verts")
            bpy.data.meshes.remove(mesh, do_unlink=True)

        for name, bm in self.bmeshes.items():
            self.log(f" Freeing {name}'s temporary snapping bmesh")
            bm.free()

        self.hittable.clear()

        self.objects.clear()
        self.meshes.clear()

        self.bmeshes.clear()

        self.loop_triangles.clear()
        self.tri_coords.clear()

def get_sorted_snap_elements(ts, pretty=True, title=True):
    sorted = []

    for item in snap_element_items:
        if item in ts.snap_elements:

            if item == 'FACE' and ts.use_snap_align_rotation:
                item = 'SURFACE'

            if pretty:
                item = item.replace('_', ' ')

            if title:
                item = item.title()

            sorted.append(item)
    return sorted
