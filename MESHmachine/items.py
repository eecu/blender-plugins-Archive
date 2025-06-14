from mathutils import Vector

prefs_tab_items = [("GENERAL", "General", ""),
                   ("PLUGS", "Plugs", ""),
                   ("ABOUT", "About", "")]

prefs_keyboard_layout_items = [("QWERTY", "QWERTY", ""),
                               ("QWERTZ", "QWERTZ", "")]

prefs_plugmode_items = [("INSERT", "Insert", ""),
                        ("REMOVE", "Remove", ""),
                        ("NONE", "None", "")]

prefs_op_context_items = [("EXEC_DEFAULT", "Simple", ""),
                          ("INVOKE_DEFAULT", "Modal", "")]

align_mode_items = [("RAYCAST", "Mouse Pointer", ""),
                    ("CURSOR", "3D Cursor", "")]

fuse_method_items = [("FUSE", "Fuse", ""),
                     ("BRIDGE", "Bridge", "")]

handle_method_items=[("FACE", "Face", ""),
                     ("LOOP", "Loop", "")]

outer_face_method_items = [("REBUILD", "Rebuild", ""),
                           ("REPLACE", "Replace", "")]

tension_preset_items = [("CUSTOM", "Custom", ""),
                        ("0.55", "0.55", ""),
                        ("0.7", "0.7", ""),
                        ("1", "1", ""),
                        ("1.33", "1.33", "")]

flatten_mode_items = [("EDGE", "Along Edge", ""),
                      ("NORMAL", "Along Normal", "")]

turn_items = [("1", "1", ""),
              ("2", "2", ""),
              ("3", "3", "")]

side_selection_items = [("A", "A", ""),
                        ("B", "B", "")]

wrap_method_items = [("SURFACEPOINT", "Surface Point", ""),
                     ("PROJECT", "Project", ""),
                     ("TARGET", "Target Normal", ""),
                     ("VERTEX", "Nearest Vertex", "")]

wrap_method_dict = {"SURFACEPOINT": "NEAREST_SURFACEPOINT",
                    "PROJECT": "PROJECT",
                    "TARGET": "TARGET_PROJECT",
                    "VERTEX": "NEAREST_VERTEX"}

loop_mapping_dict = {"NEAREST FACE": "POLYINTERP_NEAREST",
                     "PROJECTED": "POLYINTERP_LNORPROJ",
                     "NEAREST NORMAL": "NEAREST_NORMAL",
                     "NEAREST POLY NORMAL": "NEAREST_POLYNOR"}

loop_mapping_items = [("NEAREST FACE", "Nearest Face Interpolated", ""),
                      ("PROJECTED", "Projected Face Interpolated", ""),
                      ("NEAREST NORMAL", "Nearest Corner and Best Matching Normal", ""),
                      ("NEAREST POLY NORMAL", "Nearest Corner and Best Matching Face Normal", "")]

normal_flatten_threshold_preset_items = [("CUSTOM", "Custom", ""),
                                         ("5", "5", ""),
                                         ("15", "15", ""),
                                         ("30", "30", ""),
                                         ("60", "60", ""),
                                         ("90", "90", "")]

custom_normal_mirror_method_items = [("INDEX", "Index", ""),
                                     ("LOCATION", "Location", "")]

fix_center_method_items = [("CLEAR", "Clear Normals", ""),
                           ("TRANSFER", "Transfer Normals", "")]

axis_items = [("X", "X", ""),
              ("Y", "Y", ""),
              ("Z", "Z", "")]

direction_items = [("POSITIVE", "+ to -", ""),
                   ("NEGATIVE", "- to +", "")]

axis_mapping_dict = {"X": Vector((1, 0, 0)),
                     "Y": Vector((0, 1, 0)),
                     "Z": Vector((0, 0, 1))}

fillet_or_edge_items = [("FILLET", "Fillet", ""),
                        ("EDGE", "Edge", "")]

add_plug_to_library_mode_items = [("NEW", "New", ""),
                                  ("REPLACE", "Replace", "")]

plug_prop_items = [("NONE", "None", ""),
                   ("PLUG", "Plug", ""),
                   ("HANDLE", "Handle", ""),
                   ("SUBSET", "Subset", ""),
                   ("DEFORMER", "Deformer", ""),
                   ("OCCLUDER", "Occluder", "")]

looptools_circle_method = [("best", "Best fit", "Non-linear least squares"),
                           ("inside", "Fit inside", "Only move vertices towards the center")]

looptools_relax_input_items = [("all", "Parallel (all)", "Also use non-selected " "parallel loops as input"),
                               ("selected", "Selection", "Only use selected vertices as input")]

looptools_relax_interpolation_items = [("cubic", "Cubic", "Natural cubic spline, smooth results"),
                                       ("linear", "Linear", "Simple and fast linear algorithm")]

looptools_relax_iterations_items = [("1", "1", "One"),
                                    ("3", "3", "Three"),
                                    ("5", "5", "Five"),
                                    ("10", "10", "Ten"),
                                    ("25", "25", "Twenty-five")]

library_move_items = [("UP", "Up", ""),
                      ("DOWN", "Down", "")]

offsetcut_finish_type_items = [("EDGE", "Edge", ""),
                               ("CHAMFER", "Chamfer", ""),
                               ("FILLET", "Fillet", "")]

boolean_method_items = [("DIFFERENCE", "Difference", ""),
                        ("UNION", "Union", ""),
                        ("INTERSECT", "Intersect", ""),
                        ("SPLIT", "Split", "")]

boolean_solver_items = [("FAST", "Fast", ""),
                        ("EXACT", "Exact", "")]
