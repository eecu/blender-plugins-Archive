import bpy
from bpy.props import BoolProperty, StringProperty, FloatProperty
import bmesh
from .. utils.ui import draw_init, draw_title, draw_prop, draw_text, init_cursor, update_HUD_location
from .. utils.ui import init_status, finish_status, init_timer_modal, set_countdown, get_timer_progress
from .. utils.property import step_collection
from .. utils.stash import create_stash, retrieve_stash, transfer_stashes, clear_stashes, swap_stash
from .. utils.mesh import get_coords
from .. utils.draw import draw_mesh_wire, draw_edit_stash_HUD
from .. utils.object import update_local_view
from .. utils.registration import get_prefs
from .. utils.scene import set_cursor
from .. colors import yellow, green, white, red, light_blue

class CreateStash(bpy.types.Operator):
    bl_idname = "machin3.create_stash"
    bl_label = "MACHIN3: Create Stash"
    bl_description = "Stash the current state of an object"
    bl_options = {'REGISTER', 'UNDO'}

    time: FloatProperty(name="Time", default=1)
    remove_sources: BoolProperty(name="Remove Sources", default=False)
    @classmethod
    def description(cls, context, properties):
        if context.mode == 'OBJECT':
            if len(context.selected_objects) > 1:
                return "Stash the evaluated selected objects to the active object\nALT: Stash the edit mesh states to the active object"

            else:
                return "Stash the current evaluated state of the object\nALT: Stash the edit mesh state of the current object"

        else:
            return "Stash the current state of the entire mesh or only the selected faces\nALT: Stash the evaluated mesh"

    @classmethod
    def poll(cls, context):
        if context.mode in ['EDIT_MESH', 'OBJECT']:
            return context.active_object

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, "remove_sources")

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            alpha = get_timer_progress(self)

            subtitle = self.stashes[0].name if len(self.stashes) == 1 else f"{self.stashes[0].name}..{self.stashes[-1].name}"
            draw_title(self, f"Create Stash{'es' if len(self.stashes) > 1 else ''}", subtitle=subtitle, subtitleoffset=200 if len(self.stashes) > 1 else 175, HUDalpha=alpha)

            if self.is_partial:
                draw_text(self, f"from {self.active.name}'s selected faces", 11, HUDcolor=light_blue, HUDalpha=alpha)

            elif self.is_self_stash:
                draw_text(self, f"from {self.active.name} itself", 11, HUDcolor=green, HUDalpha=alpha)

            else:
                for idx, obj in enumerate(self.sources):
                    draw_text(self, f"from {obj.name}", 11, offset=0 if idx == 0 else 18, HUDcolor=yellow, HUDalpha=alpha)

                self.offset += 10

                draw_prop(self, "Remove Sources", self.remove_sources, offset=18, hint="press D")

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self)

            if self.is_partial:
                alpha *= 2

            for batch in self.batches:
                color = light_blue if self.is_partial else green if self.is_self_stash else red if self.remove_sources else yellow
                draw_mesh_wire(batch, color=color, alpha=alpha)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        if self.sources and event.type in ['D', 'X'] and event.value == "PRESS":
            self.remove_sources = not self.remove_sources

            for obj in self.sources:
                obj.hide_set(self.remove_sources)

            init_timer_modal(self)

            return {'RUNNING_MODAL'}

        if self.countdown < 0:
            self.finish(context, remove_sources=self.remove_sources)
            return {'FINISHED'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish(context, remove_sources=self.remove_sources)
            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC']:
            self.cancel_modal(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context, remove_sources=False):
        context.window_manager.event_timer_remove(self.TIMER)

        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

        if remove_sources:
            for obj in self.sources:
                bpy.data.objects.remove(obj, do_unlink=True)

    def cancel_modal(self, context):
        self.finish(context, remove_sources=False)

        if self.remove_sources:
            for obj in self.sources:
                obj.hide_set(False)

        clear_stashes(self.active, stashes=self.stashes)

    def invoke(self, context, event):
        self.active = context.active_object
        self.dg = context.evaluated_depsgraph_get()
        
        self.is_self_stash = False
        self.is_partial = False
        self.remove_sources = False

        self.flatten_stack = context.mode == 'OBJECT'

        if event.alt:
            self.flatten_stack = not self.flatten_stack

        self.stashes = []
        self.sources = []

        self.stashes = self.stash(context)

        if not self.stashes:
            return {'CANCELLED'}

        self.batches = []

        for stash in self.stashes:
            coords, indices = get_coords(stash.obj.data, mx=stash.obj.matrix_world, indices=True)
            self.batches.append((coords, indices))

        init_cursor(self, event)

        init_status(self, context, title=f"Create Stash{'es' if len(self.stashes) > 1 else ''}")

        init_timer_modal(self)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.05, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def stash(self, context):
        stashes = []

        if self.active.mode == 'EDIT':
            self.active.update_from_editmode()

            self.is_self_stash = True

            bm = bmesh.from_edit_mesh(self.active.data)
            faces = [f for f in bm.faces if f.select]

            if faces:
                self.is_partial = True

                sel = [obj for obj in context.selected_objects]

                bpy.ops.mesh.duplicate()
                bpy.ops.mesh.separate(type='SELECTED')

                separated = [obj for obj in context.selected_objects if obj not in sel][0]
                stash = create_stash(active=self.active, source=separated, self_stash=self.is_self_stash, force_default_name=True, debug=False)
                bpy.data.meshes.remove(separated.data, do_unlink=True)

                for f in faces:
                    f.select_set(True)

                if stash:
                    stashes.append(stash)

            else:
                self.is_partial = False
                self.dg.update()
                stash = create_stash(active=self.active, source=self.active, dg=self.dg if self.flatten_stack else None, self_stash=self.is_self_stash, force_default_name=True, debug=False)
                if stash:
                    stashes.append(stash)

        else:
            sel = [obj for obj in context.selected_objects if obj != self.active]
            self.sources = [obj for obj in sel if obj.type == 'MESH']

            if sel and not self.sources:
                return

            self.is_self_stash = not bool(self.sources)
            sources = [self.active] if self.is_self_stash else self.sources

            for idx, obj in enumerate(sources):
                stash = create_stash(active=self.active, source=obj, dg=self.dg if self.flatten_stack else None, self_stash=self.is_self_stash, force_default_name=True, debug=False)
                if stash:
                    stashes.append(stash)

        return stashes

class ViewStashes(bpy.types.Operator):
    bl_idname = "machin3.view_stashes"
    bl_label = "MACHIN3: View Stashes"
    bl_description = "View stashes of an object and retrieve, edit or clear them"
    bl_options = {'REGISTER', 'UNDO'}

    xray: BoolProperty(name="X-Ray", default=False)
    alpha: FloatProperty(name="Alpha", default=0.3, min=0.01, max=0.99)
    normal_offset = 0.002

    @classmethod
    def poll(cls, context):
        if context.mode in ['EDIT_MESH', 'OBJECT']:
            return context.active_object and context.active_object.MM.stashes

    def draw_HUD(self, context):
        try:
            if context.area == self.area:

                if self.editing:
                        draw_edit_stash_HUD(context, color=yellow, alpha=0.5, title="Editing %s" % (self.stash.obj.name), subtitle="press SHIFT + ESC to finish")

                else:

                    multiple = len(self.active.MM.stashes) > 1

                    draw_init(self)
                    draw_title(self, f"View Stash{'es' if multiple else ''}", subtitle=f"{self.active.name} {'(' + self.active.MM.stashname + ')' if self.active.MM.stashname else ''}", subtitleoffset=200)

                    if multiple:
                        draw_prop(self, "Stash", "%d/%d" % (self.stash.index + 1, len(self.active.MM.stashes)), hint="scroll UP/DOWN", hint_offset=250)

                    if self.stash.obj:
                        if self.stash.obj.MM.stashname:
                            draw_prop(self, "Name", self.stash.name, offset=18 if multiple else 0)

                        if multiple or self.stash.obj.MM.stashname:
                            self.offset += 10

                        draw_prop(self, "X-Ray", self.xray, offset=18 if multiple or self.stash.obj.MM.stashname else 0, hint="toggle X", hint_offset=250)
                        draw_prop(self, "Alpha", self.alpha, decimal=1, offset=18, hint="ALT scroll UP/DOWN", hint_offset=250)
                        self.offset += 10

                        draw_prop(self, "Swap", "", offset=18, hint="press S", hint_offset=250)
                        draw_prop(self, "Edit", "", offset=18, hint="press E", hint_offset=250)

                        if self.retrieved_name:
                            draw_prop(self, "Retrieved", self.retrieved_name, offset=18, hint="press R", hint_offset=250)
                        else:
                            draw_prop(self, "Retrieve", self.retrieved_name, offset=18, hint="press R", hint_offset=250)

                        draw_prop(self, "Set Cursor to Stash", "", offset=18, hint="press C", hint_offset=250)

                    else:
                        self.offset += 10
                        draw_prop(self, "INVALID", "Stash Object Not Found", offset=18, HUDcolor=(1, 0, 0))

                    self.offset += 10
                    draw_prop(self, "Delete All", self.clear_all, offset=18, hint="press A", hint_offset=250)

                    if not self.clear_all:
                        draw_prop(self, "Delete", self.stash.mark_delete, offset=18, hint="press D", hint_offset=250)

                    deleting = [stash.name for stash in self.active.MM.stashes] if self.clear_all else [stash.name for stash in self.active.MM.stashes if stash.mark_delete]

                    if deleting:
                        self.offset += 10
                        draw_text(self, f"Deleting {'All' if self.clear_all else 'Marked'}", 11, offset=18, HUDcolor=white, HUDalpha=1)
                        draw_text(self, f"{len(deleting)}", 14, offset=0, offsetx=100, HUDcolor=red, HUDalpha=1)

                    for name in deleting:
                        draw_text(self, name, 11, offset=18, offsetx=100, HUDcolor=red, HUDalpha=1)

        except ReferenceError:
            pass

    def draw_VIEW3D(self, context):
        try:
            if context.area == self.area:
                if not self.editing:
                    if self.batch:
                        clear = self.clear_all or self.stash.mark_delete
                        draw_mesh_wire(self.batch, color=red if clear else white, width=2 if clear else 1, xray=self.xray, alpha=self.alpha)

        except ReferenceError:
            pass

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        else:
            self.finish(context)
            return {'FINISHED'}

        if self.editing:
            if event.shift and event.type in {'ESC'}:
                self.exit_stash_edit_mode(context)
                return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        else:

            if event.type == 'MOUSEMOVE':
                update_HUD_location(self, event)

            events = ['WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'ONE', 'TWO', 'UP_ARROW', 'DOWN_ARROW', 'X', 'R', 'E', 'C', 'D', 'A', 'S']

            if event.type in events:

                if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE'} and event.value == 'PRESS':
                    if event.alt:
                        self.alpha += 0.01 if event.shift else 0.1

                    else:
                        self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", -1)
                        self.retrieved_name = ""
                        self.update_batch()

                elif event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO'} and event.value == 'PRESS':
                    if event.alt:
                        self.alpha -= 0.01 if event.shift else 0.1

                    else:
                        self.stash = step_collection(self.active.MM, self.stash, "stashes", "active_stash_idx", 1)
                        self.retrieved_name = ""
                        self.update_batch()

                if self.stash.obj:

                    if event.type == 'X' and event.value == 'PRESS':
                        self.xray = not self.xray

                    elif event.type == 'S' and event.value == 'PRESS':
                        self.active, self.stash = swap_stash(context, self.active, self.active.MM.active_stash_idx)
                        self.update_batch()

                    elif event.type == 'E' and event.value == 'PRESS':
                        self.enter_stash_edit_mode(context)

                    elif event.type == 'R' and event.value == 'PRESS':
                        r = retrieve_stash(self.active, self.stash.obj)
                        self.retrieved_name = r.name

                        if self.stash.self_stash:
                            transfer_stashes(self.active, r)

                        self.retrieved.append(r)

                    elif event.type == 'C' and event.value == 'PRESS':
                        deltamx = self.stash.obj.MM.stashdeltamx
                        activemx = self.active.matrix_world

                        set_cursor(matrix=activemx @ deltamx)

                if event.type == 'D' and event.value == 'PRESS':
                    self.stash.mark_delete = not self.stash.mark_delete

                elif event.type == 'A' and event.value == 'PRESS':
                    self.clear_all = not self.clear_all

            if event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
                return {'PASS_THROUGH'}

            elif event.type in ['LEFTMOUSE', 'SPACE']:
                self.finish(context)

                if self.clear_all:
                    self.active.MM.stashes.clear()
                    bpy.ops.outliner.orphans_purge()

                else:
                    stashes = [stash for stash in self.active.MM.stashes if stash.mark_delete]

                    if stashes:
                        clear_stashes(self.active, stashes=stashes)
                        bpy.ops.outliner.orphans_purge()

                if self.retrieved:
                    self.active.select_set(False)

                    for obj in self.retrieved:
                        obj.select_set(True)

                    context.view_layer.objects.active = self.retrieved[0]

                return {'FINISHED'}

            elif event.type in {'RIGHTMOUSE', 'ESC'} and not event.value == 'RELEASE':
                self.finish(context)

                for stash in self.active.MM.stashes:
                    stash.mark_delete = False

                for obj in self.retrieved:
                    bpy.data.meshes.remove(obj.data, do_unlink=True)

                return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

        self.active.show_wire = self.wire

        if context.space_data:
            context.space_data.overlay.show_wireframes = self.wire_overlay

        if context.scene.MM.draw_active_stash:
            self.active.select_set(True)

    def invoke(self, context, event):
        self.active = context.active_object
        self.mode = self.active.mode

        for stash in self.active.MM.stashes:
            if stash.obj and not stash.obj.type == 'MESH':

                stash.obj.use_fake_user = False
                stash.obj = None

        self.editing = False
        self.states = None
        self.clear_all = False
        self.batch = None
        self.stash = self.active.MM.stashes[self.active.MM.active_stash_idx]
        self.retrieved_name = ''
        self.retrieved = []

        self.wire = self.active.show_wire
        self.wire_overlay = context.space_data.overlay.show_wireframes

        if self.wire or self.wire_overlay:
            self.active.show_wire = False
            context.space_data.overlay.show_wireframes = False

        if self.stash.obj:
            offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
            self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

        init_cursor(self, event)

        init_status(self, context, title=f"View Stash{'es' if len(self.active.MM.stashes) > 1 else ''}")
        self.active.select_set(True)

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def exit_stash_edit_mode(self, context):
        self.editing = False

        bpy.ops.object.mode_set(mode='OBJECT')

        context.collection.objects.unlink(self.stash.obj)

        self.active.select_set(True)
        context.view_layer.objects.active = self.active

        if context.space_data:
            if self.states:
                update_local_view(context.space_data, [(obj, not state) for obj, state in self.states])

            else:
                bpy.ops.view3d.localview(frame_selected=False)

        self.stash.obj.update_from_editmode()
        offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
        self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

        from .. import handlers
        handlers.oldstashesuuid = None

        if self.mode == 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

    def enter_stash_edit_mode(self, context):
        self.editing = True

        context.collection.objects.link(self.stash.obj)

        if self.stash.obj.matrix_world != self.active.matrix_world:
            self.stash.obj.matrix_world = self.active.matrix_world

        context.view_layer.objects.active = self.stash.obj

        bpy.ops.object.select_all(action='DESELECT')
        self.stash.obj.select_set(True)

        if context.space_data.local_view:
            self.states = [(obj, False) for obj in context.visible_objects]
            self.states.append((self.stash.obj, True))

            update_local_view(context.space_data, self.states)

        else:
            bpy.ops.view3d.localview(frame_selected=False)

        if not bpy.context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')

    def update_batch(self):
        if self.stash.obj:
            offset = sum([d for d in self.stash.obj.dimensions]) / 3 * self.normal_offset
            self.batch = get_coords(self.stash.obj.data, mx=self.active.matrix_world, offset=offset, indices=True)

        else:
            self.batch = None

transferred_stash_meshes = []

class TransferStashes(bpy.types.Operator):
    bl_idname = "machin3.transfer_stashes"
    bl_label = "MACHIN3: Transfer Stashes"
    bl_description = "Transfer Stashes from one object to another"
    bl_options = {'REGISTER', 'UNDO'}

    restash: BoolProperty(name="Retrieve and Re-Stash", default=False)
    def draw(self, context):
        layout = self.layout
        column = layout.column()

        column.prop(self, "restash")

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            active = context.active_object
            return [obj for obj in context.selected_objects if obj != active and obj.MM.stashes]

    def execute(self, context):
        active = context.active_object
        sel = [obj for obj in context.selected_objects if obj != active and obj.MM.stashes]

        stashes = transfer_stashes(sel[0], active, restash=self.restash)

        if stashes:
            global transferred_stash_meshes
            transferred_stash_meshes = [stash.obj.data for stash in stashes]

            bpy.ops.machin3.draw_transferred_stashes()

            return {'FINISHED'}
        return {'CANCELLED'}

class ViewOrphanStashes(bpy.types.Operator):
    bl_idname = "machin3.view_orphan_stashes"
    bl_label = "MACHIN3: View Orphan Stashes"
    bl_description = "View Oprhan Stashes"
    bl_options = {'REGISTER', 'UNDO'}

    xray: BoolProperty(name="X-Ray", default=False)
    normal_offset = 0.002

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT':
            return [obj for obj in bpy.data.objects if obj.MM.isstashobj and obj.use_fake_user and obj.users == 1]

    def draw_HUD(self, context):
        if context.area == self.area:
            multiple = len(self.orphans) > 1
            orphan = self.orphans[self.idx]

            draw_init(self)
            draw_title(self, f"View Orphan Stash{'es' if multiple else ''}")

            if multiple:
                draw_prop(self, "Stash", "%d/%d" % (self.idx + 1, len(self.orphans)), hint="scroll UP/DOWN", hint_offset=250)

            if orphan.MM.stashname:
                draw_prop(self, "Name", orphan.MM.stashname, offset=18 if multiple else 0)

            if multiple or orphan.MM.stashname:
                self.offset += 10

            draw_prop(self, "X-Ray", self.xray, offset=18 if multiple or orphan.MM.stashname else 0, hint="toggle X", hint_offset=250)
            self.offset += 10

            if self.retrieved_name:
                draw_prop(self, "Retrieved", self.retrieved_name, offset=18, hint="press R", hint_offset=250)
            else:
                draw_prop(self, "Retrieve", self.retrieved_name, offset=18, hint="press R", hint_offset=250)

            draw_prop(self, "Set Cursor to Stash", "", offset=18, hint="press C", hint_offset=250)

            self.offset += 10
            draw_prop(self, "Delete All", self.clear_all, offset=18, hint="press A", hint_offset=250)

            if not self.clear_all:
                draw_prop(self, "Delete", self.mark_delete[self.idx], offset=18, hint="press D", hint_offset=250)

            deleting = [obj.name for obj in self.orphans] if self.clear_all else [obj.name for obj, marked in zip(self.orphans, self.mark_delete) if marked]

            if deleting:
                self.offset += 10
                draw_text(self, f"Deleting {'All' if self.clear_all else 'Marked'}", 11, offset=18, HUDcolor=white, HUDalpha=1)
                draw_text(self, f"{len(deleting)}", 14, offset=0, offsetx=100, HUDcolor=red, HUDalpha=1)

            for name in deleting:
                draw_text(self, name, 11, offset=18, offsetx=100, HUDcolor=red, HUDalpha=1)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            for idx, batch in enumerate(self.batches):
                clear = self.clear_all or self.mark_delete[idx]
                draw_mesh_wire(batch, color=red if clear else white, width=2 if clear else 1, xray=self.xray, alpha=0.5 if idx == self.idx else 0.1 if clear else 0.05)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'UP_ARROW', 'ONE', 'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO', 'X', 'R', 'C', 'D', 'A']

        if event.type in events:
            if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'ONE'} and event.value == 'PRESS':
                self.idx = max([0, self.idx - 1])
                self.retrieved_name = ""

            elif event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'TWO'} and event.value == 'PRESS':
                self.idx = min([self.idx + 1, len(self.orphans) - 1])
                self.retrieved_name = ""

            if event.type == 'X' and event.value == 'PRESS':
                self.xray = not self.xray

            elif event.type in ['C', 'D'] and event.value == 'PRESS':
                self.mark_delete[self.idx] = not self.mark_delete[self.idx]

            if event.type == 'A' and event.value == 'PRESS':
                self.clear_all = not self.clear_all

            elif event.type == 'R' and event.value == 'PRESS':
                r = retrieve_stash(None, self.orphans[self.idx])
                self.retrieved_name = r.name

                self.retrieved.append(r)

            elif event.type == 'C' and event.value == 'PRESS':
                obj = self.orphans[self.idx]

                deltamx = obj.MM.stashdeltamx
                orphanmx = obj.MM.stashorphanmx

                set_cursor(matrix=orphanmx @ deltamx)

        if event.type in {'MIDDLEMOUSE'} or (event.type in ['LEFTMOUSE', 'RIGHTMOUSE'] and event.alt) or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish()

            if self.clear_all:
                objects = self.orphans

            else:
                objects = [obj for (obj, marked) in zip(self.orphans, self.mark_delete) if marked]

            if objects:
                for obj in objects:
                    bpy.data.meshes.remove(obj.data, do_unlink=True)

                bpy.ops.outliner.orphans_purge()

            if self.retrieved:
                bpy.ops.object.select_all(action='DESELECT')

                for obj in self.retrieved:
                    obj.select_set(True)

                context.view_layer.objects.active = self.retrieved[0]

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish()

            for obj in self.retrieved:
                bpy.data.meshes.remove(obj.data, do_unlink=True)

            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        invalid = [obj for obj in bpy.data.objects if obj.MM.isstashobj and obj.type != 'MESH']

        for obj in invalid:
            bpy.data.objects.remove(obj, do_unlink=True)

        self.clear_all = False
        self.orphans = [obj for obj in bpy.data.objects if obj.MM.isstashobj and obj.use_fake_user and obj.users == 1 and obj.type == 'MESH']
        self.batches = [(get_coords(obj.data, mx=obj.MM.stashorphanmx, offset=sum([d for d in obj.dimensions]) / 3 * self.normal_offset, indices=True)) for obj in self.orphans]
        self.mark_delete = [False for obj in self.orphans]
        self.retrieved_name = ''
        self.retrieved = []

        self.idx = 0

        init_cursor(self, event)

        init_status(self, context, f"View Orphan Stash{'es' if len(self.orphans) > 1 else ''}")

        if context.visible_objects:
            context.visible_objects[0].select_set(context.visible_objects[0].select_get())

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
