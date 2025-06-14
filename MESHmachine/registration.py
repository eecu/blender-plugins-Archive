
classes = {'CORE': [('ui.UILists', [('PlugLibsUIList', ''),
                                    ('StashesUIList', '')]),
                    ('properties', [('PlugLibsCollection', ''),
                                    ('PlugEmptiesCollection', ''),
                                    ('PlugScalesCollection', ''),
                                    ('StashCollection', '')]),
                    ('preferences', [('MESHmachinePreferences', '')]),
                    ('ui.operators.help', [('GetSupport', 'get_meshmachine_support')]),
                    ('ui.operators.update', [('RemoveUpdate', 'remove_meshmachine_update'),
                                             ('UseFoundUpdate', 'use_meshmachine_update'),
                                             ('ReScanUpdates', 'rescan_meshmachine_updates')]),
                    ('ui.operators.libraries', [('Move', 'move_plug_library'),
                                                ('Clear', 'clear_plug_library'),
                                                ('Reload', 'reload_plug_libraries'),
                                                ('Add', 'add_plug_library'),
                                                ('Open', 'open_plug_library'),
                                                ('Rename', 'rename_plug_library'),
                                                ('Remove', 'remove_plug_library')]),

                    ('properties', [('MeshSceneProperties', ''),
                                    ('MeshObjectProperties', '')])],

           'MENU': [('ui.menus', [('MenuMeshMachine', 'mesh_machine'),
                                  ('MenuDebug', 'mesh_machine_debug'),
                                  ('MenuLoops', 'mesh_machine_loops'),
                                  ('MenuNormals', 'mesh_machine_normals'),
                                  ('MenuSymmetrize', 'mesh_machine_symmetrize'),
                                  ('MenuPlugLibraries', 'mesh_machine_plug_libbaries'),
                                  ('MenuPlugUtils', 'mesh_machine_plug_utils'),
                                  ('MenuSelect', 'mesh_machine_select'),
                                  ('MenuContext', 'mesh_machine_context')]),
                    ('ui.operators.call_menu', [('CallMeshMachineMenu', 'call_mesh_machine_menu')])],

           'PANEL': [('ui.panels', [('PanelMESHmachine', 'mesh_machine'),
                                    ('PanelHelp', 'help_mesh_machine')])],

           'FUSE': [('operators.fuse', [('Fuse', 'fuse')])],
           'CHANGEWIDTH': [('operators.change_width', [('ChangeWidth', 'change_width')])],
           'FLATTEN': [('operators.flatten', [('Flatten', 'flatten')])],

           'UNFUSE': [('operators.unfuse', [('Unfuse', 'unfuse')])],
           'REFUSE': [('operators.refuse', [('Refuse', 'refuse')])],
           'UNCHAMFER': [('operators.unchamfer', [('Unchamfer', 'unchamfer')])],
           'UNBEVEL': [('operators.unbevel', [('Unbevel', 'unbevel')])],
           'UNFUCK': [('operators.unfuck', [('Unfuck', 'unfuck')])],

           'TURNCORNER': [('operators.turn_corner', [('TurnCorner', 'turn_corner')])],
           'QUADCORNER': [('operators.quad_corner', [('QuadCorner', 'quad_corner')])],

           'MARKLOOP': [('operators.mark_loop', [('MarkLoop', 'mark_loop')])],

           'BOOLEANCLEANUP': [('operators.boolean_cleanup', [('BooleanCleanup', 'boolean_cleanup')])],
           'CHAMFER': [('operators.chamfer', [('Chamfer', 'chamfer')])],
           'OFFSET': [('operators.offset', [('Offset', 'offset')])],
           'OFFSETCUT': [('operators.offset_cut', [('OffsetCut', 'offset_cut')])],

           'STASHES': [('operators.stash', [('CreateStash', 'create_stash'),
                                            ('ViewStashes', 'view_stashes'),
                                            ('TransferStashes', 'transfer_stashes'),
                                            ('ViewOrphanStashes', 'view_orphan_stashes')]),
                       ('ui.operators.stash', [('RemoveStash', 'remove_stash'),
                                               ('SwapStash', 'swap_stash'),
                                               ('SweepStashes', 'sweep_stashes')]),
                       ('operators.draw.draw_transferred_stashes', [('DrawTransferredStashes', 'draw_transferred_stashes')])],

           'CONFORM': [('operators.conform', [('Conform', 'conform')])],

           'NORMALS': [('operators.normals', [('NormalFlatten', 'normal_flatten'),
                                              ('NormalStraighten', 'normal_straighten'),
                                              ('NormalClear', 'normal_clear'),
                                              ('NormalTransfer', 'normal_transfer')])],

           'SYMMETRIZE': [('operators.symmetrize', [('Symmetrize', 'symmetrize')]),
                          ('operators.draw.draw_symmetrize', [('DrawSymmetrize', 'draw_symmetrize')])],

           'REALMIRROR': [('operators.real_mirror', [('RealMirror', 'real_mirror')]),
                          ('operators.draw.draw_realmirror', [('DrawRealMirror', 'draw_realmirror')])],

           'SELECT': [('operators.select', [('VSelect', 'vselect'),
                                            ('SSelect', 'sselect'),
                                            ('LSelect', 'lselect'),
                                            ('Select', 'select')])],

           'INSERTREMOVE': [('operators.insert', [('Insert', 'insert_plug'),
                                                  ('Remove', 'remove_plug')])],

           'PLUG': [('operators.plug', [('Plug', 'plug'),
                                        ('DeletePlug', 'delete_plug')]),
                    ('operators.draw.draw_plug', [('DrawPlug', 'draw_plug')])],

           'CREATE': [('operators.create', [('Create', 'create_plug'),
                                            ('AddPlugToLibrary', 'add_plug_to_library'),
                                            ('SetPlugProps', 'set_plug_props'),
                                            ('ClearPlugProps', 'clear_plug_props')])],

           'VALIDATE': [('operators.validate', [('Validate', 'validate_plug')])],

           'LOOPTOOLS': [('operators.wrappers.looptools_circle', [('LoopToolsCircle', 'looptools_circle')]),
                         ('operators.wrappers.looptools_relax', [('LoopToolsRelax', 'looptools_relax')])],

           'QUICKPATCH': [('operators.quick_patch', [('QuickPatch', 'quick_patch')])],

           'BOOLEAN': [('operators.boolean', [('Boolean', 'boolean')]),
                       ('operators.boolean_apply', [('BooleanApply', 'boolean_apply')]),
                       ('operators.boolean_duplicate', [('BooleanDuplicate', 'boolean_duplicate')]),
                       ('operators.make_unique', [('MakeUnique', 'make_unique')])],

           'WEDGE': [('operators.wedge', [('Wedge', 'wedge')])],

           'DEBUG': [('operators.debug', [('GetAngle', 'get_angle'),
                                          ('GetLength', 'get_length'),
                                          ('DrawDebug', 'draw_debug'),
                                          ('DebugHUD', 'debug_hud'),
                                          ('DebugToggle', 'meshmachine_debug')])],
           }

keys = {'MENU': [{'label': 'Edit Mode', 'keymap': 'Mesh', 'idname': 'machin3.call_mesh_machine_menu', 'type': 'Y', 'value': 'PRESS', 'properties': [('idname', 'mesh_machine')]},
                 {'label': 'Object Mode', 'keymap': 'Object Mode', 'idname': 'machin3.call_mesh_machine_menu', 'type': 'Y', 'value': 'PRESS', 'properties': [('idname', 'mesh_machine')]}],

        'SYMMETRIZE': [{'keymap': 'Mesh', 'idname': 'machin3.symmetrize', 'type': 'X', 'alt': True, 'value': 'PRESS', 'properties': [('flick', True), ('objmode', False)]}],

        'SELECT': [{'info': ["This keymap should be the same as your native Blender Loop Select Keymapping", "If you don't use ALT + LMB for loop selecting, remap this accordingly!"], 'label': 'Select', 'keymap': 'Mesh', 'idname': 'machin3.select', 'type': 'LEFTMOUSE', 'alt': True, 'value': 'PRESS'}],

        }
