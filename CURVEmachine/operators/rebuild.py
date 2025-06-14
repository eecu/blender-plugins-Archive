import bpy
from bpy.props import IntProperty, BoolProperty, FloatProperty
from mathutils import Vector
from .. utils.color import mix
from .. utils.curve import create_new_spline, get_curve_as_dict
from .. utils.system import printd
from .. utils.property import rotate_list, step_list
from .. utils.ui import ignore_events, navigation_passthrough, init_status, finish_status, scroll_up, scroll_down, get_mouse_pos, init_timer_modal, get_timer_progress, set_countdown
from .. utils.draw import draw_line, draw_points, draw_init, draw_label, draw_lines, draw_point
from .. utils.math import find_outliers, remap
from .. utils.view import get_location_2d
from .. colors import orange, black, white, yellow, normal, green, red

def draw_gap_shuffle_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)

        row.label(text="Gap Shuffle")

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Confirm")

        row.label(text="", icon='MOUSE_MMB_DRAG')
        row.label(text="Navigation")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        row.label(text="", icon='MOUSE_MMB')
        row.label(text="Shuffle the Gap")

        if len(op.outliers) > 1:
            row.separator(factor=2)
            row.label(text="", icon='EVENT_Q')
            row.label(text=f"Shuffle Outlier segments only: {op.shuffle_outliers}")

        row.separator(factor=2)
        row.label(text="", icon='EVENT_C')
        row.label(text=f"Cyclic: {op.curve.splines.active.use_cyclic_u}")
        
    return draw

class GapShuffle(bpy.types.Operator):
    bl_idname = "machin3.gap_shuffle"
    bl_label = "MACHIN3: Shuffle Spline Gap"
    bl_description = "Shuffe the gap in the active Spline"
    bl_options = {'REGISTER', 'UNDO'}

    step: IntProperty(name="Shuffle Step", default=1)
    shuffle_outliers: BoolProperty(name="Shuffle Outliers", default=True)
    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            active_spline = active.data.splines.active
            if active_spline:
                return len(active_spline.points) > 2

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            dims = draw_label(context, title="Gap Shuffle ", coords=Vector((self.HUD_x, self.HUD_y)), center=False, alpha=1)

            if len(self.outliers) > 1 and self.shuffle_outliers:
                dims2 = draw_label(context, title="Outlier ", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), center=False, size=10, color=normal, alpha=1)
                draw_label(context, title="Segments", coords=Vector((self.HUD_x + dims[0] + dims2[0], self.HUD_y)), center=False, size=10, alpha=0.5)

            if self.curve.splines.active.use_cyclic_u:
                self.offset += 18
                draw_label(context, title="Cyclic", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=green, alpha=1)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.coords:

                draw_line(self.coords, color=orange, alpha=0.99)

                draw_points(self.coords[1:-1], size=4, color=black, alpha=1)

                color = white if self.curve.splines.active.use_cyclic_u else red
                draw_points([self.coords[0], self.coords[-1]], size=4, color=color, alpha=1)

            if self.orig_gap_coords:
                draw_line(self.orig_gap_coords, color=yellow, alpha=0.75)

            if self.outlier_coords:
                draw_lines(self.outlier_coords, color=normal, width=2, alpha=0.99)

            if self.active_spline.use_cyclic_u and self.active_spline.type == 'NURBS':
                draw_line([self.coords[0], self.coords[-1]], color=black, alpha=1)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        events = ['MOUSEMOVE', 'Q', 'C']

        if event.type in events or scroll_up(event, key=True) or scroll_down(event, key=True):
            if event.type == 'MOUSEMOVE':
                get_mouse_pos(self, context, event)

            elif scroll_up(event, key=True) or scroll_down(event, key=True):

                if len(self.outliers) > 1 and self.shuffle_outliers:
                    self.step = step_list(self.step - 1, self.outliers, step=1 if scroll_up(event, key=True) else -1, loop=True) + 1

                else:
                    if scroll_up(event, key=True):
                        self.step += 1

                        if self.step > len(self.new_points) - 1:
                            self.step = 1

                    else:
                        self.step -= 1

                        if self.step < 1:
                            self.step = len(self.new_points) - 1

                self.new_points = self.get_new_points(gap=self.step, debug=False)

            elif self.outliers and event.type == 'Q' and event.value == 'PRESS':
                self.shuffle_outliers = not self.shuffle_outliers

                if self.shuffle_outliers:
                    opposite_outlier_idx = int(len(self.outliers) / 2)
                    self.step = self.outliers[opposite_outlier_idx] + 1

                self.new_points = self.get_new_points(gap=self.step, debug=False)

                self.curve.splines.active.points[0].hide = True

            elif event.type == 'C' and event.value == 'PRESS':
                self.curve.splines.active.use_cyclic_u = not self.curve.splines.active.use_cyclic_u

                self.curve.splines.active.points[0].hide = True

        elif navigation_passthrough(event, alt=True, wheel=False):
            return {'PASS_THROUGH'}

        elif event.type in ['SPACE', 'LEFTMOUSE'] and not event.alt:
            self.finish(context)

            if self.step:
                spline_data = self.data['active']
                sidx = spline_data['index']

                spline_data['cyclic'] = self.curve.splines.active.use_cyclic_u

                self.curve.splines.remove(self.curve.splines[sidx])

                create_new_spline(self.curve, spline_data, self.new_points)

            else:
                for point in self.curve.splines.active.points:
                    point.hide = False

            return {'FINISHED'}

        elif event.type in ['ESC', 'RIGHTMOUSE']:
            self.finish(context)

            for point in self.curve.splines.active.points:
                point.hide = False

            if self.has_toggled_cyclic:
                self.curve.splines.active.use_cyclic_u = False

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

        self.data = get_curve_as_dict(self.curve)
        spline_data = self.data['active']

        self.active_spline = self.curve.splines.active

        for point in self.curve.splines.active.points:
            point.hide = True

        self.has_toggled_cyclic = False

        if not self.active_spline.use_cyclic_u:
            self.active_spline.use_cyclic_u = True
            self.has_toggled_cyclic = True

        self.outliers = []

        self.coords = []
        self.orig_gap_coords = []
        self.outlier_coords = []

        self.new_points = self.get_new_points(gap=None, debug=False)

        get_mouse_pos(self, context, event)

        init_status(self, context, func=draw_gap_shuffle_status(self))

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def get_new_points(self, gap=None, debug=False):
        def get_outlier_segment_indices(points):
            gap_lengths = []

            for idx, point in enumerate(points[1:]):
                prev_point = points[idx]

                length = (prev_point['co'].xyz - point['co'].xyz).length
                gap_lengths.append(length)

            lower_bound, upper_bound = find_outliers(gap_lengths, lowp=25, highp=75, multiplier=1.5, bounds=True)

            outliers = []

            for idx, length in enumerate(gap_lengths):
                if length < lower_bound:
                    if 0 < idx < len(points) - 2:
                        outliers.append(idx)

                elif length > upper_bound:
                    if 0 < idx < len(points) - 2:
                        outliers.append(idx)

            return outliers

        def get_opposite_gap(points):
            return int(len(points) / 2)

        spline_data = self.data['active']
        points = spline_data['points'].copy()

        if debug:
            print("")
            print("points:", [p['index'] for p in points])

        if gap is not None:

            if gap:
                rotate_list(points, amount=gap)

        else:
            self.outliers = get_outlier_segment_indices(points)

            if self.outliers:
                opposite_outlier_idx = int(len(self.outliers) / 2)

                step = self.outliers[opposite_outlier_idx] + 1
                rotate_list(points, amount=step)

            else:
                step = get_opposite_gap(points)
                rotate_list(points, amount=step)

            self.step = step

            if len(self.outliers) > 1:
                self.shuffle_outliers = True

        if debug:
            print("  new:", [p['index'] for p in points])

        self.coords = [self.mx @ p['co'].xyz for p in points]
        
        self.orig_gap_coords = [self.mx @ p['co'].xyz for p in [spline_data['points'][0], spline_data['points'][-1]]]

        self.outlier_coords = []

        if len(self.outliers) > 1 and self.shuffle_outliers:
            for pidx in self.outliers:
                if self.step != pidx + 1:
                    self.outlier_coords.append(self.mx @ spline_data['points'][pidx]['co'].xyz)
                    self.outlier_coords.append(self.mx @ spline_data['points'][pidx + 1]['co'].xyz)

        return points

class Convert(bpy.types.Operator):
    bl_idname = "machin3.convert_spline"
    bl_label = "MACHIN3: Convert Spline Type"
    bl_description = "Convert Spline Type"
    bl_options = {'REGISTER', 'UNDO'}

    endpoint: BoolProperty(name="Endpoints", description="Make sure to meet the Endpoints", default=True)
    show_endpoint_toggle: BoolProperty()

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            return active.data.splines.active

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        if self.show_endpoint_toggle:
            column.prop(self, 'endpoint', text="Meet Endpoints", toggle=True)

    def invoke(self, context, event):
        curve = context.active_object.data
        spline = curve.splines.active

        if spline.type in ['POLY', 'BEZIER']:
            self.endpoint = not spline.use_cyclic_u

        return self.execute(context)

    def execute(self, context):
        curve = context.active_object.data
        spline = curve.splines.active
        is_bezier = spline.type == 'BEZIER'

        if spline.type == 'NURBS':
            spline.type = 'POLY'

            self.show_endpoint_toggle = False

        else:
            spline.type = 'NURBS'

            if self.endpoint:
                spline.use_endpoint_u = True

            if is_bezier:
                
                spline.use_bezier_u = False

                data = get_curve_as_dict(curve)

                keep_points = data['active']['points'][1::3]

                curve.splines.remove(spline)

                create_new_spline(curve, data['active'], keep_points)

            self.show_endpoint_toggle = True

        return {'FINISHED'}

class Reverse(bpy.types.Operator):
    bl_idname = "machin3.reverse_spline"
    bl_label = "MACHIN3: Reverse Spline"
    bl_description = "Reverse Spline Direction\nALT: Skip reversing, only show the current direction"
    bl_options = {'REGISTER', 'UNDO'}

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=1, min=0, max=1)
    passthrough = None

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            active_spline = active.data.splines.active
            return active_spline and active_spline.type in ['POLY', 'NURBS']

    def draw_HUD(self, context):
        if self.area == context.area:
            time_passed = 1 - (self.countdown / self.time)
            
            time_compressed_start = min((1 - (self.countdown / self.time)) * 1.5, 1)

            time_compressed_end = max((1 - (self.countdown / self.time)) * 1.5 - 0.5, 0)

            alpha_start = 1 - time_compressed_start
            alpha_end = 1 - time_compressed_end

            if alpha_start < 1:
                draw_label(context, title="Start", coords=self.coords['first2d'], center=False, size=11, color=green, alpha=alpha_start)

            if alpha_end < 1:
                draw_label(context, title="End", coords=self.coords['last2d'], center=False, size=11, color=red, alpha=alpha_end)

    def draw_VIEW3D(self, context):
        if context.area == self.area:

            time_passed = min((1 - (self.countdown / self.time)) * 3, 1)

            if time_passed == 1:
                return

            for point in self.coords['points']:
                co = point['co']
                distance = point['distance']
                color = point['color']

                alpha = 1 if time_passed > distance else 0

                if time_passed > distance + 0.1:
                    alpha = 0

                draw_point(co, color=yellow, alpha=alpha)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        else:
            self.finish(context)
            return {'FINISHED'}

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        self.update_coords2d(context)

        return {'PASS_THROUGH'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        context.window_manager.event_timer_remove(self.TIMER)

    def invoke(self, context, event):
        curve = context.active_object.data
        active = curve.splines.active
        self.mx = context.active_object.matrix_world
        
        data = get_curve_as_dict(curve, debug=False)
        self.spline_data = data['active']

        if not event.alt:
            self.spline_data['points'].reverse()

            curve.splines.remove(active)
            create_new_spline(curve, self.spline_data)

        self.coords = self.get_coords(context)

        init_timer_modal(self)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.TIMER = context.window_manager.event_timer_add(0.01, window=context.window)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def get_coords(self, context):
        total_length = 0
        points = []

        for idx, point in enumerate(self.spline_data['points']):
            data = {'co': self.mx @ point['co'].xyz,
                    'distance': 0,
                    'color': None}

            prev_point = self.spline_data['points'][idx - 1] if idx > 0 else None

            if prev_point:
                distance = (prev_point['co'].xyz - point['co'].xyz).length
                total_length += distance

                data['distance'] = total_length

            points.append(data)

        for idx, point in enumerate(points):
            factor = point['distance'] / total_length
            point['distance'] = factor
            point['color'] = mix(green, red, factor)

        coords = {'points': points,
                  'first2d': get_location_2d(context, points[0]['co']) + Vector((0, 10)),
                  'last2d': get_location_2d(context, points[-1]['co']) + Vector((0, 10))}

        return coords

    def update_coords2d(self, context):
        self.coords['first2d'] = get_location_2d(context, self.coords['points'][0]['co']) + Vector((0, 10))
        self.coords['last2d'] = get_location_2d(context, self.coords['points'][-1]['co']) + Vector((0, 10))
