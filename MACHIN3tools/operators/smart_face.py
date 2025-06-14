import bpy
from bpy.props import BoolProperty, StringProperty

import bmesh
from mathutils import Vector

from .. utils.draw import draw_init, draw_label, draw_line, draw_point
from .. utils.registration import get_prefs
from .. utils.snap import get_sorted_snap_elements
from .. utils.ui import draw_status_item, finish_modal_handlers, finish_status, get_mouse_pos, ignore_events, init_modal_handlers, init_status, warp_mouse
from .. utils.view import get_location_2d, update_local_view

from .. colors import yellow, white
from .. items import alt, ctrl, shift

def draw_smart_face_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)

        r = row.row()
        r.active = False
        r.label(text="Smart Face")
        row.label(text="Topo Mode")

        draw_status_item(row, key='LMB', text="Confirm")
        draw_status_item(row, key=['ALT', 'MMB'], text="Viewport")
        draw_status_item(row, key='RMB', text="Cancel")

        draw_status_item(row, key='MOVE', text="Move new Vert", gap=10)

        draw_status_item(row, active=op.use_snap, key='CTRL', text="Snapping", gap=2)
        draw_status_item(row, key=['SHIFT', 'TAB'], text="Invert Snapping", gap=1)

    return draw

class SmartFace(bpy.types.Operator):
    bl_idname = "machin3.smart_face"
    bl_label = "MACHIN3: Smart Face"
    bl_options = {'REGISTER', 'UNDO'}

    is_f3: BoolProperty(name="Create Face from Vert or Edge Seelction")
    f3_topo_mode: BoolProperty(name="F3 Topo Mode", default=False)
    automerge: BoolProperty(name="Merge to closeby Vert", default=True)
    use_focus: BoolProperty(name="Focus on new Object", default=False)
    keep_mods: BoolProperty(name="Keep Modifiers", default=False)
    join: BoolProperty(name="Join Separated", default=False)
    mode: StringProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            mode = tuple(context.scene.tool_settings.mesh_select_mode)
            return any(mode == m for m in [(True, False, False), (False, True, False), (False, False, True)])

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if not self.is_modal:
            if self.is_f3:
                row = column.row(align=True)

                if len(self.verts) == 1:
                    row.prop(self, "automerge", toggle=True)

            elif self.is_face:

                row = column.row(align=True)
                row.prop(self, "use_focus", text="Use Focus", toggle=True)

                if self.is_multiple_separated and self.has_modifiers:
                    row = column.row(align=True)

                if self.is_multiple_separated:
                    row.prop(self, "join", toggle=True)

                if self.has_modifiers:
                    row.prop(self, "keep_mods", toggle=True)

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            dims = draw_label(context, "Smart Face ", coords=Vector((self.HUD_x, self.HUD_y)), center=False, alpha=0.5)
            draw_label(context, "Topo Mode", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False)

            self.offset += 18

            dims = draw_label(context, "Snapping: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=yellow if self.use_snap else white, alpha=1 if self.use_snap else 0.25)
            draw_label(context, self.snap_elements, coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5 if self.use_snap else 0.1)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            data = self.topo_mode_data

            draw_point(data['v_new_loc'], alpha=0.5)
            draw_line([data['v1_other_loc'], data['v_new_loc'], data['v2_other_loc']], alpha=0.3)

            if loc := data['v_next_loc']:
                draw_point(loc, color=yellow, alpha=0.5)

            if loc := data['v_next_second_loc']:
                draw_point(loc, color=yellow, alpha=0.5)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

        if self.finish_modal:
            self.finish(context)

            self.finish_f3(context)

            return {'FINISHED'}

        if event.type == 'TAB' and event.value == 'PRESS' and event.shift:
            self.use_snap = not self.use_snap

        if event.type in ctrl:
            self.use_snap = not self.use_snap

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE', 'SPACE', 'ESC', *alt, *ctrl, *shift, 'TAB']:

            if event.type == 'MIDDLEMOUSE':
                if event.alt:
                    return {'PASS_THROUGH'}

                else:
                    return {'RUNNING_MODAL'}

            if event.type in ['LEFTMOUSE', 'RIGHTMOUSE', 'SPACE', 'ESC']:

                self.finish_modal = True

            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        finish_modal_handlers(self)

        finish_status(self)

    def finish_f3(self, context):
        if self.is_automerge:
            context.scene.tool_settings.use_mesh_automerge = True

        if (idx := self.topo_mode_data['v_next']) is not None:
            bm = bmesh.from_edit_mesh(self.active.data)
            bm.normal_update()
            bm.verts.ensure_lookup_table()

            v_new = bm.verts[self.topo_mode_data['v_new']]

            v_new.select_set(False)
            bm.select_flush(False)

            v_next = bm.verts[idx]
            v_next.select_set(True)
            bm.select_flush(True)

            if (idx := self.topo_mode_data['v_next_second']) is not None:
                v_next_second = bm.verts[idx]
                v_next_second.select_set(True)
                bm.select_flush(True)

            if self.is_automerge:
                distances = [(v,  (v_new.co - v.co).length) for v in bm.verts if v != v_new]

                if distances:
                    closest = min(distances, key=lambda x: x[1])

                    if round(closest[1], 5) == 0:

                        bmesh.ops.pointmerge(bm, verts=[v_new, closest[0]], merge_co=closest[0].co)

            bmesh.update_edit_mesh(self.active.data)

    def invoke(self, context, event):
        self.active = context.active_object
        self.init_sel = context.selected_objects

        self.is_vert = tuple(context.scene.tool_settings.mesh_select_mode) == (True, False, False)
        self.is_edge = tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False)
        self.is_face = tuple(context.scene.tool_settings.mesh_select_mode) == (False, False, True)

        self.mode = 'Face from Vert' if self.is_vert else 'Face from Edge' if self.is_edge else 'Object from Faces'

        self.is_f3 = False
        self.is_modal = False  # used to determine if redo panel should be exposed, which it shouldn't when you go into f3 topo mode'

        self.f3_topo_mode = self.get_f3_topo_mode(context)

        bm = bmesh.from_edit_mesh(self.active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        if self.is_vert or self.is_edge:

            self.verts = [v for v in bm.verts if v.select]

            if self.verts:

                self.is_f3 = len(self.verts) < 3

                if self.is_f3:

                    if self.f3_topo_mode:

                        ret = self.f3(bm)

                        if ret:
                            self.mode += " (Topo Mode)"

                            self.is_modal = True

                            self.topo_mode_data = ret
                            self.finish_modal = False

                            ts = context.scene.tool_settings

                            self.use_snap = ts.use_snap
                            self.snap_elements = " + ".join(get_sorted_snap_elements(ts))

                            self.is_automerge = ts.use_mesh_automerge

                            if self.is_automerge:
                                ts.use_mesh_automerge = False

                            get_mouse_pos(self, context, event)

                            co2d = get_location_2d(context, ret['v_new_loc'])
                            warp_mouse(self, context, co2d)

                            init_status(self, context, func=draw_smart_face_status(self))

                            bpy.ops.transform.translate('INVOKE_DEFAULT')

                            init_modal_handlers(self, context, hud=True, view3d=True)
                            return {'RUNNING_MODAL'}

                        else:
                            pass

                        return {'FINISHED'}

                    else:
                        self.f3(bm)
                        return {'FINISHED'}

                else:
                    bpy.ops.mesh.edge_face_add()

                    return {'FINISHED'}

        elif self.is_face:
            if [f for f in bm.faces if f.select]:

                self.create_object_from_faces(context)
                return {'FINISHED'}

        return {'CANCELLED'}

    def execute(self, context):
        self.active = context.active_object
        self.init_sel = context.selected_objects

        bm = bmesh.from_edit_mesh(self.active.data)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        if self.is_vert or self.is_edge:

            if self.is_f3:

                self.verts = [v for v in bm.verts if v.select]

                self.f3(bm)
                return {'FINISHED'}

            else:
                bpy.ops.mesh.edge_face_add()
                return {'FINISHED'}

        elif self.is_face:
            faces = [f for f in bm.faces if f.select]

            if faces:

                self.create_object_from_faces(context)
                return {'FINISHED'}

        return {'CANCELLED'}

    def get_f3_topo_mode(self, context):
        if get_prefs().smart_face_use_topo_mode:
            if get_prefs().smart_face_topo_mode_face_snapping:
                return any(el in context.scene.tool_settings.snap_elements for el in ['FACE', 'FACE_PROJECT', 'FACE_NEAREST'])

            elif get_prefs().smart_face_topo_mode_retopology_overlay:
                return context.space_data.overlay.show_retopology
            else:
                return True
        else:
            return False

    def f3(self, bm):

        if len(self.verts) == 1:
            vs = self.verts[0]

            faces = vs.link_faces
            open_edges = [e for e in vs.link_edges if not e.is_manifold]

            if faces and len(open_edges) == 2:

                e1 = open_edges[0]
                e2 = open_edges[1]

                v1_other = e1.other_vert(vs)
                v2_other = e2.other_vert(vs)

                v1_dir = v1_other.co - vs.co
                v2_dir = v2_other.co - vs.co

                v_new = bm.verts.new()
                v_new.co = vs.co + v1_dir + v2_dir

                f = bm.faces.new([vs, v2_other, v_new, v1_other])
                f.smooth = any([f.smooth for f in faces])

                bmesh.ops.recalc_face_normals(bm, faces=[f])

                if self.automerge or self.f3_topo_mode:
                    nonmanifoldverts = [v for v in bm.verts if any([not e.is_manifold for e in v.link_edges]) and v not in [vs, v_new, v1_other, v2_other]]

                    if nonmanifoldverts:
                        distance = min([((v_new.co - v.co).length, v) for v in nonmanifoldverts], key=lambda x: x[0])
                        threshold = min([(v_new.co - v.co).length * 0.5 for v in [v1_other, v2_other]])

                        if distance[0] < threshold:
                            v_closest = distance[1]

                            bmesh.ops.pointmerge(bm, verts=[v_new, v_closest], merge_co=v_closest.co)

                v_next, v_next_second = self.f3_get_next_vert(bm, vs, v_new, v1_other, v2_other)

                if self.f3_topo_mode:
                    vs.select_set(False)
                    bm.select_flush(False)

                    v_new.select_set(True)
                    bm.select_flush(True)

                    bmesh.update_edit_mesh(self.active.data)

                    data = {'v_new': v_new.index,
                            'v_new_loc': self.active.matrix_world @ v_new.co,

                            'v1_other_loc': self.active.matrix_world @ v1_other.co,
                            'v2_other_loc': self.active.matrix_world @ v2_other.co,

                            'v_next': None,
                            'v_next_loc': None,

                            'v_next_second': None,
                            'v_next_second_loc': None }

                    if v_next:
                        data['v_next'] = v_next.index
                        data['v_next_loc'] = self.active.matrix_world @ v_next.co

                    if v_next_second:
                        data['v_next_second'] = v_next_second.index
                        data['v_next_second_loc'] = self.active.matrix_world @ v_next_second.co

                    return data

                else:
                    if v_next:
                       vs.select_set(False)
                       bm.select_flush(False)

                       v_next.select_set(True)
                       bm.select_flush(True)

                    else:
                        vs.select_set(False)
                        bm.select_flush(False)

                    if v_next_second:
                        v_next_second.select_set(True)
                        bm.select_flush(True)

        if len(self.verts) == 2:
            v1 = self.verts[0]
            v2 = self.verts[1]
            e12 = bm.edges.get([v1, v2])

            faces = [f for v in [v1, v2] for f in v.link_faces]

            v1_edges = [e for e in v1.link_edges if e != e12 and not e.is_manifold]
            v2_edges = [e for e in v2.link_edges if e != e12 and not e.is_manifold]

            if v1_edges and v2_edges:
                v1_other = v1_edges[0].other_vert(v1)
                v2_other = v2_edges[0].other_vert(v2)

                if v1_other == v2_other:
                    f = bm.faces.new([v1, v1_other, v2])
                else:
                    f = bm.faces.new([v1, v1_other, v2_other, v2])

                f.smooth = any([f.smooth for f in faces])

                bmesh.ops.recalc_face_normals(bm, faces=[f])

                v1.select = False
                v2.select = False

                if len(v1_other.link_edges) == 4 and any([not e.is_manifold for e in v1_other.link_edges]):
                    v1_other.select = True

                if len(v2_other.link_edges) == 4 and any([not e.is_manifold for e in v2_other.link_edges]):
                    v2_other.select = True

                bm.select_flush(False)

                if v1_other.select and not v2_other.select:
                    v1 = v1_other
                    v2 = v2_other

                    second_vs = [e.other_vert(v1) for e in v1.link_edges if not e.is_manifold and e.other_vert(v1) != v2 and len(e.other_vert(v1).link_edges) == 4]
                    if second_vs:
                        second_v = second_vs[0]
                        second_v.select = True

                elif v2_other.select and not v1_other.select:
                    v1 = v1_other
                    v2 = v2_other

                    second_vs = [e.other_vert(v2) for e in v2.link_edges if not e.is_manifold and e.other_vert(v2) != v1 and len(e.other_vert(v2).link_edges) == 4]
                    if second_vs:
                        second_v = second_vs[0]
                        second_v.select = True

                bm.select_flush(True)

        bmesh.update_edit_mesh(self.active.data)

    def f3_get_next_vert(self, bm, vs, v_new, v1_other, v2_other):
        v_next = None
        v_next_second = None

        if any([len(v1_other.link_edges) == 4, len(v2_other.link_edges) == 4]):
            if len(v1_other.link_edges) == 4 and any([not e.is_manifold for e in v1_other.link_edges]):
                v_next = v1_other

            elif len(v2_other.link_edges) == 4 and any([not e.is_manifold for e in v2_other.link_edges]):
                v_next = v2_other

            if v_next:
                second_vs = [e.other_vert(v_next) for e in v_next.link_edges if not e.is_manifold and len(e.other_vert(v_next).link_edges) == 4 and sum([not e.is_manifold for e in e.other_vert(v_next).link_edges]) == 2]

                if second_vs:
                    v_next_second = second_vs[0]

        return v_next, v_next_second

    def create_object_from_faces(self, context):
        bpy.ops.mesh.duplicate()
        bpy.ops.mesh.separate(type='SELECTED')

        bpy.ops.object.mode_set(mode='OBJECT')

        separated = [obj for obj in context.selected_objects if obj not in self.init_sel]

        self.is_multiple_separated = len(separated) > 1
        self.has_modifiers = any(bool(obj.modifiers) for obj in separated)

        bpy.ops.object.select_all(action='DESELECT')

        for obj in separated:
            if obj.modifiers and not self.keep_mods:
                obj.modifiers.clear()

            obj.select_set(True)
            context.view_layer.objects.active = obj

        if self.use_focus:
            self.focus(context, separated)

        if self.join:
            bpy.ops.object.join()

        bpy.ops.object.mode_set(mode='EDIT')

    def focus(self, context, separated):
        view = context.space_data
        history = context.scene.M3.focus_history

        vis = context.visible_objects
        hidden = [obj for obj in vis if obj not in separated]

        if view.local_view:
            update_local_view(view, [(obj, False) for obj in hidden])

        else:
            if history:
                history.clear()

            bpy.ops.view3d.localview(frame_selected=False)

        epoch = history.add()
        epoch.name = f"Epoch {len(history) - 1}"

        for obj in hidden:
            entry = epoch.objects.add()
            entry.obj = obj
            entry.name = obj.name
