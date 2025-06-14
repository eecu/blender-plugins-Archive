import bpy
from mathutils import Vector
from .. utils.curve import get_curve_as_dict, get_selection_history, get_curve_selection, create_new_spline
from .. utils.system import printd
from .. utils.math import average_locations
from .. utils.draw import draw_point, draw_fading_label
from .. colors import yellow, red

class MergeToLastPoint(bpy.types.Operator):
    bl_idname = "machin3.merge_to_last_point"
    bl_label = "MACHIN3: Merge to last Point"
    bl_description = "Merge Spline Point(s) to Last Selected Point"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object

            if active.type == 'CURVE':
                curve = active.data

                data = get_curve_as_dict(curve, debug=False)
                selection = get_curve_selection(data)
                history = get_selection_history()

                if history:
                    selection.discard(history[-1])
                    return selection

    def execute(self, context):
        active = context.active_object
        curve = active.data

        history = get_selection_history()

        data = get_curve_as_dict(curve, debug=False)
        selection = get_curve_selection(data)
        last = history[-1]

        selection.discard(last)

        same_spline_merge, other_spline_merge, couldnt_merge = self.verify_point_selection(data, selection, last, debug=False)

        if same_spline_merge:

            new_points, spline_data = self.get_same_spline_merge_new_points(data, last, same_spline_merge, debug=False)

            curve.splines.remove(curve.splines[last[0]])

        elif other_spline_merge:

            new_points, spline_data = self.get_other_spline_merge_new_points(context, data, last, other_spline_merge, debug=False)

            other_spline = curve.splines[other_spline_merge[0][0]]
            last_point_spline = curve.splines[last[0]]

            curve.splines.remove(last_point_spline)
            curve.splines.remove(other_spline)

        if same_spline_merge or other_spline_merge:
            create_new_spline(curve, spline_data, new_points)

            if couldnt_merge:
                draw_fading_label(context, ["Illegal Selection",
                                            "Some, but not not all of the selected points in the selection could be merged"], color=[red, yellow])

            return {'FINISHED'}

        else:
            draw_fading_label(context, ["Illegal Selection",
                                        "Nothing could be merged!",
                                        "Make a selection, that - once merged - doesn't create a self-intersecting spline, or a cyclic loop"], color=[red, yellow])

            return {'CANCELLED'}

    def verify_point_selection(self, data, selection, last, debug=False):
        if debug:
            print("merging to:", last)
            print("selection:")
        
        same_spline_merge = []
        other_spline_merge = []
        couldnt_merge = []

        for sidx, pidx in selection:
            if debug:
                print("spline:", sidx, "point:", pidx)

            if sidx == last[0]:

                if debug:
                    print(" point is on the same spline as the activ")

                if last[1] > pidx:
                    if all((sidx, idx) in selection for idx in range(pidx + 1, last[1])):
                        if debug:
                            print("  last is higher, and all points in between are selected")
                        same_spline_merge.append((sidx, pidx))
                    else:
                        if debug:
                            print("  can not be merged due to gaps")
                        couldnt_merge.append((sidx, pidx))

                else:
                    if all((sidx, idx) in selection for idx in range(last[1] + 1, pidx)):
                        if debug:
                            print("  last is lower, and all points in between are selected")
                        same_spline_merge.append((sidx, pidx))
                    else:
                        if debug:
                            print("  can not be merged due to gaps")
                        couldnt_merge.append((sidx, pidx))

            else:
                if debug:
                    print(" point is on another spline")

                if not data['splines'][last[0]]['cyclic'] and not data['splines'][sidx]['cyclic']:
                    if debug:
                        print("  both splines are not cyclic, proceeding")

                    if last[1] == 0 or last[1] == len(data['splines'][last[0]]['points']) - 1:
                        if debug:
                            print("   last is spline end point, proceeding")

                        spline_data = data['splines'][sidx]

                        if pidx == 0 or pidx == len(spline_data['points']) - 1:
                            if debug:
                                 print("    point is endpoint, can be merged")
                            other_spline_merge.append((sidx, pidx))

                        else:
                            if debug:
                                print("    point is not endpoint, checking other selected points on that spline")
                            if all((sidx, idx) in selection for idx in range(pidx + 1, len(spline_data['points']))):
                                if debug:
                                    print("     all points toward the end are selected, can be merged")
                                other_spline_merge.append((sidx, pidx))

                            elif all((sidx, idx) in selection for idx in range(pidx)):
                                if debug:
                                    print("     all points toward the beginning are selected, can be merged")
                                other_spline_merge.append((sidx, pidx))

                            else:
                                if debug:
                                    print("     there apears to be gaps toward the edns, can't be merged")
                                couldnt_merge.append((sidx, pidx))
                    else:
                        if debug:
                             print("   last is not spline endpoint, can't be merged")
                        couldnt_merge.append((sidx, pidx))
                else:
                    if debug:
                        print("  at least one of the two splines is cyclic, can't be merged")
                    couldnt_merge.append((sidx, pidx))

        return same_spline_merge, other_spline_merge, couldnt_merge

    def get_same_spline_merge_new_points(self, data, last, same_spline_merge, debug=False):
        sidx = last[0]
        spline_data = data['splines'][sidx]

        new_points = []

        for point in spline_data['points']:
            pidx = point['index']

            if (sidx, pidx) in same_spline_merge:
                continue
            else:
                new_points.append(point)

        if debug:
            print("new points", [point['index'] for point in new_points])

        return new_points, spline_data

    def get_other_spline_merge_new_points(self, data, last, other_spline_merge, debug=False):
        other_spline_merge.sort()

        sidx = other_spline_merge[0][0]
        other_spline_data = data['splines'][sidx]

        merge_points = [point[1] for point in other_spline_merge if point[0] == sidx]

        if debug:
            print(f"only points of first other splines ({sidx}) though:", merge_points)

        if merge_points[0] == 0:
            if debug:
                print(" it's the beginning of the spline")

            trimmed_merge_points = []

            for point in other_spline_data['points']:
                if point['index'] in merge_points:
                    trimmed_merge_points.append(point['index'])
                else:
                    break

        else:
            if debug:
                print(" it's the end of the spline")

            trimmed_merge_points = []

            for point in reversed(other_spline_data['points']):
                if point['index'] in merge_points:
                    trimmed_merge_points.append(point['index'])
                else:
                    break
        if debug:
            print(" trimmed merge points:", trimmed_merge_points)

        spline_data = data['splines'][last[0]]

        new_points = []

        if last[1] == 0:
            if debug:
                print("merge target is beginning")

            if trimmed_merge_points[0] == 0:
                for point in reversed(other_spline_data['points']):
                    if point['index'] not in trimmed_merge_points:
                        new_points.append(point)

            else:
                for point in other_spline_data['points']:
                    if point['index'] not in trimmed_merge_points:
                        new_points.append(point)

            new_points.extend(spline_data['points'])

        else:
            if debug:
                print("merge target is end")

            new_points.extend(spline_data['points'])

            if trimmed_merge_points[0] == 0:
                for point in other_spline_data['points']:
                    if point['index'] not in trimmed_merge_points:
                        new_points.append(point)

            else:
                for point in reversed(other_spline_data['points']):
                    if point['index'] not in trimmed_merge_points:
                        new_points.append(point)
        if debug:
            print("new points", [point['index'] for point in new_points])

        return new_points, spline_data

class MergeToCenter(bpy.types.Operator):
    bl_idname = "machin3.merge_to_center"
    bl_label = "MACHIN3: Merge to Center"
    bl_description = "Merge Selected Points to Averaged Location, optionally across 2 Splines"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_CURVE':
            active = context.active_object

            if active.type == 'CURVE':
                curve = active.data

                data = get_curve_as_dict(curve, debug=False)
                selection = get_curve_selection(data)
                return len(selection) > 1

    def execute(self, context):
        active = context.active_object
        curve = active.data

        data = get_curve_as_dict(curve, debug=False)
        selection = get_curve_selection(data)

        separated = self.verify_point_selection(selection, debug=False)

        if separated:

            if len(separated) > 1:

                new_points, spline_data, sidx1, sidx2 = self.get_other_spline_merge_new_points(context, data, separated, debug=False)

                if new_points:

                    spline1 = curve.splines[sidx1]
                    spline2 = curve.splines[sidx2]

                    curve.splines.remove(spline1)
                    curve.splines.remove(spline2)

                    create_new_spline(curve, spline_data, new_points)

            else:
                new_points, spline_data = self.get_same_spline_merge_new_points(data, separated)

                curve.splines.remove(curve.splines[spline_data['index']])

                create_new_spline(curve, spline_data, new_points)

            return {'FINISHED'}

        else:
            draw_fading_label(context, ["Illegal Selection",
                                        "Nothing could be merged!",
                                        "Make a selection, that - once merged - doesn't create a self-intersecting spline, or a cyclic loop"], color=[red, yellow])
            return {'CANCELLED'}

    def verify_point_selection(self, selection, debug=False):
        if debug:
            print("selection:", selection)

        sorted_selection = sorted(list(selection))

        if debug:
            print("sorted:", sorted_selection)

        separated = {}

        for sidx, pidx in sorted_selection:
            if sidx in separated:
                separated[sidx].append(pidx)
            else:
                separated[sidx] = [pidx]

        if debug:
            printd(separated, "separated selections")

        delete_splines = []

        if debug:
            print()

        for sidx, selection in separated.items():
            if debug:
                print(sidx, selection)

            if not all(pidx == selection[idx] + 1 for idx, pidx in enumerate(selection[1:])):
                if debug:
                    print(" selection has gaps has gaps, ignoring")

                delete_splines.append(sidx)

        for sidx in delete_splines:
            del separated[sidx]

        if debug:
            printd(separated, "continous selections")

        return separated

    def get_same_spline_merge_new_points(self, data, separated):
        sidx = list(separated)[0]
        spline_data = data['splines'][sidx]

        merge_co = average_locations([spline_data['points'][pidx]['co'].xyz for pidx in separated[sidx]])

        new_points = []
        first_merged = None

        for point in spline_data['points']:

            if point['index'] in separated[sidx]:

                if not first_merged:
                    merged_point = point.copy()
                    merged_point['co'] = Vector((*merge_co, 1))
                    merged_point['index'] = -1
                    new_points.append(merged_point)
                    first_merged = True

            else:
                new_points.append(point)

        return new_points, spline_data

    def get_other_spline_merge_new_points(self, context, data, separated, debug=False):
        new_points = []
        sidx1 = None
        sidx2 = None
        spline_data1 = None

        if len(separated) == 2:
            sidx1, sidx2 = list(separated)

            sel1 = separated[sidx1]
            spline_data1 = data['splines'][sidx1]

            sel2 = separated[sidx2]
            spline_data2 = data['splines'][sidx2]

            if sel1[0] == 0 or sel1[-1] == len(spline_data1['points']) - 1:

                if debug:
                    print(sidx1, "has end selected, proceeding")

                if sel2[0] == 0 or sel2[-1] == len(spline_data2['points']) - 1:
                    if debug:
                        print(sidx2, "has end selected too, proceeding")

                    merge_co = average_locations([spline_data1['points'][pidx]['co'].xyz for pidx in sel1] + [spline_data2['points'][pidx]['co'].xyz for pidx in sel2])

                    if sel1[0] == 0:
                        if debug:
                            print(" beginning of first spline is selected")

                        if sel2[0] == 0:
                            if debug:
                                print("  beginning of second spline is selected")
                            second_spline_points = reversed(spline_data2['points'])

                        else:
                            if debug:
                                print("  end of second spline is selected")
                            second_spline_points = spline_data2['points']

                        first_merged = None

                        for point in second_spline_points:
                            if point['index'] in sel2:
                                if not first_merged:
                                    merged_point = point.copy()
                                    merged_point['co'] = Vector((*merge_co, 1))
                                    merged_point['index'] = -1
                                    new_points.append(merged_point)
                                    first_merged = True
                            else:
                                new_points.append(point)

                        for point in spline_data1['points']:
                            if point['index'] not in sel1:
                                new_points.append(point)

                    else:
                        if debug:
                            print(" end of first spline is selected")

                        first_merged = None

                        for point in spline_data1['points']:
                            if point['index'] in sel1:
                                if not first_merged:
                                    merged_point = point.copy()
                                    merged_point['co'] = Vector((*merge_co, 1))
                                    merged_point['index'] = -1
                                    new_points.append(merged_point)
                                    first_merged = True
                            else:
                                new_points.append(point)

                        if sel2[0] == 0:
                            if debug:
                                print("  beginning of second spline is selected")
                            second_spline_points = spline_data2['points']

                        else:
                            if debug:
                                print("  end of second spline is selected")
                            second_spline_points = reversed(spline_data2['points'])

                        for point in second_spline_points:
                            if point['index'] not in sel2:
                                new_points.append(point)

                    if debug:
                        print("new points", [point['index'] for point in new_points])

                else:
                    draw_fading_label(context, ["Illegal Selection",
                                                "To Center Merge points across two splines, you need to have a continuous selection at either end of the two splines."], color=[red, yellow])

            else:
                draw_fading_label(context, ["Illegal Selection",
                                            "To Center Merge points across two splines, you need to have a continuous selection at either end of the two splines."], color=[red, yellow])
        else:
            draw_fading_label(context, ["Illegal Selection",
                                        "You can't merge spline points accross more than 2 splines"], color=[red, yellow])

        return new_points, spline_data1, sidx1, sidx2
