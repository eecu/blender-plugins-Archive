import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty, IntProperty
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

import bmesh
from mathutils import Vector
from mathutils.geometry import intersect_line_line, intersect_point_line

from math import sqrt, radians

from .. utils.bmesh import get_loop_triangles
from .. utils.draw import draw_init, draw_vector, draw_point, draw_line, draw_tris, draw_label
from .. utils.graph import get_shortest_path
from .. utils.math import average_normals, average_locations, get_center_between_verts, dynamic_format
from .. utils.property import rotate_list
from .. utils.raycast import cast_bvh_ray_from_point
from .. utils.selection import get_selection_islands, get_boundary_edges, get_edges_vert_sequences, get_selected_vert_sequences
from .. utils.snap import Snap
from .. utils.system import printd
from .. utils.ui import draw_status_item, finish_modal_handlers, force_ui_update, get_mouse_pos, ignore_events, init_modal_handlers, navigation_passthrough, popup_message, init_status, finish_status

from .. colors import green, red, blue, yellow, white, normal

from .. items import extrude_mode_items, ctrl, axis_vector_mappings, axis_items, cursor_spin_angle_preset_items

def draw_punchit_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)

        text = "Punch It"
        row.label(text=text)

        if not op.finalizing:
            if op.is_edge_picking:
                prop = "Valid" if op.edge_coords and op.data['edge_dir'] else "invalid" if op.edge_coords else "None"
                draw_status_item(row, active=prop=="Valid", key='MOVE', text="Pick Direction", prop=prop, gap=10)

            else:
                draw_status_item(row, key='LMB', text="Finalize")
                draw_status_item(row, key='MMB', text="Viewport")
                draw_status_item(row, key='RMB', text="Cancel")

                draw_status_item(row, key='MOVE', text="Amount", prop=dynamic_format(op.amount, 1), gap=10)

                if op.amount:
                    draw_status_item(row, key='R', text="Reset", gap=1)

                draw_status_item(row, text="Extrusion Direction:", gap=2)
                draw_status_item(row, active=op.mode=='AVERAGED', key='A', text="Averaged")
                draw_status_item(row, active=op.mode=='EDGE', key='E', text="Edge")
                draw_status_item(row, active=op.mode=='NORMAL', key='N', text="Normal")

        else:
            draw_status_item(row, key='LMB', text="Finish")
            draw_status_item(row, key='RMB', text="Cancel")

            draw_status_item(row, active=op.use_self, key='S', text="Use Self", gap=10)

            draw_status_item(row, text="Push and Pull:", gap=5)

            draw_status_item(row, active=op.is_shift, key='SHIFT', text="Invert")
            draw_status_item(row, active=op.is_ctrl, key='CTRL', text="x 100")

            draw_status_item(row, key='W', text="Both")
            draw_status_item(row, key='Q', text="Pull", prop=op.pulled)
            draw_status_item(row, key='E', text="Push", prop=op.pushed)

            draw_status_item(row, key='R', text="Reset", gap=2)

            draw_status_item(row, text="Pushing means widening the extrusion, moving the blue faces outwards", gap=5)
            draw_status_item(row, text="Pulling means moving the green faces back", gap=2)

    return draw

class PunchIt(bpy.types.Operator):
    bl_idname = "machin3.punch_it"
    bl_label = "MACHIN3: Punch It"
    bl_description = "Manifold Extruding that works"
    bl_options = {'REGISTER', 'UNDO'}

    use_self: BoolProperty(name="Use Self Intersection", description="Magically fix issues (slower)\nIf disabled, you'll often need bigger Push and Pull values (faster)", default=True)
    mode: EnumProperty(name="Mode", items=extrude_mode_items, default='AVERAGED')
    amount: FloatProperty(name="Amount", description="Extrusion Depth", default=0.4, min=0, precision=4, step=0.1)
    pushed: IntProperty(name="Pushed", description="Push Side Faces out", default=0)
    pulled: IntProperty(name="Pulled", description="Pull Front Face back", default=0)
    passthrough = False

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        row = column.row(align=True)
        row.label(text='Mode')
        row.prop(self, 'mode', expand=True)
        row.prop(self, 'use_self', text='', icon='SHADERFX', toggle=True)

        row = column.split(factor=0.5, align=True)
        row.prop(self, 'amount', expand=True)

        r = row.row(align=True)
        r.prop(self, 'pushed', text="Push", expand=True)
        r.prop(self, 'pulled', text="Pull", expand=True)

    def draw_HUD(self, context):
        if self.passthrough:
            return

        elif context.area == self.area:
            draw_init(self)

            dims = draw_label(context, title="Punch It ", coords=Vector((self.HUD_x, self.HUD_y)), center=False)

            if not self.finalizing:

                if self.is_edge_picking:
                    draw_label(context, title="Pick Direction", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False, alpha=0.5)

                    self.offset += 18

                    dims = draw_label(context, title="Edge: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

                    title, color, alpha = ("Valid", yellow, 1) if self.edge_coords and self.data['edge_dir'] else ("Invalid", red, 1) if self.edge_coords else ("None", white, 0.25)
                    draw_label(context, title=title, coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)

                else:
                    draw_label(context, title="Extrude", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False, alpha=0.5)

                    self.offset += 18

                    dims = draw_label(context, title="along ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

                    color = yellow if self.mode == 'EDGE' else blue if self.mode == 'AVERAGED' else normal
                    draw_label(context, title=self.mode.title(), coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, color=color)

                    self.offset += 18
                    dims = draw_label(context, title="Amount: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)
                    draw_label(context, title=dynamic_format(self.amount, 1), coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False)

            else:
                draw_label(context, title="Finalize", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), center=False, alpha=0.5)

                self.offset += 18

                dims = draw_label(context, title="Push: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=blue)
                dims += draw_label(context, title=f"{self.pushed}", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False)

                dims += draw_label(context, title=" Pull: ", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, color=green)
                draw_label(context, title=f"{self.pulled}", coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False)

                if self.use_self:
                    self.offset += 18

                    draw_label(context, title="Self-Intersection", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=yellow)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            data = self.data
            orig_verts = data['original_verts']
            extr_verts = data['extruded_verts']

            if self.finalizing:
                tri_coords = [orig_verts[idx]['co'] for idx in data['original_tri_indices']]
                draw_tris(tri_coords, mx=self.mx, color=green, alpha=0.03, xray=False)

                tri_coords = [(orig_verts | extr_verts)[idx]['co'] for idx in data['side_tri_indices']]
                draw_tris(tri_coords, mx=self.mx, color=blue, alpha=0.03, xray=False)

            else:
                data = self.data
                orig_verts = data['original_verts']
                extr_verts = data['extruded_verts']

                avg_co = self.mx @ data['avg_co']
                edge_dir = data['edge_dir']

                draw_point(avg_co, color=red if self.amount == 0 else white)

                if self.amount:
                    draw_vector(self.loc - self.init_loc, origin=avg_co, alpha=0.5)

                    tri_coords = [(orig_verts | extr_verts)[idx]['co'] for idx in data['original_tri_indices'] + data['extruded_tri_indices'] + data['side_tri_indices']]
                    draw_tris(tri_coords, mx=self.mx, color=green, alpha=0.1)

                if self.is_edge_picking and self.edge_coords:
                    color = yellow if self.edge_coords and edge_dir else red
                    draw_line(self.edge_coords, color=color, width=2)

                exit_coords = [orig_verts[vidx]['exit_co'] for vidx in data['sorted_boundary'] if orig_verts[vidx]['exit_co']]

                if exit_coords:
                    exit_coords.append(exit_coords[0])
                    draw_line(exit_coords, mx=self.mx, alpha=0.075)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

            if self.passthrough:
                self.passthrough = False

                i = self.get_mouse_intersection(context)
                self.init_loc = i - self.amount_dir * self.amount

        if not self.finalizing:

            if event.type in ['E', *ctrl]:
                if event.value == 'PRESS':
                    self.is_edge_picking = True
                    self.get_edge_dir(context)

                elif event.value == 'RELEASE':
                    self.is_edge_picking = False

                force_ui_update(context)
                return {'RUNNING_MODAL'}

            events = ['MOUSEMOVE', 'A', 'N', 'X', 'R']

            if event.type in events:

                if event.type == 'MOUSEMOVE':

                    if self.is_edge_picking:
                        self.get_edge_dir(context)

                    else:
                        self.loc = self.get_mouse_intersection(context)
                        self.set_extrusion_amount(context)

                elif event.type == 'A' and event.value == 'PRESS':
                    self.setup_extrusion_direction(context, direction='AVERAGED')
                    self.set_extrusion_amount(context)

                elif event.type in ['X', 'N'] and event.value == 'PRESS':
                    self.setup_extrusion_direction(context, direction='NORMAL')
                    self.set_extrusion_amount(context)

                elif event.type == 'R' and event.value == 'PRESS':
                    self.init_loc = self.get_mouse_intersection(context)
                    self.set_extrusion_amount(context)

                force_ui_update(context)

            elif navigation_passthrough(event, alt=True, wheel=True):
                self.passthrough = True
                return {'PASS_THROUGH'}

            if self.amount and event.type in {'LEFTMOUSE', 'SPACE'} and event.value == 'PRESS':

                self.create_extruded_geo(self.active, self.bm)

                bpy.ops.mesh.intersect_boolean(use_self=self.use_self)
                self.active.update_from_editmode()

                self.finalizing = True
                return {'RUNNING_MODAL'}

            elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
                self.finish(context)
                return {'CANCELLED'}

        else:

            self.is_shift = event.shift
            self.is_ctrl = event.ctrl

            if event.type in ['Q', 'W', 'E', 'R', 'S'] and event.value == 'PRESS':
                self.reset_mesh(self.init_bm)

                bm = bmesh.from_edit_mesh(self.active.data)
                bm.normal_update()

                factor = 100 if self.is_ctrl else 1

                if event.type == 'W':
                    self.pushed += -factor if self.is_shift else factor
                    self.pulled += -factor if self.is_shift else factor

                elif event.type == 'E':
                    self.pushed += -factor if self.is_shift else factor

                elif event.type == 'Q':
                    self.pulled += -factor if self.is_shift else factor

                elif event.type == 'R':
                    self.pushed = 0
                    self.pulled = 0

                elif event.type == 'S':
                    self.use_self = not self.use_self

                self.set_push_and_pull_amount(context)

                self.create_extruded_geo(self.active, bm)

                bpy.ops.mesh.intersect_boolean(use_self=self.use_self)
                self.active.update_from_editmode()

                force_ui_update(context)
                return {'RUNNING_MODAL'}

            elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
                return {'PASS_THROUGH'}

            elif event.type in {'LEFTMOUSE', 'SPACE'} and event.value == 'PRESS':
                self.finish(context)

                return {'FINISHED'}

            elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
                self.reset_mesh(self.init_bm)
                self.finish(context)

                return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        finish_modal_handlers(self)

        finish_status(self)

        self.S.finish()

    def invoke(self, context, event):
        debug = False

        self.active = context.active_object
        self.active.update_from_editmode()

        self.mx = self.active.matrix_world

        self.init_bm = bmesh.new()
        self.init_bm.from_mesh(self.active.data)
        self.init_bm.normal_update()

        self.bm = bmesh.from_edit_mesh(self.active.data)
        self.bm.normal_update()

        self.cache = None

        selection = self.get_selection(self.bm, debug=debug)

        if selection:

            self.data = self.get_data(*selection)

            self.get_exit_coords()

            self.get_extruded_data()

            self.get_side_data()

            if not context.region_data:
                return self.execute(context)

            get_mouse_pos(self, context, event)

            self.amount = 0
            self.setup_extrusion_direction(context, 'AVERAGED')

            if self.init_loc:
                self.prev_mode = 'AVERAGED'

                self.finalizing = False
                self.pushed = 0
                self.pulled = 0

                self.is_edge_picking = False
                self.edge_coords = None

                self.is_shift = False
                self.is_ctrl = False

                self.S = Snap(context, debug=False)

                get_mouse_pos(self, context, event)

                init_status(self, context, func=draw_punchit_status(self))
                force_ui_update(context)

                init_modal_handlers(self, context, hud=True, view3d=True)
                return {'RUNNING_MODAL'}

        return {'CANCELLED'}

    def execute(self, context):
        if self.amount:
            if self.mode == 'EDGE' and not self.data['edge_dir']:
                self.mode = 'AVERAGED'  # avoid EDGE mode when an edge dir was never set

            self.active = context.active_object

            self.bm = bmesh.from_edit_mesh(self.active.data)
            self.bm.normal_update()

            self.set_extrusion_amount(context, amount=self.amount)

            self.set_push_and_pull_amount(context)

            self.create_extruded_geo(self.active, self.bm)

            bpy.ops.mesh.intersect_boolean(use_self=self.use_self)

        return {'FINISHED'}

    def get_mouse_intersection(self, context):
        view_origin = region_2d_to_origin_3d(context.region, context.region_data, self.mouse_pos)
        view_dir = region_2d_to_vector_3d(context.region, context.region_data, self.mouse_pos)

        i = intersect_line_line(self.amount_origin, self.amount_origin + self.amount_dir, view_origin, view_origin + view_dir)

        if i:
            return i[0]

    def get_edge_dir(self, context):
        self.S.get_hit(self.mouse_pos)

        if self.mode != 'EDGE':
            self.prev_mode = self.mode

        if self.S.hit:
            hitmx = self.S.hitmx
            hit_co = hitmx.inverted_safe() @ self.S.hitlocation
            hitface = self.S.hitface

            edge = min([(e, (hit_co - intersect_point_line(hit_co, e.verts[0].co, e.verts[1].co)[0]).length, (hit_co - get_center_between_verts(*e.verts)).length) for e in hitface.edges if e.calc_length()], key=lambda x: (x[1] * x[2]) / x[0].calc_length())
            edge_dir = (edge[0].verts[1].co - edge[0].verts[0].co).normalized()

            self.edge_coords = [hitmx @ v.co for v in edge[0].verts]

            closest_point_on_edge = intersect_point_line(hit_co, edge[0].verts[0].co, edge[0].verts[1].co)[0]

            if self.S.hitobj != self.active:
                edge_dir = self.mx.inverted_safe().to_3x3() @ hitmx.to_3x3() @ edge_dir
                closest_point_on_edge = self.mx.inverted_safe() @ hitmx @ closest_point_on_edge

            dot = edge_dir.dot(self.data['avg_dir'])

            if dot < 0:
                edge_dir.negate()

            if round(dot, 4) == 0:

                self.data['edge_dir'] = None

            elif round(dot, 4) != 0:
                self.data['edge_co'] = closest_point_on_edge
                self.data['edge_dir'] = edge_dir

                self.setup_extrusion_direction(context, direction='EDGE')
                self.set_extrusion_amount(context)
                return

        else:
            self.edge_coords = None
            self.data['edge_dir'] = None

        self.mode = self.prev_mode

        self.setup_extrusion_direction(context, direction=self.mode)
        self.set_extrusion_amount(context)

    def setup_extrusion_direction(self, context, direction='AVERAGED'):
        self.mode = direction

        if direction in ['AVERAGED', 'NORMAL']:

            self.amount_origin = self.mx @ self.data['avg_co']
            self.amount_dir = self.mx.to_3x3() @ self.data['avg_dir']

        elif direction == 'EDGE':

            self.amount_origin = self.mx @ self.data['edge_co']
            self.amount_dir = self.mx.to_3x3() @ self.data['edge_dir']

        i = self.get_mouse_intersection(context)

        self.init_loc = i - self.amount_dir * self.amount
        self.loc = i

        self.get_exit_coords(direction=direction)

    def set_extrusion_amount(self, context, amount=None):
        if not amount:
            amount_vector = (self.loc - self.init_loc)
            self.amount = amount_vector.length if amount_vector.dot(self.amount_dir) > 0 else 0

        if self.amount:
            for vdata in self.data['extruded_verts'].values():

                if self.mode == 'AVERAGED':
                    vdata['co'] = vdata['init_co'] + self.data['avg_dir'] * self.amount
                elif self.mode == 'EDGE':
                    vdata['co'] = vdata['init_co'] + self.data['edge_dir'] * self.amount
                elif self.mode == 'NORMAL':
                    vdata['co'] = vdata['init_co'] + vdata['vert_dir'] * self.amount

        else:
            self.init_loc = self.get_mouse_intersection(context)
            self.loc = self.init_loc

    def set_push_and_pull_amount(self, context):
        data = self.data
        mode = self.mode

        orig_verts = data['original_verts']
        extr_verts = data['extruded_verts']

        push_pull_scale = sqrt(data['area']) * 0.00001

        for vidx, vdata in (orig_verts | extr_verts).items():
            co = vdata['init_co'].copy()

            extr_dir = self.amount * (data['avg_dir'] if mode == 'AVERAGED' else data['edge_dir'] if mode == 'EDGE' else vdata['vert_dir'])

            if vidx in extr_verts:
                co += extr_dir

            if vdata['push_dir'] and self.pushed:
                co += vdata['push_dir'] * push_pull_scale * self.pushed

            if vidx in orig_verts and self.pulled:
                co -= extr_dir.normalized() * push_pull_scale * self.pulled

            vdata['co'] = co

    def reset_mesh(self, init_bm):
        bpy.ops.object.mode_set(mode='OBJECT')
        init_bm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def get_selection(self, bm, debug=False):
        is_manifold = all([e.is_manifold for e in bm.edges])

        if not is_manifold:
            popup_message("Mesh is non-manifold!", title="Fix your shit")
            return

        faces = [f for f in bm.faces if f.select]

        if not faces and (tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (True, False, False) or tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, True, False)):
            verts = [v for v in bm.verts if v.select]

            vert_mode = False

            if tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (True, False, False):
                vert_mode = True
                bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE')

            sequences = get_selected_vert_sequences(verts, ensure_seq_len=True, debug=False)

            if len(sequences):
                seq, cyclic = max(sequences, key=lambda x: len(x[0]))

                if len(sequences) > 1:
                    for s, c in sequences:
                        if s != seq:
                            for idx, v in enumerate(s):
                                if idx != len(s) - 1:
                                    nextv = s[idx + 1]
                                    e = bm.edges.get([v, nextv])
                                    e.select_set(False)

                if not cyclic:
                    path = get_shortest_path(bm, seq[0], seq[-1], topo=True, ignore_selected=True, select=True)

                    for idx, v in enumerate(path):
                        if idx != len(path) - 1:
                            nextv = path[idx + 1]
                            e = bm.edges.get([v, nextv])
                            e.select_set(True)

                bpy.ops.mesh.loop_to_region()
                faces = [f for f in bm.faces if f.select]

                if vert_mode:
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

            else:
                if vert_mode:
                    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')

                popup_message("You need to select at least one edge", title="Illegal Selection!")
                return

        islands = get_selection_islands(faces, debug=debug)

        if not islands:
            popup_message("Select at least one face, duh!", title="Pay attention, numbnuts!")
            return

        faces = max(islands, key=lambda x: len(x[2]))[2]

        if set(faces) == {f for f in bm.faces}:
            popup_message("You can't extrude all faces at once!", title="Illegal Selection!")
            return

        loop_triangles = get_loop_triangles(bm, faces=faces)

        verts = {v for f in faces for v in f.verts}

        boundary = get_boundary_edges(faces)
        boundary_verts = list(set(v for e in boundary for v in e.verts))

        inner_verts = [v for v in verts if v not in boundary_verts]

        sequences = get_edges_vert_sequences(boundary_verts, boundary, debug=debug)

        if len(sequences) > 1:
            popup_message("Face Selection can't be cyclic!", title="Invalid Selection")
            return

        sorted_boundary_verts = sequences[0][0]

        first_edge = bm.edges.get(sorted_boundary_verts[:2])

        for loop in first_edge.link_loops:
            if loop.face in faces:
                if loop.vert != sorted_boundary_verts[0]:
                    sorted_boundary_verts.reverse()

        smallest = min(sorted_boundary_verts, key=lambda x: x.index)

        if smallest != sorted_boundary_verts[0]:
            rotate_list(sorted_boundary_verts, sorted_boundary_verts.index(smallest))

        if debug:
            print()
            print("faces:", [f.index for f in faces])
            print("sorted boundary verts:", [v.index for v in sorted_boundary_verts])
            print("inner verts:", [v.index for v in inner_verts])

        return faces, loop_triangles, sorted_boundary_verts, inner_verts

    def get_data(self, faces, loop_triangles, sorted_boundary_verts, inner_verts):
        data = {'original_verts': {},
                'extruded_verts': {},

                'original_faces': {},
                'extruded_faces': {},
                'side_faces': {},

                'original_tri_indices': [],
                'extruded_tri_indices': [],
                'side_tri_indices': [],

                'sorted_boundary': [],
                'sorted_boundary_indices': [],
                'side_edges': {},

                'vert_map': {},
                'face_map': {},

                'avg_co': average_locations([f.calc_center_median() for f in faces]),
                'avg_dir': -average_normals([f.normal for f in faces]),

                'edge_co': None,
                'edge_dir': None,

                'area': 0}

        seen = {}

        orig_verts = data['original_verts']
        orig_faces = data['original_faces']

        vidx = 0

        for fidx, f in enumerate(faces):
            fdata = []

            for v in f.verts:

                if v not in seen:

                    seen[v] = vidx

                    orig_verts[vidx] = {'co': v.co.copy(),
                                        'init_co': v.co.copy(),
                                        'exit_co': None,

                                        'vert_dir': -average_normals([f.normal for f in v.link_faces if f in faces]),
                                        'push_dir': None,

                                        'bound_idx': -1 if v in inner_verts else sorted_boundary_verts.index(v)}

                    fdata.append(vidx)

                    vidx += 1

                else:
                    fdata.append(seen[v])

            orig_faces[fidx] = fdata

            data['area'] += f.calc_area()

        data['original_tri_indices'] = [seen[l.vert] for lt in loop_triangles for l in lt]

        sorted_boundary = [seen[v] for v in sorted_boundary_verts]
        data['sorted_boundary'] = sorted_boundary
        data['sorted_boundary_indices'] = [(idx, (idx + 1) % len(sorted_boundary)) for idx, _ in enumerate(sorted_boundary)]

        for idx, vidx in enumerate(sorted_boundary):
            v_co = orig_verts[vidx]['co']
            vert_dir = orig_verts[vidx]['vert_dir']

            next_vidx = sorted_boundary[(idx + 1) % len(sorted_boundary)]
            prev_vidx = sorted_boundary[(idx - 1) % len(sorted_boundary)]

            fwd_co = v_co + (orig_verts[next_vidx]['co'] - v_co).normalized()
            bwd_co = v_co + (orig_verts[prev_vidx]['co'] - v_co).normalized()

            fwd_dir = (fwd_co - bwd_co).normalized()
            push_dir = vert_dir.cross(fwd_dir)

            data['original_verts'][vidx]['push_dir'] = push_dir

        return data

    def get_exit_coords(self, direction='AVERAGED'):
        self.cache = None
        offset = sqrt(self.data['area']) * 0.00001

        if direction == 'AVERAGED':
            direction = self.data['avg_dir']

        elif direction == 'EDGE':
            direction = self.data['edge_dir']

        else:
            direction = None

        for idx in self.data['sorted_boundary']:
            vdata = self.data['original_verts'][idx]
            ray_dir = direction if direction else vdata['vert_dir']

            ray_origin = vdata['init_co'] - vdata['push_dir'] * offset + ray_dir * offset

            _, hitloc, _, _, _, self.cache = cast_bvh_ray_from_point(ray_origin, direction=ray_dir, cache=self.cache, candidates=[self.active], debug=False)

            if hitloc:
                vdata['exit_co'] = hitloc

    def get_extruded_data(self):
        data = self.data

        vert_len = len(data['original_verts'])
        face_len = len(data['original_faces'])

        for vidx, vdata in data['original_verts'].items():

            extr_vdata = vdata.copy()

            extr_vidx = vidx + vert_len

            data['extruded_verts'][extr_vidx] = extr_vdata

            data['vert_map'][vidx] = extr_vidx
            data['vert_map'][extr_vidx] = vidx

        for fidx, fdata in data['original_faces'].items():

            extr_fidx = fidx + face_len

            extr_fdata = [data['vert_map'][vidx] for vidx in fdata]

            data['extruded_faces'][extr_fidx] = extr_fdata

            data['face_map'][fidx] = extr_fidx
            data['face_map'][extr_fidx] = fidx

        data['extruded_tri_indices'] = [data['vert_map'][idx] for idx in data['original_tri_indices']]

    def get_side_data(self):
        data = self.data

        sorted_boundary = data['sorted_boundary']

        face_idx = len(data['original_faces']) + len(data['extruded_faces'])

        for idx, vidx in enumerate(sorted_boundary):
            extr_vidx = data['vert_map'][vidx]

            next_vidx = sorted_boundary[(idx + 1) % len(sorted_boundary)]
            next_extr_vidx = data['vert_map'][next_vidx]

            data['side_faces'][face_idx] = [vidx, extr_vidx, next_extr_vidx, next_vidx]
            face_idx += 1

            data['side_tri_indices'].extend([vidx, extr_vidx, next_extr_vidx, vidx, next_extr_vidx, next_vidx])

    def debug_data(self, context, debug=False):
        data = self.data

        printd(data)

        sorted_boundary = data['sorted_boundary']
        bound_len = len(sorted_boundary)

        avg_dir = data['avg_dir']
        edge_dir = data['edge_dir']

        draw_point(data['avg_co'], mx=self.mx, color=yellow, modal=False)

        if edge_dir:
            draw_vector(edge_dir * 0.5, origin=data['avg_co'], mx=self.mx, color=blue, modal=False)

        if data['original_verts']:

            for v in data['original_verts'].values():
                co = v['co']
                vert_dir = v['vert_dir']
                push_dir = v['push_dir']
                bidx = v['bound_idx']

                draw_point(co, mx=self.mx, color=red if bidx == -1 else (0, bidx / (bound_len - 1), 0), modal=False)
                draw_vector(vert_dir * 0.3, origin=co + (vert_dir * 0.02), mx=self.mx, color=green, modal=False)
                draw_vector(avg_dir * 0.2, origin=co + (avg_dir * 0.02), mx=self.mx, color=yellow, modal=False)

                if edge_dir:
                    draw_vector(edge_dir * 0.1, origin=co + (edge_dir * 0.02), mx=self.mx, color=blue, modal=False)

                if push_dir:
                    draw_vector(push_dir * 0.1, origin=co + push_dir * 0.02, mx=self.mx, color=red, modal=False)

            coords = [data['original_verts'][idx]['co'] for idx in data['original_tri_indices']]
            draw_tris(coords, mx=self.mx, color=green, alpha=0.1, modal=False)

            exit_coords = [data['original_verts'][vidx]['exit_co'] for vidx in data['sorted_boundary'] if data['original_verts'][vidx]['exit_co']]

            if exit_coords:
                exit_coords.append(exit_coords[0])
                draw_line(exit_coords, mx=self.mx, color=red, modal=False)

        if data['extruded_verts']:

            coords = [data['extruded_verts'][data['vert_map'][vidx]]['co'] for vidx in data['sorted_boundary']]
            draw_line(coords, indices=data['sorted_boundary_indices'], mx=self.mx, color=blue, modal=False)

            for v in data['extruded_verts'].values():
                co = v['co']
                vert_dir = v['vert_dir']
                push_dir = v['push_dir']
                bidx = v['bound_idx']

                draw_point(co, mx=self.mx, color=red if bidx == -1 else (0, 0, bidx / (bound_len - 1)), modal=False)
                draw_vector(vert_dir * 0.3, origin=co + (vert_dir * 0.02), mx=self.mx, color=green, modal=False)
                draw_vector(avg_dir * 0.2, origin=co + (avg_dir * 0.02), mx=self.mx, color=yellow, modal=False)

                if edge_dir:
                    draw_vector(edge_dir * 0.1, origin=co + (edge_dir * 0.02), mx=self.mx, color=blue, modal=False)

                if push_dir:
                    draw_vector(push_dir * 0.1, origin=co + push_dir * 0.02, mx=self.mx, color=red, modal=False)

            coords = [data['extruded_verts'][idx]['co'] for idx in data['extruded_tri_indices']]
            draw_tris(coords, mx=self.mx, color=blue, alpha=0.1, modal=False)

        if data['side_faces']:

            for idx, (fidx, fdata) in enumerate(data['side_faces'].items()):

                all_verts = data['original_verts'] | data['extruded_verts']

                face_center = average_locations([all_verts[idx]['co'] for idx in fdata])

                gradient = idx / (len(data['side_faces']) - 1)
                draw_point(face_center, mx=self.mx, color=(gradient, gradient, 0), size=10, modal=False)

            coords = [(data['original_verts'] | data['extruded_verts'])[idx]['co'] for idx in data['side_tri_indices']]
            draw_tris(coords, mx=self.mx, color=yellow, alpha=0.1, modal=False)

        context.area.tag_redraw()

    def create_extruded_geo(self, active, bm):
        data = self.data

        vert_map = {}
        face_map = {}
        faces = []

        for vidx, vdata in (data['original_verts'] | data['extruded_verts']).items():
            v = bm.verts.new(vdata['co'])
            vert_map[vidx] = v

        for fidx, indices in (data['original_faces'] | data['extruded_faces'] | data['side_faces']).items():
            verts = [vert_map[vidx] for vidx in indices]

            f = bm.faces.new(verts)
            face_map[fidx] = f
            faces.append(f)

        bmesh.ops.recalc_face_normals(bm, faces=faces)

        bpy.ops.mesh.select_all(action='DESELECT')

        for f in faces:
            f.select_set(True)

        bmesh.update_edit_mesh(active.data)

class CursorSpin(bpy.types.Operator):
    bl_idname = "machin3.cursor_spin"
    bl_label = "MACHIN3: Cursor Spin"
    bl_description = "Cursor Spin"
    bl_options = {'REGISTER', 'UNDO'}

    def update_angle(self, context):
        if self.angle_preset != 'None' and self.angle != int(self.angle_preset):
            self.avoid_update = True
            self.angle_preset = 'None'

    def update_angle_preset(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.angle_preset != 'None':
            self.angle = int(self.angle_preset)

    def update_offset_reset(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        self.offset = 0

        self.avoid_update = True
        self.offset_reset = False

    angle: FloatProperty(name='Angle', default=45, min=0, update=update_angle)
    angle_preset: EnumProperty(name='Angle Preset', items=cursor_spin_angle_preset_items, default='45', update=update_angle_preset)
    angle_invert: BoolProperty(name='Invert', default=False)
    steps: IntProperty(name='Steps', default=4, min=1)
    adaptive: BoolProperty(name="Adaptive Steps", default=True)
    adaptive_factor: FloatProperty(name="Adaptive Factor", default=0.1, step=0.05)
    axis: EnumProperty(name='Axis', description='Cursor Axis', items=axis_items, default='Y')
    offset: FloatProperty(name='Offset', default=0, step=0.1)
    offset_reset: BoolProperty(name='Offset Reset', default=False, update=update_offset_reset)
    avoid_update: BoolProperty()

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        row = column.row(align=True)
        r = row.row(align=True)
        r.scale_y = 1.2
        r.prop(self, 'angle_preset', expand=True)
        row.prop(self, 'angle_invert', toggle=True)

        row = column.split(factor=0.4, align=True)
        row.prop(self, 'angle')

        r = row.split(factor=0.6, align=True)

        if self.adaptive:
            r.prop(self, 'adaptive_factor', text='Factor')
        else:
            r.prop(self, 'steps')

        r.prop(self, 'adaptive', text='Adaptive', toggle=True)

        column.separator()

        row = column.split(factor=0.5, align=True)

        r = row.row(align=True)
        r.prop(self, 'axis', expand=True)

        r = row.row(align=True)
        r.prop(self, 'offset')
        r.prop(self, 'offset_reset', text='', icon='LOOP_BACK', toggle=True)

    def execute(self, context):
        debug = False

        if self.angle:
            cmx = context.scene.cursor.matrix
            mx = context.active_object.matrix_world

            angle = radians(-self.angle if self.angle_invert else self.angle)

            axis = cmx.to_quaternion() @ axis_vector_mappings[self.axis]

            center = cmx.to_translation()

            bm = bmesh.from_edit_mesh(context.active_object.data)
            verts = [v for v in bm.verts if v.select]

            if verts:
                center_sel = mx @ average_locations([v.co for v in verts])
                if debug:
                    draw_point(center_sel, modal=False)

                i = intersect_point_line(center_sel, center, center + axis)

                if i:
                    closest_on_axis = i[0]
                    if debug:
                        draw_point(closest_on_axis, color=yellow, modal=False)

                    offset_vector = (closest_on_axis - center_sel).normalized()
                    if debug:
                        draw_vector(offset_vector, closest_on_axis, color=yellow, modal=False)

                    center = center + offset_vector * self.offset
                    if debug:
                        draw_point(center, color=blue, modal=False)

                    faces = [f for f in bm.faces if f.select]

                    avg_normal = average_normals([f.normal for f in faces])

                    cross = offset_vector.cross(avg_normal)
                    if debug:
                        draw_vector(cross, origin=center, color=red, modal=False)

                    dot = cross.dot(axis)

                    if dot < 0:
                        angle = -angle

                if debug:
                    context.area.tag_redraw()

            if self.adaptive:
                steps = max([int(self.angle * self.adaptive_factor), 1])

            else:
                steps = self.steps

            bpy.ops.mesh.spin(angle=angle, steps=steps, center=center, axis=axis)
        return {'FINISHED'}
