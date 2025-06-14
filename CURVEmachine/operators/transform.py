import bpy
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, location_3d_to_region_2d
from mathutils import Vector
from mathutils.geometry import intersect_line_line
from .. utils.curve import get_curve_as_dict, get_curve_selection
from .. utils.system import printd
from .. utils.draw import draw_vector, draw_point, draw_init, draw_label, draw_line
from .. utils.ui import get_zoom_factor, init_status, finish_status, ignore_events, get_mouse_pos
from .. colors import red, green, yellow
from .. items import shift, alt

def draw_slide_point_status(op):
    def draw(self, context):
        layout = self.layout

        seg = op.data['slide_segment']
        locked = op.data['locked']

        row = layout.row(align=True)

        row.label(text="Slide Point")

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Confirm")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        row.label(text="", icon='MOUSE_MOVE')
        row.label(text="Slide")

        row.separator(factor=2)

        row.label(text="", icon='EVENT_SHIFT')
        row.label(text=f"Precision: {op.is_shift}")

        if seg and op.data['prev_dir'] and op.data['next_dir']:
            row.separator(factor=2)

            row.label(text="", icon='EVENT_ALT')
            row.label(text=f"Locked: {bool(locked)}")
        
    return draw

class SlidePoint(bpy.types.Operator):
    bl_idname = "machin3.slide_point"
    bl_label = "MACHIN3: Slide Point"
    bl_description = "Slide Single Curve Point on its connected Segment(s)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            curve = active.data
            data = get_curve_as_dict(curve)
            selection = get_curve_selection(data)

            if len(selection) == 1:
                sidx, pidx = selection.pop()

                splinelen = len(curve.splines[sidx].points)
                return splinelen > 1

    def draw_HUD(self, context):
        if context.area == self.area:
            data = self.data
            seg = data['slide_segment']
            locked = data['locked']

            draw_init(self)

            title = f"Slide Point {'🔒 ' if locked else ''}"
            dims = draw_label(context, title=title, coords=Vector((self.HUD_x, self.HUD_y)), center=False, alpha=1)

            if self.is_shift:
                draw_label(context, title="a little", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), center=False, size=10, alpha=0.5,)

            if seg and data['prev_dir'] and data['next_dir']:
                self.offset += 18
                segment = locked if locked else seg
                segment = segment.replace('prev', 'previous')

                dims = draw_label(context, title="on ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)
                dims2 = draw_label(context, title=f"{segment} ", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, color=green, alpha=1)

                if locked:
                    dims3 = draw_label(context, title="locked ", coords=Vector((self.HUD_x + dims[0] + dims2[0], self.HUD_y)), offset=self.offset, center=False, color=yellow, alpha=1)
                else:
                    dims3 = (0, 0)

                draw_label(context, title="Segment ", coords=Vector((self.HUD_x + dims[0] + dims2[0] + dims3[0], self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            data = self.data

            draw_point(data['point_co'], size=4, alpha=0.3)

            if data['prev_point_co']:
                draw_line([data['point_co'], data['prev_point_co']], alpha=0.2)

            if data['next_point_co']:
                draw_line([data['point_co'], data['next_point_co']], alpha=0.2)

            seg = data['slide_segment']
            locked = data['locked']

            if seg:
                length = self.zoom * 20 * context.preferences.system.ui_scale

                dir = (data[f'{locked if locked else seg}_point_co'] - data['point_co']).normalized()
                draw_vector(dir * length, origin=data['point_co'], color=green, width=2, alpha=0.75, fade=True)

                if seg and data['prev_dir'] and data['next_dir']:
                    if locked:
                        dir = (data['locked_coords'][1] - data['locked_coords'][0]).normalized()
                        draw_vector(dir * length, origin=data['point_co'], color=yellow, width=2, alpha=0.75, fade=True)

                else:
                    draw_vector(-dir * length, origin=data['point_co'], color=green, width=2, alpha=0.75, fade=True)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        self.is_shift = event.shift
        self.is_alt = event.alt

        if self.is_g_invoked:

            if self.data['prev_dir'] and self.data['next_dir']:
                seg = self.data['slide_segment']

                if self.is_alt and seg and not self.data['locked']:
                    self.data['locked'] = seg
                    self.data['locked_coords'] = [self.data['point_co'], self.data['point_co'] + self.data['point_co'] - self.data[f'{seg}_point_co']]

                elif self.data['locked'] and not self.is_alt:
                    self.data['locked'] = None
                    self.data['locked_coords'] = []

            if event.type in ['MOUSEMOVE', *shift, *alt]:
                get_mouse_pos(self, context, event)

                self.slide_point(context)

            if event.type in ['SPACE', 'LEFTMOUSE']:
                self.finish(context)
                return {'FINISHED'}

            elif event.type in ['ESC', 'RIGHTMOUSE']:
                self.finish(context)

                self.data['point'].co.xyz = self.data['point_co_local']

                return {'CANCELLED'}

        elif not ignore_events(event):
            
            if event.type == 'G':
                if event.value == 'PRESS':
                    self.initiate_sliding(context, event)

            else:
                if event.type in ['X', 'Y', 'Z']:
                    bpy.ops.transform.translate('INVOKE_DEFAULT', constraint_axis=(event.type =='X', event.type == 'Y', event.type == 'Z'))

                else:
                    bpy.ops.transform.translate('INVOKE_DEFAULT')
                return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        self.active = context.active_object
        self.curve = self.active.data
        self.mx = self.active.matrix_world

        self.is_shift = False
        self.is_alt = False

        self.data = self.get_data(context, debug=False)

        self.zoom = get_zoom_factor(context, self.data['point_co'])

        get_mouse_pos(self, context, event)

        self.mouse_offset = self.data['point_co_2d'] - self.mouse_pos

        if event.type in ['LEFTMOUSE', 'RIGHTMOUSE', 'S']:
            self.initiate_sliding(context, event)

        else:
            self.is_g_invoked = False
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def initiate_sliding(self, context, event):
        self.is_g_invoked = True

        init_status(self, context, func=draw_slide_point_status(self))

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        self.data['point'].co.xyz = self.data['point_co_local']

    def get_data(self, context, debug=False):
        data = get_curve_as_dict(self.curve)
        selection = get_curve_selection(data)

        sidx, pidx = selection.pop()

        points = self.curve.splines[sidx].points

        point = points[pidx]
        point_co_2d = location_3d_to_region_2d(context.region, context.region_data, self.mx @ point.co.xyz)

        point_data = {'point': point,
                      'point_co': self.mx @ point.co.xyz,
                      'point_co_local': point.co.xyz,
                      'point_co_2d': point_co_2d,

                      'prev_point_co': None,
                      'next_point_co': None,

                      'prev_dir': None,
                      'next_dir': None,

                      'slide_segment': None,
                      'locked': None,
                      'locked_coords': []}

        if 0 < pidx < len(points) - 1:

            prev_point = points[pidx - 1]
            next_point = points[pidx + 1]

            point_data['prev_point_co'] = self.mx @ prev_point.co.xyz
            point_data['next_point_co'] = self.mx @ next_point.co.xyz

            prev_dir = prev_point.co.xyz - point.co.xyz
            next_dir = next_point.co.xyz - point.co.xyz

            point_data['prev_dir'] = (self.mx.to_3x3() @ prev_dir).normalized()
            point_data['next_dir'] = (self.mx.to_3x3() @ next_dir).normalized()

        elif pidx == 0:
            next_point = points[pidx + 1]
            point_data['next_point_co'] = self.mx @ next_point.co.xyz

            prev_dir = None
            next_dir = next_point.co.xyz - point.co.xyz

            point_data['next_dir'] = (self.mx.to_3x3() @ next_dir).normalized()

        else:
            prev_point = points[pidx - 1]
            point_data['prev_point_co'] = self.mx @ prev_point.co.xyz

            prev_dir = prev_point.co.xyz - point.co.xyz
            next_dir = None

            point_data['prev_dir'] = (self.mx.to_3x3() @ prev_dir).normalized()

        if debug:
            printd(point_data)

            draw_point(Vector((*point_co_2d, 0)), color=yellow, modal=False, screen=True)

            if prev_dir:
                draw_vector(prev_dir, origin=point.co.xyz, mx=self.mx, color=red, modal=False)

            if next_dir:
                draw_vector(next_dir, origin=point.co.xyz, mx=self.mx, color=green, modal=False)

            context.area.tag_redraw()

        return point_data

    def slide_point(self, context):
        view_origin = region_2d_to_origin_3d(context.region, context.region_data, self.mouse_pos + self.mouse_offset)
        view_dir = region_2d_to_vector_3d(context.region, context.region_data, self.mouse_pos + self.mouse_offset)

        point_co = self.data['point_co']
        prev_dir = self.data['prev_dir']
        next_dir = self.data['next_dir']
        locked = self.data['locked']

        if prev_dir:
            i = intersect_line_line(point_co, point_co + prev_dir, view_origin, view_origin + view_dir)

            if i:
                prev_i_co = i[0]
                prev_m_co = i[1]

        if next_dir:
            i = intersect_line_line(point_co, point_co + next_dir, view_origin, view_origin + view_dir)

            if i:
                next_i_co = i[0]
                next_m_co = i[1]

        if prev_dir and next_dir:
            prev_mouse_dir = (prev_m_co - point_co).normalized()
            prev_dot = prev_mouse_dir.dot(prev_dir)

            next_mouse_dir = (next_m_co - point_co).normalized()
            next_dot = next_mouse_dir.dot(next_dir)

            if locked:
                slide_co = self.mx.inverted_safe() @ eval(f'{locked}_i_co')

            else:
                if next_dot > prev_dot:
                    slide_co = self.mx.inverted_safe() @ next_i_co
                else:
                    slide_co = self.mx.inverted_safe() @ prev_i_co

            self.data['slide_segment'] = 'next' if next_dot > prev_dot else 'prev'

        elif prev_dir:
            slide_co = self.mx.inverted_safe() @ prev_i_co
            self.data['slide_segment'] = 'prev'

        else:
            slide_co = self.mx.inverted_safe() @ next_i_co
            self.data['slide_segment'] = 'next'

        if self.is_shift:
            point_co_local = self.data['point_co_local']
            slide_vec = slide_co - point_co_local

            slide_co = point_co_local + slide_vec * 0.2

        self.data['point'].co.xyz = slide_co
