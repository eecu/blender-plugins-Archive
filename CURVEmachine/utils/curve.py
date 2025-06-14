from . system import printd
from . math import average_locations

def get_curve_as_dict(curve, select=True, debug=False):
    data = {# all the curve's splines
            'splines': [],

            'active': None,
            'active_selection': [],
            'active_selection_mid_point': None}

    for sidx, spline in enumerate(curve.splines):
        is_active = spline == curve.splines.active

        spline_data = {'index': sidx,
                       'type': spline.type,

                       'smooth': spline.use_smooth,
                       'cyclic': spline.use_cyclic_u,

                       'endpoint': spline.use_endpoint_u,
                       'order': spline.order_u,
                       'resolution': spline.resolution_u,

                       'points': []}

        if select:
            spline_data['active'] = is_active

            if is_active:
                data['active'] = spline_data

        for pidx, point in enumerate(spline.points):
            point_data = {'index': pidx,

                          'co': point.co.copy(),
                          'radius': point.radius,
                          'tilt': point.tilt,

                          'hide': point.hide}

            if select:
                point_data['select'] = point.select

            spline_data['points'].append(point_data)

            if select and is_active and point.select:
                data['active_selection'].append(point_data)

        if select and data['active_selection']:
            data['active_selection_mid_point'] = average_locations([point['co'].xyz for point in data['active_selection']])

        data['splines'].append(spline_data)

    if debug:
        printd(data, name="curve as dict")

    return data

def verify_curve_data(data, type=''):
    if type == 'has_active_spline':
        return data['active']

    elif type == 'has_active_selection':
        return data['active_selection']

    elif type == 'is_active_end_selected':
        spline = data['active']

        if spline:
            return (spline['points'][0]['select'] or spline['points'][-1]['select'])

    elif type == 'is_active_selection_continuous':
        selection = data['active_selection']

        return all(point['index'] == selection[idx]['index'] + 1 for idx, point in enumerate(selection[1:]))

def get_curve_selection(data, debug=False):
    selection = set()

    for spline in data['splines']:
        for point in spline['points']:
            if point['select']:
                selection.add((spline['index'], point['index']))

    if debug:
        print("selection:", selection)

    return selection

def get_selection_history():
    from .. handlers import selection_history
    return selection_history

def create_new_spline(curve, spline_data, new_points=[]):
    new_spline = curve.splines.new(spline_data['type'])
    new_points = new_points if new_points else spline_data['points']

    if spline_data['active']:
        curve.splines.active = new_spline

    new_spline.points.add(len(new_points) - 1)

    for point, point_data in zip(new_spline.points, new_points):
        point.co = point_data['co']
        point.radius = point_data['radius']
        point.tilt = point_data['tilt']
        point.select = point_data['select']
        point.hide = point_data['hide']

    new_spline.use_cyclic_u = spline_data['cyclic']
    new_spline.use_smooth = spline_data['smooth']

    if spline_data['type'] == 'NURBS':
        new_spline.use_endpoint_u = spline_data['endpoint']
        new_spline.order_u = spline_data['order']
        new_spline.resolution_u = spline_data['resolution']

    return new_spline
