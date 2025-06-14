import bpy
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty
from math import radians
from uuid import uuid4
from .. utils.object import disable_auto_smooth, enable_auto_smooth, hide_render, is_auto_smooth, parent, set_auto_smooth_angle, get_auto_smooth_angle, unparent
from .. utils.mesh import get_coords, unhide_deselect, shade 
from .. utils.modifier import add_boolean, add_displace, get_auto_smooth, move_mod, remove_mod, sort_mod
from .. utils.ui import draw_title, draw_prop, draw_init, draw_text, init_cursor, init_status, finish_status, update_HUD_location, init_timer_modal, set_countdown, get_timer_progress
from .. utils.draw import draw_mesh_wire
from .. utils.property import step_enum
from .. utils.system import printd
from .. items import boolean_method_items, boolean_solver_items
from .. colors import yellow, blue, red, normal, green

def draw_add_boolean(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text='Add Boolean')

        row.label(text="", icon='EVENT_SPACEKEY')
        row.label(text="Finish and hide Cutters")

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Finish and select Cutters")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        row.label(text="", icon='MOUSE_MMB')
        row.label(text=f"Method: {op.method.title()}")

        row.separator(factor=2)
        row.label(text="", icon='EVENT_E')
        row.label(text="", icon='EVENT_F')
        row.label(text=f"Solver: {op.solver.title()}")

        row.separator(factor=2)
        row.label(text="", icon='EVENT_S')
        row.label(text=f"Smooth: {op.auto_smooth}")

        if op.auto_smooth:
            row.separator(factor=1)
            row.label(text="", icon='EVENT_ALT')
            row.label(text="", icon='MOUSE_MMB')
            row.label(text=f"Smooth: {op.auto_smooth_angle}")

    return draw

class Boolean(bpy.types.Operator):
    bl_idname = "machin3.boolean"
    bl_label = "MACHIN3: Boolean"
    bl_description = "Add Boolean Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(name="Method", items=boolean_method_items, default='DIFFERENCE')
    solver: EnumProperty(name="Solver", items=boolean_solver_items, default='FAST')
    auto_smooth: BoolProperty(name="Auto-Smooth", default=True)
    auto_smooth_angle: IntProperty(name="Angle", default=20)
    time: FloatProperty(name="Time (s)", default=2)
    passthrough = None

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            sel = [obj for obj in context.selected_objects if obj != active]
            return active and sel

    def draw_HUD(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self)

            draw_init(self)

            draw_title(self, "Add Boolean", subtitle="to %s" % (self.active.name), subtitleoffset=160, HUDalpha=alpha)

            for idx, name in enumerate([obj.name for obj in self.sel]):
                text = "%s" % (name)
                draw_text(self, text, 11, offset=0 if idx == 0 else 18, HUDcolor=yellow, HUDalpha=alpha)

            self.offset += 10

            draw_prop(self, "Method", self.method, offset=18, hint="scroll UP/DOWN,", hint_offset=210)
            draw_prop(self, "Solver", self.solver, offset=18, hint="Set E/F", hint_offset=210)

            self.offset += 10

            draw_prop(self, "Auto-Smooth", self.auto_smooth, offset=18, hint="toggle S", hint_offset=210)

            if self.auto_smooth:
                draw_prop(self, "Angle", self.auto_smooth_angle, offset=18, hint="ALT scroll UP/DOWN", hint_offset=210)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self)

            color = red if self.method == 'DIFFERENCE' else blue if self.method == 'UNION' else normal if self.method == 'INTERSECT' else green

            for batch in self.batches:
                if not self.passthrough:
                    draw_mesh_wire(batch, color=color, alpha=alpha)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'UP_ARROW', 'ONE', 'WHEELDOWNMOUSE', 'DOWN_ARROW', 'S', 'E', 'F']

        if event.type in events:

            if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE', 'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO', 'E', 'F'} and event.value == 'PRESS':

                if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE'} and event.value == 'PRESS':
                    if event.alt and self.auto_smooth:
                        self.auto_smooth_angle += 5

                    else:
                        self.method = step_enum(self.method, boolean_method_items, 1, loop=True)

                elif event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO'} and event.value == 'PRESS':
                    if event.alt and self.auto_smooth:
                        self.auto_smooth_angle -= 5

                    else:
                        self.method = step_enum(self.method, boolean_method_items, -1, loop=True)

                if event.type == 'E' and event.value == 'PRESS':
                    self.solver = 'EXACT'

                elif event.type == 'F' and event.value == 'PRESS':
                    self.solver = 'FAST'
                
                for mod in self.boolean_mods:

                    if self.method == 'SPLIT':
                        mod.operation = 'DIFFERENCE'
                        mod.show_viewport = False

                    else:
                        mod.operation = self.method
                        mod.show_viewport = True

                    mod.solver = self.solver
                    mod.name = self.method.title()

                if event.alt and self.auto_smooth:
                    set_auto_smooth_angle(self.active, angle=self.auto_smooth_angle)

            elif event.type == 'S' and event.value == 'PRESS':
                self.auto_smooth = not self.auto_smooth

                for obj in self.sel + [self.active]:
                    shade(obj.data, self.auto_smooth)

                    auto_smooth = is_auto_smooth(obj)
                    
                    if self.auto_smooth and not auto_smooth:
                        mod = enable_auto_smooth(obj)

                        if mod:
                            sort_mod(mod)

                    elif not self.auto_smooth and auto_smooth:
                        disable_auto_smooth(obj)

                    shade(obj.data, self.auto_smooth)

            init_timer_modal(self)

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        if self.passthrough and not event.type == 'TIMER':
            if self.passthrough:
                self.passthrough = False

                init_timer_modal(self)

        if event.type == 'TIMER' and not self.passthrough:
            set_countdown(self)

        if self.countdown < 0:
            self.finish(context)

            if self.method == 'SPLIT':
                self.setup_split_boolean(context)

            return {'FINISHED'}

        elif event.type in {'LEFTMOUSE', 'SPACE'} and not event.alt:
            self.finish(context)

            cutters = self.sel

            if self.method == 'SPLIT':
                split_cutters = self.setup_split_boolean(context)
                cutters += split_cutters

            if event.type == 'LEFTMOUSE':
                self.select_cutters(context, cutters)

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'} and not event.alt:
            self.finish(context)

            for mod in self.boolean_mods:
                remove_mod(mod)

            self.restore_initial_states()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        context.window_manager.event_timer_remove(self.TIMER)
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        self.active = context.active_object
        self.sel = [obj for obj in context.selected_objects if obj != self.active]
        self.split = {}

        self.init_auto_smooth()

        self.setup_booleans()

        init_cursor(self, event)

        init_status(self, context, func=draw_add_boolean(self))

        init_timer_modal(self)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.05, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def init_auto_smooth(self):
        self.auto_smooth = is_auto_smooth(self.active)

        if self.auto_smooth:
            self.auto_smooth_angle = get_auto_smooth_angle(self.active)

        else:
            self.auto_smooth_angle = 20

    def setup_booleans(self):
        self.batches = []

        self.boolean_mods = []

        self.initial_states = {}

        for obj in self.sel:
            self.initial_states[obj] = {'parent': obj.parent,
                                        'display_type': obj.display_type,

                                        'hide_render': obj.hide_render, 
                                        'visible_camera': obj.visible_camera,
                                        'visible_diffuse': obj.visible_diffuse,
                                        'visible_glossy': obj.visible_glossy,
                                        'visible_transmission': obj.visible_transmission,
                                        'visible_volume_scatter': obj.visible_volume_scatter,
                                        'visible_shadow': obj.visible_shadow,

                                        'auto_smooth': is_auto_smooth(obj),
                                        'auto_smooth_angle': get_auto_smooth_angle(obj)
                                        }

            parent(obj, self.active)

            mod = add_boolean(self.active, obj, method=self.method, solver=self.solver)
            self.boolean_mods.append(mod)

            sort_mod(mod)

            obj.display_type = 'WIRE'

            hide_render(obj, True)

            obj.hide_set(True)

            if self.auto_smooth:
                shade(obj.data, smooth=True)

                mod = enable_auto_smooth(obj)

                if mod:
                    sort_mod(mod)

            coords, indices = get_coords(obj.data, mx=obj.matrix_world, indices=True)
            self.batches.append((coords, indices))

    def setup_split_boolean(self, context):
        view = context.space_data
        cutter_dups = []

        for cutter, mod in zip(self.sel, self.boolean_mods):

            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = self.active
            self.active.select_set(True)

            mod.name = "Split (Difference)"
            mod.show_viewport = True

            children = {str(uuid4()): (obj, obj.visible_get()) for obj in self.active.children_recursive if obj.name in context.view_layer.objects}

            for dup_hash, (obj, vis) in children.items():
                obj.MM.dup_hash = dup_hash

                if not vis:
                    if view.local_view and not obj.local_view_get(view):
                        obj.local_view_set(view, True)

                obj.hide_set(False)
                obj.select_set(True)

            bpy.ops.object.duplicate(linked=False)

            active_dup = context.active_object
            dup_mod = active_dup.modifiers.get(mod.name)
            dup_mod.operation = 'INTERSECT'
            dup_mod.name ='Split (Intersect)'

            dup_children = [obj for obj in active_dup.children_recursive if obj.name in context.view_layer.objects]

            for dup in dup_children:
                orig, vis = children[dup.MM.dup_hash]

                orig.hide_set(not vis)
                dup.hide_set(not vis)

                if orig == cutter:

                    dupmesh = dup.data
                    dup.data = orig.data

                    bpy.data.meshes.remove(dupmesh, do_unlink=False)

                    cutter_dups.append(dup)

                orig.MM.dup_hash = ''
                dup.MM.dup_hash = ''

            add_displace(dup_mod.object, mid_level=0, strength=0)

        bpy.ops.object.select_all(action='DESELECT')

        return cutter_dups

    def select_cutters(self, context, cutters):
        for obj in cutters:
            obj.hide_set(False)
            obj.select_set(True)

        context.view_layer.objects.active = cutters[0]

        self.active.select_set(False)

    def restore_initial_states(self):
        for obj, states in self.initial_states.items():

            parent(obj, parent) if (parent := states['parent']) else unparent(obj)

            obj.display_type = states['display_type']

            obj.hide_render = states['hide_render']
            obj.visible_camera = states['visible_camera']
            obj.visible_diffuse = states['visible_diffuse']
            obj.visible_glossy = states['visible_glossy']
            obj.visible_transmission = states['visible_transmission']
            obj.visible_volume_scatter = states['visible_volume_scatter']
            obj.visible_shadow = states['visible_shadow']

            if not obj.visible_get():
                obj.hide_set(False)

                obj.select_set(True)

            auto_smooth = is_auto_smooth(obj)

            if auto_smooth and not states['auto_smooth']:
                shade(obj.data, smooth=False)
                disable_auto_smooth(obj)

            elif not auto_smooth and states['auto_smooth']:
                shade(obj.data, smooth=True)
                enable_auto_smooth(obj)

            if (angle := states['auto_smooth_angle']) is not None:
                set_auto_smooth_angle(obj, angle=angle)
