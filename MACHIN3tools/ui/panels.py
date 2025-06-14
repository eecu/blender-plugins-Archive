import bpy
from mathutils import Vector

import os

from .. utils.asset import is_local_assembly_asset
from .. utils.collection import get_instance_collections_recursively
from .. utils.object import is_instance_collection
from .. utils.group import get_group_base_name, get_group_polls
from .. utils.registration import get_path, get_prefs, get_pretty_version
from .. utils.ui import get_icon, get_panel_fold

from .. import bl_info

class PanelMACHIN3tools(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_machin3_tools"
    bl_label = ''
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MACHIN3"
    bl_order = 20

    @classmethod
    def poll(cls, context):
        p = get_prefs()

        if p.show_sidebar_panel:
            if get_prefs().update_available:
                return True

            if context.mode == 'OBJECT':
                return p.activate_smart_drive or p.activate_unity or p.activate_group_tools or p.activate_assetbrowser_tools or p.show_help_in_sidebar_panel

            elif context.mode == 'EDIT_MESH':
                return p.activate_extrude or p.show_help_in_sidebar_panel

    def draw_header(self, context):
        layout = self.layout

        if get_prefs().update_available:
            layout.label(text="", icon_value=get_icon("refresh_green"))

        row = layout.row(align=True)

        row.label(text=f"MACHIN3tools {get_pretty_version(bl_info['version'])}")
        row.prop(get_prefs(), 'show_help_in_sidebar_panel', text='', icon='QUESTION')

    def draw(self, context):
        layout = self.layout

        m3 = context.scene.M3
        p = get_prefs()

        if p.update_available:
            layout.separator()

            row = layout.row()
            row.scale_y = 1.2
            row.label(text="An Update is Available", icon_value=get_icon("refresh_green"))
            row.operator("wm.url_open", text="What's new?").url = 'https://machin3.io/MACHIN3tools/docs/whatsnew'

            layout.separator()

        if context.mode == 'OBJECT':
            if p.activate_smart_drive:
                panel = get_panel_fold(layout, idname='smart_drive',  text='Smart Drive', icon='AUTO', align=True, default_closed=True)
                if panel:
                    self.draw_smart_drive(m3, panel)

            if p.activate_unity:
                panel = get_panel_fold(layout, idname='unity',  text='Unity', custom_icon='unity', align=True, default_closed=True)
                if panel:
                    self.draw_unity(context, m3, panel)

            if p.activate_group_tools:
                panel = get_panel_fold(layout, idname='group',  text='Group Tools', icon='GROUP_VERTEX', align=True, default_closed=True)
                if panel:
                    self.draw_group(context, m3, panel)

            if p.activate_assetbrowser_tools:
                panel = get_panel_fold(layout, idname='assetbrowser_tools', text='Assetbrowser Tools', icon='ASSET_MANAGER', align=True, default_closed=True)
                if panel:
                    self.draw_assetbrowser_tools(context, panel)

        elif context.mode == 'EDIT_MESH':

            if p.activate_extrude:
                panel = get_panel_fold(layout, idname='extrude', text='Extrude', icon='FACESEL', align=True, default_closed=False)
                if panel:
                    self.draw_extrude(context, m3, panel)

        if p.show_help_in_sidebar_panel:
            col = layout.column(align=True)
            col.alert = True

            if panel := get_panel_fold(col, 'get_support', "Get Support", icon='GREASEPENCIL', default_closed=False):
                self.draw_support(panel)

            if panel := get_panel_fold(layout, 'documentation', "Documentation", icon='INFO', default_closed=False):
                self.draw_documentation(panel)

        if bpy.ops.machin3.machin3tools_debug.poll():
            layout.separator()
            column = layout.column()
            column.scale_y = 2
            column.operator('machin3.machin3tools_debug', text='Button')

    def draw_smart_drive(self, m3, layout):
        column = layout.column()

        b = column.box()
        b.label(text="Driver")

        col = b.column(align=True)

        row = col.split(factor=0.25, align=True)
        row.label(text="Values")
        r = row.row(align=True)
        op = r.operator("machin3.set_driver_value", text='', icon='SORT_ASC')
        op.mode = 'DRIVER'
        op.value = 'START'
        r.prop(m3, 'driver_start', text='')
        r.operator("machin3.switch_driver_values", text='', icon='ARROW_LEFTRIGHT').mode = 'DRIVER'
        r.prop(m3, 'driver_end', text='')
        op = r.operator("machin3.set_driver_value", text='', icon='SORT_ASC')
        op.mode = 'DRIVER'
        op.value = 'END'

        row = col.split(factor=0.25, align=True)
        row.label(text="Transform")
        r = row.row(align=True)
        r.prop(m3, 'driver_transform', expand=True)

        row = col.split(factor=0.25, align=True)
        row.scale_y = 0.9
        row.label(text="Axis")
        r = row.row(align=True)
        r.prop(m3, 'driver_axis', expand=True)

        row = col.split(factor=0.25, align=True)
        row.label(text="Space")
        r = row.row(align=True)
        r.prop(m3, 'driver_space', expand=True)

        b = column.box()
        b.label(text="Driven")

        col = b.column(align=True)

        row = col.split(factor=0.25, align=True)
        row.label(text="Values")
        r = row.row(align=True)
        op = r.operator("machin3.set_driver_value", text='', icon='SORT_ASC')
        op.mode = 'DRIVEN'
        op.value = 'START'
        r.prop(m3, 'driven_start', text='')
        r.operator("machin3.switch_driver_values", text='', icon='ARROW_LEFTRIGHT').mode = 'DRIVEN'
        r.prop(m3, 'driven_end', text='')
        op = r.operator("machin3.set_driver_value", text='', icon='SORT_ASC')
        op.mode = 'DRIVEN'
        op.value = 'END'

        row = col.split(factor=0.25, align=True)
        row.label(text="Transform")
        r = row.row(align=True)
        r.prop(m3, 'driven_transform', expand=True)

        row = col.split(factor=0.25, align=True)
        row.scale_y = 0.9
        row.label(text="Axis")
        r = row.row(align=True)
        r.prop(m3, 'driven_axis', expand=True)

        row = col.split(factor=0.25, align=True)
        row.label(text="Limit")
        r = row.row(align=True)
        r.prop(m3, 'driven_limit', expand=True)

        r = column.row()
        r.scale_y = 1.2
        r.operator("machin3.smart_drive", text='Drive it!', icon='AUTO')

    def draw_unity(self, context, m3, layout):
        all_prepared = True if context.selected_objects and all([obj.M3.unity_exported for obj in context.selected_objects]) else False

        column = layout.column(align=True)

        row = column.split(factor=0.3)
        row.label(text="Export")
        row.prop(m3, 'unity_export', text='True' if m3.unity_export else 'False', toggle=True)

        row = column.split(factor=0.3)
        row.label(text="Triangulate")
        row.prop(m3, 'unity_triangulate', text='True' if m3.unity_triangulate else 'False', toggle=True)

        column.separator()

        if m3.unity_export:
            column.prop(m3, 'unity_export_path', text='')

            if all_prepared:
                row = column.row(align=True)
                row.scale_y = 1.5

                if m3.unity_export_path:
                    row.operator_context = 'EXEC_DEFAULT'

                op = row.operator("export_scene.fbx", text='Export')
                op.use_selection = True
                op.apply_scale_options = 'FBX_SCALE_ALL'

                if m3.unity_export_path:
                    op.filepath = m3.unity_export_path

        if not m3.unity_export or not all_prepared:
            row = column.row(align=True)
            row.scale_y = 1.5
            row.operator("machin3.prepare_unity_export", text="Prepare + Export %s" % ('Selected' if context.selected_objects else 'Visible') if m3.unity_export else "Prepare %s" % ('Selected' if context.selected_objects else 'Visible')).prepare_only = False

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.restore_unity_export", text="Restore Transformations")

    def draw_group(self, context, m3, layout):
        p = get_prefs()

        active_group, active_child, has_group_empties, has_visible_group_empties, is_groupable, is_ungroupable, is_addable, is_removable, is_selectable, is_duplicatable, is_groupifyable, is_batchposable = get_group_polls(context)

        box = layout.box()

        if has_visible_group_empties:

            b = box.box()
            b.label(text='Group Gizmos')

            split = b.split(factor=0.5, align=True)
            split.enabled = not m3.group_origin_mode

            split.prop(m3, 'show_group_gizmos', text="Global Group Gizmos", toggle=True, icon='HIDE_OFF' if m3.show_group_gizmos else 'HIDE_ON')

            row = split.row(align=True)
            row.prop(m3, 'group_gizmo_size', text='Size')

            r = row.row(align=True)
            r.active = m3.group_gizmo_size != 1
            op = r.operator('wm.context_set_float', text='', icon='LOOP_BACK')
            op.data_path = 'scene.M3.group_gizmo_size'
            op.value = 1
            r.operator('machin3.bake_group_gizmo_size', text='', icon='SORT_ASC')

            if active_group:
                empty = context.active_object

                prefix, basename, suffix = get_group_base_name(empty.name, remove_index=False)

                b = box.box()
                b.label(text='Active Group')

                row = b.row(align=True)
                row.alignment = 'LEFT'
                row.label(text='', icon='SPHERE')

                if prefix:
                    r = row.row(align=True)
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text=prefix)

                r = row.row(align=True)
                r.alignment = 'LEFT'
                r.active = True
                r.label(text=basename)

                if suffix:
                    r = row.row(align=True)
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text=suffix)

                row = b.row()
                row.scale_y = 1.25

                if m3.group_origin_mode:
                    row.prop(m3, "group_origin_mode", text="Disable Group Origin Adjustment!", toggle=True, icon_value=get_icon('error'))
                else:
                    row.prop(m3, "group_origin_mode", text="Adjust Group Origin", toggle=True, icon='OBJECT_ORIGIN')

                if True:

                    if m3.show_group_gizmos:

                        panel = get_panel_fold(b, "active_gizmo_settings", text="Group Gizmo")

                        if panel:
                            column = panel.column(align=True)
                            split = column.split(factor=0.5, align=True)

                            split.prop(empty.M3, 'show_group_gizmo', text="Show Gizmo", toggle=True, icon='HIDE_OFF' if empty.M3.show_group_gizmo else 'HIDE_ON')

                            row = split.row(align=True)
                            row.enabled = empty.M3.show_group_gizmo
                            row.prop(empty.M3, 'group_gizmo_size', text='Size')

                            r = row.row(align=True)
                            r.active = empty.M3.group_gizmo_size != 1
                            op = r.operator('wm.context_set_float', text='', icon='LOOP_BACK')
                            op.data_path = 'active_object.M3.group_gizmo_size'
                            op.value = 1

                            row = column.row(align=True)
                            row.active = empty.M3.show_group_gizmo
                            row.prop(empty.M3, 'show_group_x_rotation', text="X", toggle=True)
                            row.prop(empty.M3, 'show_group_y_rotation', text="Y", toggle=True)
                            row.prop(empty.M3, 'show_group_z_rotation', text="Z", toggle=True)

                    panel = get_panel_fold(b, "active_poses", text="Group Poses")

                    if panel:
                        column = panel.column()
                        row = column.row(align=True)
                        row.enabled = not m3.group_origin_mode

                        if empty.M3.group_pose_COL and empty.M3.group_pose_IDX >= 0:
                            row.prop(empty.M3, 'draw_active_group_pose', text='Preview Active Pose', icon='HIDE_OFF' if empty.M3.draw_active_group_pose else 'HIDE_ON')

                            r = row.row(align=True)
                            r.enabled = empty.M3.draw_active_group_pose
                            r.prop(empty.M3, 'group_pose_alpha', text='Alpha')

                        column = panel.column()
                        column.enabled = not m3.group_origin_mode

                        if empty.M3.group_pose_COL:
                            column.template_list("MACHIN3_UL_group_poses", "", empty.M3, "group_pose_COL", empty.M3, "group_pose_IDX", rows=max(len(empty.M3.group_pose_COL), 1))

                        else:
                            column.active = False
                            column.label(text=" None")

                        split = panel.split(factor=0.3, align=True)
                        split.enabled = not m3.group_origin_mode
                        split.scale_y = 1.25
                        split.operator('machin3.set_group_pose', text='Set Pose', icon='ARMATURE_DATA').batch = False

                        s = split.split(factor=0.6, align=True)
                        row = s.row(align=True)
                        row.enabled = is_batchposable
                        row.operator('machin3.set_group_pose', text='Set Batch Pose', icon='LINKED').batch = True

                        s.operator('machin3.update_group_pose', text='Update', icon='FILE_REFRESH').index = -1

        b = box.box()
        b.label(text='Settings')

        if not active_group and m3.group_origin_mode:

            row = b.row()
            row.scale_y = 1.2
            row.prop(m3, "group_origin_mode", text="Disable Group Origin Adjustment!", toggle=True, icon_value=get_icon('error'))

        column = b.column(align=True)

        row = column.split(factor=0.3, align=True)
        row.enabled = not m3.group_origin_mode
        row.label(text="Auto Select")
        r = row.row(align=True)

        if not p.group_tools_show_context_sub_menu:
            r.prop(m3, 'show_group_select', text='', icon='HIDE_OFF' if m3.show_group_select else 'HIDE_ON')

        r.prop(m3, 'group_select', text=str(m3.group_select), toggle=True)

        row = column.split(factor=0.3, align=True)
        row.enabled = not m3.group_origin_mode
        row.label(text="Recursive")
        r = row.row(align=True)

        if not p.group_tools_show_context_sub_menu:
            r.prop(m3, 'show_group_recursive_select', text='', icon='HIDE_OFF' if m3.show_group_recursive_select else 'HIDE_ON')

        r.prop(m3, 'group_recursive_select', text=str(m3.group_recursive_select), toggle=True)

        row = column.split(factor=0.3, align=True)
        row.label(text="Hide Empties")
        r = row.row(align=True)

        if not p.group_tools_show_context_sub_menu:
            r.prop(m3, 'show_group_hide', text='', icon='HIDE_OFF' if m3.show_group_hide else 'HIDE_ON')

        r.prop(m3, 'group_hide', text=str(m3.group_hide), toggle=True)

        column = b.column(align=True)

        split = column.split(factor=0.3, align=True)
        row = split.row(align=True)
        row.enabled = not m3.group_origin_mode
        row.label(text="Draw Relations")

        row = split.row(align=True)
        r = row.row(align=True)
        r.enabled = not m3.group_origin_mode
        r.prop(m3, 'draw_group_relations', text=str(m3.draw_group_relations), icon="PARTICLE_DATA")

        r = row.row(align=True)
        r.scale_x = 1.2
        r.active =  m3.draw_group_relations
        r.prop(m3, 'draw_group_relations_active_only', text='', icon="SPHERE")
        r.prop(m3, 'draw_group_relations_objects', text='', icon="MESH_CUBE")

        b = box.box()
        b.label(text='Tools')

        column = b.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.2
        r = row.row(align=True)
        r.active = is_groupable
        r.operator("machin3.group", text="Group")
        r = row.row(align=True)
        r.active = is_ungroupable
        r.operator("machin3.ungroup", text="Un-Group")
        r = row.row(align=True)

        row = column.row(align=True)
        row.scale_y = 1
        r.active = is_groupifyable
        row.operator("machin3.groupify", text="Groupify")

        column.separator()
        column = column.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.2
        r = row.row(align=True)
        r.active = is_selectable
        r.operator("machin3.select_group", text="Select Group")
        r = row.row(align=True)
        r.active = is_duplicatable
        r.operator("machin3.duplicate_group", text="Duplicate Group")

        column = column.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.2
        r = row.row(align=True)
        r.active = is_addable and (active_group or active_child)
        r.operator("machin3.add_to_group", text="Add to Group")
        r = row.row(align=True)
        r.active = is_removable
        r.operator("machin3.remove_from_group", text="Remove from Group")

    def draw_assetbrowser_tools(self, context, layout):
        active = context.active_object
        icol = None

        is_linked = bool(active and active.library)
        is_assembly = bool(active and (icol := is_instance_collection(active)))
        is_linked_collection = bool(active and icol and icol.library)
        is_local_asset = bool(active and (asset := is_local_assembly_asset(active)))
        is_asset_instance = bool(active and not active.asset_data)

        if is_assembly:
            box = layout.box()
            column = box.column(align=True)

            icols = {}
            get_instance_collections_recursively(icols, icol)

            if True:
                split = column.split(factor=0.9, align=True)
                row = split.row(align=True)

            else:
                row = column.row(align=True)

            row.alignment = 'LEFT'
            row.label(text="Assembly ")

            if is_local_asset:
                r = row.row(align=False)
                r.active = False
                r.label(text=f"is {'recursive ' if icols else''}Local Asset {'Instance' if is_asset_instance else 'Original'}")

                if asset.preview:
                    row = column.row(align=True)
                    row.template_icon(icon_value=asset.preview.icon_id, scale=15)

                    if True:
                        row = column.row(align=True)
                        row.scale_y = 1.2
                        row.operator("machin3.edit_assembly", text='Edit Assembly', icon_value=get_icon('edit_red' if is_linked_collection else 'edit'))

                        r = row.row(align=True)
                        r.operator("machin3.update_asset_thumbnail", text='Update Thumbnail', icon='IMAGE_DATA')

                        r.prop(active.M3, "use_asset_thumbnail_helper", text="", icon='FULLSCREEN_ENTER')
                        column.separator()

                    else:
                        row = column.row(align=True)
                        row.scale_y = 1.2
                        row.operator("machin3.update_asset_thumbnail", text='Update Thumbnail', icon='IMAGE_DATA')

            elif icols or is_linked or is_linked_collection:
                r = row.row(align=False)
                r.active = is_linked or is_linked_collection
                r.alert = True if is_linked or is_linked_collection else False

                text = "is "

                if icols:
                    text += "recursive "

                if is_linked:
                    text += f"{'and ' if icols else ''}linked (object)"

                elif is_linked_collection:
                    text += f"{'and ' if icols else ''}linked (collection)"

                r.label(text=text)

            if True and not is_local_asset and not (is_linked or is_linked_collection):
                split.operator("machin3.turn_assembly_into_asset", text=" ", icon='ASSET_MANAGER')

            if True and not is_local_asset and is_assembly:
                row = column.row()
                row.scale_y = 1.2
                row.operator("machin3.edit_assembly", text='Edit Assembly', icon_value=get_icon('edit_red' if is_linked_collection else 'edit'))

                column.separator()

            split = column.split(factor=0.3, align=True)
            split.enabled = not is_linked_collection
            row = split.row()
            row.active = False
            row.alignment = 'RIGHT'
            row.label(text="Collection")

            row = split.row(align=True)
            row.alert = bool(icol.library)

            if is_local_asset:
                row.prop(icol, 'name', text='')

            else:
                row.prop(active, 'instance_collection', text='')

            split = column.split(factor=0.3, align=True)
            row = split.row()
            row.active = False
            row.alignment = 'RIGHT'

            if is_local_asset:
                row.label(text="Asset Name")
                split.prop(asset, 'name', text='')

            else:
                row.label(text="Instance Name")
                split.prop(active, 'name', text='')

            if icols:
                split = column.split(factor=0.3, align=True)
                row = split.row()
                row.active = False
                row.alignment = 'RIGHT'
                row.label(text="Children")

                col = split.column(align=True)

                for depth, cols in icols.items():
                    unique_cols = set(cols)

                    for c in unique_cols:
                        row = col.row(align=True)
                        row.alignment = 'LEFT'

                        depth_str = (depth - 1) * '  '
                        r = row.row(align=True)
                        r.active = not bool(c.library)
                        r.alert = bool(c.library)
                        r.label(text=f"{depth_str} ◦ {c.name}")

                        if (count := cols.count(icol)) > 1:
                            r = row.row(align=True)
                            r.alignment = 'LEFT'
                            r.active = False
                            r.label(text=f"x {count}")

            if is_assembly:
                split = column.split(factor=0.3, align=True)

                row = split.row()
                row.active = False
                row.alignment = 'RIGHT'

                row.label(text="Origin")

                c = split.column(align=True)
                row = c.row(align=True)
                row.prop(icol, 'instance_offset', text='')

                if icol.instance_offset != Vector():
                    row.operator("machin3.reset_assembly_origin", text="", icon='LOOP_BACK')

                row = c.row(align=True)
                row.operator("machin3.set_assembly_origin", text="from Cursor").source = "CURSOR"
                row.operator("machin3.set_assembly_origin", text="from Object").source = "OBJECT"

            column.separator()

        column = layout.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.5

        if True:
            if context.scene.M3.is_assembly_edit_scene:
                row.alert = True
                row.operator("machin3.finish_assembly_edit", text='Finish Assembly Edit', icon='CHECKMARK').is_topbar_invoke = False
            else:
                row.operator("machin3.create_assembly_asset", text='Create Assembly Asset', icon='ASSET_MANAGER')
        else:
            row.operator("machin3.create_assembly_asset", text='Create Assembly Asset', icon='ASSET_MANAGER')

        if is_assembly:
            row = column.row(align=True)
            row.scale_y = 1.2

            row.operator("machin3.disassemble_assembly", text='Disassemble', icon='NETWORK_DRIVE')

            if True:
                row.operator("machin3.create_assembly_variant", text="Create Variant", icon='DUPLICATE')

            row = column.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.remove_assembly_asset", text='Remove Assembly', icon='TRASH').remove_asset = False

            if is_local_asset:
                row.operator("machin3.remove_assembly_asset", text='Remove Asset', icon_value=get_icon('cancel')).remove_asset = True

        column = layout.column()
        column.separator()

        column.operator('machin3.clean_out_non_assets', text="Clean out Non-Assets from .blend file", icon_value=get_icon('error'))

    def draw_extrude(self, context, m3, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.cursor_spin", text='Cursor Spin')
        row.operator("machin3.punch_it", text='Punch It', icon_value=get_icon('fist'))

    def draw_support(self, layout):
        layout.scale_y = 1.5
        layout.operator('machin3.get_machin3tools_support', text='Get Support', icon='GREASEPENCIL')

    def draw_documentation(self, layout):
        layout.scale_y = 1.25

        row = layout.row(align=True)
        row.operator("wm.url_open", text='Local', icon='INTERNET_OFFLINE').url = "file://" + os.path.join(get_path(), "docs", "index.html")
        row.operator("wm.url_open", text='Online', icon='INTERNET').url = 'https://machin3.io/MACHIN3tools/docs'

        row = layout.row(align=True)
        row.operator("wm.url_open", text='FAQ', icon='QUESTION').url = 'https://machin3.io/MACHIN3tools/docs/faq'
        row.operator("wm.url_open", text='Youtube', icon='FILE_MOVIE').url = 'https://www.youtube.com/playlist?list=PLcEiZ9GDvSdWZtaUZ6_neEbAIBryEa3SO'

class PanelGreasePencilExtras(bpy.types.Panel):
    bl_idname = "MACHIN3_PT_grease_pencil_extras"
    bl_label = "Grease Pencil Extras"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 12

    @classmethod
    def poll(cls, context):
        active = context.active_object
        return active and active.type in ['GPENCIL', 'GREASEPENCIL']

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        gpd = context.active_object.data

        layer = gpd.layers.active

        if bpy.app.version < (4, 3, 0):
            if gpd.layers:
                row = column.row()
                col = row.column()
                col.template_list("GPENCIL_UL_layer", "", gpd, "layers", gpd.layers, "active_index", rows=7 if len(gpd.layers) > 1 else 2, sort_reverse=True, sort_lock=True)

                col = row.column()
                sub = col.column(align=True)
                sub.operator("gpencil.layer_add", icon='ADD', text="")
                sub.operator("gpencil.layer_remove", icon='REMOVE', text="")

                sub.separator()

                if layer:
                    sub.menu("GPENCIL_MT_layer_context_menu", icon='DOWNARROW_HLT', text="")

                    if len(gpd.layers) > 1:
                        col.separator()

                        sub = col.column(align=True)
                        sub.operator("gpencil.layer_move", icon='TRIA_UP', text="").type = 'UP'
                        sub.operator("gpencil.layer_move", icon='TRIA_DOWN', text="").type = 'DOWN'

                        col.separator()

                        sub = col.column(align=True)
                        sub.operator("gpencil.layer_isolate", icon='RESTRICT_VIEW_ON', text="").affect_visibility = True
                        sub.operator("gpencil.layer_isolate", icon='LOCKED', text="").affect_visibility = False

            else:
                column.operator("gpencil.layer_add")

        else:
            if gpd.layers:
                is_layer_active = layer is not None
                is_group_active = gpd.layer_groups.active is not None

                row = column.row()
                row.template_grease_pencil_layer_tree()

                col = row.column()
                sub = col.column(align=True)
                sub.operator_context = 'EXEC_DEFAULT'
                sub.operator("grease_pencil.layer_add", icon='ADD', text="")
                sub.operator("grease_pencil.layer_group_add", icon='NEWFOLDER', text="")
                sub.separator()

                if is_layer_active:
                    sub.operator("grease_pencil.layer_remove", icon='REMOVE', text="")
                elif is_group_active:
                    sub.operator("grease_pencil.layer_group_remove", icon='REMOVE', text="").keep_children = True

                if is_layer_active or is_group_active:
                    sub.separator()

                if layer:
                    sub.menu("GREASE_PENCIL_MT_grease_pencil_add_layer_extra", icon='DOWNARROW_HLT', text="")

                    sub = col.column(align=True)
                    sub.operator("grease_pencil.layer_move", icon='TRIA_UP', text="").direction = 'UP'
                    sub.operator("grease_pencil.layer_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            else:
                column.operator("grease_pencil.layer_add")
                column.separator()

        if layer:
            col = column.column(align=True)
            row = col.row(align=True)
            row.prop(layer, "blend_mode", expand=True)

            col.prop(layer, "opacity", text="Opacity", slider=True)

            col.separator()

            col.prop(layer, "tint_color", text="")
            col.prop(layer, "tint_factor", text="Factor", slider=True)

            if bpy.app.version < (4, 3, 0):
                col.prop(layer, "line_change", text="Stroke Thickness")
            else:
                col.prop(layer, "radius_offset", text="Stroke Thickness")
