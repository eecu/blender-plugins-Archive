import bpy
from bpy.props import FloatProperty, IntProperty, BoolProperty
from mathutils import Vector
from mathutils.geometry import interpolate_bezier, intersect_line_line
from math import degrees
import numpy as np
from .. utils.system import printd
from .. utils.ui import ignore_events, get_zoom_factor, init_status, finish_status, navigation_passthrough, get_mousemove_divisor, scroll_up, scroll_down, get_mouse_pos, wrap_mouse, is_key, force_ui_update
from .. utils.draw import draw_point, draw_points, draw_vector, draw_line, draw_init, draw_label, draw_fading_label
from .. utils.math import average_locations, dynamic_format
from .. utils.curve import get_curve_as_dict, verify_curve_data
from .. utils.registration import get_prefs
from .. colors import green, red, yellow, blue, white

def draw_blendulate_status(op):
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)

        is_merge = op.auto_merge or op.merge

        row.label(text="Blendulate")

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Finish")

        row.label(text="", icon='MOUSE_MMB_DRAG')
        row.label(text="Viewport")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        row.label(text="", icon='EVENT_M')
        row.label(text=f"Merge: {'Auto' if op.auto_merge else op.merge}")

        if not is_merge:
            row.separator(factor=2)

            row.label(text="", icon='EVENT_SHIFT')
            row.label(text="", icon='EVENT_CTRL')
            row.label(text=f"Precision: {'fine' if op.is_shift else 'coarse' if op.is_ctrl else 'normal'}")

            if op.is_tension_adjustment:
                row.separator(factor=2)

                row.label(text="", icon='MOUSE_MOVE')
                row.label(text=f"Adjust Tension: {dynamic_format(op.tension, decimal_offset=2)}")

            else:
                row.separator(factor=2)

                row.label(text="", icon='MOUSE_MOVE')
                row.label(text=f"Adjust Width: {dynamic_format(op.amount, decimal_offset=2)}")

                row.separator(factor=2)

                row.label(text="", icon='EVENT_C')
                row.label(text=f"Chamfer: {op.chamfer}")

                if not op.chamfer:
                    row.separator(factor=2)

                    row.label(text="", icon='MOUSE_MMB')
                    row.label(text=f"Segments: {op.segments}")

                    if op.segments > 0:
                        row.separator(factor=2)

                        tension = op.bezier_data['circular_approxinate_tension'] if op.auto_tension else op.tension
                        row.label(text="", icon='EVENT_T')
                        r = row.row(align=True)
                        r.active = not op.auto_tension
                        r.label(text=f"Tension: {dynamic_format(tension, decimal_offset=2)}")

                        row.separator(factor=2)
                        row.label(text="", icon='EVENT_A')
                        row.label(text=f"Auto Tension: {op.auto_tension}")

                if op.curve.bevel_depth:
                    row.separator(factor=2)

                    row.label(text="", icon='EVENT_W')
                    row.label(text=f"Wireframe: {op.active.show_wire}")

    return draw

class Bendulate(bpy.types.Operator):
    bl_idname = "machin3.bendulate"
    bl_label = "MACHIN3: Blendulate"
    bl_description = "Blend selected Curve Points, or create Arc from single Point selection\nALT: Repeat Blendulate using previous values"
    bl_options = {'REGISTER', 'UNDO'}

    def update_tension(self, context):
        if self.auto_tension:
            self.auto_tension = False

    tension: FloatProperty(name="Tension", description="Tension used for blending the two Spline Segments before and after the selected Point(s)", default=0.7, min=0.001, update=update_tension)
    segments: IntProperty(name="Segments", description="Amount of Points used to interpolate", default=6, min=0)
    chamfer: BoolProperty(name="Chamfer", description="Chamfer the Blend", default=False)
    auto_tension: BoolProperty(name="Auto Tension", description="Use automatically calculated tension to approximate a Circular Arc", default=True)
    amount: FloatProperty(name="Amount", description="Distance by withthe two outer Points are moved", default=0)
    merge: BoolProperty(name="Merge to Single Point", description="Set Merge Selected Points to a single Point", default=False)

    passthrough = False

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object

            if active.type == 'CURVE':
                curve = active.data
                return curve.splines.active and curve.splines.active.type in ['POLY', 'NURBS']

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        split = column.split(align=True, factor=0.5)
        split.active = not self.merge and not self.auto_merge
        split.prop(self, 'amount')

        row = split.row(align=True)
        r = row.row(align=True)
        r.active = not self.auto_tension

        r.prop(self, 'tension')
        row.prop(self, 'auto_tension', text='', toggle=True, icon='AUTO')

        row = column.row(align=True)
        row.scale_y = 1.2

        if self.auto_merge:
            row.label(text='Auto-Merging, increase Amount to avoid this', icon='INFO')

        else:
            split = row.split(factor=0.5, align=True)
            split.active = not self.merge

            s = split.split(factor=0.9, align=True)
            r = s.row(align=True)
            r.active = not self.chamfer
            r.prop(self, 'segments', text='Segment Count')
            s.prop(self, 'chamfer', text='C', toggle=True)

            split.prop(self, 'merge', toggle=True)

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            dims = draw_label(context, title="Blendulate ", coords=Vector((self.HUD_x, self.HUD_y)), center=False, alpha=1)
            if self.is_shift:
                draw_label(context, title="a little", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), center=False, size=10, alpha=0.5)
            elif self.is_ctrl:
                draw_label(context, title="a lot", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), center=False, size=10, alpha=0.5)

            if self.is_tension_adjustment:
                
                self.offset += 18

                tension = self.bezier_data['circular_approxinate_tension'] if self.auto_tension else self.tension

                dims = draw_label(context, title="Tension: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=yellow, alpha=1)
                dims2 = draw_label(context, title=dynamic_format(tension, decimal_offset=2), coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, color=yellow, alpha=1)

            else:

                self.offset += 18

                if self.auto_merge:
                    draw_label(context, title="Auto Merge", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, color=yellow, center=False, alpha=1)

                elif self.merge:
                    draw_label(context, title="Merge", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, color=yellow, center=False, alpha=1)

                else:
                    color, alpha = (white, 0.5) if self.is_tension_adjustment else (yellow, 1)
                    dims = draw_label(context, title="Amount: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)
                    draw_label(context, title=dynamic_format(self.amount, decimal_offset=2), coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)

                if not self.auto_merge and not self.merge:
                    
                    self.offset += 18

                    tension = self.bezier_data['circular_approxinate_tension'] if self.auto_tension else self.tension

                    dims = draw_label(context, title="Tension: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=white, alpha=0.5)
                    dims2 = draw_label(context, title=dynamic_format(tension, decimal_offset=2), coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, color=white, alpha=0.5)

                    if self.auto_tension:
                        dims3 = draw_label(context, title=" Auto ", coords=Vector((self.HUD_x + dims[0] + dims2[0], self.HUD_y)), offset=self.offset, center=False, color=green, alpha=1)
                        draw_label(context, title="(Arc Approximation)", coords=Vector((self.HUD_x + dims[0] + dims2[0] + dims3[0], self.HUD_y)), offset=self.offset, size=10, center=False, alpha=0.5)

                    self.offset += 18

                    if self.chamfer:
                        draw_label(context, title="Chamfer", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=blue, alpha=1)

                    else:
                        dims = draw_label(context, title="Segments: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=1)
                        draw_label(context, title=str(self.segments), coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, alpha=1)

                if self.curve.bevel_depth and self.active.show_wire:
                    self.offset += 18
                    draw_label(context, title="Wireframe", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=blue, alpha=1)

                warning = self.bezier_data['WARNING']
                if warning:
                    self.offset += 18
                    draw_label(context, title=warning, coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=red, alpha=1)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if self.debug_coords:

                first_co = self.debug_coords['first_co']
                last_co = self.debug_coords['last_co']

                draw_point(first_co, mx=self.mx, color=green)
                draw_point(last_co, mx=self.mx, color=red)

                avg_handle_intersect_co = self.debug_coords['avg_handle_intersect_co']
                first_handle_intersect_co = self.debug_coords['first_handle_intersect_co']
                last_handle_intersect_co = self.debug_coords['last_handle_intersect_co']

                if avg_handle_intersect_co:
                    draw_point(avg_handle_intersect_co, mx=self.mx, color=blue)

                if first_handle_intersect_co:
                    draw_line([first_co, first_handle_intersect_co], mx=self.mx, alpha=0.2)

                if last_handle_intersect_co:
                    draw_line([last_co, last_handle_intersect_co], mx=self.mx, alpha=0.2)

                bezier_coords = self.debug_coords['bezier_coords']

                if bezier_coords:
                    draw_points(bezier_coords, mx=self.mx, size=4)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        self.is_shift = event.shift
        self.is_ctrl = event.ctrl

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

        is_key(self, event, 'T', onpress=self.update_tension_adjustment(context, 'PRESS'), onrelease=self.update_tension_adjustment(context, 'RELEASE'))

        if self.is_tension_adjustment:
            if ret := self.adjust_tension(context, event):
                return ret

        if ret := self.refresh(context, event):
            return ret

        if navigation_passthrough(event, alt=True, wheel=False):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'} and not event.alt:
            self.finish(context)

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish(context)

            for spline_data in self.data['splines']:
                if spline_data['active']:

                    self.create_new_active_spline(spline_data)
                    break

            return {'CANCELLED'}

        self.last_mouse = self.mouse_pos

        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        context.window.cursor_set('DEFAULT')

        finish_status(self)

        if self.curve.bevel_depth and self.active.show_wire:
            self.active.show_wire = False

    def invoke(self, context, event):
        self.active = context.active_object
        self.curve = self.active.data
        self.mx = self.active.matrix_world

        self.data = get_curve_as_dict(self.curve, debug=False)

        if spline := verify_curve_data(self.data, 'has_active_spline'):
            if spline['type'] in ['POLY', 'NURBS'] and len(spline['points']) >= 3:

                if selection := verify_curve_data(self.data, 'has_active_selection'):

                    if not verify_curve_data(self.data, 'is_active_end_selected'):

                        if verify_curve_data(self.data, 'is_active_selection_continuous'):

                            self.bezier_data = self.get_bezier_data(spline['points'], selection, debug=False)

                            if event.alt:

                                self.create_bezier_coords(self.amount, self.segments, debug=False)

                                new_spline_data = self.create_new_spline_data(debug=False)

                                self.create_new_active_spline(new_spline_data)

                                return {'FINISHED'}

                            elif len(selection) > 2:

                                self.create_bezier_coords(0, len(selection) - 2, debug=False)

                                new_spline_data = self.create_new_spline_data(debug=False)

                                self.create_new_active_spline(new_spline_data)

                            self.amount = 0
                            self.chamfer = False
                            self.merge = False
                            self.auto_merge = False

                            self.is_tension_adjustment = False

                            self.is_shift = False
                            self.is_ctrl = False

                            self.debug_coords = {}

                            if self.active.data.bevel_depth:
                                self.active.show_wire = True

                            self.segments = get_prefs().blendulate_segment_count if len(selection) == 1 else len(selection) - 2

                            self.factor = get_zoom_factor(context, self.mx @ self.data['active_selection_mid_point'], scale=5)

                            get_mouse_pos(self, context, event)

                            self.last_mouse = self.mouse_pos

                            context.window.cursor_set('SCROLL_X')

                            init_status(self, context, func=draw_blendulate_status(self))

                            self.area = context.area
                            self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
                            self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

                            context.window_manager.modal_handler_add(self)
                            return {'RUNNING_MODAL'}

                        else:
                            draw_fading_label(context, ["Illegal Selection",
                                                        "Make a continuous Selection of Points, without unselected gaps."], color=[red, yellow])

                    else:
                        draw_fading_label(context, ["Illegal Selection",
                                                    "Avoid selecting the Spline Ends", "You can use the Gap Shuffle tool to easiy move the End Points elsewhere."], color=[red, yellow])

                else:
                    draw_fading_label(context, ["Illegal Selection",
                                                "Select at least one Point in the Active Spline."], color=[red, yellow])

            else:
                draw_fading_label(context, ["Illegal Selection",
                                            "Ensure the Active Spline is of type POLY or NURBS with at least 3 Points."], color=[red, yellow])

        else:
            draw_fading_label(context, ["Invalid Curve/Spline",
                                        "Ensure there is an Active Spline."], color=[red, yellow])

        return {'CANCELLED'}

    def execute(self, context):
        self.create_bezier_coords(self.amount, self.segments, debug=False)

        new_spline_data = self.create_new_spline_data(debug=False)

        self.create_new_active_spline(new_spline_data)

        return {'FINISHED'}

    def update_tension_adjustment(self, context, value='PRESS'):
        def press():
            self.is_tension_adjustment = True
            context.window.cursor_set('SCROLL_Y')

            if self.auto_tension:
                self.auto_tension = False
                
                self.tension = self.bezier_data['circular_approxinate_tension']

            force_ui_update(context)

        def release():
            self.is_tension_adjustment = False

            context.window.cursor_set('SCROLL_X')

            force_ui_update(context)

        if value == 'PRESS':
            return press

        elif value == 'RELEASE':
            return release

    def adjust_tension(self, context, event):
        wrap_mouse(self, context, y=True)

        divisor = get_mousemove_divisor(event, 3, 15, 1, sensitivity=10)

        delta_y = self.mouse_pos.y - self.last_mouse.y
        delta_tension = delta_y / divisor

        self.tension += delta_tension

        self.create_bezier_coords(self.amount, self.segments, debug=False)

        new_spline_data = self.create_new_spline_data(debug=False)

        self.create_new_active_spline(new_spline_data)

        self.last_mouse = self.mouse_pos
        return {'RUNNING_MODAL'}

    def refresh(self, context, event):
        events = ['MOUSEMOVE', 'A', 'M', 'C']

        if self.curve.bevel_depth:
            events.append('W')

        if event.type in events or scroll_up(event, key=True) or scroll_down(event, key=True):

            if event.type in  ['MOUSEMOVE', 'A', 'M', 'C'] or scroll_up(event, key=True) or scroll_down(event, key=True):

                if event.type == 'MOUSEMOVE':

                    if self.passthrough:
                        self.last_mouse = self.mouse_pos

                        self.passthrough = False
                        self.factor = get_zoom_factor(context, self.mx @ self.data['active_selection_mid_point'], scale=5)

                    wrap_mouse(self, context, x=True)
                    divisor = get_mousemove_divisor(event, 3, 15, 1)

                    delta_x = self.mouse_pos.x - self.last_mouse.x
                    delta_amount = delta_x / divisor * self.factor

                    self.amount += delta_amount

                elif scroll_up(event, key=True) or scroll_down(event, key=True):

                    if scroll_up(event, key=True):
                        self.segments += 1

                    else:
                        self.segments -= 1

                elif event.type == 'C' and event.value == 'PRESS': 
                    self.chamfer = not self.chamfer

                elif event.type == 'A' and event.value == 'PRESS': 
                    self.auto_tension = not self.auto_tension

                elif event.type == 'M' and event.value == 'PRESS': 
                    self.merge = not self.merge

                self.create_bezier_coords(self.amount, self.segments, debug=False)

                new_spline_data = self.create_new_spline_data(debug=False)

                self.create_new_active_spline(new_spline_data)

            elif event.type == 'W' and event.value == 'PRESS':
                self.active.show_wire = not self.active.show_wire

    def get_bezier_data(self, points, selected_points, debug=False):
        bdata = {'WARNING': None}

        is_single = len(selected_points) == 1
        bdata['is_single'] = is_single

        first_index = selected_points[0]['index']
        last_index = selected_points[-1]['index']

        first_point = points[first_index]
        last_point = points[last_index]

        previous_point = points[first_index - 1]
        next_point = points[last_index + 1]

        first_co = first_point['co'].xyz
        last_co = last_point['co'].xyz

        previous_co = previous_point['co'].xyz
        next_co = next_point['co'].xyz

        bdata['first_co'] = first_co
        bdata['last_co'] = last_co

        bdata['previous_co'] = previous_co
        bdata['next_co'] = next_co

        bdata['previous_radius'] = previous_point['radius']
        bdata['next_radius'] = next_point['radius']

        bdata['previous_tilt'] = previous_point['tilt']
        bdata['next_tilt'] = next_point['tilt']

        first_move_dir = (previous_co - first_co).normalized()
        last_move_dir = (next_co - last_co).normalized()

        bdata['first_move_dir'] = first_move_dir
        bdata['last_move_dir'] = last_move_dir

        angle = 180 - degrees(first_move_dir.angle(last_move_dir))
        bdata['angle'] = angle

        bdata['circular_approxinate_tension'] = self.get_bezier_tension_from_angle(angle, first_co, last_co)

        if is_single:
            bdata['avg_handle_intersect_co'] = first_co
            bdata['first_handle_intersect_co'] = first_co
            bdata['last_handle_intersect_co'] = first_co

        else:
            handle_intersects = intersect_line_line(previous_co, first_co, next_co, last_co)

            if handle_intersects and not angle == 180:
                bdata['avg_handle_intersect_co'] = average_locations(handle_intersects)
                bdata['first_handle_intersect_co'] = handle_intersects[0]
                bdata['last_handle_intersect_co'] = handle_intersects[1]

            else:
                bdata['avg_handle_intersect_co'] = average_locations([first_co, last_co])
                bdata['first_handle_intersect_co'] = first_co - first_move_dir
                bdata['last_handle_intersect_co'] = last_co - last_move_dir
                bdata['WARNING'] = '180° Blend!'

        bdata['bezier_coords'] = []
        
        bdata['interpolation_factors'] = []

        if debug:
            draw_vector(first_move_dir, origin=first_co, mx=self.mx, color=green, modal=False)
            draw_vector(last_move_dir, origin=last_co, mx=self.mx, color=red, modal=False)

            printd(bdata)

        return bdata

    def get_bezier_tension_from_angle(self, angle, first_co, last_co):
        if angle == 180:
            tension =  0.7 * (first_co - last_co).length
            return tension

        else:
            x = [5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 175]
            y = [0.665, 0.661, 0.658, 0.645, 0.636, 0.625, 0.605, 0.59, 0.57, 0.55, 0.52, 0.482, 0.445, 0.395, 0.34, 0.273, 0.196, 0.1065, 0.0557]

            coefficients = np.polyfit(x, y, deg=4)
            poly = np.poly1d(coefficients)

            return poly(angle)

    def create_bezier_coords(self, amount, segments, debug=False):
        def get_interpolation_factors():
            interpolation_coords = [bdata['previous_co']] + bdata['bezier_coords'] + [bdata['next_co']]
            interpolation_distances = []

            for idx, co in enumerate(interpolation_coords):

                if idx == 0:
                    distance = 0
                else:
                    vec = co - interpolation_coords[idx - 1]
                    distance = vec.length

                interpolation_distances.append(distance)

            total_distance = sum(interpolation_distances)

            interpolation_factors = []
            cumulative_distance = 0

            for distance in interpolation_distances:
                cumulative_distance += distance
                factor = cumulative_distance / total_distance
                interpolation_factors.append(factor)

            return interpolation_factors[1:-1]

        bdata = self.bezier_data
        bezier_coords = []
        debug_coords = {}

        self.auto_merge = bdata['is_single'] and self.amount <= 0

        new_first_co = bdata['first_co'] + bdata['first_move_dir'] * amount
        new_last_co = bdata['last_co'] + bdata['last_move_dir'] * amount

        if bdata['is_single'] and amount < 0:
            new_first_co = bdata['first_co']
            new_last_co = bdata['last_co']

        else:
            first_handle_dir = bdata['first_handle_intersect_co'] - new_first_co
            first_dot = first_handle_dir.dot(bdata['first_move_dir'])

            if first_dot >= 0:
                new_first_co = bdata['first_handle_intersect_co']

            last_handle_dir = bdata['first_handle_intersect_co'] - new_last_co
            last_dot = last_handle_dir.dot(bdata['last_move_dir'])
            
            if last_dot >= 0:
                new_last_co = bdata['last_handle_intersect_co']

            if first_dot > 0 and last_dot > 0:
                self.auto_merge = True

        if self.merge or self.auto_merge:
            bdata['bezier_coords'] = [bdata['avg_handle_intersect_co']]

        else:

            first_dir = bdata['first_handle_intersect_co'] - new_first_co
            last_dir = bdata['last_handle_intersect_co'] - new_last_co

            if self.auto_tension:
                tension = bdata['circular_approxinate_tension']
            else:
                tension = self.tension

            resolution = 2 if self.chamfer else segments + 2
            bezier_coords = interpolate_bezier(new_first_co, new_first_co + first_dir * tension, new_last_co + last_dir * tension, new_last_co, resolution)

            bdata['bezier_coords'] = bezier_coords

        bdata['interpolation_factors'] = get_interpolation_factors()

        if debug:
            debug_coords['first_co'] = new_first_co
            debug_coords['last_co'] = new_last_co

            debug_coords['avg_handle_intersect_co'] = bdata['avg_handle_intersect_co']
            debug_coords['first_handle_intersect_co'] = bdata['first_handle_intersect_co']
            debug_coords['last_handle_intersect_co'] = bdata['last_handle_intersect_co']

            debug_coords['bezier_coords'] = bezier_coords if bezier_coords else [new_first_co, new_last_co]

            self.debug_coords = debug_coords

            print()
            printd(bdata, 'active spline data')

    def create_new_spline_data(self, debug=False):
        bdata = self.bezier_data

        def interpolate(start, end, factor):
            value = start + (end - start) * factor
            return value

        for spline in self.data['splines']:

            if spline['active']:
                new_spline_data = {'index': spline['index'],
                                   'active': True,
                                   'type': spline['type'],
                                   'smooth': spline['smooth'],
                                   'cyclic': spline['cyclic'],

                                   'endpoint': spline['endpoint'],
                                   'order': spline['order'],
                                   'resolution': spline['resolution'],

                                   'points': []}

                pidx = 0
                has_inserted_bezier = False

                for point in spline['points']:

                    if point['select']:

                        if has_inserted_bezier:
                            continue

                        else:

                            previous_radius = bdata['previous_radius']
                            next_radius = bdata['next_radius']

                            previous_tilt = bdata['previous_tilt']
                            next_tilt = bdata['next_tilt']

                            interpolation_factors = bdata['interpolation_factors']

                            for idx, co in enumerate(bdata['bezier_coords']):
                                point_data = {'index': pidx,
                                              'co': Vector((*co, 1)),
                                              'radius': interpolate(previous_radius, next_radius, interpolation_factors[idx]),
                                              'tilt': interpolate(previous_tilt, next_tilt, interpolation_factors[idx]),
                                              'select': True,
                                              'hide': False}

                                new_spline_data['points'].append(point_data)
                                pidx += 1

                            has_inserted_bezier = True

                    else:
                        point_data = {'index': pidx,
                                       'co': point['co'],
                                       'radius': point['radius'],
                                       'tilt': point['tilt'],
                                       'select': False,
                                       'hide': point['hide']}

                        new_spline_data['points'].append(point_data)

                        pidx += 1

                if debug:
                    print()
                    printd(self.data, 'old data')
                    printd(bdata, 'bezier data')
                    printd(new_spline_data, 'new spline data')

                return new_spline_data

    def create_new_active_spline(self, data, debug=False):
        active_spline = self.curve.splines.active

        if active_spline:
            self.curve.splines.remove(active_spline)

        new_spline = self.curve.splines.new(data['type'])

        self.curve.splines.active = new_spline

        new_spline.points.add(len(data['points']) - 1)

        for point, point_data in zip(new_spline.points, data['points']):
            point.co = point_data['co']
            point.radius = point_data['radius']
            point.tilt = point_data['tilt']
            point.select = point_data['select']
            point.hide = point_data['hide']

        new_spline.use_cyclic_u = data['cyclic']
        new_spline.use_smooth = data['smooth']

        if data['type'] == 'NURBS':
            new_spline.use_endpoint_u = data['endpoint']
            new_spline.order_u = data['order']
            new_spline.resolution_u = data['resolution']

class Interpolate(bpy.types.Operator):
    bl_idname = "machin3.interpolate_points"
    bl_label = "MACHIN3: Interpolate Points"
    bl_description = "Interpolate Tilt and/or Radius of selected Curve Points"
    bl_options = {'REGISTER', 'UNDO'}

    tilt: BoolProperty(name="Interpolate Tilt", default=True)
    radius: BoolProperty(name="Interpolate Radius", default=True)
    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            active_spline = active.data.splines.active

            if active_spline and active_spline.type in ['POLY', 'NURBS']:
                has_tilt = len(set(point.tilt for point in active_spline.points)) - 1
                has_radius = len(set(point.radius for point in active_spline.points)) -1
                return has_tilt or has_radius

    def draw(self, context):
        layout = self.layout
        column = layout.column()

        row = column.row(align=True)
        row.prop(self, 'tilt', toggle=True)
        row.prop(self, 'radius', toggle=True)

    def execute(self, context):
        if self.tilt:
            bpy.ops.curve.smooth_tilt()

        if self.radius:
            bpy.ops.curve.smooth_radius()
        
        return {'FINISHED'}
