import bpy
from bpy.props import BoolProperty
from mathutils import Vector
from mathutils.geometry import intersect_line_line_2d, intersect_line_plane
from .. utils.curve import create_new_spline, get_curve_as_dict
from .. utils.draw import draw_init, draw_label, draw_point, draw_line, draw_points
from .. utils.ui import get_mouse_pos, ignore_events, is_on_screen, init_status, finish_status, force_ui_update
from .. utils.property import rotate_list
from .. utils.view import get_location_2d, get_view_origin_and_dir
from .. colors import white, red, violet, black, green

def draw_curve_knife_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)

        row.label(text=f"Curve Knife")

        row.label(text="", icon='MOUSE_LMB')
        if not op.start_loc:
            row.label(text="Start Cut")

        else:
            row.label(text="Finish Cut")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

        row.separator(factor=10)

        if op.start_loc:
            row.label(text="", icon='MOUSE_MOVE')
            row.label(text="Adjust Cut")

            if op.cuts:
                row.separator(factor=1)
                row.label(text=f"Intersections: {op.cuts['count']}")

            row.separator(factor=2)

            row.label(text="", icon='EVENT_ALT')
            row.label(text=f"Split Cut: {op.is_split_cut}")

    return draw

class Knife(bpy.types.Operator):
    bl_idname = "machin3.curve_knife"
    bl_label = "MACHIN3: Curve Knife"
    bl_description = "Cut new Curve Points and optionally Split Splines"
    bl_options = {'REGISTER', 'UNDO'}

    is_split_cut: BoolProperty(name="Split Splines at Knife Intersections", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object
            return any(spline.type in ['POLY', 'NURBS'] for spline in active.data.splines)

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

    def draw_HUD(self, context):
       if self.area == context.area:
            draw_init(self)

            dims = draw_label(context, title="Curve ", coords=Vector((self.HUD_x, self.HUD_y)), center=False, color=white, alpha=1)

            color, alpha = (green, 1) if self.start_loc else (white, 0.5)
            draw_label(context, title="Knife", coords=Vector((self.HUD_x + dims[0], self.HUD_y)), center=False, color=color, alpha=alpha)

            if self.cuts:
                self.offset += 18

                dims = draw_label(context, title="Intersections: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=white, alpha=0.5)

                title, color = (str(self.cuts['count']), white) if self.cuts['count'] else ("None", red)
                draw_label(context, title=title, coords=Vector((self.HUD_x + dims[0], self.HUD_y)), offset=self.offset, center=False, color=color, alpha=1)

            if self.is_split_cut:
                self.offset += 18

                dims = draw_label(context, title="Split", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=red, alpha=1)

            if self.start_loc:
                draw_point(self.start_loc.resized(3), size=4, alpha=0.5)

            if self.end_loc:
                draw_point(self.end_loc.resized(3), size=8, color=black, alpha=0.5)

            if self.start_loc and self.end_loc:
                draw_line([self.start_loc.resized(3), self.end_loc.resized(3)], color=violet, alpha=0.5)

            if self.coords:
                draw_points(self.coords, color=red if self.is_split_cut else green)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        self.is_alt = event.alt

        self.is_split_cut = bool(self.start_loc and self.is_alt)

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)
            
            if self.start_loc:
                self.end_loc = self.mouse_pos if self.mouse_pos != self.start_loc else None

        if not self.start_loc and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.start_loc = self.mouse_pos

            force_ui_update(context)

        if self.start_loc and self.end_loc and self.segments:
            self.cuts = self.get_cuts_2d()

            force_ui_update(context)

        if self.start_loc and self.end_loc and event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish(context)

            if self.cuts:
                self.get_cuts_3d(context)

                self.rebuild_cut_splines()
            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            self.finish(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

        context.window.cursor_set('DEFAULT')

    def invoke(self, context, event):
        self.active = context.active_object
        self.curve = self.active.data
        self.mx = self.active.matrix_world

        self.data = get_curve_as_dict(self.curve)

        self.populate_2d_point_coords(context)

        self.segments = self.get_knifeable_segments(context)

        self.cuts = []
        self.is_split_cut = False

        self.is_alt = False

        self.coords = []

        get_mouse_pos(self, context, event)
        context.window.cursor_set('KNIFE')

        self.start_loc = None
        self.end_loc = None

        init_status(self, context, func=draw_curve_knife_status(self))

        force_ui_update(context)

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def populate_2d_point_coords(self, context):
        for spline_data in self.data['splines']:
            for point in spline_data['points']:
                co2d = get_location_2d(context, self.mx @ point['co'].xyz)

                point['co2d'] = co2d

    def get_knifeable_segments(self, context):
        def get_next_point(idx):
            if is_cyclic:
                return spline_data['points'][(idx + 1) % len(spline_data['points'])]

            else:
                if idx < len(spline_data['points']) - 1:
                    return spline_data['points'][idx + 1]

        segments = []

        for spline_data in self.data['splines']:
            sidx = spline_data['index']
            is_cyclic = spline_data['cyclic']

            segments.append([])

            for idx, point in enumerate(spline_data['points']):
                next_point = get_next_point(idx)

                if next_point:

                    if not is_on_screen(context, point['co2d']) and not is_on_screen(context, next_point['co2d']):
                        continue

                    segments[-1].append((point['index'], next_point['index']))

        return segments

    def get_cuts_2d(self):
        self.coords.clear()
        cuts = {'splines': {},
                'count': 0}

        cut_line = (self.start_loc, self.end_loc)

        for sidx, segment in enumerate(self.segments):

            for idx, next_idx in segment:

                segment_line = (self.data['splines'][sidx]['points'][idx]['co2d'], self.data['splines'][sidx]['points'][next_idx]['co2d'])

                i = intersect_line_line_2d(*segment_line, *cut_line)

                if i:
                    self.coords.append(i.resized(3))

                    if sidx not in cuts['splines']:
                        cuts['splines'][sidx] = []

                    cuts['splines'][sidx].append({'segment': (idx, next_idx),
                                                  'intersect2d': i,
                                                  'intersect': None})

                    cuts['count'] += 1

        return cuts

    def get_cuts_3d(self, context):
        is_ortho = context.space_data.region_3d.view_perspective == 'ORTHO'

        if is_ortho:
            cut_origin, view_dir = get_view_origin_and_dir(context, self.start_loc)
            cut_origin_end, _ = get_view_origin_and_dir(context, self.end_loc)

            cut_normal = (cut_origin_end - cut_origin).normalized().cross(view_dir.normalized())

        else:
            cut_origin, view_dir_start = get_view_origin_and_dir(context, self.start_loc)

            _, view_dir_end = get_view_origin_and_dir(context, self.end_loc)

            cut_normal = view_dir_start.normalized().cross(view_dir_end.normalized())

        for sidx, cuts in self.cuts['splines'].items():
            for cut in cuts:
                idx, next_idx = cut['segment']

                point = self.data['splines'][sidx]['points'][idx]
                next_point = self.data['splines'][sidx]['points'][next_idx]

                co = self.mx @ point['co'].xyz
                next_co = self.mx @ next_point['co'].xyz

                i = intersect_line_plane(co, next_co, cut_origin, cut_normal)

                if i:
                    cut['intersect'] = self.mx.inverted_safe() @ i

    def rebuild_cut_splines(self):
        new_splines = []
        remove_splines = []

        for spline_data in self.data['splines']:
            sidx = spline_data['index']

            if sidx in self.cuts['splines']:
                spline = self.curve.splines[sidx]

                remove_splines.append(spline)

                cut_data = self.cuts['splines'][sidx]
                new_data = spline_data.copy()
                new_data['points'] = []

                idx = 0

                for point in spline_data['points']:

                    dup = point.copy()
                    dup['index'] = idx
                    dup['select'] = False  
                    dup['is_split'] = False
                    new_data['points'].append(dup)

                    idx += 1

                    for cut in cut_data:

                        if cut['segment'][0] == point['index']:
                            idx += 1

                            next_point = spline_data['points'][cut['segment'][1]]
                            is_after = True

                            if spline_data['cyclic'] and next_point['index'] == 0:
                                first_distance = (next_point['co'].xyz - cut['intersect']).length
                                last_distance = (point['co'].xyz - cut['intersect']).length

                                is_after = last_distance < first_distance

                            radius = (point['radius'] + next_point['radius']) / 2
                            tilt = (point['tilt'] + next_point['tilt']) / 2

                            c_point = {'index': idx if is_after else -1,
                                       'co': Vector((*cut['intersect'], 1.0)),
                                       'radius': radius, 
                                       'tilt': tilt, 
                                       'hide': False,
                                       'select': True,
                                       'is_split': self.is_split_cut}

                            if is_after:
                                new_data['points'].append(c_point)

                                if self.is_split_cut:
                                    new_data['points'].append(c_point)

                            else:
                                new_data['points'].insert(0, c_point)

                                if self.is_split_cut:
                                    new_data['points'].insert(0, c_point)

                new_splines.append(new_data)

        if self.is_split_cut:
            split_splines = []

            for spline_data in new_splines:
                new_spline = spline_data.copy()
                new_spline['cyclic'] = False   # when splitting cyclic always is False
                new_spline['points'] = []
                
                split_splines.append(new_spline)

                points = spline_data['points'].copy()

                split_indices = [idx for idx, point in enumerate(points) if point['is_split']]

                if spline_data['cyclic']:
                    points = rotate_list(points, amount=split_indices[1])

                pidx = 0 

                for idx, point in enumerate(points):
                    dup = point.copy()
                    dup['select'] = False   
                    dup['index'] = pidx

                    new_spline['points'].append(dup)

                    if pidx > 0:

                        if point['is_split'] and not idx == len(points) - 1:
                            new_spline = spline_data.copy()
                            new_spline['cyclic'] = False
                            new_spline['points'] = []

                            split_splines.append(new_spline)

                            pidx = 0
                            continue

                    pidx += 1

            new_splines = split_splines

        for idx, spline in enumerate(remove_splines):
            self.curve.splines.remove(spline)

        active = None

        for idx, spline_data in enumerate(new_splines):
            spline = create_new_spline(self.curve, spline_data)

            if spline_data['active']:
                active = spline

        if active:
            self.curve.splines.active = active
