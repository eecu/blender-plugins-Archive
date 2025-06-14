import bpy
from bpy.props import BoolProperty
from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d
from mathutils import Vector
from mathutils.geometry import intersect_line_plane
from math import degrees
from .. utils.curve import create_new_spline, get_curve_as_dict
from .. utils.draw import draw_point, draw_label, draw_vector, draw_circle, draw_line, draw_points, draw_vectors
from .. utils.property import rotate_list
from .. utils.ui import get_scale, get_mouse_pos, get_zoom_factor, ignore_events, navigation_passthrough, init_status, finish_status, force_ui_update
from .. utils.registration import get_prefs
from .. utils.view import get_view_origin_and_dir
from .. utils.system import printd
from .. colors import yellow, red, green, blue, white, orange, black

def draw_symmetrize_curve_status(op):
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)

        row.label(text=f"Symmetrize")

        r = row.row(align=True)
        r.active = op.flick_direction != 'NONE'
        r.label(text="", icon='MOUSE_LMB')
        r.label(text="Finish")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        row.label(text="", icon='MOUSE_MOVE')
        row.label(text=f"Pick Axis: {op.flick_direction.replace('_', ' ').title()}")

        row.separator(factor=2)

        row.label(text="", icon='EVENT_C')
        row.label(text=f"Across Cursor: {op.is_cursor}")
        
        if op.has_redundant:
            row.separator(factor=2)

            row.label(text="", icon='EVENT_R')
            row.label(text=f"Remove Redundant: {op.remove_redundant}")

    return draw

class Symmetrize(bpy.types.Operator):
    bl_idname = "machin3.symmetrize_curve"
    bl_label = "MACHIN3: Symmetrize Curve"
    bl_description = "Symmetrize Curve"
    bl_options = {'REGISTER', 'UNDO'}

    is_cursor: BoolProperty(name="Cursor", description="Symmetrize in Cursor Space", default=False)
    remove_redundant: BoolProperty(name="Remove Redundant", description="Remove Redundant Center Points", default=True)
    passthrough = None

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            active_spline = active.data.splines.active
            return active_spline and active_spline.type in ['POLY', 'NURBS']

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

    def draw_HUD(self, context):
        if self.area == context.area:
            if not self.passthrough:

                draw_vector(self.flick_vector.resized(3), origin=self.init_mouse.resized(3), fade=True, alpha=1)

                color, alpha = (white, 0.02) if self.is_valid or self.flick_direction == 'NONE' else (red, 0.5)
                draw_circle(self.init_mouse, radius=self.flick_distance, width=3, color=color, alpha=alpha)

                title, color, alpha = ('Symmetrize', white, 0.8) if self.is_valid or self.flick_direction == 'NONE' else ('Invalid', red, 1)
                draw_label(context, title=title, coords=(self.init_mouse.x, self.init_mouse.y + self.flick_distance - (15 * self.scale)), center=True, color=color, alpha=alpha)

                draw_label(context, title=self.flick_direction.replace('_', ' ').title(), coords=(self.init_mouse.x, self.init_mouse.y - self.flick_distance + (15 * self.scale)), center=True, alpha=0.4)

                if self.is_cursor:
                    draw_label(context, title="Cursor", coords=(self.init_mouse.x, self.init_mouse.y - self.flick_distance + (30 * self.scale)), center=True, color=green, alpha=1)

                if self.has_redundant:
                    color, alpha = (red, 1) if self.remove_redundant else (white, 0.2)
                    draw_label(context, title="Remove Redundant", coords=(self.init_mouse.x, self.init_mouse.y - self.flick_distance), center=True, color=color, alpha=alpha)

    def draw_VIEW3D(self, context):
        if context.area == self.area:

            if not self.passthrough:
                for direction, axis, color in zip(self.axes.keys(), self.axes.values(), self.axes_colors):
                    is_positive = 'POSITIVE' in direction

                    draw_vector(axis * self.factor / 2, origin=self.init_mouse_3d, color=color, width=2 if is_positive else 1, alpha=1 if is_positive else 0.3)

                if self.flick_direction != 'NONE':
                    draw_point(self.init_mouse_3d + self.axes[self.flick_direction] * self.factor / 2 * 1.2, size=5, alpha=0.8)

            if 'mirror' in self.coords:
                if loc := self.coords['mirror'].get('loc'):
                    draw_point(loc, color=yellow)

            if 'geometry' in self.coords:
                for is_cyclic, coords in self.coords['geometry']:
                    draw_line(coords, width=2, color=orange if self.is_valid else red)
                    draw_points(coords, color=black if self.is_valid else red)

                    if self.is_valid and is_cyclic:
                        draw_line([coords[0], coords[-1]], width=2, color=black)

                    if self.coords['lines']:
                        vectors = self.coords['lines']['vectors']
                        origins = self.coords['lines']['origins']

                        color = red if '_X' in self.flick_direction else green if '_Y' in self.flick_direction else blue
                        draw_vectors(vectors, origins, fade=True, color=color, alpha=0.3)

                    if coords := self.coords['redundant']:
                        color = red if self.remove_redundant else yellow
                        draw_points(coords, color=color)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        self.is_shift = event.shift
        self.is_ctrl = event.ctrl

        if ret := self.update_mouse(context, event):
            return ret

        if ret := self.refresh(context, event):
            return ret

        if navigation_passthrough(event):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif self.flick_direction != 'NONE' and event.type in ['LEFTMOUSE', 'SPACE'] and event.value == 'PRESS':
            self.finish(context)

            if self.is_valid:
                self.symmetrize_spline()
            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            self.finish(context)

            if self.flick_direction != 'NONE':
                for idx, point in enumerate(self.curve.splines.active.points):
                    if point.hide != self.data['active']['points'][idx]['hide']:
                        point.hide = not point.hide

            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context): 
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event): 
        self.active = context.active_object
        self.curve = self.active.data

        self.mx = self.active.matrix_world
        self.cmx = context.scene.cursor.matrix

        self.scale = get_scale(context)
        self.flick_distance = get_prefs().symmetrize_flick_distance * self.scale

        self.is_valid = False
        self.has_redundant = False

        get_mouse_pos(self, context, event)

        self.origin = self.get_flick_origin(context)

        self.init_mouse = self.mouse_pos
        self.init_mouse_3d = region_2d_to_location_3d(context.region, context.region_data, self.init_mouse, self.origin)

        self.factor = get_zoom_factor(context, depth_location=self.origin, scale=self.flick_distance, ignore_obj_scale=True)

        self.flick_vector = self.mouse_pos - self.init_mouse
        self.flick_direction = 'NONE'
        self.last_direction = self.flick_direction

        self.axes = self.get_axes()

        self.axes_colors = [red, red, green, green, blue, blue]

        self.coords = {}

        self.data = get_curve_as_dict(self.curve, debug=False)

        init_status(self, context, func=draw_symmetrize_curve_status(self))

        force_ui_update(context)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        self.is_interactive = False

        print("executing Symmetrize")
        
        return {'FINISHED'}

    def update_mouse(self, context, event):
        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

            if self.passthrough:
                self.passthrough = False

                self.init_mouse = self.mouse_pos
                self.init_mouse_3d = region_2d_to_location_3d(context.region, context.region_data, self.init_mouse, self.origin)
                self.factor = get_zoom_factor(context, depth_location=self.origin, scale=self.flick_distance, ignore_obj_scale=True)

    def refresh(self, context, event):
        events = ['MOUSEMOVE', 'C']

        if self.has_redundant:
            events.append('R')

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                self.flick_vector = self.mouse_pos - self.init_mouse

                if self.flick_vector.length:
                    self.flick_direction = self.get_flick_direction(context)

                    if self.flick_direction != self.last_direction:
                        self.last_direction = self.flick_direction

                        self.symmetrize = self.get_symmetrized_spline_data()

                        self.is_valid = self.flick_direction != 'NONE' and self.symmetrize['type'] != 'INVALID'

                        self.set_active_spline_visibility()

                        self.create_preview_coords()

                        force_ui_update(context)

                if self.flick_vector.length > self.flick_distance:
                    self.finish(context)

                    if self.is_valid:
                        self.symmetrize_spline()

                    return {'FINISHED'}

            elif event.type == 'C' and event.value == 'PRESS':
                self.is_cursor = not self.is_cursor

                self.axes = self.get_axes()

                if self.flick_vector.length:
                    self.flick_direction = self.get_flick_direction(context)
                    self.last_direction = self.flick_direction

                    self.symmetrize = self.get_symmetrized_spline_data()

                    self.is_valid = self.flick_direction != 'NONE' and self.symmetrize['type'] != 'INVALID'

                    self.set_active_spline_visibility()

                    self.create_preview_coords()

                else:
                    self.get_mirror_data()

                force_ui_update(context)

            elif event.type == 'R' and event.value == 'PRESS':
                self.remove_redundant = not self.remove_redundant

                force_ui_update(context)

    def get_flick_origin(self, context):
        view_origin, view_dir = get_view_origin_and_dir(context, self.mouse_pos)

        origin = view_origin + view_dir * 10

        return origin

    def get_flick_direction(self, context):
        origin_2d = location_3d_to_region_2d(context.region, context.region_data, self.init_mouse_3d, default=Vector((context.region.width / 2, context.region.height / 2)))
        axes_2d = {}

        for direction, axis in self.axes.items():

            axis_2d = location_3d_to_region_2d(context.region, context.region_data, self.init_mouse_3d + axis, default=origin_2d)
            if (axis_2d - origin_2d).length:
                axes_2d[direction] = (axis_2d - origin_2d).normalized()

        return min([(d, abs(self.flick_vector.xy.angle_signed(a))) for d, a in axes_2d.items()], key=lambda x: x[1])[0]

    def get_axes(self):
        mx = self.cmx if self.is_cursor else self.mx

        axes = {'POSITIVE_X': mx.to_quaternion() @ Vector((1, 0, 0)),
                'NEGATIVE_X': mx.to_quaternion() @ Vector((-1, 0, 0)),
                'POSITIVE_Y': mx.to_quaternion() @ Vector((0, 1, 0)),
                'NEGATIVE_Y': mx.to_quaternion() @ Vector((0, -1, 0)),
                'POSITIVE_Z': mx.to_quaternion() @ Vector((0, 0, 1)),
                'NEGATIVE_Z': mx.to_quaternion() @ Vector((0, 0, -1))}

        return axes

    def get_mirror_data(self):
        planes = {'POSITIVE_X': Vector((1, 0, 0)),
                  'NEGATIVE_X': Vector((-1, 0, 0)),
                  'POSITIVE_Y': Vector((0, 1, 0)),
                  'NEGATIVE_Y': Vector((0, -1, 0)),
                  'POSITIVE_Z': Vector((0, 0, 1)),
                  'NEGATIVE_Z': Vector((0, 0, -1))}

        normal = planes[self.flick_direction] if self.flick_direction != 'NONE' else None
        loc = Vector()
        offset = Vector()

        mx = self.cmx if self.is_cursor else self.mx

        if 'mirror' in self.coords:
            self.coords['mirror']['loc'] = mx @ loc
            self.coords['mirror']['normal'] = mx.to_quaternion() @ normal if normal else None

        else:
            self.coords['mirror'] = {'loc': mx @ loc,
                                     'normal': mx.to_quaternion() @ normal if normal else None}

        if self.is_cursor:
            loc = self.mx.inverted_safe() @ self.cmx @ loc

            if normal:
                normal = self.mx.to_3x3().inverted_safe() @ (self.cmx.to_quaternion() @ normal)

                i = intersect_line_plane(Vector(), normal, loc, normal)
                offset = i * 2

        return loc, normal, offset

    def create_preview_coords(self):
        self.coords['geometry'] = []
        self.coords['lines'] = {}
        self.coords['redundant'] = []

        if self.is_valid:
            for data in self.symmetrize['mirrored_splines']:
                coords = [self.mx @ p['co'].xyz for p in data['points']]
                self.coords['geometry'].append((data['cyclic'], coords))

                line_points = [p for p in data['points'] if p.get('line', None)]

                if line_points:
                    if not self.coords['lines'].get('vectors'):
                        self.coords['lines']['vectors'] = []

                    if not self.coords['lines'].get('origins'):
                        self.coords['lines']['origins'] = []
                
                    for point in line_points:
                        self.coords['lines']['vectors'].append(self.mx.to_3x3() @ (point['line'][1].xyz - point['line'][0].xyz))
                        self.coords['lines']['origins'].append(self.mx @ point['line'][0].xyz)

                self.coords['redundant'].extend([self.mx @ p['co'].xyz for p in data['points'] if p.get('is_redundant')])
                
        else:
            active = self.curve.splines.active
            coords = [self.mx @ p.co.xyz for p in active.points]
            self.coords['geometry'].append((active.use_cyclic_u, coords))

    def set_active_spline_visibility(self):
        if self.symmetrize['type'] == 'COMPLEX':
            for point in self.curve.splines.active.points:
                point.hide = True
    
        else:
            for idx, point in enumerate(self.curve.splines.active.points):
                if point.hide != self.data['active']['points'][idx]['hide']:
                    point.hide = not point.hide

    def get_symmetrized_spline_data(self, debug=False):
        spline_data = self.data['active']

        loc, normal, offset = self.get_mirror_data()

        is_cyclic = spline_data['cyclic']
        points = spline_data['points']

        for idx, point, in enumerate(points):
            point['is_gap'] = is_cyclic and (idx == 0 or idx == len(points) - 1)

            if debug and point['is_gap']:
                draw_point(self.mx @ point['co'].xyz, size=10, color=yellow, modal=False)

        def get_next_point(idx, points):
            if spline_data['cyclic']:
                return points[(idx + 1) % len(points)].copy()
            else:
                if idx < len(points) - 1:
                    return points[idx + 1].copy()

        points = spline_data['points']
        intersected_points = []

        pidx = 0

        for point in points:
            if debug:
                if point['index'] == 0:
                    draw_point(point['co'], mx=self.mx, color=green, modal=False)

                elif point['index'] == len(points) - 1:
                    draw_point(point['co'], mx=self.mx, color=red, modal=False)

            dup = point.copy()
            dup['index'] = pidx
            dup['is_intersect'] = point.get('is_intersect', False)
            intersected_points.append(dup)

            next_point = get_next_point(point['index'], points)

            if debug:
                print("", point['index'], next_point['index'] if next_point else None)

            if next_point:
                if dup['is_intersect']:
                    pidx += 1
                    continue

                co = point['co'].xyz
                next_co = next_point['co'].xyz

                i = intersect_line_plane(co, next_co, loc, normal)

                if i:

                    cur_distance = (i - co).length
                    next_distance = (i - next_co).length

                    if debug:
                        print("  length1:", cur_distance, round(cur_distance, 6), round(cur_distance, 6) == 0)
                        print("  length2:", next_distance, round(next_distance, 6), round(next_distance, 6) == 0)

                    if round(cur_distance, 6) == 0:
                        dup['is_intersect'] = True

                        if debug:
                            draw_point(dup['co'], mx=self.mx, color=blue, modal=False)

                        pidx += 1
                        continue

                    elif round(next_distance, 6) == 0:
                        next_point['is_intersect'] = True

                        if debug:
                            draw_point(next_point['co'], mx=self.mx, color=blue, modal=False)

                        pidx += 1
                        continue

                    else:

                        dir = next_co - co
                        i_dir = i - co

                        if dir.normalized().dot(i_dir.normalized()) > 0.99:

                            if i_dir.length < dir.length:
                                if debug:
                                    draw_point(i, mx=self.mx, color=blue, modal=False)

                                pidx += 1

                                radius = (point['radius'] + next_point['radius']) / 2
                                tilt = (point['tilt'] + next_point['tilt']) / 2

                                is_inbetween_gap = point['is_gap'] and next_point['is_gap']

                                if is_inbetween_gap:
                                    intersected_points[-1]['is_gap'] = False

                                i_point = {'index': pidx,
                                           'co': Vector((*i, 1.0)),
                                           'radius': radius, 
                                           'tilt': tilt, 
                                           'hide': False,
                                           'select': False,
                                           'is_gap': is_inbetween_gap,
                                           'is_intersect': True}

                                intersected_points.append(i_point)

            pidx += 1

        if debug:
            printd(intersected_points, name="intersected points")

        for point in intersected_points:

            if point['is_intersect']:
                point['keep'] = True

            else:
                i = intersect_line_plane(point['co'].xyz, point['co'].xyz + normal, loc, normal)

                if debug:
                    draw_line([point['co'].xyz, i], mx=self.mx, color=blue, modal=False)

                side_dir = i - point['co'].xyz
                dot = side_dir.normalized().dot(normal)

                point['keep'] = dot >= 0

                if dot == 0:
                    point['is_intersect'] = True

            if debug:
                draw_point(point['co'].xyz, mx=self.mx, color=blue if point['is_intersect'] else green if point['keep'] else red, modal=False)

        if debug:
            printd(intersected_points, name="intersected points")

        if not any(p['keep'] for p in intersected_points):
            symmetrize = {'type': 'INVALID',
                          'mirrored_splines': []}

        elif any(p['is_intersect'] or not p['keep'] for p in intersected_points):
            data = self.get_complex_mirror_data(normal, offset, spline_data, intersected_points, debug=debug)

            symmetrize = {'type': 'COMPLEX',
                          'mirrored_splines': data}

        else:
            data = self.get_easy_mirror_data(normal, offset, spline_data, intersected_points, debug=debug)

            symmetrize = {'type': 'EASY',
                          'mirrored_splines': data}

        return symmetrize

    def get_easy_mirror_data(self, mirror_normal, mirror_offset, spline_data, points, debug=False):
        mirrored_points = []

        for point in points:
            mirror_co = point['co'].xyz.reflect(mirror_normal) + mirror_offset

            if debug:
                draw_point(mirror_co, mx=self.mx, color=yellow, modal=False)
                draw_line([mirror_co, point['co'].xyz], mx=self.mx, color=yellow, alpha=0.1, modal=False)

            m_point = {'index': point['index'],
                       'co': Vector((*mirror_co, 1.0)),
                       'radius': point['radius'], 
                       'tilt': -point['tilt'],
                       'hide': False,
                       'select': False,
                       'line': [point['co'].xyz, mirror_co]} 

            mirrored_points.append(m_point)

        mirrored_data = spline_data.copy()
        mirrored_data['index'] = len(self.curve.splines)
        mirrored_data['points'] = mirrored_points

        if debug:
            printd(mirrored_points)

        return [mirrored_data]

    def get_complex_mirror_data(self, mirror_normal, mirror_offset, spline_data, points, debug=False):
        def debug_intersected_points():
            print()

            for idx, point in enumerate(points):

                if idx == 0:
                    p = f" all points: {idx}["
                else:
                    p = f"{idx}["

                if not point['keep']:
                    p += 'X'

                if point['is_gap']:
                    p += 'G'

                if p[-1] == "[":
                    p = f"{idx}, "

                else:
                    p += "], "

                print(p, end="")

            gap_keep_indices = [idx for idx, point in enumerate(points) if point['is_gap'] and point['keep']]
            print("\ngap indices:", gap_keep_indices)

        if spline_data['cyclic'] and len([point for point in points if point['is_gap'] and point['keep']]) == 2:
            if debug:
                debug_intersected_points()

            remove_indices = [idx for idx, point in enumerate(points) if not point['keep'] and not point['is_gap']]

            if debug:
                print("remove indices:", remove_indices)

            if remove_indices:

                points[0]['is_first'] = True

                if debug:
                    print("rotating:", [point['index'] for point in points])

                rotate_list(points, amount=remove_indices[0])

                if debug:
                    print("    done:", [point['index'] for point in points])

        new_spline_points = []
        start_new_spline = False

        if debug:
            print()
            print("grouping:")

        for idx, point in enumerate(points):
            if debug:
                print(point['index'])
                print(" keep:", point['keep'])
                print(" intersect:", point['is_intersect'])

            if not point['keep']:
                if debug:
                    draw_point(point['co'], mx=self.mx, color=red, modal=False)

                continue

            if not new_spline_points or point['is_intersect']:
                start_new_spline = not start_new_spline

                if start_new_spline:
                    new_spline_points.append([])

                    if debug:
                        draw_point(point['co'], mx=self.mx, color=green, modal=False)

            new_spline_points[-1].append(point)

        if debug:
            print()
            print("splines:")

            for points in new_spline_points:
                print([p['index'] for p in points])

        def collect_original_points(idx):
            for point in keep_points:
                data['points'].append(point)

                data['points'][-1]['index'] = idx
                
                idx += 1

            return idx

        def create_mirrored_points(idx): 
            for point in reversed(keep_points):
                if not point['is_intersect']:
                    mirror_co = point['co'].xyz.reflect(mirror_normal) + mirror_offset

                    if debug:
                        draw_point(mirror_co, mx=self.mx, color=yellow, modal=False)
                        draw_line([mirror_co, point['co'].xyz], mx=self.mx, color=yellow, alpha=0.1, modal=False)

                    m_point = {'index': idx,
                               'co': Vector((*mirror_co, 1.0)),
                               'radius': point['radius'], 
                               'tilt': point['tilt'],
                               'hide': False,
                               'select': False,
                               'line': [point['co'].xyz, mirror_co]}

                    data['points'].append(m_point)

                    idx += 1

            return idx

        mirrored = []

        sidx = len(self.curve.splines) - 1

        for keep_points in new_spline_points:

            data = spline_data.copy()
            data['index'] = sidx
            data['points'] = []

            data['cyclic'] = len(keep_points) > 2 and keep_points[0]['is_intersect'] and keep_points[-1]['is_intersect']

            is_last_intersect = keep_points[-1]['is_intersect'] 

            idx = 0

            if is_last_intersect:
                idx = collect_original_points(idx)
                create_mirrored_points(idx)

            else:
                idx = create_mirrored_points(idx)
                collect_original_points(idx)

            mirrored.append(data)

            sidx +=  1

        for spline_data in mirrored:
            if (first := [p for p in spline_data['points'] if p.get('is_first')]):

                amount = first[0]['index']
                if amount:
                    rotate_list(spline_data['points'], amount=amount)

        def get_prev_point(idx):
            if spline_data['cyclic']:
                return points[(idx - 1) % len(points)]
 
            else:
                if idx > 0:
                    return points[idx - 1]

        def get_next_point(idx):
            if spline_data['cyclic']:
                return points[(idx + 1) % len(points)] 

            else:
                if idx < len(points) - 1:
                    return points[idx + 1]

        for spline_data in mirrored:
            points = spline_data['points']

            for idx, point in enumerate(points):
                if point.get('is_intersect'):
                    
                    prev_point = get_prev_point(idx)
                    next_point = get_next_point(idx)
                    
                    if prev_point and next_point:
                        prev_dir = (prev_point['co'].xyz - point['co'].xyz).normalized()
                        next_dir = (next_point['co'].xyz - point['co'].xyz).normalized()

                        angle = prev_dir.angle(next_dir)
                        if debug:
                            print("   angle:", degrees(angle), round(degrees(angle), 2))

                        if round(degrees(angle), 2) == 180:
                            point['is_redundant'] = True

                            if debug:
                                draw_point(self.mx @ point['co'].xyz, color=yellow, modal=False)

        self.has_redundant = any(point.get('is_redundant') for data in mirrored for point in data['points'])

        if debug:
            printd(mirrored)

        return mirrored

    def symmetrize_spline(self): 
        mtype = self.symmetrize['type']
        active = self.curve.splines.active

        if mtype == 'COMPLEX':
            self.curve.splines.remove(active)
            active = None

            if self.has_redundant and self.remove_redundant:
                for spline_data in self.symmetrize['mirrored_splines']:
                    spline_data['points'] = [p for p in spline_data['points'] if not p.get('is_redundant')]

        for spline_data in self.symmetrize['mirrored_splines']:
            spline = create_new_spline(self.curve, spline_data)

            if not active:
                active = spline

        self.curve.splines.active = active
