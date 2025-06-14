import bpy
from bpy.props import EnumProperty, BoolProperty

from mathutils import Vector

from .. utils.system import printd

from .. utils.draw import draw_fading_label, get_text_dimensions
from .. utils.modifier import get_mod_obj
from .. utils.object import get_object_hierarchy_layers, get_parent
from .. utils.registration import get_prefs
from .. utils.ui import get_mouse_pos
from .. utils.view import ensure_visibility, is_local_view, is_obj_in_scene, visible_get

from .. colors import yellow, red, green, white, normal, blue

axis_items = [("0", "X", ""),
              ("1", "Y", ""),
              ("2", "Z", "")]

class SelectCenterObjects(bpy.types.Operator):
    bl_idname = "machin3.select_center_objects"
    bl_label = "MACHIN3: Select Center Objects"
    bl_description = "Selects Objects in the Center, objects, that have verts on both sides of the X, Y or Z axis."
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(name="Axis", items=axis_items, default="0")
    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.prop(self, "axis", expand=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        visible = [obj for obj in context.visible_objects if obj.type == "MESH"]

        if visible:

            bpy.ops.object.select_all(action='DESELECT')

            for obj in visible:
                mx = obj.matrix_world

                coords = [(mx @ Vector(co))[int(self.axis)] for co in obj.bound_box]

                if min(coords) < 0 and max(coords) > 0:
                    obj.select_set(True)

        return {'FINISHED'}

class SelectWireObjects(bpy.types.Operator):
    bl_idname = "machin3.select_wire_objects"
    bl_label = "MACHIN3: Select Wire Objects"
    bl_description = "Select Objects set to WIRE display type\nALT: Hide Objects\nCLTR: Include Empties"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in context.visible_objects if obj.display_type in ['WIRE', 'BOUNDS'] or obj.type == 'EMPTY']

    def invoke(self, context, event):
        bpy.ops.object.select_all(action='DESELECT')

        for obj in context.visible_objects:
            if obj.display_type == '':
                obj.display_type = 'WIRE'

        if event.ctrl:
            objects = [obj for obj in context.visible_objects if obj.display_type in ['WIRE', 'BOUNDS'] or obj.type == 'EMPTY']
        else:
            objects = [obj for obj in context.visible_objects if obj.display_type in ['WIRE', 'BOUNDS']]

        for obj in objects:
            if event.alt:
                obj.hide_set(True)
            else:
                obj.select_set(True)

        return {'FINISHED'}

class SelectHierarchy(bpy.types.Operator):
    bl_idname = "machin3.select_hierarchy"
    bl_label = "MACHIN3: Select Hierarchy"
    bl_description = "Select Hierarchy Down"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(name="Hierarchy Direction", items=[('UP', 'Up', ''), ('DOWN', 'Down', '')], default='DOWN')
    include_selection: BoolProperty(name="Include Selection", description="Include Current Selection", default=False)
    include_mod_objects: BoolProperty(name="Include Mod Objects", description="Include Mod Objects, even if they aren't parented", default=False)
    recursive_down: BoolProperty(name="Select Recursive Children", description="Select Children Recursively", default=False)
    recursive_up: BoolProperty(name="Select Recursive Parents", description="Select Parents Recursively", default=False)
    localview: BoolProperty(name="LocalView", description="Bring Objects into Local View, if they are outside of it", default=True)
    unhide: BoolProperty(name="Unhide", description="Unhide Objects, if they are hidden", default=False)
    link: BoolProperty(name="Link", description="Bring Objects on View Layer, if they are in excluded collections or in hidden collections only", default=False)

    def update_all(self, context):
        if self.all:
            self.include_selection = False

            self.include_mod_objects = True
            self.recursive_down = True
            self.recursive_up = True

            self.localview = True
            self.unhide = True
            self.link = True

            self.all = False

    def update_all_inclusive(self, context):
        if self.all_inclusive:
            self.include_selection = True

            self.include_mod_objects = True
            self.recursive_down = True
            self.recursive_up = True

            self.localview = True
            self.unhide = True
            self.link = True

            self.all_inclusive = False

    all: BoolProperty(name="All", description="Use all Scope and Reveal Options to Select Everything", default=False, update=update_all)
    all_inclusive: BoolProperty(name="All Incl.", description="Use all Scope and Reveal Options to Select Everything including the initial Selection", default=False, update=update_all_inclusive)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return context.selected_objects

    def draw(self, context):
        layout = self.layout
        toggles = self.status['toggles']

        box = layout.box()
        box.label(text="Direction in Hierarchy")

        row = box.row(align=True)
        row.prop(self, "direction", expand=True)

        box = layout.box()
        box.label(text="Selection Scope")

        column = box.column(align=True)
        row = column.row(align=True)

        row.row(align=True)
        row.prop(self, 'include_selection', toggle=True)

        r = row.row(align=True)
        r.alert = 'RECURSIVE' in toggles
        r.prop(self, 'recursive_down' if self.direction == 'DOWN' else 'recursive_up', text="Recursive", toggle=True)

        if self.direction == 'DOWN':
            row = column.row(align=True)
            row.alert = 'MOD_OBJECTS' in toggles
            row.prop(self, 'include_mod_objects', toggle=True)

        box = layout.box()
        box.label(text="Reveal")

        column = box.column(align=True)
        row = column.row(align=True)

        if is_local_view():
            r = row.row(align=True)
            r.alert = 'LOCALVIEW' in toggles
            r.prop(self, 'localview', text="Local View", toggle=True)

        r = row.row(align=True)
        r.alert = 'UNHIDE' in toggles
        r.prop(self, 'unhide', text="Unhide", toggle=True)

        r = row.row(align=True)
        r.alert = 'LINK' in toggles
        r.prop(self, 'link', text="Link", toggle=True)

        if self.status['visible'] or self.status['hidden'] or self.status['toggles']:
            box = layout.box()

            row = box.row()
            row.label(text="Statistics")

            r = row.row(align=True)
            r.alignment = 'RIGHT'

            rr = r.row()
            rr.active = False
            rr.alignment = 'RIGHT'
            rr.label(text="Select ")

            r.prop(self, "all", toggle=True)
            r.prop(self, "all_inclusive", toggle=True)

            objtype = 'children' if self.direction == 'DOWN' else 'parents'

            column = box.column(align=True)

            if self.status['visible']:
                split = column.split(factor=0.42)

                row = split.row()
                row.alignment = 'RIGHT'
                row.active = False
                row.label(text=f"more visible {objtype}:")

                split.label(text=f"{self.status['visible']}")

            if self.status['hidden']:
                split = column.split(factor=0.42)

                row = split.row()
                row.alignment = 'RIGHT'
                row.active = False
                row.label(text=f"more hidden {objtype}:")

                split.label(text=f"{self.status['hidden']}")

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud=False)

        return self.execute(context)

    def execute(self, context):
        self.dg = context.evaluated_depsgraph_get()

        time = get_prefs().HUD_fade_select_hierarchy
        scale = context.preferences.system.ui_scale

        layers = get_object_hierarchy_layers(context, debug=False)

        self.status = self.select(context, context.selected_objects, layers, direction=self.direction)#

        type = self.status['type']
        visible_count = self.status['visible']
        hidden_count = self.status['hidden']
        toggles = self.status['toggles']

        coords = self.mouse_pos + Vector((0, 15))

        x = coords.x - 25 * scale
        y = coords.y + ((26 if self.direction == 'UP' else 8) * scale)

        text= "🔼" if self.direction == 'UP' else "🔽"
        draw_fading_label(context, text=text, x=x, y=y, center=False, size=12, time=time, alpha=0.25)

        if type in ['TOP', 'BOTTOM']:
            text = f"{type} "

            dims = Vector((x - get_text_dimensions(context, text).x, y))
            draw_fading_label(context, text=text, x=dims.x, y=dims.y, center=False, size=12, color=yellow, time=time)

        elif type in ['ABSOLUTE_TOP', 'ABSOLUTE_BOTTOM']:
            text = f"{type.replace('_', ' ')} "

            dims = Vector((x - get_text_dimensions(context, text).x, y))
            color = green if type == 'ABSOLUTE_TOP' else red
            draw_fading_label(context, text=text, x=dims.x, y=dims.y, center=False, size=12, color=color, time=time)

        x = coords.x
        y = coords.y + 16 * scale

        text = f"Selecting {self.direction.title()} "
        dims = get_text_dimensions(context, text)

        draw_fading_label(context, text=text, x=x, y=y, center=False, size=12, time=time)

        scope_dims = Vector((x, y)) + Vector((get_text_dimensions(context, "Selecting Down ").x, 6 * scale))
        reveal_dims = Vector((x, y)) + Vector((get_text_dimensions(context, "Selecting Down ").x, -6 * scale))

        if self.include_selection:
            text = "Inclusive "
            draw_fading_label(context, text=text, x=scope_dims.x, y=scope_dims.y, center=False, size=10, time=time, alpha=0.5)

            scope_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

        if getattr(self, f"recursive_{self.direction.lower()}"):
            text = "+ Recursive " if self.include_selection else "Recursive"
            draw_fading_label(context, text=text, x=scope_dims.x, y=scope_dims.y, center=False, size=10, time=time, alpha=0.5)

            scope_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

        if self.direction == 'DOWN' and self.include_mod_objects:
            text = "+ Mod Objects" if self.include_selection or self.recursive_down else "Mod Objects"
            draw_fading_label(context, text=text, x=scope_dims.x, y=scope_dims.y, center=False, size=10, time=time, alpha=0.5)

        if local_view := is_local_view() and self.localview:
            text = "Local View "
            draw_fading_label(context, text=text, x=reveal_dims.x, y=reveal_dims.y, center=False, size=10, color=normal, time=time)

            reveal_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

        if self.unhide:
            text = "+ Unhide " if local_view else "Unhide "
            draw_fading_label(context, text=text, x=reveal_dims.x, y=reveal_dims.y, center=False, size=10, color=blue, time=time)

            reveal_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

        if self.link:
            text = "+ Link" if local_view or self.unhide else "Link"
            draw_fading_label(context, text=text, x=reveal_dims.x, y=reveal_dims.y, center=False, size=10, color=green, time=time)

        if visible_count or hidden_count:
            text = f"more {'children' if self.direction == 'DOWN' else 'parents'}: "

            more_dims = Vector((x, y)) + Vector((get_text_dimensions(context, "more children: ", size=10).x - get_text_dimensions(context, text, size=10).x, -20* scale))

            draw_fading_label(context, text=text, x=more_dims.x, y=more_dims.y, center=False, size=10, color=white, time=time, alpha=0.5)

            more_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

            if toggles:
                toggle_text = "toggle: "

                toggle_dims = Vector((more_dims.x - get_text_dimensions(context, toggle_text, size=10).x, more_dims.y -15 * scale))

            if visible_count:
                text = f"{visible_count} visible "
                draw_fading_label(context, text=text, x=more_dims.x, y=more_dims.y, center=False, size=10, color=white, time=time, alpha=0.3)

                more_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

            if hidden_count:
                text = f"+ {hidden_count} hidden" if visible_count else f"{hidden_count} hidden"
                draw_fading_label(context, text=text, x=more_dims.x, y=more_dims.y, center=False, size=10, color=yellow, time=time, alpha=1)

            if toggles:
                draw_fading_label(context, text=toggle_text, x=toggle_dims.x, y=toggle_dims.y, center=False, size=10, color=white, time=time * 1.5, alpha=0.5)

                toggle_dims += Vector((get_text_dimensions(context, toggle_text, size=10).x, 0))

                for idx, toggle in enumerate(toggles):

                    text = f"{toggle.replace('_', ' ').title()} " if idx == 0 else f"+ {toggle.replace('_', ' ').title()} "
                    color, alpha = (normal, 1) if toggle == 'LOCALVIEW' else (blue, 1) if toggle == 'UNHIDE' else (green, 1) if toggle == 'LINK' else (white, 0.5)

                    draw_fading_label(context, text=text, x=toggle_dims.x, y=toggle_dims.y, center=False, size=10, color=color, time=time * 1.5, alpha=alpha)

                    toggle_dims += Vector((get_text_dimensions(context, text, size=10).x, 0))

        return {'FINISHED'}

    def select(self, context, objects, layers, direction='DOWN', debug=False):

        is_down = direction == 'DOWN'
        is_up = direction == 'UP'
        objtype = 'children' if is_down else 'parents' if is_up else None

        init_selection = set(objects)

        direct = set()
        recursive = set()
        mod_objects = set()

        if debug:
            print()
            print("-----", direction, "-----")
            print("selected:")

            for obj in init_selection:
                print("", obj.name)

        if is_down:

            for obj in init_selection:
                obj_children = {c for c in obj.children if is_obj_in_scene(c)}
                obj_recursive_children = {c for c in obj.children_recursive if is_obj_in_scene(c)}
                obj_mod_objects = {modobj for mod in obj.modifiers if mod.show_viewport and (modobj := get_mod_obj(mod)) and is_obj_in_scene(modobj)}

                direct.update(obj_children)

                recursive.update(obj_recursive_children - obj_children)

                mod_objects.update(obj_mod_objects - obj_recursive_children)

        elif is_up:

            for obj in init_selection:
                if obj.parent:
                    direct.add(obj.parent)

                    recursive.update([p for p in get_parent(obj, recursive=True) if p != obj.parent])

        else:
            return

        all = direct | recursive | mod_objects

        if debug:
            print()
            print(f"direct {objtype}:", len(direct))
            print(f"recursive {objtype}:", len(recursive))

            if is_down:
                print("mod objects:", len(mod_objects))

        visible = set()
        localview = set()
        hidden = set()
        severely_hidden_excluded = set()
        severely_hidden_collection = set()

        if debug:
            print()
            print("all children:")

        for obj in all:
            vis = visible_get(obj, self.dg, debug=False)

            if vis['visible']:
                visible.add(obj)

            else:
                if vis['local_view'] is False:
                    localview.add(obj)

                if vis['hide'] or vis['hide_viewport']:
                    hidden.add(obj)

                if vis['viewlayer'] is False:
                    severely_hidden_excluded.add(obj)

                if vis['visible_collection'] is False:
                    severely_hidden_collection.add(obj)

        if debug:
            print()
            print(f"visible {objtype}:")

            for obj in visible:
                print("", obj.name)

            print()
            print(f"outside of local view {objtype}:")

            for obj in localview:
                print("", obj.name)

            print()
            print(f"hidden {objtype}:")

            for obj in hidden:
                print("", obj.name)

            print()
            print(f"severely hidden {objtype}:")

            for obj in severely_hidden_excluded | severely_hidden_collection:
                print("", obj.name)

        in_scope = direct.copy()

        if is_up:
            if self.recursive_up:
                in_scope.update(recursive)
        elif is_down:
            if self.recursive_down:
                in_scope.update(recursive)

            if self.include_mod_objects:
                in_scope.update(mod_objects)

        selectable = in_scope & visible

        if self.localview:
            selectable |= in_scope & localview

        if self.unhide:
            selectable |= in_scope & hidden

        if self.link:
            selectable |= in_scope & (severely_hidden_excluded | severely_hidden_collection)

        if not self.localview:
            selectable -= localview

        if not self.unhide:
            selectable -= hidden

        if not self.link:
            selectable -= (severely_hidden_excluded | severely_hidden_collection)

        if debug:
            print()
            print(f"selectable {objtype}:")

            for obj in selectable:
                print("", obj.name)

        args = {
            'scene': False,

            'local_view': self.localview,

            'unhide': self.unhide,
            'unhide_viewport': self.unhide,

            'viewlayer': self.link,
            'hidden_collection': self.link
        }

        if selectable:
            ensure_visibility(context, selectable, **args, select=True)

            if not self.include_selection:

                for obj in init_selection - selectable:
                    obj.select_set(False)

        still_visible = visible - selectable

        still_hidden = all - visible - selectable

        if debug:
            print("visible (and still unselected):", len(still_visible))
            print("still hidden:", len(still_hidden))

        status = {
            'type': None,
            'toggles': [],
            'visible': len(still_visible),
            'hidden': len(still_hidden),
        }

        if still_hidden:

            if (is_down and not self.recursive_down) or (is_up and not self.recursive_up):
                if still_hidden & recursive:
                    status['toggles'].append('RECURSIVE')

            if is_down and not self.include_mod_objects:
                if still_hidden & mod_objects:
                    status['toggles'].append('MOD_OBJECTS')

            if not self.localview:
                if still_hidden & localview:
                    status['toggles'].append('LOCALVIEW')

            if not self.unhide:
                if still_hidden & hidden:
                    status['toggles'].append('UNHIDE')

            if not self.link:
                if still_hidden & (severely_hidden_excluded | severely_hidden_collection):
                    status['toggles'].append('LINK')

        if still_visible:
            if is_down and not self.include_mod_objects:
                if still_visible & mod_objects and 'MOD_OBJECTS' not in status['toggles']:
                    status['toggles'].insert(0, 'MOD_OBJECTS')

            if (is_down and not self.recursive_down) or (is_up and not self.recursive_up):
                if still_visible & recursive and 'RECURSIVE' not in status['toggles']:
                    status['toggles'].insert(0, 'RECURSIVE')

        if all - init_selection:
            if selectable:
                status['type'] = 'SELECT'

            else:
                status['type'] = 'BOTTOM' if is_down else 'TOP' if is_up else None

        else:
            status['type'] = 'ABSOLUTE_BOTTOM' if is_down else 'ABSOLUTE_TOP' if is_up else None

        if debug:
            printd(status)

        selected = selectable | (init_selection if self.include_selection else set()) if selectable else init_selection

        if (active := context.active_object):

            for idx, layer in enumerate(layers):
                if (top_layer := set(layer) & selected):

                    if active not in top_layer:

                        group_empties = [obj for obj in top_layer if obj.M3.is_group_empty]

                        if group_empties:
                            context.view_layer.objects.active = group_empties[0]
                        else:
                            context.view_layer.objects.active = top_layer.pop()

                    break

        return status
