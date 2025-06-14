import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty
from bpy_extras.view3d_utils import location_3d_to_region_2d
import bmesh
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from mathutils import Vector
from mathutils.geometry import intersect_point_line, intersect_line_line, intersect_line_plane, intersect_ray_tri
from .. utils.bmesh import ensure_custom_data_layers
from .. utils.snap import Snap
from .. utils.draw import draw_point, draw_line, draw_vector, draw_lines, draw_points
from .. utils.property import rotate_list
from .. utils.ui import init_status, finish_status, popup_message
from .. utils.system import printd
from .. utils.registration import get_addon
from .. utils.data import get_wedge_data
from .. colors import white, red, blue, green, yellow, black

hypercursor = None

def draw_wedge(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text='Wedge')

        if not op.setting_depth:
            row.label(text="", icon='MOUSE_MOVE')
            row.label(text="Define Wedge Area")

        row.label(text="", icon='MOUSE_LMB_DRAG')
        row.label(text="Define Wedge Depth")

        if op.can_flip:
            row.label(text="", icon='EVENT_F')
            row.label(text="Flip Wedge Direction")

        if op.depth_dir:
            row.label(text="", icon='EVENT_E')
            row.label(text=f"Planar Wedge Quad: {op.planar_wedge_quad}")

            row.label(text="", icon='EVENT_W')
            row.label(text=f"Redefine Wedge Area")
            row.label(text="", icon='MOUSE_LMB')
            row.label(text="Finish")

        else:

            row.label(text="", icon='EVENT_S')
            row.label(text=f"Slide Wedge Corner: {op.sliding_wedge_corner}")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")
    return draw

class Wedge(bpy.types.Operator):
    bl_idname = "machin3.wedge"
    bl_label = "MACHIN3: Wedge"
    bl_description = "Create Wedge from Edge Selection"
    bl_options = {'REGISTER', 'UNDO'}

    planar_wedge_quad: BoolProperty(name="Planar Wedge Quad", default=True)
    flip: BoolProperty(name="Flip Wedge Direction", default=False)
    depth_amount: FloatProperty(name="Depth Amount", step=0.1)
    slide_amount: FloatProperty(name="Slide Amount", step=0.1)

    index: IntProperty(name="Edge Index")

    passthrough = False

    @classmethod
    def poll(cls, context):
        if context.active_object:
            return context.mode in ['EDIT_MESH', 'OBJECT']

    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        row = column.row(align=True)
        row.prop(self, 'depth_amount')
        row.prop(self, 'slide_amount')

        row = column.row(align=True)
        row.prop(self, 'planar_wedge_quad', toggle=True)

        r = row.row(align=True)
        r.active = self.can_flip
        r.prop(self, 'flip', toggle=True)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.wedge_corner:

                draw_line(self.wedge_axis_coords, mx=self.mx, color=yellow, width=2, alpha=0.99)

                draw_points(self.wedge_axis_dots_coords, mx=self.mx, color=yellow, size=3)

                draw_line(self.wedge_width_coords, mx=self.mx, color=black, width=1.5, alpha=0.99)

                draw_line(self.wedge_length_coords, mx=self.mx, color=green, alpha=0.99)

                if self.depth_dir:
                    draw_lines(self.wedge_depth_on_end_face_coords, mx=self.mx, color=blue, alpha=0.99)
                    draw_lines(self.wedge_side_coords, mx=self.mx, color=white if self.planar_wedge_quad else red, alpha=0.5)

    def modal(self, context, event):
        context.area.tag_redraw()

        self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))

        events = ['MOUSEMOVE', 'E', 'S']

        if self.can_flip:
            events.append('F')

        if self.setting_depth:
            events.append('W')

        if event.type in events:
            if event.type == 'MOUSEMOVE':
                if self.setting_depth:
                    self.get_wedge_depth(context)

                    if self.depth_dir:
                        self.get_end_area()

                elif self.sliding_wedge_corner:
                    self.S.get_hit(self.mouse_pos)

                    if self.S.hit and self.S.hitindex in self.data['side_faces']:
                        self.slide_wedge_corner(self.S.hitlocation)

                else:
                    self.S.get_hit(self.mouse_pos)

                    if self.S.hit and self.S.hitindex in self.data['side_faces']:
                        self.get_wedge_area(self.S.hitindex, self.S.hitlocation, self.S.hitnormal)

                self.get_view3d_coords()

            elif event.type == 'S' and event.value == 'PRESS':
                self.sliding_wedge_corner = not self.sliding_wedge_corner
                context.active_object.select_set(True)

                if not self.sliding_wedge_corner:
                    self.slide_dir = Vector()
                    self.slide_amount = 0

                    self.S.get_hit(self.mouse_pos)

                    if self.S.hit and self.S.hitindex in self.data['side_faces']:
                        self.get_wedge_area(self.S.hitindex, self.S.hitlocation, self.S.hitnormal)

                        self.get_view3d_coords()

            elif event.type in ['E', 'F'] and event.value == 'PRESS':

                if event.type == 'E' and event.value == 'PRESS':
                    self.planar_wedge_quad = not self.planar_wedge_quad

                    context.active_object.select_set(True)

                elif event.type == 'F' and event.value == 'PRESS':
                    self.flip = not self.flip

                    self.get_wedge_area(self.S.hitindex, self.S.hitlocation, self.S.hitnormal)

                if self.setting_depth:
                    self.get_wedge_depth(context)

                    if self.depth_dir:
                        self.get_end_area()

                self.get_view3d_coords()

            elif event.type == 'W' and event.value == 'PRESS':
                self.setting_depth = False
                self.depth_dir = None
                self.sliding_wedge_corner = False
                self.slide_dir = Vector()
                self.slide_amount = 0
                self.is_statusbar_updated = False

                self.S.get_hit(self.mouse_pos)

                if self.S.hit and self.S.hitindex in self.data['side_faces']:
                    self.get_wedge_area(self.S.hitindex, self.S.hitlocation, self.S.hitnormal)
                    self.get_view3d_coords()

                context.active_object.select_set(True)

        elif event.type == 'MIDDLEMOUSE':
            return {'PASS_THROUGH'}

        elif self.S.hit and self.S.hitindex in self.data['side_faces'] and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.setting_depth = True

            context.active_object.select_set(True)

        if self.depth_dir and (event.type == 'SPACE' or (event.type == 'LEFTMOUSE' and event.value == 'RELEASE')):
            self.finish(context)
            return self.execute(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

        self.S.finish()

        if context.mode == 'OBJECT':

            for mod, state in self.mods:
                mod.show_viewport = state

    def invoke(self, context, event):
        global hypercursor

        if context.mode == 'OBJECT':
            if hypercursor is None:
                hypercursor = get_addon('HyperCursor')[0]

        self.active = context.active_object
        self.mx = self.active.matrix_world

        self.data = get_wedge_data(context, self.index)

        if self.data:

            if context.mode == 'OBJECT' and hypercursor:
                wm = context.window_manager

                context.window.cursor_warp(int(wm.HC_mouse_pos[0]), int(wm.HC_mouse_pos[1]))
                self.mouse_pos = Vector(wm.HC_mouse_pos_region)

            else:
                self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))

            if context.mode == 'OBJECT':
                self.mods = [(mod, mod.show_viewport) for mod in self.active.modifiers]

                for mod, _ in self.mods:
                    mod.show_viewport = False

            self.S = Snap(context, include=[self.active], debug=False)

            self.count = 0

            self.flip = False
            self.can_flip = self.data['end1']['face'] is not None and self.data['end2']['face'] is not None

            self.sliding_wedge_corner = False
            self.setting_depth = False

            self.hitindex = None
            self.hitlocation = None
            self.hitnormal = None

            self.wedge_corner = None
            self.slide_dir = Vector()
            self.slide_amount = 0

            self.edge_intersection = None
            self.end_edge_intersection = None
            self.end_other_edge_intersection = None
            self.end_face_intersection = None

            self.depth_dir = None
            self.depth_amount = 0

            self.wedge_axis_coords = []
            self.wedge_axis_dots_coords = []
            self.wedge_width_coords = []
            self.wedge_length_coords = []
            self.wedge_depth_on_end_face_coords = []
            self.wedge_side_coords = []

            init_status(self, context, func=draw_wedge(self))
            context.active_object.select_set(True)
            self.is_statusbar_updated = False

            self.area = context.area
            self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

        popup_message('Make sure to select a single, manifold edge, with at least one end leading to exactly 2 other edges!', title='Invalid Selection')

        return {'CANCELLED'}

    def execute(self, context):
        global hypercursor

        if self.count:
            self.get_wedge_area(self.hitindex, self.hitlocation, self.hitnormal)
            self.get_end_area()

        self.create_wedge_geometry(context, self.S.hitindex, debug=False)

        if context.mode == 'OBJECT':
            if hypercursor:
                from HyperCursor.utils.ui import force_geo_gizmo_update

                force_geo_gizmo_update(context)

        self.count += 1
        return {'FINISHED'}

    def get_end(self):
        if self.can_flip:
            if self.flip:
                return 'end2'
            else:
                return 'end1'

        elif self.data['end1']['face'] is not None:
            return 'end1'

        elif self.data['end2']['face'] is not None:
            return 'end2'

    def get_wedge_area(self, faceidx, location, normal):
        mx = self.data['mx']
        edge_coords = [mx @ co for co in self.data['edge_coords']]

        closest_on_edge, _ = intersect_point_line(location, *edge_coords)

        self.hitindex = faceidx
        self.hitlocation = location
        self.hitnormal = normal

        self.wedge_corner = mx.inverted_safe() @ location
        self.edge_intersection = mx.inverted_safe() @ closest_on_edge

        end_edge_coords = [mx @ co for co in self.data[self.get_end()]['edge_coords'][faceidx]]
        edge_dir = edge_coords[1] - edge_coords[0]

        _, closest_on_edge = intersect_line_line(location, location + edge_dir, *end_edge_coords)

        self.end_edge_intersection = self.mx.inverted_safe() @ closest_on_edge

        if self.slide_dir == Vector():
            self.slide_dir = (self.end_edge_intersection - self.wedge_corner).normalized()

    def slide_wedge_corner(self, location):
        wedge_dir_coords = [self.wedge_corner, self.end_edge_intersection]

        closest_on_wedge_dir, _ = intersect_point_line(self.mx.inverted_safe() @ location, *wedge_dir_coords)

        slide_dir = closest_on_wedge_dir - self.wedge_corner

        self.slide_dir = slide_dir.normalized()
        self.slide_amount = slide_dir.length

    def get_wedge_depth(self, context):
        hitlocation = self.hitlocation + (self.slide_dir * self.slide_amount)

        normal_coords = [hitlocation, hitlocation + self.hitnormal]

        view_origin = region_2d_to_origin_3d(context.region, context.region_data, self.mouse_pos)
        view_dir = region_2d_to_vector_3d(context.region, context.region_data, self.mouse_pos)

        closest_on_normal, _ = intersect_line_line(*normal_coords, view_origin, view_origin + view_dir)

        depth_dir = self.mx.inverted_safe().to_quaternion() @ (closest_on_normal - hitlocation)

        self.depth_dir = depth_dir.normalized()

        self.depth_amount = depth_dir.length

        if not self.is_statusbar_updated:
            context.active_object.select_set(True)
            self.is_statusbar_updated = True

    def get_end_area(self):
        end = self.get_end()
        end_face_normal = self.data[end]['face_no']

        edge_dir = self.data['edge_coords'][1] - self.data['edge_coords'][0]
        intersector = [self.end_edge_intersection + self.depth_dir * self.depth_amount, self.end_edge_intersection + self.depth_dir * self.depth_amount + edge_dir]

        i = intersect_line_plane(*intersector, self.end_edge_intersection, end_face_normal)

        if i:
            self.end_face_intersection = i
            end_other_edge_coords = self.data[end]['other_edge_coords'][self.hitindex]

            if self.planar_wedge_quad:
                wedge_corner = self.wedge_corner + self.slide_dir * self.slide_amount

                tri_v1= (self.edge_intersection - wedge_corner).normalized()
                tri_v2= (self.end_face_intersection - wedge_corner).normalized()
                tri_no = tri_v1.cross(tri_v2)

                i = intersect_line_plane(*end_other_edge_coords, wedge_corner, tri_no)

                if i:
                    self.end_other_edge_intersection = i

            else:
                end_edge_coords = self.data[end]['edge_coords'][self.hitindex]
                end_edge_dir = (end_edge_coords[1] - end_edge_coords[0]).normalized()

                _, i = intersect_line_line(self.end_face_intersection, self.end_face_intersection + end_edge_dir, *end_other_edge_coords)

                if i:
                    self.end_other_edge_intersection = i

    def get_view3d_coords(self):
        if self.wedge_corner:
            end = self.get_end()

            wedge_corner = self.wedge_corner + self.slide_dir * self.slide_amount

            self.wedge_axis_coords = [wedge_corner, self.edge_intersection]
            self.wedge_axis_dots_coords = [self.wedge_axis_coords[0] + (self.wedge_axis_coords[0] - self.wedge_axis_coords[1]) * 0.2, self.wedge_axis_coords[1] - (self.wedge_axis_coords[0] - self.wedge_axis_coords[1]) * 0.2]

            self.wedge_width_coords = [self.data[end]['vert_co'], self.end_edge_intersection]
            self.wedge_length_coords = [wedge_corner, self.end_edge_intersection]

            if self.depth_dir:
                end_vert_co = self.data[end]['vert_co']

                self.wedge_depth_on_end_face_coords = [self.end_edge_intersection, self.end_face_intersection]
                self.wedge_depth_on_end_face_coords.extend([end_vert_co, self.end_other_edge_intersection])
                self.wedge_depth_on_end_face_coords.extend([self.end_face_intersection, self.end_other_edge_intersection])

                self.wedge_side_coords = [wedge_corner, self.end_face_intersection]
                self.wedge_side_coords.extend([self.edge_intersection, self.end_other_edge_intersection])

    def create_wedge_geometry(self, context, faceidx, debug=False):
        global hypercursor

        active = context.active_object

        if context.mode == 'OBJECT':
            bm = bmesh.new()
            bm.from_mesh(active.data)

        else:
            bm = bmesh.from_edit_mesh(active.data)

        bm.normal_update()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        bw = ensure_custom_data_layers(bm)[1]

        edge_glayer = bm.edges.layers.int.get('HyperEdgeGizmo')
        face_glayer = bm.faces.layers.int.get('HyperFaceGizmo')

        edge = bm.edges[self.data['edge']]
        end = self.get_end()

        if debug:
            print()
            print("edge:", edge)
            print(" end:", end)

        side_face = bm.faces[faceidx]
        other_side_face = [bm.faces[idx] for idx in self.data['side_faces'] if idx != faceidx][0]
        end_face = bm.faces[(self.data[end]['face'])]

        if debug:
            print("     face index:", faceidx)
            print("      side face:", side_face)
            print("other side face:", other_side_face)
            print("       end face:", end_face)

        side_face_verts = [v for v in side_face.verts]
        other_side_face_verts = [v for v in other_side_face.verts]
        end_face_verts = [v for v in end_face.verts]

        end_vert = bm.verts[self.data[end]['vert']]

        idx = side_face_verts.index(end_vert)

        if idx != 0:
            rotate_list(side_face_verts, idx)

        idx = other_side_face_verts.index(end_vert)

        if idx != 0:
            rotate_list(other_side_face_verts, idx)

        idx = end_face_verts.index(end_vert)

        if idx != 0:
            rotate_list(end_face_verts, idx)

        loop = [l for l in edge.link_loops if l.face == side_face][0]
        loop_vert_is_end = loop.vert == end_vert

        if debug:
            print()
            print("       end vert:", end_vert.index)
            print("      side_face:", side_face)
            print("          verts:", [v.index for v in side_face_verts])
            print("other_side_face:", other_side_face)
            print("          verts:", [v.index for v in other_side_face_verts])
            print("       end_face:", end_face)
            print("          verts:", [v.index for v in end_face_verts])
            print(" loop is corner:", loop_vert_is_end)

        edge_vert = bm.verts.new(self.edge_intersection)
        wedge_corner_vert = bm.verts.new(self.wedge_corner + self.slide_dir * self.slide_amount)
        end_edge_vert = bm.verts.new(self.end_edge_intersection)
        end_face_vert = bm.verts.new(self.end_face_intersection)

        if debug:
            edge_vert.select_set(True)
            wedge_corner_vert.select_set(True)
            end_edge_vert.select_set(True)
            end_face_vert.select_set(True)

            bm.verts.index_update()

        for v in side_face.verts:
            v.select_set(True)

        side_face_verts.remove(end_vert)

        if loop_vert_is_end:
            side_face_verts.insert(0, edge_vert)
            side_face_verts.insert(0, wedge_corner_vert)
            side_face_verts.insert(0, end_edge_vert)

        else:
            side_face_verts.insert(0, end_edge_vert)
            side_face_verts.insert(0, wedge_corner_vert)
            side_face_verts.insert(0, edge_vert)

        if debug:
            print("new side face verts:", [v.index for v in side_face_verts])

        side_face.hide_set(True)
        new_side_face = bm.faces.new(side_face_verts)
        new_side_face.smooth = side_face.smooth

        for v in other_side_face.verts:
            v.select_set(True)

        if loop_vert_is_end:
            other_side_face_verts.insert(0, edge_vert)

        else:
            other_side_face_verts.insert(1, edge_vert)

        if debug:
            print("new other side face verts:", [v.index for v in other_side_face_verts])

        other_side_face.hide_set(True)
        new_other_side_face = bm.faces.new(other_side_face_verts)
        new_other_side_face.smooth = other_side_face.smooth

        end_vert.co = self.end_other_edge_intersection

        for v in end_face.verts:
            v.select_set(True)

        if loop_vert_is_end:
            end_face_verts.insert(1, end_face_vert)
            end_face_verts.insert(2, end_edge_vert)

        else:
            end_face_verts.insert(0, end_face_vert)
            end_face_verts.insert(0, end_edge_vert)

        if debug:
            print("new end face verts:", [v.index for v in end_face_verts])

        end_face.hide_set(True)
        new_end_face = bm.faces.new(end_face_verts)
        new_end_face.smooth = end_face.smooth

        if loop_vert_is_end:
            wedge_tri = bm.faces.new([wedge_corner_vert, end_edge_vert, end_face_vert])
            wedge_quad = bm.faces.new([end_vert, edge_vert, wedge_corner_vert, end_face_vert])

        else:
            wedge_tri = bm.faces.new([wedge_corner_vert, end_face_vert, end_edge_vert])
            wedge_quad = bm.faces.new([end_vert, end_face_vert, wedge_corner_vert, edge_vert])

        wedge_tri.smooth = new_side_face.smooth
        wedge_quad.smooth = new_side_face.smooth

        axis_edge = bm.edges.get([edge_vert, wedge_corner_vert])
        length_edge = bm.edges.get([wedge_corner_vert, end_edge_vert])
        wedge_edge1 = bm.edges.get([edge_vert, end_vert])
        wedge_edge2 = bm.edges.get([wedge_corner_vert, end_face_vert])
        end_face_edge1 = bm.edges.get([end_edge_vert, end_face_vert])
        end_face_edge2 = bm.edges.get([end_vert, end_face_vert])

        edges = [axis_edge, length_edge, wedge_edge1, wedge_edge2, end_face_edge1, end_face_edge2]
        connected_edges = [e for v in [edge_vert, end_edge_vert] for e in v.link_edges if e not in edges]

        for e in edges + connected_edges:
            e.smooth = not self.data['edge_sharp']
            e[bw] = self.data['edge_bw']

            if edge_glayer:
                e[edge_glayer] = 1

        if face_glayer:
            for f in [new_side_face, new_other_side_face, new_end_face, wedge_tri, wedge_quad]:
                f[face_glayer] = 1

        bmesh.ops.delete(bm, geom=[side_face, other_side_face, end_face], context='FACES')

        bm.normal_update()

        if context.mode == 'OBJECT':
            bm.to_mesh(active.data)
            bm.free()

            active.select_set(True)

        else:
            bmesh.update_edit_mesh(active.data)
