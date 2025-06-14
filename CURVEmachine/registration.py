
classes = {'CORE': [('preferences', [('CURVEmachinePreferences', '')]),
                    ('ui.panels', [('PanelCURVEmachine', 'curve_machine')]),
                    ('ui.operators.draw', [('DrawCurveLabel', 'draw_curve_label')]),
                    ('ui.operators.help', [('GetSupport', 'get_curvemachine_support')]),
                    ('ui.operators.update', [('RemoveUpdate', 'remove_curvemachine_update'),
                                             ('UseFoundUpdate', 'use_curvemachine_update'),
                                             ('ReScanUpdates', 'rescan_curvemachine_updates')])],

           'MENU': [('ui.menus', [('MenuCURVEmachine', 'curve_machine'),
                                  ('MenuCURVEmachineContext', 'curve_machine_context')])],

           'ADD': [('operators.add', [('AddSinglePointPOLYCurve', 'add_single_point_poly_curve')])],

           'BLEND': [('operators.blend', [('Bendulate', 'bendulate'),
                                          ('Interpolate', 'interpolate_points')])],

           'KNIFE': [('operators.knife', [('Knife', 'curve_knife')])],

           'MERGE': [('operators.merge', [('MergeToLastPoint', 'merge_to_last_point')]),
                     ('operators.merge', [('MergeToCenter', 'merge_to_center')])],

           'REBUILD': [('operators.rebuild', [('GapShuffle', 'gap_shuffle'),
                                              ('Convert', 'convert_spline'),
                                              ('Reverse', 'reverse_spline')])],

           'SYMMETRIZE': [('operators.symmetrize', [('Symmetrize', 'symmetrize_curve')])],

           'TRANSFORM': [('operators.transform', [('SlidePoint', 'slide_point')])],
           }

keys = {'MENU': [{'label': 'Menu', 'keymap': 'Curve', 'idname': 'wm.call_menu', 'type': 'Y', 'value': 'PRESS', 'properties': [('name', 'MACHIN3_MT_curve_machine')]}],

        'BLEND': [{'label': 'Blendulate', 'keymap': 'Curve', 'idname': 'machin3.bendulate', 'type': 'B', 'ctrl': True, 'value': 'PRESS', 'properties': []}],

        'KNIFE': [{'label': 'Curve Knife', 'keymap': 'Curve', 'idname': 'machin3.curve_knife', 'type': 'TWO', 'value': 'PRESS', 'properties': []}],

        'MERGE': [{'label': 'Merge to Last', 'keymap': 'Curve', 'idname': 'machin3.merge_to_last_point', 'type': 'ONE', 'value': 'PRESS', 'properties': []},
                  {'label': 'Merge to Center', 'keymap': 'Curve', 'idname': 'machin3.merge_to_center', 'type': 'ONE', 'shift': True, 'value': 'PRESS', 'properties': []},
                  {'label': 'Connect', 'keymap': 'Curve', 'idname': 'curve.make_segment', 'type': 'ONE', 'alt': True, 'value': 'PRESS', 'properties': []}],

        'SYMMETRIZE': [{'label': 'Symmetrize', 'keymap': 'Curve', 'idname': 'machin3.symmetrize_curve', 'type': 'X', 'alt': True, 'value': 'PRESS', 'properties': []}],

        'TRANSFORM': [{'keymap': 'Curve', 'idname': 'machin3.slide_point', 'type': 'G', 'value': 'PRESS', 'properties': []},
                      {'keymap': 'Curve', 'idname': 'machin3.slide_point', 'type': 'G', 'value': 'DOUBLE_CLICK', 'properties': []}],
        }
