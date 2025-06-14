from . tools import prettify_tool_name

from .. items import addon_prefix_mapping

def get_last_operators(context, debug=False):
    def get_addon_prefix(idname):
        if idname.startswith('hops.'):
            return 'HO'
        elif idname.startswith('bc.'):
            return 'BC'

        for addon, prefix in addon_prefix_mapping.items():
            idnames = M3.addons[addon.lower()].get('idnames', [])

            if idname in idnames:
                return prefix

        return None

    from .. import MACHIN3toolsManager as M3

    M3.init_machin3_operator_idnames()

    operators = []

    for op in context.window_manager.operators:
        idname = op.bl_idname.replace('_OT_', '.').lower()
        label = op.bl_label.replace('MACHIN3: ', '').replace('Macro', '').strip()
        prefix = get_addon_prefix(idname)
        prop = ''

        if idname.startswith('machin3.call_'):
            continue

        elif idname == 'machin3.set_tool_by_name':
            prop = prettify_tool_name(op.properties.get('name', ''))

        elif idname == 'machin3.switch_workspace':
            prop = op.properties.get('name', '')

        elif idname == 'machin3.switch_shading':
            toggled_overlays = getattr(op, 'toggled_overlays', False)
            prop = op.properties.get('shading_type', '').capitalize()

            if toggled_overlays:
                label = f"{toggled_overlays} Overlays"

        elif idname == 'machin3.edit_mode':
            toggled_object = getattr(op, 'toggled_object', False)
            label = 'Object Mode' if toggled_object else 'Edit Mesh Mode'

        elif idname == 'machin3.mesh_mode':
            mode = op.properties.get('mode', '')
            label = f"{mode.capitalize()} Mode"

        elif idname == 'machin3.smart_vert':
            if op.properties.get('slideoverride', ''):
                prop = 'Side Extend'

            elif op.properties.get('vertbevel', False):
                prop = 'Vert Bevel'

            else:
                modeint = op.properties.get('mode')
                mergetypeint = op.properties.get('mergetype')
                mousemerge = getattr(op, 'mousemerge', False)

                mode = 'Merge ' if modeint== 0 else 'Connect'
                mergetype = 'At Mouse' if mousemerge else 'At Last' if mergetypeint == 0 else 'At Center' if mergetypeint == 1 else 'Paths'

                if mode == 'Merge ':
                    prop = mode + mergetype
                else:
                    pathtype = getattr(op, 'pathtype', False)
                    prop = mode + 'Pathtype' + pathtype.title()

        elif idname == 'machin3.transform_group':

            if op.is_setting_rest_pose:
                label = "Set Group's Rest Pose"
            elif op.is_recalling_rest_pose:
                label = "Recall Group's Rest Pose"
            else:
                pass

        elif idname == 'machin3.set_group_pose':
            is_batch = getattr(op, 'batch')

            label = f"Set Group {'Batch ' if is_batch else ''}Pose"

        elif idname == 'machin3.update_group_pose':
            is_batch = getattr(op, 'is_batch')

            label = f"Update Group's {'Batch ' if is_batch else ''}Pose"

            up = getattr(op, 'update_up', False)
            unlinked = getattr(op, 'update_unlinked', False)

            if up and unlinked:
                prop += 'Update Up and Unlinked too'
            elif up:
                prop += 'Update Up too'
            elif unlinked:
                prop += 'Update Unlinked too'

        elif idname == 'machin3.retrieve_group_pose':
            is_batch = getattr(op, 'is_batch')

            label = f"Retrieve Group's {'Batch ' if is_batch else ''}Pose"

            up = getattr(op, 'retrieve_up', False)
            unlinked = getattr(op, 'retrieve_unlinked', False)

            if up and unlinked:
                prop += 'Retrieve Up and Unlinked too'
            elif up:
                prop += 'Retrieve Up too'
            elif unlinked:
                prop += 'Retrieve Unlinked too'

        elif idname == 'machin3.remove_group_pose':
            is_batch = getattr(op, 'is_batch') and getattr(op, 'remove_batch')

            label = f"Remove Group's {'Batch ' if is_batch else ''}Pose"

            up = getattr(op, 'remove_up', False)
            unlinked = getattr(op, 'remove_unlinked', False)

            if up and unlinked:
                prop += 'Remove Up and Unlinked too'
            elif up:
                prop += 'Remove Up too'
            elif unlinked:
                prop += 'Remove Unlinked too'

        elif idname == 'machin3.smart_edge':
            if op.properties.get('is_knife_project', False):
                prop = 'KnifeProject'

            elif op.properties.get('sharp', False):
                mode = getattr(op, 'sharp_mode')

                if mode == 'SHARPEN':
                    prop = 'ToggleSharp'
                elif mode == 'CHAMFER':
                    prop = 'ToggleChamfer'
                elif mode == 'KOREAN':
                    prop = 'ToggleKoreanBevel'

            elif op.properties.get('offset', False):
                prop = 'KoreanBevel'

            elif getattr(op, 'draw_bridge_props'):
                prop = 'Bridge'

            elif getattr(op, 'is_knife'):
                prop = 'Knife'

            elif getattr(op, 'is_connect'):
                prop = 'Connect'

            elif getattr(op, 'is_starconnect'):
                prop = 'StarConnect'

            elif getattr(op, 'is_select'):
                mode = getattr(op, 'select_mode')

                if getattr(op, 'is_region'):
                    prop = 'SelectRegion'
                else:
                    prop = f'Select{mode.title()}'

            elif getattr(op, 'is_loop_cut'):
                prop = 'LoopCut'

            elif getattr(op, 'is_turn'):
                prop = 'Turn'

        elif idname == 'machin3.smart_face':
            prop = getattr(op, 'mode')

        elif idname == 'machin3.focus':
            if op.properties.get('method', 0) == 1:
                prop = 'LocalView'

        elif idname == 'machin3.mirror':
            removeall = getattr(op, 'removeall')

            if removeall:
                label = "Remove All Mirrors"

            else:
                axis = getattr(op, 'axis')
                remove = getattr(op, 'remove')

                if remove:
                    label = "Remove Mirror"

                    across = getattr(op, 'removeacross')
                    cursor = getattr(op, 'removecursor')

                else:
                    cursor = getattr(op, 'cursor')
                    across = getattr(op, 'across')

                if cursor:
                    prop = f'Cursor {axis}'
                elif across:
                    prop = f'Object {axis}'
                else:
                    prop = f'Local {axis}'

        elif idname == 'machin3.shade':
            shade_type = getattr(op, 'shade_type')

            label = f"Shade {shade_type.title()}"

            incl_children = getattr(op, 'include_children')
            incl_boolean = getattr(op, 'include_boolean_objs')

            if shade_type == 'SMOOTH':
                sharpen = getattr(op, 'sharpen')

                if sharpen:
                    prop += '+Sharpen'

            elif shade_type == 'FLAT':
                clear = getattr(op, 'clear')

                if clear:
                    prop += '+Clear'

            if incl_children:
                prop += ' +incl Children'

            if incl_boolean:
                prop += ' +incl. Boolean'

            prop = prop.strip()

        elif idname == 'machin3.purge_orphans':
            recursive = getattr(op, 'recursive')
            label = 'Purge Orphans Recursively' if recursive else 'Purge Orphans'

        elif idname == 'machin3.select_hierarchy':
            direction = getattr(op, 'direction')
            label = f"Select Hierarchy {direction.title()}"

        elif idname == 'machin3.assetbrowser_bookmark':
            mode = 'Save' if getattr(op, 'save_bookmark') else 'Clear' if getattr(op, 'clear_bookmark') else 'Jump to'

            label = f"{mode} Assetbrowser Bookmark"
            prop = str(getattr(op, 'index'))

        elif idname == 'machin3.set_assembly_origin':
            source = getattr(op, 'source')
            relative = getattr(op, 'relative_to_original')

            if True:
                location = getattr(op, 'location')
                rotation = getattr(op, 'rotation')

            label += f" from {source.title()}"

            if relative:
                prop = "relative to Original"

            if True:
                if location and not rotation:
                    label += " (Only Location)"

                elif rotation and not location:
                    label += " (Only Rotation)"

                elif not rotation and not rotation:
                    prop = "Didn't set anything actually!"

        elif idname == 'machin3.decal_library_visibility_preset':
            label = f"{label} {op.properties.get('name')}"
            prop = 'Store' if op.properties.get('store') else 'Recall'

        elif idname == 'machin3.override_decal_materials':
            undo = getattr(op, 'undo')
            label = "Undo Material Override" if undo else "Material Override"

        elif idname == 'machin3.select':
            if getattr(op, 'vgroup', False):
                prop = 'VertexGroup'
            elif getattr(op, 'faceloop', False):
                prop = 'FaceLoop'
            else:
                prop = 'Loop' if op.properties.get('loop', False) else 'Sharp'

        elif idname == 'machin3.boolean':
            prop = getattr(op, 'method', False).capitalize()

        elif idname == 'machin3.symmetrize':

            if getattr(op, 'remove'):
                prop = 'Remove'

            if getattr(op, 'partial'):
                label = 'Selected ' + label

        elif idname == 'machin3.add_object_at_cursor':
            is_pipe_init = getattr(op, 'is_pipe_init', False)

            if is_pipe_init:
                label = 'Initiate Pipe Creation'

            else:
                objtype = getattr(op, 'type', False)
                label = f"Add {objtype.title()} at Cursor"

        elif idname == 'machin3.transform_cursor':
            mode = getattr(op, 'mode', False).capitalize()
            is_array = getattr(op, 'is_array', False)
            is_macro = getattr(op, 'is_macro', False)
            is_duplicate = getattr(op, 'is_duplicate', False)

            if is_macro:
                geo = 'Mesh Selection' if context.mode == 'EDIT_MESH' else 'Object Selection'

                if is_duplicate:
                    label = f"Duplicate {mode} {geo}"

                else:
                    label = f"{mode} {geo}"

            elif is_array:

                if mode == 'Translate':
                    label = "Linear Array"
                elif mode == 'Rotate':
                    label = "Radial Array"

            else:
                label = f"{mode} Cursor"

        elif idname == 'machin3.pick_hyper_bevel':
            mirror = getattr(op, 'mirror')

            if mirror:
                label = 'Mirror Hyper Bevel'
            else:
                label = 'Remove Hyper Bevel'

        elif idname == 'machin3.point_cursor':
            align_y_axis = getattr(op, 'align_y_axis')
            label = 'Point Cursor'
            prop = 'Y' if align_y_axis else 'Z'

        elif idname == 'machin3.hyper_cursor_object':
            hide_all = getattr(op, 'hide_all_visible_wire_objs')
            sort_modifiers = getattr(op, 'sort_modifiers')
            cycle_object_tree = getattr(op, 'cycle_object_tree')

            if hide_all:
                label = "Hide All Visible Wire Objects"
            elif sort_modifiers:
                label = "Sort Modifiers + Force Gizmo Update"
            elif cycle_object_tree:
                label = "Cycle Object Tree"

        operators.append((prefix, label, idname, prop))

    if not operators:
        operators.append((None, 'Undo', 'ed.undo', ''))

    if debug:
        for prefix, label, idname, prop in operators:
            print(prefix, label, f"({idname})", prop)

    return operators
