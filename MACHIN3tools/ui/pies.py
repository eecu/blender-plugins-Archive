import bpy
from bpy.types import Menu

import os

from mathutils import Vector

from .. utils.asset import is_local_assembly_asset
from .. utils.collection import get_scene_collections_old
from .. utils.light import get_area_light_poll
from .. utils.math import compare_quat
from .. utils.modifier import get_auto_smooth
from .. utils.object import is_decal, is_instance_collection, is_linked_object
from .. utils.registration import get_prefs
from .. utils.render import get_user_presets, is_cycles_view, is_eevee_view, is_volume
from .. utils.scene import get_composite_dispersion, get_composite_glare
from .. utils.snap import get_sorted_snap_elements
from .. utils.system import abspath, get_temp_dir
from .. utils.tools import get_active_tool, get_tool_options, get_tools_from_context
from .. utils.ui import build_pie_button_stack, draw_pie_button_stack, get_icon
from .. utils.view import get_shading_type, is_local_view
from .. utils.world import get_use_world, get_world_surface_inputs

from .. import MACHIN3toolsManager as M3

class PieModes(Menu):
    bl_idname = "MACHIN3_MT_modes_pie"
    bl_label = "Modes"

    def draw(self, context):
        layout = self.layout
        toolsettings = context.tool_settings
        active = context.active_object
        sel = context.selected_objects

        if True:
            self.show_assembly_edit = context.mode == 'OBJECT' and get_prefs().activate_assetbrowser_tools and get_prefs().object_mode_show_assembly_edit
            self.show_finish_assembly_edit = context.mode == 'OBJECT' and get_prefs().activate_assetbrowser_tools and get_prefs().object_mode_show_assembly_edit_finish and context.scene.M3.is_assembly_edit_scene

        self.show_edit_toggle = context.mode == 'OBJECT' and active and get_prefs().modes_pie_object_mode_top_show_edit
        self.show_sculpt_toggle = context.mode == 'OBJECT' and active and get_prefs().modes_pie_object_mode_top_show_sculpt

        self.show_ungroup = context.mode == 'OBJECT' and active and get_prefs().activate_group_tools and get_prefs().modes_pie_object_mode_top_show_ungroup and active.M3.is_group_empty
        self.show_select_group = context.mode == 'OBJECT' and active and active.select_get() and len(sel) == 1 and get_prefs().activate_group_tools and not self.show_ungroup and get_prefs().modes_pie_object_mode_top_show_select_group and active.M3.is_group_object
        self.show_create_group = context.mode == 'OBJECT' and get_prefs().activate_group_tools and not self.show_ungroup and not self.show_select_group and get_prefs().modes_pie_object_mode_top_show_create_group and bool(sel)

        self.show_dual_mesh = False

        pie = layout.menu_pie()

        if active:
            if context.mode in ['OBJECT', 'EDIT_MESH', 'EDIT_ARMATURE', 'POSE', 'EDIT_CURVE', 'EDIT_TEXT', 'EDIT_SURFACE', 'EDIT_METABALL', 'EDIT_LATTICE', *self.get_grease_pencil_modes(), 'EDIT_CURVES', 'SCULPT_CURVES']:

                if context.mode == 'OBJECT' and (linked := is_linked_object(active)):
                    self.draw_linked(context, active, linked, pie)
                    return

                if active.type == 'MESH':
                    self.draw_mesh(context, active, toolsettings, pie)

                elif active.type == 'ARMATURE':
                    self.draw_armature(active, pie)

                elif active.type in ['CURVE', 'FONT', 'SURFACE', 'META', 'LATTICE']:
                    self.draw_misc(context, active, pie)

                elif active.type == 'CURVES':
                    self.draw_curves(context, active, pie)

                elif active.type in ['GPENCIL', 'GREASEPENCIL']:
                    self.draw_grease_pencil(context, active, toolsettings, pie)

                elif active.type == 'EMPTY':
                    self.draw_empty(context, active, None, pie)

            elif context.mode == "SCULPT":
                self.draw_sculpt(context, active, pie)

            elif context.mode == "PAINT_TEXTURE":
                self.draw_paint_texture(context, active, pie)

            elif context.mode == "PAINT_WEIGHT":
                self.draw_paint_weight(context, active, pie)

            elif context.mode == "PAINT_VERTEX":
                self.draw_paint_vertex(context, active, pie)

            elif context.mode == "PARTICLE":
                self.draw_particle(context, active, toolsettings, pie)

        else:
            self.draw_no_active(context, pie)

    def draw_linked(self, context, active, linked, pie):
        if active.type == 'EMPTY' and get_prefs().activate_assetbrowser_tools:
            self.draw_empty(context, active, linked, pie)

        else:
            blendpath = abspath(linked[0].library.filepath)
            library = linked[0].library.name

            pie.operator('machin3.reload_actives_libraries', text="Reload Library", icon_value=get_icon('refresh'))

            pie.separator()

            if get_prefs().activate_assetbrowser_tools:
                pie.operator("machin3.make_id_local", text="Make Local", icon='UNLINKED')

            else:
                pie.operator("object.make_local", text="Make Local", icon='UNLINKED').type = 'SELECT_OBDATA'

            stack = []

            if True and self.show_finish_assembly_edit:
                build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

            self.add_contextual_group_button(stack)

            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.open_library_blend', text=f"Open {os.path.basename(blendpath)}", icon='FILE_BLEND', props={'blendpath': blendpath, 'library': library})

            draw_pie_button_stack(stack, pie)

            pie.separator()

            pie.separator()

            pie.separator()

            pie.separator()

    def draw_mesh(self, context, active, toolsettings, pie):
        def draw_mesh_in_view3d():

            depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
            pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

            depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
            pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

            depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
            pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

            if context.mode == 'EDIT_MESH':
                pie.operator("machin3.edit_mode", text='Object', icon_value=get_icon('object'))

            else:

                stack = []

                if True and self.show_finish_assembly_edit:
                    build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

                self.add_contextual_group_button(stack)

                if self.show_sculpt_toggle:
                    build_pie_button_stack(stack, 'OPERATOR', operator='object.mode_set', text="Sculpt", icon='SCULPTMODE_HLT', props={'mode': 'SCULPT'})

                if self.show_edit_toggle:
                    build_pie_button_stack(stack, 'OPERATOR', operator='machin3.edit_mode', text="Edit", icon_value=get_icon('edit_mesh'))

                draw_pie_button_stack(stack, pie)

            self.draw_mesh_tiny(context, pie)

            if M3.get_addon("HyperCursor") and context.mode == 'EDIT_MESH':
                box = pie.split()
                column = box.column()

                row = column.row(align=True)
                row.scale_y = 1.2

                row.label(text="Gizmos")

                depress = getattr(active, 'HC') and active.HC.geometry_gizmos_show_previews
                row.operator("machin3.toggle_gizmo_data_layer_preview", text="Preview", depress=depress)

                if tuple(bpy.context.scene.tool_settings.mesh_select_mode) in [(False, True, False), (False, False, True)]:
                    row.operator("machin3.toggle_gizmo", text="Toggle")

            else:
                pie.separator()

            if get_prefs().activate_surface_slide:
                hassurfaceslide = [mod for mod in active.modifiers if mod.type == 'SHRINKWRAP' and 'SurfaceSlide' in mod.name]

                if context.mode == 'EDIT_MESH':
                    box = pie.split()
                    column = box.column(align=True)

                    row = column.row(align=True)
                    row.scale_y = 1.2

                    if hassurfaceslide:
                        row.operator("machin3.finish_surface_slide", text='Finish Surface Slide', icon='OUTLINER_DATA_SURFACE')
                    else:
                        row.operator("machin3.surface_slide", text='Surface Slide', icon='OUTLINER_DATA_SURFACE')

                elif hassurfaceslide:
                    box = pie.split()
                    column = box.column(align=True)

                    row = column.row(align=True)
                    row.scale_y = 1.2
                    row.operator("machin3.finish_surface_slide", text='Finish Surface Slide', icon='OUTLINER_DATA_SURFACE')

                else:
                    pie.separator()

            else:
                pie.separator()

            if context.mode == "EDIT_MESH":
                box = pie.split()
                column = box.column()

                row = column.row()
                row.scale_y = 1.2
                row.prop(context.scene.M3, "pass_through", text="Pass Through" if context.scene.M3.pass_through else "Occlude", icon="XRAY")

                column.prop(toolsettings, "use_mesh_automerge", text="Auto Merge")

            else:
                pie.separator()

        def draw_mesh_in_image_editor():
            if context.mode == "OBJECT":
                pie.operator("machin3.image_mode", text="UV Edit", icon="GROUP_UVS").mode = "UV"

                pie.operator("machin3.image_mode", text="Paint", icon="TPAINT_HLT").mode = "PAINT"

                pie.operator("machin3.image_mode", text="Mask", icon="MOD_MASK").mode = "MASK"

                pie.operator("machin3.image_mode", text="View", icon="FILE_IMAGE").mode = "VIEW"

            elif context.mode == "EDIT_MESH":
                pie.operator("machin3.uv_mode", text="Vertex", icon_value=get_icon('vertex')).mode = "VERTEX"

                pie.operator("machin3.uv_mode", text="Face", icon_value=get_icon('face')).mode = "FACE"

                pie.operator("machin3.uv_mode", text="Edge", icon_value=get_icon('edge')).mode = "EDGE"

                pie.operator("object.mode_set", text="Object", icon_value=get_icon('object')).mode = "OBJECT"

                pie.prop(context.scene.M3, "uv_sync_select", text="Sync Selection", icon="UV_SYNC_SELECT")

                if toolsettings.use_uv_select_sync:
                    pie.separator()
                else:
                    pie.operator("machin3.uv_mode", text="Island", icon_value=get_icon('island')).mode = "ISLAND"

                pie.separator()

                pie.separator()

        if context.area.type == "VIEW_3D":
            draw_mesh_in_view3d()

        if context.area.type == "IMAGE_EDITOR":
            draw_mesh_in_image_editor()

    def draw_armature(self, active, pie):

        pie.operator("object.mode_set", text="Edit Mode", icon='EDITMODE_HLT').mode = "EDIT"

        pie.operator("object.mode_set", text="Pose", icon='POSE_HLT').mode = "POSE"

        pie.separator()

        stack = []

        if True and self.show_finish_assembly_edit:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

        self.add_contextual_group_button(stack)

        if active.mode == 'OBJECT':
            if self.show_edit_toggle:
                build_pie_button_stack(stack, 'OPERATOR', operator="object.editmode_toggle", text='Edit', icon='EDITMODE_HLT')

        else:
            build_pie_button_stack(stack, 'OPERATOR', operator="object.editmode_toggle", text='Object', icon='OBJECT_DATAMODE')

        draw_pie_button_stack(stack, pie)

        pie.separator()

        pie.separator()

        pie.separator()

        pie.separator()

    def draw_misc(self, context, active, pie):

        pie.operator("object.mode_set", text="Edit Mode", icon='EDITMODE_HLT').mode = "EDIT"

        pie.separator()

        pie.separator()

        stack = []

        if True and self.show_finish_assembly_edit:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

        self.add_contextual_group_button(stack)

        if active.mode == 'OBJECT':
            if self.show_edit_toggle:
                build_pie_button_stack(stack, 'OPERATOR', operator='object.editmode_toggle', text='Edit', icon='EDITMODE_HLT')
        else:
            build_pie_button_stack(stack, 'OPERATOR', operator='object.editmode_toggle', text='Object', icon='OBJECT_DATAMODE')

        draw_pie_button_stack(stack, pie)

        pie.separator()

        pie.separator()

        pie.separator()

        if context.mode in ['EDIT_SURFACE', 'EDIT_METABALL']:
            box = pie.split()
            column = box.column()

            row = column.row()
            row.scale_y = 1.2
            row.prop(context.scene.M3, "pass_through", text="Pass Through" if context.scene.M3.pass_through else "Occlude", icon="XRAY")
        else:
            pie.separator()

    def draw_curves(self, context, active, pie):

        pie.operator("object.mode_set", text="Edit Mode", icon='EDITMODE_HLT').mode = "EDIT"

        pie.separator()

        pie.operator("object.mode_set", text="Sculpt Mode", icon='EDITMODE_HLT').mode = "SCULPT_CURVES"

        stack = []

        if True and self.show_finish_assembly_edit:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

        if active.mode == 'OBJECT':
            if self.show_edit_toggle:
                build_pie_button_stack(stack, 'OPERATOR', operator='object.editmode_toggle', text='Edit', icon='EDITMODE_HLT')
        else:
            build_pie_button_stack(stack, 'OPERATOR', operator='object.editmode_toggle', text='Object', icon='OBJECT_DATAMODE')

        draw_pie_button_stack(stack, pie)

        self.draw_hair_tiny(context, pie)

        if context.mode in ['EDIT_CURVES', 'SCULPT_CURVES']:
            box = pie.split()
            column = box.column()
            column.scale_y = 1.5
            column.scale_x = 1.5

            row = column.row(align=True)

            domain = active.data.selection_domain

            if domain == 'POINT':
                row.operator("curves.set_selection_domain", text="", icon='CURVE_PATH').domain = 'CURVE'
            elif domain == 'CURVE':
                row.operator("curves.set_selection_domain", text="", icon='CURVE_BEZCIRCLE').domain = 'POINT'

        else:
            pie.separator()

        pie.separator()

        pie.separator()

    def draw_grease_pencil(self, context, active, toolsettings, pie):

        def draw_4_2_and_earlier():
            gpd = context.gpencil_data

            pie.operator("object.mode_set", text="Edit Mode", icon='EDITMODE_HLT').mode = "EDIT_GPENCIL"

            pie.operator("object.mode_set", text="Sculpt", icon='SCULPTMODE_HLT').mode = "SCULPT_GPENCIL"

            pie.operator("object.mode_set", text="Draw", icon='GREASEPENCIL').mode = "PAINT_GPENCIL"

            if context.mode == 'OBJECT':
                stack = []

                if True and self.show_finish_assembly_edit:
                    build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

                draw_pie_button_stack(stack, pie)

            else:
                pie.operator("object.mode_set", text="Object", icon='OBJECT_DATAMODE').mode = "OBJECT"

            self.draw_grease_pencil_tiny(context, pie)

            pie.separator()

            box = pie.split()
            column = box.column()
            column.scale_y = 1.2
            column.scale_x = 1.2

            if context.mode in ["EDIT_GPENCIL"]:
                row = column.row(align=True)
                row.prop(toolsettings, "gpencil_selectmode_edit", text="", expand=True)

                row.prop(active.data, "use_curve_edit", text="", icon='IPO_BEZIER')

            elif context.mode == "PAINT_GPENCIL":
                row = column.row(align=True)
                row.prop(toolsettings, "use_gpencil_draw_onback", text="", icon="MOD_OPACITY")
                row.prop(toolsettings, "use_gpencil_automerge_strokes", text="", icon="AUTOMERGE_OFF")
                row.prop(toolsettings, "use_gpencil_weight_data_add", text="", icon="WPAINT_HLT")
                row.prop(toolsettings, "use_gpencil_draw_additive", text="", icon="FREEZE")

                row.separator()
                row.prop(active.data, "use_multiedit", text="", icon='GP_MULTIFRAME_EDITING')

            box = pie.split()
            column = box.column(align=True)

            if context.mode in "EDIT_GPENCIL":
                row = column.row(align=True)
                row.prop(gpd, "use_multiedit", text="", icon='GP_MULTIFRAME_EDITING')

                r = row.row(align=True)
                r.active = gpd.use_multiedit
                r.popover(panel="VIEW3D_PT_gpencil_multi_frame", text="Multiframe")

            elif context.mode == "SCULPT_GPENCIL":
                row = column.row(align=True)
                row.prop(toolsettings, "use_gpencil_select_mask_point", text="")
                row.prop(toolsettings, "use_gpencil_select_mask_stroke", text="")
                row.prop(toolsettings, "use_gpencil_select_mask_segment", text="")

                row.separator()
                row.prop(gpd, "use_multiedit", text="", icon='GP_MULTIFRAME_EDITING')

                r = row.row(align=True)
                r.active = gpd.use_multiedit
                r.popover(panel="VIEW3D_PT_gpencil_multi_frame", text="Multiframe")

            elif context.mode == "PAINT_GPENCIL":
                row = column.row(align=True)
                row.prop_with_popover(toolsettings, "gpencil_stroke_placement_view3d", text="", panel="VIEW3D_PT_gpencil_origin")

        def draw_4_3():

            pie.operator("object.mode_set", text="Edit Mode", icon='EDITMODE_HLT').mode = "EDIT"

            pie.operator("object.mode_set", text="Sculpt", icon='SCULPTMODE_HLT').mode = "SCULPT_GREASE_PENCIL"

            pie.operator("object.mode_set", text="Draw", icon='GREASEPENCIL').mode = "PAINT_GREASE_PENCIL"

            stack = []

            if context.mode == 'OBJECT':

                if True and self.show_finish_assembly_edit:
                    build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

                if self.show_edit_toggle:
                    build_pie_button_stack(stack, 'OPERATOR', operator='object.mode_set', text="Edit", icon='EDITMODE_HLT', props={'mode': 'EDIT'})

            else:
                build_pie_button_stack(stack, 'OPERATOR', operator='object.mode_set', text="Object", icon='OBJECT_DATAMODE', props={'mode': 'OBJECT'})

            draw_pie_button_stack(stack, pie)

            self.draw_grease_pencil_tiny(context, pie)

            pie.separator()

            box = pie.split()
            column = box.column()
            column.scale_y = 1.2
            column.scale_x = 1.2

            if context.mode == "EDIT_GREASE_PENCIL":
                row = column.row(align=True)

                modes = ['POINT', 'STROKE', 'SEGMENT']
                icons = ['GP_SELECT_POINTS', 'GP_SELECT_STROKES', 'GP_SELECT_BETWEEN_STROKES']

                for mode, icon in zip(modes, icons):
                    row.operator( "grease_pencil.set_selection_mode", text="", icon=icon, depress=toolsettings.gpencil_selectmode_edit == mode).mode = mode

            elif context.mode == "PAINT_GREASE_PENCIL":
                row = column.row(align=True)
                row.prop(toolsettings, "use_gpencil_draw_onback", text="", icon="MOD_OPACITY")
                row.prop(toolsettings, "use_gpencil_automerge_strokes", text="", icon="AUTOMERGE_OFF")
                row.prop(toolsettings, "use_gpencil_weight_data_add", text="", icon="WPAINT_HLT")
                row.prop(toolsettings, "use_gpencil_draw_additive", text="", icon="FREEZE")

                row.separator()
                row.prop(toolsettings, "use_grease_pencil_multi_frame_editing", text="", icon='GP_MULTIFRAME_EDITING')

            box = pie.split()
            column = box.column(align=True)

            if context.mode in "EDIT_GREASE_PENCIL":
                row = column.row(align=True)
                row.prop(toolsettings, "use_grease_pencil_multi_frame_editing", text="", icon='GP_MULTIFRAME_EDITING')

                r = row.row(align=True)
                r.active = toolsettings.use_grease_pencil_multi_frame_editing
                r.popover(panel="VIEW3D_PT_grease_pencil_multi_frame", text="Multiframe")

            elif context.mode in ["SCULPT_GREASE_PENCIL", "VERTEX_GREASE_PENCIL"]:
                row = column.row(align=True)
                row.prop(toolsettings, "use_gpencil_select_mask_point", text="")
                row.prop(toolsettings, "use_gpencil_select_mask_stroke", text="")
                row.prop(toolsettings, "use_gpencil_select_mask_segment", text="")

                row.separator()
                row.prop(toolsettings, "use_grease_pencil_multi_frame_editing", text="", icon='GP_MULTIFRAME_EDITING')

                r = row.row(align=True)
                r.active = toolsettings.use_grease_pencil_multi_frame_editing
                r.popover(panel="VIEW3D_PT_grease_pencil_multi_frame", text="Multiframe")

            elif context.mode == "WEIGHT_GREASE_PENCIL":
                row = column.row(align=True)
                row.prop(toolsettings, "use_grease_pencil_multi_frame_editing", text="", icon='GP_MULTIFRAME_EDITING')

                r = row.row(align=True)
                r.active = toolsettings.use_grease_pencil_multi_frame_editing
                r.popover(panel="VIEW3D_PT_grease_pencil_multi_frame", text="Multiframe")

            elif context.mode == "PAINT_GREASE_PENCIL":
                row = column.row(align=True)
                row.prop_with_popover(toolsettings, "gpencil_stroke_placement_view3d", text="", panel="VIEW3D_PT_grease_pencil_origin")

        if bpy.app.version < (4, 3, 0):
            draw_4_2_and_earlier()

        else:
            draw_4_3()

    def draw_empty(self, context, active, linked, pie):
        if get_prefs().activate_assetbrowser_tools:
            is_linked = bool(linked)
            is_assembly = bool(icol := is_instance_collection(active))
            is_local_asset = bool(asset := is_local_assembly_asset(active))

            is_linked_icol = bool(icol and icol.library)

            if is_linked:
                blendpath = abspath(linked[0].library.filepath)
                library = linked[0].library.name

        else:
            asset = None
            is_assembly = False
            is_linked = False
            is_local_asset = False
            is_linked_icol = False

        is_group = get_prefs().activate_group_tools and active.M3.is_group_empty

        m3 = context.scene.M3

        if is_assembly:
            pie.operator("machin3.disassemble_assembly", text="Disassemble", icon='PARTICLE_DATA')

        elif is_group:
            box = pie.split()

            column = box.column(align=True)
            column.scale_y = 1.2

            row = column.row(align=True)
            row.enabled = not m3.group_origin_mode
            row.prop(m3, "group_select", text="Auto Select", icon="GROUP_VERTEX", toggle=True)

            row = column.row(align=True)
            row.enabled = not m3.group_origin_mode
            row.prop(m3, "group_recursive_select", text="Recursive", icon="CON_SIZELIKE", toggle=True)

            column.prop(m3, "group_hide", text="Hide Empties", icon='HIDE_OFF' if m3.group_hide else 'HIDE_ON', toggle=True)

        else:
            box = pie.split()
            column = box.column(align=True)
            column.prop(active, 'empty_display_type', expand=True)

        if is_assembly:
            pie.operator("machin3.remove_assembly_asset", text="Remove Assembly", icon='TRASH').remove_asset = False

        elif active.empty_display_type == 'IMAGE':
            box = pie.box()
            column = box.column(align=True)

            split = column.split(factor=0.2, align=True)
            split.alignment = 'RIGHT'
            split.label(text="Gizmo")

            row = split.row(align=True)
            row.prop(context.space_data, "show_gizmo_context", text="Show Gizmo", icon="GIZMO", toggle=True)

            column.separator()

            split = column.split(factor=0.2, align=True)
            split.alignment = 'RIGHT'
            split.label(text="Side")

            row = split.row(align=True)
            row.prop(active, "empty_image_side", expand=True)

            split = column.split(factor=0.2, align=True)
            split.alignment = 'RIGHT'
            split.label(text="Depth")

            row = split.row(align=True)
            row.prop(active, "empty_image_depth", expand=True)

            split = column.split(factor=0.2, align=True)
            split.alignment = 'RIGHT'
            split.label(text="Opacity")

            row = split.row(align=True)
            row.prop(active, "use_empty_image_alpha", text="Use", toggle=True, icon='NONE')
            r = row.row(align=True)
            r.active = active.use_empty_image_alpha
            r.prop(active, "color", index=3, text="", slider=True)

        elif is_group:
            if m3.group_origin_mode:
                pie.prop(m3, "group_origin_mode", text="Disable, when done!", toggle=True, icon_value=get_icon('error'))
            else:
                pie.prop(m3, "group_origin_mode", text="Adjust Group Origin", toggle=True, icon='OBJECT_ORIGIN')

        elif get_prefs().activate_group_tools and not active.M3.is_group_empty and active.children:
            pie.operator("machin3.groupify", text="Groupify")

        else:
            pie.separator()

        if is_linked:
            if is_assembly:

                stack = []

                if not active.library:
                    build_pie_button_stack(stack, 'PROPERTY', data=active, property='empty_display_size', text="Empty Size", scale=1.2)

                build_pie_button_stack(stack, 'OPERATOR', 'machin3.make_id_local', text="Make Local", icon='UNLINKED')

                if True and self.show_assembly_edit:
                    build_pie_button_stack(stack, 'OPERATOR', 'machin3.edit_assembly', text="Edit Assembly", icon_value=get_icon('edit_red' if is_linked_icol else 'edit'))

                draw_pie_button_stack(stack, pie, alignment='EXPAND')

            else:
                pie.operator("machin3.make_id_local", text="Make Local", icon='UNLINKED')

        else:
            box = pie.split()

            column = box.column(align=True)
            column.scale_y = 1.2

            if not is_group:
                column.prop(active, 'empty_display_size', text="Empty Size")

            if is_group:
                column.prop(active, 'name', text="")
                column.prop(active, 'empty_display_size', text="Group Size")

                if True:
                    if m3.show_group_gizmos:
                        column.separator(factor=0.5)
                        row = column.row(align=True)

                        r = row.row(align=True)
                        r.scale_x = 1.3
                        r.prop(active.M3, 'show_group_gizmo', text='', icon='HIDE_OFF' if active.M3.show_group_gizmo else 'HIDE_ON')

                        r = row.row(align=True)
                        r.enabled = context.scene.M3.show_group_gizmos and active.M3.show_group_gizmo
                        r.prop(active.M3, 'group_gizmo_size', text="Gizmo Size")

                        r = row.row(align=True)
                        r.enabled = context.scene.M3.show_group_gizmos and active.M3.show_group_gizmo and active.M3.group_gizmo_size != 1
                        op = r.operator("wm.context_set_float", text="", icon="LOOP_BACK")
                        op.data_path = "active_object.M3.group_gizmo_size"
                        op.value = 1

                        row = column.row(align=True)
                        row.enabled = context.scene.M3.show_group_gizmos and active.M3.show_group_gizmo
                        row.scale_y = 0.8
                        row.prop(active.M3, 'show_group_x_rotation', text="X", icon="BLANK1")
                        row.prop(active.M3, 'show_group_y_rotation', text="Y", icon="BLANK1")
                        row.prop(active.M3, 'show_group_z_rotation', text="Z", icon="BLANK1")

                    row = column.row(align=True)
                    row.enabled = not m3.group_origin_mode
                    row.prop(context.scene.M3, "show_group_gizmos", text="Show Group Gizmos", icon='HIDE_OFF' if context.scene.M3.show_group_gizmos else 'HIDE_ON')

                if not m3.group_select or is_local_view():
                    column.separator(factor=0.3)

                    row = column.row()
                    row.alignment = 'CENTER'
                    row.scale_y = 1.3
                    row.operator("machin3.select_group", text="Select Group", icon="GROUP_VERTEX")

            if True and is_assembly and self.show_assembly_edit:
                row = column.row()
                row.scale_y = 1.4

                row.operator("machin3.edit_assembly", text="Edit Assembly", icon_value=get_icon('edit_red' if is_linked_icol else 'edit'))

        stack = []

        if True and self.show_finish_assembly_edit:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

        self.add_contextual_group_button(stack)

        if is_linked:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.open_library_blend', text=f"Open {os.path.basename(blendpath)}", icon='FILE_BLEND', props={'blendpath': blendpath, 'library': library})

        draw_pie_button_stack(stack, pie)

        if True and is_assembly:
            pie.operator("machin3.create_assembly_variant", text="Create Variant", icon='DUPLICATE')

        else:
            pie.separator()

        if True and is_assembly and not is_linked and not is_local_asset:
            pie.operator("machin3.turn_assembly_into_asset", text="Turn into Asset", icon='ASSET_MANAGER')

        elif is_assembly and is_local_asset and asset and asset.preview:
            box = pie.split()

            column = box.column(align=True)
            column.template_icon(icon_value=asset.preview.icon_id, scale=6.5)

            row = column.row(align=True)
            row.operator("machin3.update_asset_thumbnail", text="Update", icon='IMAGE_DATA')

            if True:
                row.prop(active.M3, "use_asset_thumbnail_helper", text="", icon='FULLSCREEN_ENTER')

            column.separator(factor=11)

        elif is_group:
            box = pie.split()

            row = box.row(align=True)
            row.scale_y = 1.2

            r = row.row(align=True)
            r.enabled = not m3.group_origin_mode
            r.prop(m3, "draw_group_relations", text="Draw Relations", icon='PARTICLE_DATA', toggle=True)

            r = row.row(align=True)
            r.active = m3.draw_group_relations
            r.prop(m3, "draw_group_relations_active_only", text='', icon='SPHERE', toggle=True)
            r.prop(m3, "draw_group_relations_objects", text='', icon='MESH_CUBE', toggle=True)

        else:
            pie.separator()

        if is_linked:
            pie.operator('machin3.reload_actives_libraries', text="Reload Library", icon_value=get_icon('refresh'))

        elif True and is_group:

            box = pie.split()
            box.enabled = not m3.group_origin_mode
            box.scale_y = 1.2

            split = box.split(factor=0.8)
            split.scale_x = 1.2

            column = split.column()
            column.operator("machin3.setup_group_gizmos", text="Setup Gizmos", icon='GIZMO')

            split.separator()

        else:
            pie.separator()

        if is_local_asset:
            pie.operator("machin3.remove_assembly_asset", text="Remove Asset", icon_value=get_icon('cancel')).remove_asset = True

        elif True and is_group:
            box = pie.split()
            box.enabled = not m3.group_origin_mode

            split = box.split(factor=0.2)
            split.separator()

            column = split.column(align=True)
            column.scale_x = 1.3

            poseCOL = active.M3.group_pose_COL

            if len(poseCOL) > 1:
                column.separator(factor=(len(poseCOL) - 1) * 3)

            row = column.row()
            row.alignment = 'CENTER'
            row.label(text="Poses")

            if poseCOL:
                for pose in poseCOL:
                    s = column.split(factor=0.15, align=True)

                    if pose.batch:
                        s.prop(pose, 'batchlinked', text='', icon='LINKED' if pose.batchlinked else 'UNLINKED')
                    else:
                        s.separator()

                    rs = s.row(align=True)

                    depress = compare_quat(pose.mx.to_quaternion(), active.matrix_local.to_quaternion(), precision=4, debug=False)
                    rs.operator("machin3.retrieve_group_pose", text=pose.name, depress=depress, icon='ARMATURE_DATA').index = pose.index
                    rs.operator("machin3.update_group_pose", text='', icon='FILE_REFRESH').index = pose.index

                column.separator()

            row = column.row(align=True)
            row.operator("machin3.set_group_pose", text="Add", icon="ARMATURE_DATA").batch = False

            batchposable = bool([obj for obj in active.children_recursive if obj.type == 'EMPTY' and obj.M3.is_group_empty])
            r = row.row(align=True)
            r.enabled = batchposable
            r.operator("machin3.set_group_pose", text="Add Batch", icon="LINKED").batch = True

        else:
            pie.separator()

    def draw_grease_pencil_tiny(self, context, pie):
        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)

        if bpy.app.version < (4, 3, 0):
            modes = ['WEIGHT_GPENCIL', 'VERTEX_GPENCIL', 'PAINT_GPENCIL', 'SCULPT_GPENCIL', 'OBJECT', 'EDIT_GPENCIL']

        else:
            modes = ['WEIGHT_GREASE_PENCIL', 'VERTEX_GREASE_PENCIL', 'PAINT_GREASE_PENCIL', 'SCULPT_GREASE_PENCIL', 'OBJECT', 'EDIT']

        icons = ['WPAINT_HLT', 'VPAINT_HLT', 'GREASEPENCIL', 'SCULPTMODE_HLT', 'OBJECT_DATA', 'EDITMODE_HLT']

        for mode, icon in zip(modes, icons):
            r = row.row(align=True)
            r.active = context.mode != mode
            r.operator("object.mode_set", text="", icon=icon).mode = mode

    def draw_mesh_tiny(self, context, pie):
        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)

        if context.active_object.particle_systems:
            r = row.row(align=True)
            r.active = False if context.mode == 'PARTICLE' else True
            r.operator("object.mode_set", text="", icon="PARTICLEMODE").mode = 'PARTICLE_EDIT'

        r = row.row(align=True)
        r.active = False if context.mode == 'PAINT_TEXTURE' else True
        r.operator("object.mode_set", text="", icon="TPAINT_HLT").mode = 'TEXTURE_PAINT'

        r = row.row(align=True)
        r.active = False if context.mode == 'PAINT_WEIGHT' else True
        r.operator("object.mode_set", text="", icon="WPAINT_HLT").mode = 'WEIGHT_PAINT'

        r = row.row(align=True)
        r.active = False if context.mode == 'PAINT_VERTEX' else True
        r.operator("object.mode_set", text="", icon="VPAINT_HLT").mode = 'VERTEX_PAINT'

        r = row.row(align=True)
        r.active = False if context.mode == 'SCULPT' else True
        r.operator("object.mode_set", text="", icon="SCULPTMODE_HLT").mode = 'SCULPT'

        r = row.row(align=True)
        r.active = False if context.mode == 'OBJECT' else True
        r.operator("object.mode_set", text="", icon="OBJECT_DATA").mode = 'OBJECT'

        r = row.row(align=True)
        r.active = False if context.mode == 'EDIT_MESH' else True
        r.operator("object.mode_set", text="", icon="EDITMODE_HLT").mode = 'EDIT'

    def draw_hair_tiny(self, context, pie):
        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)

        r = row.row(align=True)
        r.active = False if context.mode == 'SCULPT_CURVES' else True
        r.operator("object.mode_set", text="", icon="SCULPTMODE_HLT").mode = 'SCULPT_CURVES'

        r = row.row(align=True)
        r.active = False if context.mode == 'OBJECT' else True
        r.operator("object.mode_set", text="", icon="OBJECT_DATA").mode = 'OBJECT'

    def draw_grease_pencil_extra(self, active, toolsettings, pie):
        box = pie.split()
        column = box.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.5

        row.operator('machin3.shrinkwrap_grease_pencil', text='Shrinkwrap')

        if bpy.app.version < (4, 3, 0):
            row.prop(active.data, "zdepth_offset", text='')

        else:
            row.prop(toolsettings, "gpencil_surface_offset", text='')

        if bpy.app.version < (4, 3, 0):
            opacity = [mod for mod in active.grease_pencil_modifiers if mod.type == 'GP_OPACITY']
            thickness = [mod for mod in active.grease_pencil_modifiers if mod.type == 'GP_THICK']

        else:
            opacity = [mod for mod in active.modifiers if mod.type == 'GREASE_PENCIL_OPACITY']
            thickness = [mod for mod in active.modifiers if mod.type == 'GREASE_PENCIL_THICKNESS']

        if opacity:
            row = column.row(align=True)

            factor = 'factor' if bpy.app.version < (4, 3, 0) else 'color_factor'
            row.prop(opacity[0], factor, text='Opacity')

        if thickness:
            row = column.row(align=True)
            row.prop(thickness[0], 'thickness_factor', text='Thickness')

    def get_grease_pencil_modes(self):
        if bpy.app.version < (4, 3, 0):
            return ['EDIT_GPENCIL', 'PAINT_GPENCIL', 'SCULPT_GPENCIL', 'WEIGHT_GPENCIL', 'VERTEX_GPENCIL']

        else:
            return ['EDIT_GREASE_PENCIL', 'PAINT_GREASE_PENCIL', 'SCULPT_GREASE_PENCIL', 'WEIGHT_GREASE_PENCIL', 'VERTEX_GREASE_PENCIL']

    def draw_sculpt(self, context, active, pie):

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
        pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
        pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
        pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

        pie.operator("object.mode_set", text="Object", icon="OBJECT_DATA").mode = 'OBJECT'

        self.draw_mesh_tiny(context, pie)

        pie.separator()

        pie.separator()

        box = pie.split()
        column = box.column()

        row = column.row(align=True)

        row.label(icon='MOD_MIRROR')

        r = row.row(align=True)
        r.scale_x = 1.25
        r.prop(active, "use_mesh_mirror_x", text='', icon_value=get_icon('axis_x_grey'), toggle=True)
        r.prop(active, "use_mesh_mirror_y", text='', icon_value=get_icon('axis_y_grey'), toggle=True)
        r.prop(active, "use_mesh_mirror_z", text='', icon_value=get_icon('axis_z_grey'), toggle=True)

        row.popover(panel="VIEW3D_PT_sculpt_symmetry_for_topbar", text='')

        row = column.row(align=True)
        row.scale_y = 1.2

        is_dyntopo = context.sculpt_object.use_dynamic_topology_sculpting

        if is_dyntopo:
            row.popover(panel="VIEW3D_PT_sculpt_dyntopo", text="Dyntopo")

        else:
            row.operator("sculpt.dynamic_topology_toggle", text="Use Dyntopo", depress=is_dyntopo, icon='CHECKBOX_DEHLT')

        row = column.row(align=True)
        row.enabled = not is_dyntopo
        row.scale_y = 1.2
        row.popover(panel="VIEW3D_PT_sculpt_voxel_remesh", text="Remesh")

    def draw_paint_texture(self, context, active, pie):
        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
        pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
        pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
        pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

        pie.operator("object.mode_set", text="Object", icon="OBJECT_DATA").mode = 'OBJECT'

        self.draw_mesh_tiny(context, pie)

        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)
        row.prop(active.data, "use_paint_mask", text="", icon="FACESEL")

        pie.separator()

        pie.separator()

    def draw_paint_weight(self, context, active, pie):
        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
        pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
        pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
        pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

        pie.operator("object.mode_set", text="Object", icon="OBJECT_DATA").mode = 'OBJECT'

        self.draw_mesh_tiny(context, pie)

        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)
        row.prop(active.data, "use_paint_mask", text="", icon="FACESEL")
        row.prop(active.data, "use_paint_mask_vertex", text="", icon="VERTEXSEL")

        pie.separator()

        pie.separator()

    def draw_paint_vertex(self, context, active, pie):
        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
        pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
        pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
        pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

        pie.operator("object.mode_set", text="Object", icon="OBJECT_DATA").mode = 'OBJECT'

        self.draw_mesh_tiny(context, pie)

        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)
        row.prop(active.data, "use_paint_mask", text="", icon="FACESEL")
        row.prop(active.data, "use_paint_mask_vertex", text="", icon="VERTEXSEL")

        pie.separator()

        pie.separator()

    def draw_particle(self, context, active, toolsettings, pie):
        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[0]
        pie.operator("machin3.mesh_mode", text="Vertex", depress=depress, icon_value=get_icon('vertex')).mode = 'VERT'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[2]
        pie.operator("machin3.mesh_mode", text="Face", depress=depress, icon_value=get_icon('face')).mode = 'FACE'

        depress = active.mode == 'EDIT' and context.scene.tool_settings.mesh_select_mode[1]
        pie.operator("machin3.mesh_mode", text="Edge", depress=depress, icon_value=get_icon('edge')).mode = 'EDGE'

        pie.operator("object.mode_set", text="Object", icon="OBJECT_DATA").mode = 'OBJECT'

        self.draw_mesh_tiny(context, pie)

        box = pie.split()
        column = box.column()
        column.scale_y = 1.5
        column.scale_x = 1.5

        row = column.row(align=True)
        row.prop(toolsettings.particle_edit, "select_mode", text="", expand=True)

        pie.separator()

        pie.separator()

    def draw_no_active(self, context, pie):

        pie.separator()

        pie.separator()

        row = pie.row()
        row.alert = False
        row.label(text="", icon="INFO")
        row.alert = True
        row.label(text="No Active Object Selected")

        stack = []

        if True and self.show_finish_assembly_edit:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.finish_assembly_edit', text="Finish Assembly Edit", icon='CHECKMARK', alert=True)

        if self.show_create_group:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.group', text="Group", icon="GROUP_VERTEX")

        draw_pie_button_stack(stack, pie)

        pie.separator()

        pie.separator()

        pie.separator()

        pie.separator()

    def add_contextual_group_button(self, stack):
        if self.show_ungroup:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.ungroup', text="Ungroup", icon_value=get_icon('cancel'))

        if self.show_select_group:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.select_group', text="Select Group", icon='GROUP_VERTEX')

        if self.show_create_group:
            build_pie_button_stack(stack, 'OPERATOR', operator='machin3.group', text="Group", icon='GROUP_VERTEX')

class PieSave(Menu):
    bl_idname = "MACHIN3_MT_save_pie"
    bl_label = "Save, Open, Append"

    def draw(self, context):
        layout = self.layout

        pie = layout.menu_pie()

        scene = context.scene
        wm = context.window_manager

        is_image_editor = context.area and context.area.type == 'IMAGE_EDITOR'
        is_img = bool(context.space_data and context.space_data.image) if is_image_editor else False
        is_img_dirty = img.is_dirty if is_img and (img := context.space_data.image) else False
        is_img_packed = bool(context.space_data.image.packed_file) if is_img else False

        has_external_image_editor = path if (path := context.preferences.filepaths.image_editor) and os.path.exists(path) else None

        is_export = any(getattr(get_prefs(), f"save_pie_show_{ext}_export") for ext in ['obj', 'plasticity', 'fbx', 'usd', 'stl', 'gltf'])

        is_blend_dirty = bpy.data.is_dirty
        is_blend_saved = bpy.data.filepath
        is_blend_saved_in_temp_dir = is_blend_saved and get_temp_dir(context) == os.path.dirname(bpy.data.filepath)

        pie.operator("wm.open_mainfile", text="Open...", icon_value=get_icon('open'))

        pie.operator("machin3.save", text=f"Save{'*' if is_blend_dirty else ''}", icon_value=get_icon('save'))

        pie.operator("machin3.save_as", text=f"Save As..{'*' if is_blend_dirty else ''}", icon_value=get_icon('save_as'))

        if is_image_editor:

            if context.space_data.image:
                box = pie.split()
                column = box.column()
                column.scale_y = 1.5

                column.operator("image.save_as", text=f"Save Image As..{'*' if is_img_dirty else ''}" , icon='IMAGE_DATA')

            else:
                box = pie.split()

                column = box.column()
                column.scale_y = 1.3
                column.template_ID(context.space_data, "image", new="image.new", open="image.open")

        else:
            box = pie.split()

            b = box.box()
            self.draw_left_column(wm, scene, b)

            if is_export or is_blend_saved:
                column = box.column()

                if is_export:
                    b = column.box()
                    self.draw_center_column_top(context, b)

                if is_blend_saved:
                    b = column.box()
                    self.draw_center_column_bottom(b, is_in_temp_dir=is_blend_saved_in_temp_dir)

            b = box.box()

            self.draw_right_column(scene, b)

        if is_image_editor:

            box = pie.split()
            column = box.column()
            column.scale_y = 1.5
            column.enabled = bool(is_img)

            row = column.row(align=True)
            row.operator("image.open", text="Open Image", icon='FILEBROWSER')

            r = row.row(align=True)
            r.scale_x = 1.1
            op = r.operator("wm.context_set_id", text="", icon='PANEL_CLOSE')
            op.data_path = 'space_data.image'
            op.value = ''

            if has_external_image_editor:
                r = row.row(align=True)
                r.scale_x = 1.1
                r.operator("image.external_edit", text="", icon='GREASEPENCIL')

        else:
            pie.separator()

        if is_image_editor:
            box = pie.split()
            column = box.column()
            column.scale_y = 1.5
            column.enabled = bool(is_img)

            row = column.row(align=True)

            r = row.row(align=True)
            r.scale_x = 1.1

            if is_img_packed:
                r.operator("image.unpack", text="", icon='PACKAGE')
            else:
                r.operator("image.pack", text="", icon='UGLYPACKAGE')

            row.operator("image.save", text=f"Save Image{'*' if is_img_dirty else ''}", icon='FILE_TICK')

        else:
            pie.separator()

        pie.operator("machin3.new", text="New", icon_value=get_icon('new'))

        pie.operator("machin3.save_incremental", text=f"Incremental Save{'*' if is_blend_dirty else ''}", icon_value=get_icon('save_incremental'))

    def draw_left_column(self, wm, scene, layout):
        column = layout.column(align=True)
        column.scale_x = 1.1

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.load_most_recent", text="(R) Most Recent", icon_value=get_icon('open_recent'))
        row.operator("wm.call_menu", text="All Recent", icon_value=get_icon('open_recent')).name = "TOPBAR_MT_file_open_recent"

        column.separator()

        if get_prefs().save_pie_use_undo_save:
            row = column.row(align=True)
            row.prop(scene.M3, "use_undo_save", text="Undo Save", icon='LOOP_BACK')

            r = row.row(align=True)
            r.active = scene.M3.use_undo_save
            r.prop(scene.M3, "use_redo_save", text="Redo Save", icon='FILE_REFRESH')

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.open_current_dir", text="Open Current", icon_value=get_icon('open'))

        row.operator("machin3.open_temp_dir", text="Open Temp", icon_value=get_icon('recover_auto_save'))

        column.operator("wm.revert_mainfile", text="Revert", icon_value=get_icon('revert'))

        if get_prefs().show_screencast:
            column.separator()

            screencast = getattr(wm, 'M3_screen_cast', False)
            text, icon = ('Disable', 'PAUSE') if screencast else ('Enable', 'PLAY')

            sk = getattr(wm, 'enable_screencast_keys', False)

            row = column.row(align=True)
            row.operator('machin3.screen_cast', text=f"{text} Screen Cast", depress=screencast, icon=icon)

            if not screencast and sk:
                row.prop(wm, 'enable_screencast_keys', text="Keys", toggle=True, icon='PAUSE')

    def draw_center_column_top(self, context, layout):
        column = layout.column(align=True)

        factor = 0.3 if M3.get_addon("Better FBX Importer & Exporter") and get_prefs().save_pie_show_better_fbx_export else 0.25 if get_prefs().save_pie_show_plasticity_export else 0.15

        if get_prefs().save_pie_show_obj_export:
            row = column.split(factor=factor, align=True)
            row.label(text="OBJ")
            r = row.row(align=True)

            r.operator("wm.obj_import", text="Import", icon_value=get_icon('import'))

            op = r.operator("wm.obj_export", text="Export", icon_value=get_icon('export'))
            op.export_selected_objects = bool(context.selected_objects)

            if path := get_prefs().save_pie_obj_folder:
                op.filepath = os.path.join(path, 'untitled.obj')

        if get_prefs().save_pie_show_plasticity_export:
            row = column.split(factor=factor, align=True)
            row.label(text="Plasticity")
            r = row.row(align=True)

            op = r.operator("wm.obj_import", text="Import", icon_value=get_icon('import'))
            op.up_axis = 'Z'
            op.forward_axis = 'Y'

            op = r.operator("wm.obj_export", text="Export", icon_value=get_icon('export'))
            op.export_selected_objects = bool(context.selected_objects)
            op.up_axis = 'Z'
            op.forward_axis = 'Y'

            if path := get_prefs().save_pie_plasticity_folder:
                op.filepath = os.path.join(path, 'untitled.obj')

        if M3.get_addon("FBX format") and get_prefs().save_pie_show_fbx_export:
            row = column.split(factor=factor, align=True)

            row.label(text="FBX")

            s = row.split(factor=0.5, align=True)
            s.operator("import_scene.fbx", text="Import", icon_value=get_icon('import'))

            r = s.row(align=True)
            op = r.operator("export_scene.fbx", text="Export", icon_value=get_icon('export'))
            op.use_selection = bool(context.selected_objects)

            if get_prefs().fbx_export_apply_scale_all:
                op.apply_scale_options='FBX_SCALE_ALL'

            if path := get_prefs().save_pie_fbx_folder:
                op.filepath = os.path.join(path, 'untitled.fbx')

            r.prop(get_prefs(), 'fbx_export_apply_scale_all', text='', icon_value=get_icon('unity'))

        if M3.get_addon("Better FBX Importer & Exporter") and get_prefs().save_pie_show_better_fbx_export:
            row = column.split(factor=factor, align=True)
            row.label(text="Better FBX")
            r = row.row(align=True)
            r.operator("better_import.fbx", text="Import", icon_value=get_icon('import'))

            op = r.operator("better_export.fbx", text="Export", icon_value=get_icon('export'))
            op.use_selection = bool(context.selected_objects)

            if path := get_prefs().save_pie_better_fbx_folder:
                op.filepath = os.path.join(path, 'untitled.fbx')

        if get_prefs().save_pie_show_usd_export and getattr(bpy.ops.wm, 'usd_import', False):
            row = column.split(factor=factor, align=True)
            row.label(text="USD")
            r = row.row(align=True)
            r.operator("wm.usd_import", text="Import", icon_value=get_icon('import'))

            op = r.operator("wm.usd_export", text="Export", icon_value=get_icon('export'))
            op.selected_objects_only = bool(context.selected_objects)

            if path := get_prefs().save_pie_usd_folder:
                op.filepath = os.path.join(path, 'untitled.usdc')

        if get_prefs().save_pie_show_stl_export:
            row = column.split(factor=factor, align=True)
            row.label(text="STL")
            r = row.row(align=True)

            r.operator("wm.stl_import", text="Import", icon_value=get_icon('import'))

            op = r.operator("wm.stl_export", text="Export", icon_value=get_icon('export'))
            op.export_selected_objects = bool(context.selected_objects)

            if path := get_prefs().save_pie_stl_folder:
                op.filepath = os.path.join(path, 'untitled.stl')

        if M3.get_addon("glTF 2.0 format") and get_prefs().save_pie_show_gltf_export:
            row = column.split(factor=factor, align=True)
            row.label(text="glTF")
            r = row.row(align=True)

            r.operator("import_scene.gltf", text="Import", icon_value=get_icon('import'))

            op = r.operator("export_scene.gltf", text="Export", icon_value=get_icon('export'))
            op.use_selection = bool(context.selected_objects)

            if path := get_prefs().save_pie_gltf_folder:
                op.filepath = os.path.join(path, 'untitled.gltf')

    def draw_center_column_bottom(self, layout, is_in_temp_dir=False):
        column = layout.column(align=True)

        row = column.split(factor=0.5, align=True)
        row.scale_y = 1.2
        row.operator("machin3.load_previous", text="Previous", icon_value=get_icon('open_previous'))
        row.operator("machin3.load_next", text="Next", icon_value=get_icon('open_next'))

        if is_in_temp_dir:
            column = layout.column(align=True)
            column.label(text="You are currently in the Temp Folder", icon_value=get_icon('warning'))
            column.label(text="If you want to save, do it elsewhere!", icon='BLANK1')

    def draw_right_column(self, scene, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        r = row.row(align=True)
        r.operator("wm.append", text="Append", icon_value=get_icon('append'))
        r.operator("wm.link", text="Link", icon_value=get_icon('link'))

        row.separator()

        r = row.row(align=True)
        r.operator("wm.call_menu", text='', icon_value=get_icon('external_data')).name = "TOPBAR_MT_file_external_data"
        r.operator("machin3.purge_orphans", text="Purge")

        if lib_count := len(bpy.data.libraries):
            row = column.row(align=True)

            row.operator("machin3.reload_all_libraries", text=f"Reload {'All ' if lib_count > 1 else ''}Linked {'Libraries' if lib_count > 1 else 'Library'}", icon_value=get_icon('refresh'))

        if get_prefs().activate_assetbrowser_tools and get_prefs().assetbrowser_tools_show_assembly_creation_in_save_pie:
            column.separator()
            row = column.row()
            row.scale_y = 1.2

            if True:
                if scene.M3.is_assembly_edit_scene:
                    row.alert = True
                    row.operator("machin3.finish_assembly_edit", text="Finish Assembly Edit", icon='CHECKMARK').is_topbar_invoke = False
                else:
                    row.operator("machin3.create_assembly_asset", text="Create Assembly Asset", icon='ASSET_MANAGER')

            else:
                row.operator("machin3.create_assembly_asset", text="Create Assembly Asset", icon='ASSET_MANAGER')

        column.separator()

        row = column.row(align=True)
        row.operator("machin3.clean_out_blend_file", text="Clean out .blend", icon_value=get_icon('error'))

        if get_prefs().activate_assetbrowser_tools:
            row.operator("machin3.clean_out_non_assets", text="Keep Assets", icon="ASSET_MANAGER")

class PieShading(Menu):
    bl_idname = "MACHIN3_MT_shading_pie"
    bl_label = "Shading and Overlays"

    def draw(self, context):
        layout = self.layout

        view = context.space_data
        active = context.active_object
        activemat = active.active_material if active else None

        overlay = view.overlay
        shading = view.shading

        pie = layout.menu_pie()

        m3 = context.scene.M3

        text, icon = self.get_text_icon(context, "SOLID")
        pie.operator("machin3.switch_shading", text=text, icon=icon, depress=shading.type == 'SOLID' and overlay.show_overlays).shading_type = 'SOLID'

        text, icon = self.get_text_icon(context, "MATERIAL")
        pie.operator("machin3.switch_shading", text=text, icon=icon, depress=shading.type == 'MATERIAL' and overlay.show_overlays).shading_type = 'MATERIAL'

        pie.separator()

        box = pie.split()

        if (active and active.select_get()) or context.mode == 'EDIT_MESH':
            b = box.box()
            self.draw_object_box(context, active, view, b)

        if overlay.show_overlays and shading.type == 'SOLID':
            column = box.column()
            b = column.box()
            self.draw_overlay_box(context, active, view, b)

            b = column.box()
            self.draw_solid_box(context, view, b)

        elif overlay.show_overlays:
            b = box.box()
            self.draw_overlay_box(context, active, view, b)

        elif shading.type == 'SOLID':
            b = box.box()
            self.draw_solid_box(context, view, b)

        b = box.box()
        self.draw_shade_box(context, activemat, view, b)

        if get_shading_type(context) in ["MATERIAL", 'RENDERED']:
            b = box.box()

            if is_eevee_view(context):
                self.draw_eevee_box(context, view, b)

            elif is_cycles_view(context):
               self.draw_cycles_box(context, view, b)

            if get_prefs().activate_render and get_prefs().render_adjust_lights_on_render and get_area_light_poll():
                self.draw_light_adjust_box(context, m3, b)

        pie.separator()

        pie.separator()

        text, icon = self.get_text_icon(context, "WIREFRAME")
        pie.operator("machin3.switch_shading", text=text, icon=icon, depress=shading.type == 'WIREFRAME' and overlay.show_overlays).shading_type = 'WIREFRAME'

        text, icon = self.get_text_icon(context, "RENDERED")
        pie.operator("machin3.switch_shading", text=text, icon=icon, depress=shading.type == 'RENDERED' and overlay.show_overlays).shading_type = 'RENDERED'

    def draw_overlay_box(self, context, active, view, layout):
        m3 = context.scene.M3

        overlay = context.space_data.overlay
        perspective_type = view.region_3d.view_perspective
        shading_type = view.shading.type

        sel = context.selected_objects
        is_sel_wire = any(obj.show_wire for obj in context.selected_objects)

        is_retopology = context.mode == 'EDIT_MESH' and view.overlay.show_retopology
        is_backface_culling = shading_type == 'SOLID' and view.shading.show_backface_culling

        can_face_orient = not is_backface_culling and (shading_type in ['MATERIAL', 'RENDERED'] or (shading_type == 'SOLID' and (not view.shading.show_xray or view.shading.xray_alpha == 1)) or (shading_type == 'WIREFRAME' and (not view.shading.show_xray_wireframe or view.shading.xray_alpha_wireframe == 1)))

        column = layout.column(align=True)
        row = column.row(align=True)

        row.prop(view.overlay, "show_stats", text="Stats")
        row.prop(view.overlay, "show_cursor", text="Cursor")
        row.prop(view.overlay, "show_object_origins", text="Origins")

        r = row.row(align=True)
        r.active = view.overlay.show_object_origins
        r.prop(view.overlay, "show_object_origins_all", text="All")

        column.separator()

        if shading_type == 'WIREFRAME' and not can_face_orient:
            lay = column

        else:
            lay = column.split(factor=0.5, align=True)

        col = lay.column(align=True)

        if context.mode == 'EDIT_MESH':
            col.prop(view.overlay, "show_retopology")

            if is_retopology:
                col.prop(view.overlay, "retopology_offset", text='Offset')

        if not is_retopology:

            if shading_type == 'SOLID':
                col.prop(view.shading, "show_backface_culling")

            if can_face_orient:
                col.prop(view.overlay, "show_face_orientation")

        col = lay.column(align=True)
        col.prop(view.overlay, "show_relationship_lines")

        if context.mode == 'OBJECT':
           if get_prefs().activate_group_tools:
                col.prop(m3, "show_group_gizmos", text="Show Group Gizmos", toggle=True)

        elif context.mode == 'SCULPT':
            pass

        elif context.mode == 'EDIT_MESH':
            col.prop(view.overlay, "show_extra_indices")

        column.separator()

        row = column.split(factor=0.4, align=True)
        row.operator("machin3.toggle_grid", text="Grid", icon="GRID", depress=overlay.show_ortho_grid if perspective_type == 'ORTHO' and view.region_3d.is_orthographic_side_view else overlay.show_floor)
        r = row.row(align=True)
        r.active = view.overlay.show_floor
        r.prop(view.overlay, "show_axis_x", text="X", toggle=True)
        r.prop(view.overlay, "show_axis_y", text="Y", toggle=True)
        r.prop(view.overlay, "show_axis_z", text="Z", toggle=True)

        if context.mode in ['OBJECT', 'EDIT_MESH', 'SCULPT']:
            row = column.split(factor=0.4, align=True)
            icon = 'wireframe_xray' if m3.show_edit_mesh_wire else 'wireframe'

            if context.mode in 'OBJECT':
                depress = overlay.show_wireframes or is_sel_wire
                text = 'Wireframe (all + selection)' if overlay.show_wireframes and is_sel_wire else 'Wireframe (all)' if (overlay.show_wireframes or not sel) else 'Wireframe (selection)' if (is_sel_wire or sel or active) else 'Wireframe'

            elif context.mode == 'EDIT_MESH':
                depress = m3.show_edit_mesh_wire
                text = 'Wireframe (XRay)'

            elif context.mode == 'SCULPT':
                depress = active.show_wire
                text = 'Wireframe (Active)'

            row.operator("machin3.toggle_wireframe", text=text, icon_value=get_icon(icon), depress=depress)

            r = row.row(align=True)

            if context.mode in ["OBJECT", 'SCULPT']:
                r.active = view.shading.type == 'WIREFRAME' or view.overlay.show_wireframes or bool(active and active.show_wire)
                r.prop(view.overlay, "wireframe_opacity", text="Opacity")

            elif context.mode == "EDIT_MESH":
                r.active = view.shading.show_xray
                r.prop(view.shading, "xray_alpha", text="X-Ray")

        hasaxes = m3.draw_cursor_axes or m3.draw_active_axes or any([obj.M3.draw_axes for obj in context.visible_objects])

        row = column.split(factor=0.4, align=True)
        rs = row.split(factor=0.5, align=True)
        rs.prop(m3, "draw_active_axes", text="Active", icon='EMPTY_AXIS')
        rs.prop(m3, "draw_cursor_axes", text="Cursor", icon='PIVOT_CURSOR')

        r = row.row(align=True)
        r.active = hasaxes
        r.prop(m3, "draw_axes_screenspace", text="", icon='WORKSPACE')
        r.prop(m3, "draw_axes_size", text="")
        r.prop(m3, "draw_axes_alpha", text="")

    def draw_solid_box(self, context, view, layout):
        shading = context.space_data.shading

        column = layout.column(align=True)

        row = column.split(factor=0.4, align=True)
        row.operator("machin3.toggle_outline", text="(Q) Outline", depress=shading.show_object_outline)
        row.prop(view.shading, "object_outline_color", text="")

        hascavity = view.shading.show_cavity and view.shading.cavity_type in ['WORLD', 'BOTH']

        row = column.split(factor=0.4, align=True)
        row.operator("machin3.toggle_cavity", text="Cavity", depress=hascavity)
        r = row.row(align=True)
        r.active = hascavity
        r.prop(view.shading, "cavity_valley_factor", text="")
        r.prop(context.scene.display, "matcap_ssao_distance", text="")

        hascurvature = view.shading.show_cavity and view.shading.cavity_type in ['SCREEN', 'BOTH']

        row = column.split(factor=0.4, align=True)
        row.operator("machin3.toggle_curvature", text="(V) Curvature", depress=hascurvature)
        r = row.row(align=True)
        r.active = hascurvature
        r.prop(view.shading, "curvature_ridge_factor", text="")
        r.prop(view.shading, "curvature_valley_factor", text="")

    def draw_object_box(self, context, active, view, layout):
        overlay = view.overlay
        shading = view.shading

        column = layout.column(align=True)

        row = column.row()
        row = column.split(factor=0.5)
        row.prop(active, "name", text="")

        if active.type == 'ARMATURE':
            row.prop(active.data, "display_type", text="")
        else:
            row.prop(active, "display_type", text="")

        if overlay.show_overlays and shading.type in ['SOLID', 'WIREFRAME']:
            row = column.split(factor=0.5)
            r = row.row(align=True)
            r.prop(active, "show_name", text="Name")

            if active.type == 'ARMATURE':
                r.prop(active.data, "show_axes", text="Axes")
            else:
                r.prop(active.M3, "draw_axes", text="Axes")

            r = row.row(align=True)
            r.prop(active, "show_in_front", text="In Front")

            if shading.color_type == 'OBJECT':
                r.prop(active, "color", text="")

        elif overlay.show_overlays:
            row = column.split(factor=0.5)

            r = row.row(align=True)
            r.prop(active, "show_name", text="Name")

            if active.type == 'ARMATURE':
                r.prop(active.data, "show_axes", text="Axes")
            else:
                row.prop(active, "show_axis", text="Axis")

            row.separator()

        elif shading.type in ['SOLID', 'WIREFRAME']:
            if shading.color_type == 'OBJECT':
                row = column.split(factor=0.5, align=True)
                row.prop(active, "show_in_front", text="In Front")
                row.prop(active, "color", text="")

            else:
                row = column.row()
                row.prop(active, "show_in_front", text="In Front")

        if active.type == "MESH":
            mesh = active.data
            angles = [int(a) for a in get_prefs().auto_smooth_angle_presets.split(',')]

            column.separator()

            row = column.split(factor=0.55, align=True)
            r = row.row(align=True)
            r.operator("machin3.shade", text="Smooth", icon_value=get_icon('smooth')).shade_type = 'SMOOTH'
            r.operator("machin3.shade", text="Flat", icon_value=get_icon('flat')).shade_type = 'FLAT'

            is_auto_smooth = bool(mod := get_auto_smooth(active))
            icon = "CHECKBOX_HLT" if is_auto_smooth else "CHECKBOX_DEHLT"

            if is_auto_smooth:
                angle_input_name = None
                sharps_input_name = None

                if mod.get('Input_1', None):
                    angle_input_name = 'Input_1'

                    if mod.get('Socket_1', None) is not None:
                        sharps_input_name = 'Socket_1'

                elif mod.get('Socket_1', None):
                    angle_input_name = 'Socket_1'

            r = row.row(align=True)
            r.operator("machin3.toggle_auto_smooth", text="Auto Smooth", icon=icon).angle = 0

            if is_auto_smooth and sharps_input_name is not None:
                r.prop(mod, f'["{sharps_input_name}"]', text="", icon='IPO_LINEAR', invert_checkbox=True)

            row = column.split(factor=0.55, align=True)
            r = row.row(align=True)
            r.active = is_auto_smooth

            for angle in angles:
                r.operator("machin3.toggle_auto_smooth", text=str(angle)).angle = angle

            r = row.row(align=True)
            r.active = is_auto_smooth

            if is_auto_smooth and angle_input_name:
                r.prop(mod, f'["{angle_input_name}"]', text="Auto Smooth Angle")  # see https://blender.stackexchange.com/questions/222535/how-to-draw-inputs-from-geometry-nodes-modifier-in-a-panel and the following comment below as well

            else:
                r.label(text="Auto Smooth Angle: None")

            if mesh.has_custom_normals:
                column.operator("mesh.customdata_custom_splitnormals_clear", text="(N) Clear Custom Normals")

            if active.mode == 'EDIT' and view.overlay.show_overlays:
                column.separator()

                row = column.split(factor=0.2, align=True)
                row.label(text='Normals')
                row.prop(view.overlay, "show_vertex_normals", text="", icon='NORMALS_VERTEX')
                row.prop(view.overlay, "show_split_normals", text="", icon='NORMALS_VERTEX_FACE')
                row.prop(view.overlay, "show_face_normals", text="", icon='NORMALS_FACE')

                r = row.row(align=True)
                r.active = any([view.overlay.show_vertex_normals, view.overlay.show_face_normals, view.overlay.show_split_normals])
                r.prop(view.overlay, "normals_length", text="Size")

                row = column.split(factor=0.2, align=True)
                row.label(text='Edges')
                row.prop(view.overlay, "show_edge_sharp", text="Sharp", toggle=True)
                row.prop(view.overlay, "show_edge_bevel_weight", text="Bevel", toggle=True)
                row.prop(view.overlay, "show_edge_crease", text="Creases", toggle=True)
                row.prop(view.overlay, "show_edge_seams", text="Seams", toggle=True)

        elif active.type == "CURVE" and context.mode == 'OBJECT':
            curve = active.data

            column.separator()

            row = column.split(factor=0.2, align=True)
            row.label(text='Curve')

            r = row.split(factor=0.4, align=True)
            r.prop(curve, "bevel_depth", text="Depth")
            r.prop(curve, "resolution_u")

            row = column.split(factor=0.2, align=True)
            row.label(text='Fill')

            r = row.split(factor=0.4, align=True)
            r.active = curve.bevel_depth > 0
            r.prop(curve, "fill_mode", text="")
            r.prop(curve, "bevel_resolution", text="Resolution")

            if active.mode == 'EDIT' and view.overlay.show_overlays:
                column.separator()

                splines = curve.splines
                if splines:
                    spline = curve.splines[0]
                    if spline.type == 'BEZIER':
                        row = column.split(factor=0.2, align=True)
                        row.label(text='Handles')
                        row.prop(view.overlay, "display_handle", text="")

                row = column.split(factor=0.2, align=True)
                row.label(text='Normals')

                r = row.split(factor=0.2, align=True)
                r.prop(view.overlay, "show_curve_normals", text="", icon='CURVE_PATH')
                rr = r.row(align=True)
                rr.active = view.overlay.show_curve_normals
                rr.prop(view.overlay, "normals_length", text="Length")

            column.separator()

            row = column.split(factor=0.55, align=True)
            r = row.row(align=True)
            r.operator("machin3.shade", text="Smooth", icon_value=get_icon('smooth')).shade_type = 'SMOOTH'
            r.operator("machin3.shade", text="Flat", icon_value=get_icon('flat')).shade_type = 'FLAT'

            angles = [int(a) for a in get_prefs().auto_smooth_angle_presets.split(',')]

            is_auto_smooth = bool(mod := get_auto_smooth(active))
            icon = "CHECKBOX_HLT" if is_auto_smooth else "CHECKBOX_DEHLT"

            row.operator("machin3.toggle_auto_smooth", text="Auto Smooth", icon=icon).angle = 0

            row = column.split(factor=0.55, align=True)
            r = row.row(align=True)

            for angle in angles:
                r.operator("machin3.toggle_auto_smooth", text=str(angle)).angle = angle

            r = row.row(align=True)
            r.active = is_auto_smooth

            if is_auto_smooth:
                r.prop(mod, '["Input_1"]', text="Auto Smooth Angle")
            else:
                r.label(text="Auto Smooth Angle: None")

        elif active.type == "SURFACE" and context.mode == 'OBJECT':
            row = column.split(factor=0.5, align=True)
            row.operator("machin3.shade", text="Smooth", icon_value=get_icon('smooth')).shade_type = 'SMOOTH'
            row.operator("machin3.shade", text="Flat", icon_value=get_icon('flat')).shade_type = 'FLAT'

    def draw_shade_box(self, context, activemat, view, layout):
        scene = context.scene
        m3 = scene.M3
        viewlayer = context.view_layer

        column = layout.column(align=True)

        if view.shading.type == "SOLID":

            row = column.row(align=True)
            row.prop(m3, "shading_light", expand=True)

            if view.shading.light in ["STUDIO", "MATCAP"]:
                row = column.row()
                row.template_icon_view(view.shading, "studio_light", show_labels=True, scale=4, scale_popup=3)

            if view.shading.light == "STUDIO":
                row = column.split(factor=0.3, align=True)
                row.prop(view.shading, "use_world_space_lighting", text='World Space', icon='WORLD')
                r = row.row(align=True)
                r.active = view.shading.use_world_space_lighting
                r.prop(view.shading, "studiolight_rotate_z", text="Rotation")

            elif view.shading.light == "MATCAP":
                row = column.row(align=True)
                row.operator("machin3.matcap_switch", text="(X) Matcap Switch")
                row.operator('view3d.toggle_matcap_flip', text="Matcap Flip", icon='ARROW_LEFTRIGHT')

            elif view.shading.light == "FLAT":

                if m3.use_flat_shadows:
                    row = column.split(factor=0.6, align=True)

                    col = row.column(align=True)
                    r = col.row(align=True)
                    r.scale_y = 1.25
                    r.prop(m3, "use_flat_shadows")

                    c = col.column(align=True)
                    c.active = m3.use_flat_shadows
                    c.prop(scene.display, "shadow_shift")
                    c.prop(scene.display, "shadow_focus")

                    r = row.row(align=True)
                    r.prop(scene.display, "light_direction", text="")

                else:
                    row = column.row(align=True)
                    row.scale_y = 1.25
                    row.prop(m3, "use_flat_shadows")

            row = column.row(align=True)
            row.scale_y = 1.2
            row.prop(view.shading, "color_type", expand=True)

            if view.shading.color_type == 'SINGLE':
                column.prop(view.shading, "single_color", text="")

            elif view.shading.color_type == 'MATERIAL':
                row = column.row(align=True)

                if activemat:
                    row.prop(activemat, 'diffuse_color', text='')

                row.operator("machin3.colorize_materials", text='Colorize Scene Materials', icon='MATERIAL')

            elif view.shading.color_type == 'OBJECT':
                r = column.split(factor=0.12, align=True)
                r.label(text="from")
                r.operator("machin3.colorize_objects_from_active", text='Active', icon='OBJECT_DATA')
                r.operator("machin3.colorize_objects_from_materials", text='Material', icon='MATERIAL')
                r.operator("machin3.colorize_objects_from_collections", text='Collection', icon='OUTLINER_OB_GROUP_INSTANCE')
                r.operator("machin3.colorize_objects_from_groups", text='Group', icon='GROUP_VERTEX')

        elif view.shading.type == "WIREFRAME":
            row = column.row(align=True)
            r = row.row(align=True)
            r.scale_x = 2
            r.prop(view.shading, "show_xray_wireframe", text="")

            r = row.row(align=True)
            r.active = view.shading.show_xray_wireframe
            r.prop(view.shading, "xray_alpha_wireframe", text="X-Ray")

            row = column.row(align=True)
            row.prop(view.shading, "wireframe_color_type", expand=True)

        elif view.shading.type in ['MATERIAL', 'RENDERED']:

            if view.shading.type == 'RENDERED':
                row = column.split(factor=0.3, align=True)
                row.scale_y = 1.2
                row.label(text='Engine')
                row.prop(m3, 'render_engine', expand=True)
                column.separator()

            row = column.row(align=True)

            if bpy.data.lights:
                if view.shading.type == 'MATERIAL':
                    row.prop(view.shading, "use_scene_lights")

                elif view.shading.type == 'RENDERED':
                    row.prop(view.shading, "use_scene_lights_render")

            if view.shading.type == 'MATERIAL':
                row.prop(view.shading, "use_scene_world")

            elif view.shading.type == 'RENDERED':
                row.prop(view.shading, "use_scene_world_render")

            if scene.world:
                row.prop(scene, 'world', text='')

            else:
                row.operator("machin3.add_world", text=f"{'Set' if bpy.data.worlds else 'New'} World", icon='ADD')

            if (world := scene.world) and get_use_world(context):

                split = column.split(factor=0.3, align=True)

                split.prop(world, 'use_sun_shadow', text="World Shadow")

                r = split.row(align=True)
                r.active = world.use_sun_shadow
                r.prop(world, 'sun_angle')
                r.prop(world, 'sun_shadow_maximum_resolution', text="Resolution")

                if viewlayer.use_pass_mist:
                    row = column.row(align=True)
                    row.prop(world.mist_settings, 'start', text='Mist Start')
                    row.prop(world.mist_settings, 'depth', text='Mist Depth')
                    row.prop(world.mist_settings, 'falloff', text='')

                inputs = get_world_surface_inputs(world, debug=False)

                if inputs:
                    for idx, (name, input) in enumerate(inputs.items()):
                        if idx % 2 == 0:
                            if idx != len(inputs) - 1:
                                row = column.split(factor=0.5, align=True)
                            else:
                                row = column.row(align=True)

                        if input.type == 'RGBA':
                            row.prop(input, 'default_value', text='')
                        if input.type in ['VALUE', 'BOOLEAN']:
                            row.prop(input, 'default_value', text=name)
                        elif input.type == 'VECTOR':
                            row.prop(input, 'default_value', text=name, index=2)

            else:

                row = column.row(align=True)
                row.template_icon_view(view.shading, "studio_light", scale=4, scale_popup=4)

                if world := scene.world:
                    split = column.split(factor=0.29, align=True)
                    split.prop(world, 'use_sun_shadow', text="World Shadow")

                    r = split.row(align=True)
                    r.active = scene.world.use_sun_shadow
                    r.prop(world, 'sun_angle')
                    r.prop(world, 'sun_shadow_maximum_resolution', text="Resolution")

                    if viewlayer.use_pass_mist:
                        row = column.row(align=True)
                        row.prop(world.mist_settings, 'start', text='Mist Start')
                        row.prop(world.mist_settings, 'depth', text='Mist Depth')
                        row.prop(world.mist_settings, 'falloff', text='')

                if is_eevee_view(context) and view.shading.studiolight_background_alpha:
                    row = column.split(factor=0.55, align=True)
                    r = row.row(align=True)
                    r.operator("machin3.rotate_studiolight", text='+180').angle = 180
                    r.prop(view.shading, "studiolight_rotate_z", text="Rotation")
                    row.prop(view.shading, "studiolight_background_blur")

                else:
                    row = column.split(factor=0.15, align=True)
                    row.operator("machin3.rotate_studiolight", text='+180').angle = 180
                    row.prop(view.shading, "studiolight_rotate_z", text="Rotation")

                row = column.split(factor=0.5, align=True)
                row.prop(view.shading, "studiolight_intensity")
                row.prop(view.shading, "studiolight_background_alpha")

            if view.shading.type == 'RENDERED':
                enforce_hide_render = get_prefs().activate_render and get_prefs().render_enforce_hide_render

                if enforce_hide_render:
                    row = column.split(factor=0.5, align=True)
                else:
                    row = column.row(align=True)

                row.prop(scene.render, 'film_transparent')

                if enforce_hide_render:
                    row.prop(m3, 'enforce_hide_render', text="Enforce hide_render")

    def draw_eevee_box(self, context, view, layout):
        column = layout.column(align=True)
        eevee = context.scene.eevee
        m3 = context.scene.M3

        split = column.split(factor=0.2, align=True)

        split.label(text='Presets')
        row = split.row(align=True)
        row.prop(context.scene.M3, "eevee_next_preset_set_use_scene_lights", text='', icon='LIGHT_SUN')
        row.prop(context.scene.M3, "eevee_next_preset_set_use_scene_world", text='', icon='WORLD')

        row.prop(context.scene.M3, "eevee_next_preset", expand=True)

        if presets := get_user_presets():
            split = column.split(factor=0.2, align=True)

            row = split.row(align=True)
            row.active = False
            row.label(text='User Presets')
            row = split.row(align=True)

            for preset in presets:
                row.operator("machin3.apply_eevee_user_preset", text=preset).name = preset

        split = column.split(factor=0.2, align=True)
        split.label(text='Passes')

        row = split.row(align=True)

        split = row.split(factor=0.35, align=True)
        split.prop(view.shading, "render_pass", text='')
        split.prop(m3, "eevee_passes_preset", expand=True)

        split = column.split(factor=0.2, align=True)
        split.label(text='Compositor')

        row = split.row(align=True)
        row.prop(context.space_data.shading, "use_compositor", expand=True)

        if view.shading.render_pass == 'AO':
            pass

        elif view.shading.render_pass == 'SHADOW':
            pass

        else:

            col = column.column(align=True)

            icon = "TRIA_DOWN" if m3.use_bloom else "TRIA_RIGHT"
            col.prop(m3, "use_bloom", text="Bloom", icon=icon)

            if m3.use_bloom and (glare := get_composite_glare(context.scene)):
                row = col.row(align=True)

                if bpy.app.version >= (4, 4, 0):
                    row.prop(glare.inputs[1], "default_value", text='Threshold')
                    if bpy.app.version >= (4, 5, 0):
                        row.prop(glare.inputs[8], "default_value", text='Size')
                    else:
                        row.prop(glare.inputs[7], "default_value", text='Size')
                else:
                    row.prop(glare, "threshold")
                    row.prop(glare, "size")

                disp = get_composite_dispersion(context.scene, force=False)
                is_disp = disp and not disp.inputs[2].links

                row.prop(m3, 'use_dispersion', text='' if is_disp else 'Disperse', toggle=True)

                if is_disp:
                    r = row.row(align=True)
                    r.active = not disp.mute and disp.inputs[2].default_value > 0
                    r.prop(disp.inputs[2], 'default_value', text="Dispersion")

            col = column.column(align=True)

            icon = "TRIA_DOWN" if eevee.use_shadows else "TRIA_RIGHT"
            col.prop(eevee, "use_shadows", icon=icon)

            if eevee.use_shadows:
                split = col.split(factor=0.49, align=True)

                row = split.row(align=True)
                row.prop(eevee, "shadow_ray_count", text='Rays')
                row.prop(eevee, "shadow_step_count", text='Steps')

                row = split.row(align=True)
                row.prop(eevee, "use_shadow_jitter_viewport", text='Jittered')
                row.prop(eevee, "use_volumetric_shadows", text='Volumetric', icon='OUTLINER_OB_VOLUME' if eevee.use_volumetric_shadows else 'VOLUME_DATA')

            col = column.column(align=True)
            icon = "TRIA_DOWN" if eevee.use_raytracing else "TRIA_RIGHT"

            if eevee.use_raytracing:
                split = col.split(factor=0.49, align=True)

                row = split.row(align=True)
                row.prop(eevee, "use_raytracing", text='Raytracing', icon=icon)
                row.prop(eevee.ray_tracing_options, "use_denoise")

                split.prop(eevee, "ray_tracing_method", expand=True)

                split = col.split(factor=0.49, align=True)
                split.prop(eevee.ray_tracing_options, "trace_max_roughness", text='Max Roughness')
                s = split.split(align=True)
                s.prop(m3, "eevee_next_resolution", expand=True)

                if eevee.ray_tracing_options.trace_max_roughness < 1:
                    split = col.split(factor=0.49, align=True)

                    row = split.row(align=True)
                    row.prop(eevee, "fast_gi_ray_count", text='Rays')
                    row.prop(eevee, "fast_gi_step_count", text='Steps')

                    split.prop(eevee, "fast_gi_method", expand=True)

                    row = col.row(align=True)
                    r = row.row(align=True)
                    r.alert = True
                    r.prop(m3, "eevee_next_thickness", text='Thickness')
                    row.prop(m3, "eevee_next_quality", text='Precision')

                    split = col.split(factor=0.49, align=True)
                    split.prop(eevee, "fast_gi_thickness_far", text="Angular Thickness")
                    split.prop(eevee, "fast_gi_bias")

            else:
                row = col.row(align=True)
                row.prop(eevee, "use_raytracing", text='Raytracing', icon=icon)

            col = column.column(align=True)

            icon = "TRIA_DOWN" if m3.use_volumes else "TRIA_RIGHT"
            col.prop(m3, "use_volumes", text='Volumes', icon=icon)

            if m3.use_volumes:
                split = col.split(factor=0.49, align=True)
                split.prop(eevee, "volumetric_samples", text='Steps')

                s = split.split(align=True)
                s.prop(eevee, "volumetric_tile_size", expand=True)

                data = is_volume(context, simple=False)

                if data['is_world_volume']:
                    split = col.split(factor=0.29, align=True)
                    split.prop(eevee, "use_volume_custom_range", text="Custom Range")

                    row = split.row(align=True)
                    row.active = eevee.use_volume_custom_range
                    row.prop(eevee, "volumetric_start")
                    row.prop(eevee, "volumetric_end")

                if node := data['world_volume']:
                    color = node.inputs[0]
                    density = node.inputs[2]
                    emission_color = node.inputs[7]
                    emission_strength = node.inputs[6]

                    if not all(i.links for i in [color, density, emission_color, emission_strength]):
                        row = col.row(align=True)

                        if not color.links:
                            row.prop(color, "default_value", text="")
                        if not density.links:
                            row.prop(density, "default_value", text="Density")
                        if not emission_color.links:
                            row.prop(emission_color, "default_value", text="")
                        if not emission_strength.links:
                            row.prop(emission_strength, "default_value", text="Strength")
    def draw_cycles_box(self, context, view, layout):
        cycles = context.scene.cycles
        column = layout.column(align=True)

        m3 = context.scene.M3
        active = active if (active := context.active_object) and active.select_get() else None

        row = column.split(factor=0.3, align=True)
        row.label(text='Cycles Settings')
        row.prop(context.scene.M3, 'cycles_device', expand=True)

        row = column.split(factor=0.297, align=True)
        row.label(text='Passes')
        row.prop(view.shading.cycles, "render_pass", text='')

        row = column.split(factor=0.31, align=True)
        row.label(text='Compositor')
        row.prop(context.space_data.shading, "use_compositor", expand=True)

        if view.shading.cycles.render_pass == 'COMBINED':
            col = column.column(align=True)

            icon = "TRIA_DOWN" if m3.use_bloom else "TRIA_RIGHT"
            col.prop(m3, "use_bloom", text="Bloom", icon=icon)

            if m3.use_bloom and (glare := get_composite_glare(context.scene)):
                row = col.row(align=True)
                row.prop(glare, "threshold")
                row.prop(glare, "size")

                disp = get_composite_dispersion(context.scene, force=False)
                is_disp = disp and not disp.inputs[2].links

                row.prop(m3, 'use_dispersion', text='' if is_disp else 'Disperse', toggle=True)

                if is_disp:
                    r = row.row(align=True)
                    r.active = not disp.mute and disp.inputs[2].default_value > 0
                    r.prop(disp.inputs[2], 'default_value', text="Dispersion")

        row = column.split(factor=0.33, align=True)
        row.prop(cycles, 'use_preview_denoising', text='Denoise')
        row.prop(cycles, 'use_adaptive_sampling', text='Adaptive')
        row.prop(cycles, 'seed')

        row = column.split(factor=0.5, align=True)
        row.prop(cycles, 'preview_samples', text='Viewport')
        row.prop(cycles, 'samples', text='Render')

        row = column.split(factor=0.33, align=True)
        row.prop(cycles, 'use_fast_gi', text='Fast GI')
        row.prop(cycles, 'ao_bounces', text="Viewport")
        row.prop(cycles, 'ao_bounces_render', text="Render")

        if view.shading.cycles.render_pass == 'COMBINED':
            col = column.column(align=True)

            icon = "TRIA_DOWN" if m3.use_volumes else "TRIA_RIGHT"
            col.prop(m3, "use_volumes", text='Volumes', icon=icon)

            if m3.use_volumes:
                row = col.row(align=True)

                row.prop(context.scene.cycles, 'volume_preview_step_rate', text='Viewport')
                row.prop(context.scene.cycles, 'volume_step_rate', text='Render')
                row.prop(context.scene.cycles, 'volume_max_steps', text='Max Steps')

                data = is_volume(context, simple=False)

                if node := data['world_volume']:
                    color = node.inputs[0]
                    density = node.inputs[2]
                    emission_color = node.inputs[7]
                    emission_strength = node.inputs[6]

                    if not all(i.links for i in [color, density, emission_color, emission_strength]):
                        row = col.row(align=True)

                        if not color.links:
                            row.prop(color, "default_value", text="")
                        if not density.links:
                            row.prop(density, "default_value", text="Density")
                        if not emission_color.links:
                            row.prop(emission_color, "default_value", text="")
                        if not emission_strength.links:
                            row.prop(emission_strength, "default_value", text="Strength")

        if active:
            column = layout.column(align=True)
            row = column.split(factor=0.5, align=True)
            row.prop(active, 'is_shadow_catcher')
            row.prop(active, 'is_holdout')

        use_bevel_shader = get_prefs().activate_render and get_prefs().render_use_bevel_shader

        if use_bevel_shader:
            m3 = context.scene.M3

            column = layout.column(align=True)

            split = column.split(factor=0.35, align=True)
            split.prop(m3, 'use_bevel_shader')

            row = split.row(align=True)
            row.active = m3.use_bevel_shader
            row.prop(m3, 'bevel_shader_use_dimensions', text="", icon='FULLSCREEN_ENTER')
            row.prop(m3, 'bevel_shader_samples')
            row.prop(m3, 'bevel_shader_radius', text='Width')
            op = row.operator('machin3.adjust_bevel_shader_radius', text='', icon='TRIA_DOWN')
            op.global_radius = True
            op.decrease = True
            op = row.operator('machin3.adjust_bevel_shader_radius', text='', icon='TRIA_UP')
            op.global_radius = True
            op.decrease = False

            if active:
                row = column.row(align=True)

                if M3.get_addon("DECALmachine") and is_decal(active):
                    if active.parent:
                        if active.DM.decaltype == 'PANEL':
                            row.label(text="Bevel Radius of Panel Decals is modulated via the parent object!", icon='INFO')
                        else:
                            row.label(text="Bevel Shader on non-panel decals is not (yet?) supported!", icon='INFO')

                            row = column.row(align=True)
                            row.label(text='', icon='BLANK1')
                            row.label(text="Do you really need this? Email me, if so: decal@machin3.io")

                    else:
                        row.label(text="Bevel Shader on decals without parent objects is not supported.", icon='INFO')

                else:
                    row = column.row(align=True)

                    row.active = m3.use_bevel_shader
                    row.prop(active.M3, 'bevel_shader_toggle', text="Active Object Toggle")

                    r = row.row(align=True)
                    r.active = m3.use_bevel_shader and active.M3.bevel_shader_toggle
                    r.prop(active.M3, 'bevel_shader_radius_mod', text="Active Object Factor")
                    op = r.operator('machin3.adjust_bevel_shader_radius', text='', icon='TRIA_DOWN')
                    op.global_radius = False
                    op.decrease = True
                    op = r.operator('machin3.adjust_bevel_shader_radius', text='', icon='TRIA_UP')
                    op.global_radius = False
                    op.decrease = False

    def draw_light_adjust_box(self, context, m3, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        row.prop(m3, 'adjust_lights_on_render', text='Adjust Lights when Rendering')
        r = row.row(align=True)
        r.active = m3.adjust_lights_on_render
        r.prop(m3, 'adjust_lights_on_render_divider', text='')

    def get_text_icon(self, context, shading):
        if context.space_data.shading.type == shading:
            text = "Overlays"
            icon = "OVERLAY"
        else:
            if shading == "SOLID":
                text = "(L) Solid"
                icon = "SHADING_SOLID"
            elif shading == "MATERIAL":
                text = "Material"
                icon = "SHADING_TEXTURE"
            elif shading == "RENDERED":
                text = "Rendered"
                icon = "SHADING_RENDERED"
            elif shading == "WIREFRAME":
                text = "Wireframe"
                icon = "SHADING_WIRE"

        return text, icon

class PieViewport(Menu):
    bl_idname = "MACHIN3_MT_viewport_pie"
    bl_label = "Viewport and Cameras"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        scene = context.scene
        view = context.space_data
        r3d = view.region_3d

        op = pie.operator("machin3.view_axis", text="Front")
        op.axis='FRONT'

        op = pie.operator("machin3.view_axis", text="Right")
        op.axis='RIGHT'

        op = pie.operator("machin3.view_axis", text="Top")
        op.axis='TOP'

        box = pie.split()

        b = box.box()
        self.draw_camera_box(scene, view, b)

        column = box.column()
        b = column.box()
        self.draw_other_views_box(b)

        b = column.box()
        self.draw_custom_views_box(scene, b)

        b = box.box()
        self.draw_view_properties_box(context, view, r3d, b)

        pie.separator()

        pie.separator()

        if get_prefs().show_orbit_selection:
            box = pie.split()
            box.scale_y = 1.2
            box.operator("machin3.toggle_orbit_selection", text="Orbit Selection", depress=context.preferences.inputs.use_rotate_around_active)
        else:
            pie.separator()

        if get_prefs().show_orbit_method:
            box = pie.split()
            box.scale_y = 1.2
            box.operator("machin3.toggle_orbit_method", text=context.preferences.inputs.view_rotate_method.title())
        else:
            pie.separator()

    def draw_camera_box(self, scene, view, layout):
        column = layout.column(align=True)
        column.scale_x = 2

        is_cam_view =  view.region_3d.view_perspective == 'CAMERA'

        if scene.camera and is_cam_view:
            row = column.row(align=True)
            row.scale_y = 1.5
            row.prop(scene.camera, 'name', text='')

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("machin3.smart_view_cam", text="Smart View Cam", icon='HIDE_OFF')

        if view.region_3d.view_perspective == 'CAMERA':
            cams = [obj for obj in scene.objects if obj.type == "CAMERA"]

            if len(cams) > 1:
                split = column.split(factor=0.49, align=True)
                split.operator("machin3.next_cam", text="(Q) Previous Cam").previous = True
                split.operator("machin3.next_cam", text="(W) Next Cam").previous = False

        row = column.split(align=True)
        row.operator("machin3.make_cam_active")
        row.prop(scene, "camera", text="")

        row = column.split(align=True)
        row.operator("view3d.camera_to_view", text="Cam to view", icon='VIEW_CAMERA')

        text, icon = ("Unlock from View", "UNLOCKED") if view.lock_camera else ("Lock to View", "LOCKED")
        row.operator("wm.context_toggle", text=text, icon=icon).data_path = "space_data.lock_camera"

    def draw_other_views_box(self, layout):
        column = layout.column(align=True)

        column.scale_y = 1.2
        op = column.operator("machin3.view_axis", text="Bottom")
        op.axis='BOTTOM'

        row = column.row(align=True)
        op = row.operator("machin3.view_axis", text="Left")
        op.axis='LEFT'

        op = row.operator("machin3.view_axis", text="Back")
        op.axis='BACK'

    def draw_custom_views_box(self, scene, layout):
        column = layout.column(align=True)

        row = column.split(factor=0.33, align=True)
        row.scale_y = 1.25
        row.label(text="Custom Views")
        row.prop(scene.M3, "custom_views_local", text='Local')
        row.prop(scene.M3, "custom_views_cursor", text='Cursor')

    def draw_view_properties_box(self, context, view, r3d, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.5

        if view.region_3d.view_perspective == 'CAMERA':
            cam = context.scene.camera

            if cam:
                text, icon = ("Orthographic", "VIEW_ORTHO") if cam.data.type == "PERSP" else ("Perspective", "VIEW_PERSPECTIVE")
                row.operator("machin3.toggle_cam_persportho", text=text, icon=icon)

                if cam.data.type == "PERSP":
                    row = column.row(align=True)
                    row.prop(cam.data, "lens")
                    row.prop(cam.data, "sensor_width")

                elif cam.data.type == "ORTHO":
                    column.prop(cam.data, "ortho_scale")

                dof = cam.data.dof

                row = column.row(align=True)
                icon = "TRIA_DOWN" if dof.use_dof else "TRIA_RIGHT"
                row.prop(dof, 'use_dof', icon=icon)

                if dof.use_dof:
                    row.prop(dof, 'aperture_fstop')

                    row = column.row(align=True)
                    row.prop(dof, 'aperture_blades')
                    row.prop(dof, 'aperture_rotation')
                    row.prop(dof, 'aperture_ratio')

                    row = column.row(align=True)

                    row.operator("machin3.select_dof_object", text='', icon='RESTRICT_SELECT_OFF')
                    row.prop(dof, "focus_object", text='')

                    r = row.row(align=True)
                    r.scale_x = 1.5
                    r.operator("machin3.create_dof_empty", text='', icon='SPHERE')

                    r = row.row(align=True)
                    r.enabled = not dof.focus_object
                    r.prop(dof, "focus_distance", text='')

                    r.operator("ui.eyedropper_depth", icon='EYEDROPPER', text="").prop_data_path = "scene.camera.data.dof.focus_distance"

        else:
            text, icon = ("Orthographic", "VIEW_ORTHO") if r3d.is_perspective else ("Perspective", "VIEW_PERSPECTIVE")
            row.operator("machin3.toggle_view_persportho", text=text, icon=icon)

            column.prop(view, "lens")

            column.operator("machin3.reset_viewport", text='Reset Viewport')

class PieAlign(Menu):
    bl_idname = "MACHIN3_MT_align_pie"
    bl_label = "Align"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        m3 = context.scene.M3
        active = context.active_object
        sel = [obj for obj in context.selected_objects if obj != active]

        if m3.align_mode == 'AXES':
            self.draw_align_with_axes(pie, m3, sel)
        elif m3.align_mode == "VIEW":
            self.draw_align_with_view(pie, m3, sel)

    def draw_align_with_axes(self, pie, m3, sel):
        op = pie.operator("machin3.align_editmesh", text="Y min")
        op.mode = "AXES"
        op.axis = "Y"
        op.type = "MIN"

        op = pie.operator("machin3.align_editmesh", text="Y max")
        op.mode = "AXES"
        op.axis = "Y"
        op.type = "MAX"

        box = pie.split()
        column = box.column(align=True)

        column.separator()

        row = column.split(factor=0.2, align=True)
        row.separator()
        row.label(text="Center")

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.center_editmesh", text="X").axis = "X"
        row.operator("machin3.center_editmesh", text="Y").axis = "Y"
        row.operator("machin3.center_editmesh", text="Z").axis = "Z"

        column.separator()

        row = column.row(align=True)
        row.scale_y = 1.2
        row.operator("machin3.straighten", text="Straighten")

        if sel:
            row = column.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.align_object_to_vert", text="Align Object to Vert")

            row = column.row(align=True)
            row.scale_y = 1.2
            row.operator("machin3.align_object_to_edge", text="Align Object to Edge")

        box = pie.split()
        column = box.column()

        row = column.split(factor=0.2)
        row.label(icon="ARROW_LEFTRIGHT")
        r = row.row(align=True)
        r.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="X")
        op.mode = "AXES"
        op.axis = "X"
        op.type = "AVERAGE"
        op = r.operator("machin3.align_editmesh", text="Y")
        op.mode = "AXES"
        op.axis = "Y"
        op.type = "AVERAGE"
        op = r.operator("machin3.align_editmesh", text="Z")
        op.mode = "AXES"
        op.axis = "Z"
        op.type = "AVERAGE"

        row = column.split(factor=0.2)
        row.label(icon="FREEZE")
        r = row.row(align=True)
        r.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="X")
        op.mode = "AXES"
        op.axis = "X"
        op.type = "ZERO"
        op = r.operator("machin3.align_editmesh", text="Y")
        op.mode = "AXES"
        op.axis = "Y"
        op.type = "ZERO"
        op = r.operator("machin3.align_editmesh", text="Z")
        op.mode = "AXES"
        op.axis = "Z"
        op.type = "ZERO"

        row = column.split(factor=0.2)
        row.label(icon="PIVOT_CURSOR")
        r = row.row(align=True)
        r.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="X")
        op.mode = "AXES"
        op.axis = "X"
        op.type = "CURSOR"
        op = r.operator("machin3.align_editmesh", text="Y")
        op.mode = "AXES"
        op.axis = "Y"
        op.type = "CURSOR"
        op = r.operator("machin3.align_editmesh", text="Z")
        op.mode = "AXES"
        op.axis = "Z"
        op.type = "CURSOR"

        column.separator()

        row = column.split(factor=0.15)
        row.separator()
        r = row.split(factor=0.8)
        rr = r.row(align=True)
        rr.prop(m3, "align_mode", expand=True)

        column.separator()

        op = pie.operator("machin3.align_editmesh", text="X min")
        op.mode = "AXES"
        op.axis = "X"
        op.type = "MIN"

        op = pie.operator("machin3.align_editmesh", text="X max")
        op.mode = "AXES"
        op.axis = "X"
        op.type = "MAX"

        op = pie.operator("machin3.align_editmesh", text="Z min")
        op.mode = "AXES"
        op.axis = "Z"
        op.type = "MIN"

        op = pie.operator("machin3.align_editmesh", text="Z max")
        op.mode = "AXES"
        op.axis = "Z"
        op.type = "MAX"

    def draw_align_with_view(self, pie, m3, sel):
        op = pie.operator("machin3.align_editmesh", text="Left")
        op.mode = "VIEW"
        op.direction = "LEFT"

        op = pie.operator("machin3.align_editmesh", text="Right")
        op.mode = "VIEW"
        op.direction = "RIGHT"

        op = pie.operator("machin3.align_editmesh", text="Bottom")
        op.mode = "VIEW"
        op.direction = "BOTTOM"

        op = pie.operator("machin3.align_editmesh", text="Top")
        op.mode = "VIEW"
        op.direction = "TOP"

        pie.separator()

        box = pie.split()
        column = box.column()

        row = column.row(align=True)
        row.prop(m3, "align_mode", expand=True)

        box = pie.split()
        column = box.column(align=True)

        column.separator()

        row = column.split(factor=0.25)
        row.label(text="Center")

        r = row.row(align=True)
        r.scale_y = 1.2
        op = r.operator("machin3.center_editmesh", text="Horizontal")
        op.direction = "HORIZONTAL"
        op = r.operator("machin3.center_editmesh", text="Vertical")
        op.direction = "VERTICAL"

        column.separator()
        row = column.split(factor=0.25, align=True)
        row.scale_y = 1.2
        row.separator()
        row.operator("machin3.straighten", text="Straighten")

        if sel:
            row = column.split(factor=0.25, align=True)
            row.scale_y = 1.2
            row.separator()
            row.operator("machin3.align_object_to_vert", text="Align Object to Vert")

            row = column.split(factor=0.25, align=True)
            row.scale_y = 1.2
            row.separator()
            row.operator("machin3.align_object_to_edge", text="Align Object to Edge")

        box = pie.split()
        column = box.column(align=True)

        row = column.split(factor=0.2, align=True)
        row.label(icon="ARROW_LEFTRIGHT")

        r = row.row(align=True)
        row.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="Horizontal")
        op.mode = "VIEW"
        op.type = "AVERAGE"
        op.direction = "HORIZONTAL"
        op = r.operator("machin3.align_editmesh", text="Vertical")
        op.mode = "VIEW"
        op.type = "AVERAGE"
        op.direction = "VERTICAL"

        row = column.split(factor=0.2, align=True)
        row.label(icon="FREEZE")

        r = row.row(align=True)
        r.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="Horizontal")
        op.mode = "VIEW"
        op.type = "ZERO"
        op.direction = "HORIZONTAL"
        op = r.operator("machin3.align_editmesh", text="Vertical")
        op.mode = "VIEW"
        op.type = "ZERO"
        op.direction = "VERTICAL"

        row = column.split(factor=0.2, align=True)
        row.label(icon="PIVOT_CURSOR")

        r = row.row(align=True)
        row.scale_y = 1.2
        op = r.operator("machin3.align_editmesh", text="Horizontal")
        op.mode = "VIEW"
        op.type = "CURSOR"
        op.direction = "HORIZONTAL"
        op = r.operator("machin3.align_editmesh", text="Vertical")
        op.mode = "VIEW"
        op.type = "CURSOR"
        op.direction = "VERTICAL"

class PieUVAlign(Menu):
    bl_idname = "MACHIN3_MT_uv_align_pie"
    bl_label = "UV Align"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        m3 = context.scene.M3

        if m3.align_mode == 'AXES':
            self.draw_align_with_axes(pie, m3)
        elif m3.align_mode == "VIEW":
            self.draw_align_with_view(pie, m3)

    def draw_align_with_axes(self, pie, m3):
        op = pie.operator("machin3.align_uv", text="V min")
        op.axis = "V"
        op.type = "MIN"

        op = pie.operator("machin3.align_uv", text="V max")
        op.axis = "V"
        op.type = "MAX"

        pie.separator()

        box = pie.split()
        column = box.column()

        row = column.row(align=True)
        row.prop(m3, "align_mode", expand=True)

        column.separator()
        column.separator()

        op = pie.operator("machin3.align_uv", text="U min")
        op.axis = "U"
        op.type = "MIN"

        op = pie.operator("machin3.align_uv", text="U max")
        op.axis = "U"
        op.type = "MAX"

        op = pie.operator("machin3.align_uv", text="U Cursor")
        op.axis = "U"
        op.type = "CURSOR"

        op = pie.operator("machin3.align_uv", text="V Cursor")
        op.axis = "V"
        op.type = "CURSOR"

    def draw_align_with_view(self, pie, m3):
        op = pie.operator("machin3.align_uv", text="Left")
        op.axis = "U"
        op.type = "MIN"

        op = pie.operator("machin3.align_uv", text="Right")
        op.axis = "U"
        op.type = "MAX"

        op = pie.operator("machin3.align_uv", text="Bottom")
        op.axis = "V"
        op.type = "MIN"

        op = pie.operator("machin3.align_uv", text="Top")
        op.axis = "V"
        op.type = "MAX"

        pie.separator()

        box = pie.split()
        column = box.column()

        row = column.row(align=True)
        row.prop(m3, "align_mode", expand=True)

        pie.separator()

        box = pie.split()
        column = box.column()

        row = column.split(factor=0.2)

        row.label(icon="PIVOT_CURSOR")

        r = row.row(align=True)
        row.scale_y = 1.2
        op = r.operator("machin3.align_uv", text="Horizontal")
        op.type = "CURSOR"
        op.axis = "U"
        op = r.operator("machin3.align_uv", text="Vertical")
        op.type = "CURSOR"
        op.axis = "V"

class PieCursor(Menu):
    bl_idname = "MACHIN3_MT_cursor_pie"
    bl_label = "Cursor and Origin"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        active = context.active_object
        icol = None

        is_assembly = bool(active and (icol := is_instance_collection(active)))
        is_linked_icol = bool(icol and icol.library)

        has_offset = is_assembly and active.instance_collection.instance_offset != Vector()

        if context.mode == 'EDIT_MESH':
            sel, icon = ('Vert', 'VERTEXSEL') if tuple(context.scene.tool_settings.mesh_select_mode) == (True, False, False) else ('Edge', 'EDGESEL') if tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False) else ('Face', 'FACESEL') if tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True) else (None, None)
            pie.operator("machin3.cursor_to_selected", text="to %s" % (sel), icon="PIVOT_CURSOR")
        else:
            pie.operator("machin3.cursor_to_selected", text="to Selected", icon="PIVOT_CURSOR")

        if context.mode == 'OBJECT':
            pie.operator("machin3.selected_to_cursor", text="to Cursor", icon="RESTRICT_SELECT_OFF")

        else:
            pie.operator("view3d.snap_selected_to_cursor", text="to Cursor", icon="RESTRICT_SELECT_OFF").use_offset = False

        if context.mode in ['OBJECT', 'EDIT_MESH']:
            box = pie.split()
            column = box.column(align=True)

            if get_prefs().cursor_show_to_grid:
                column.separator()
                column.separator()

            if context.mode == 'OBJECT':
                row = column.split(factor=0.25)
                row.separator()

                if is_assembly:
                    row.alert = is_linked_icol
                    row.label(text="Assembly Origin")
                else:
                    row.label(text="Object Origin")

                column.scale_x = 1.1

                row = column.split(factor=0.5, align=True)
                row.scale_y = 1.5
                row.operator("object.origin_set", text="to Geometry", icon="MESH_DATA").type = "ORIGIN_GEOMETRY"

                if is_assembly:
                    row.operator("machin3.set_assembly_origin", text="to Cursor", icon="LAYER_ACTIVE").source = 'CURSOR'

                else:
                    row.operator("machin3.origin_to_cursor", text="to Cursor", icon="LAYER_ACTIVE")

                row = column.split(factor=0.5, align=True)
                row.scale_y = 1.5

                if is_assembly and has_offset:
                    row
                    row.operator("machin3.reset_assembly_origin", text="Reset Origin", icon="LOOP_BACK")

                else:
                    row.operator("machin3.origin_to_active", text="to Active", icon="TRANSFORM_ORIGINS")

                if is_assembly:
                    row.operator("machin3.set_assembly_origin", text="to Object", icon="LAYER_ACTIVE").source = 'OBJECT'
                else:
                    row.operator("machin3.origin_to_bottom_bounds", text="to Bottom", icon="AXIS_TOP")

            elif context.mode == 'EDIT_MESH':
                row = column.split(factor=0.25)
                row.separator()
                row.label(text="Object Origin")

                if tuple(context.scene.tool_settings.mesh_select_mode) in [(True, False, False), (False, True, False), (False, False, True)]:
                    column.scale_x = 1.1

                    sel, icon = ('Vert', 'VERTEXSEL') if tuple(context.scene.tool_settings.mesh_select_mode) == (True, False, False) else ('Edge', 'EDGESEL') if tuple(context.scene.tool_settings.mesh_select_mode) == (False, True, False) else ('Face', 'FACESEL') if tuple(bpy.context.scene.tool_settings.mesh_select_mode) == (False, False, True) else (None, None)

                    row = column.row(align=True)
                    row.scale_y = 1.5
                    row.operator("machin3.origin_to_active", text="to %s" % (sel), icon=icon)
                    row.operator("machin3.origin_to_cursor", text="to Cursor", icon='LAYER_ACTIVE')

                else:
                    column.scale_x = 1.5

                    row = column.split(factor=0.25, align=True)
                    row.scale_y = 1.5
                    row.separator()
                    row.operator("machin3.origin_to_cursor", text="to Cursor", icon='LAYER_ACTIVE')

        else:
            pie.separator()

        if M3.get_addon("HyperCursor") and context.mode in ['OBJECT', 'EDIT_MESH']:
            tools = get_tools_from_context(context)
            pie.operator("machin3.transform_cursor", text="   Drag Hyper Cursor", icon_value=tools['machin3.tool_hyper_cursor']['icon_value']).mode = 'DRAG'
        else:
            pie.separator()

        pie.operator("machin3.cursor_to_origin", text="to Origin", icon="PIVOT_CURSOR")

        pie.operator("view3d.snap_selected_to_cursor", text="to Cursor, Offset", icon="RESTRICT_SELECT_OFF").use_offset = True

        if get_prefs().cursor_show_to_grid:
            pie.operator("view3d.snap_cursor_to_grid", text="to Grid", icon="PIVOT_CURSOR")
        else:
            pie.separator()

        if get_prefs().cursor_show_to_grid:
            pie.operator("view3d.snap_selected_to_grid", text="to Grid", icon="RESTRICT_SELECT_OFF")
        else:
            pie.separator()

class PieTransform(Menu):
    bl_idname = "MACHIN3_MT_transform_pie"
    bl_label = "Transform"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        scene = context.scene
        m3 = context.scene.M3
        active = context.active_object

        pivot = context.scene.tool_settings.transform_pivot_point
        orientation = context.scene.transform_orientation_slots[0].type

        op = pie.operator('machin3.set_transform_preset', text='Local', depress=pivot == 'MEDIAN_POINT' and orientation == 'LOCAL')
        op.pivot = 'MEDIAN_POINT'
        op.orientation = 'LOCAL'

        ori = 'VIEW' if (m3.custom_views_local or m3.custom_views_cursor) else 'GLOBAL'
        op = pie.operator('machin3.set_transform_preset', text=ori.capitalize(), depress=pivot == 'MEDIAN_POINT' and orientation == ori)
        op.pivot = 'MEDIAN_POINT'
        op.orientation = ori

        ori = 'NORMAL' if context.mode in ['EDIT_MESH', 'EDIT_ARMATURE'] else 'LOCAL'
        op = pie.operator('machin3.set_transform_preset', text='Active', depress=pivot == 'ACTIVE_ELEMENT' and orientation == ori)
        op.pivot = 'ACTIVE_ELEMENT'
        op.orientation = ori

        box = pie.split()

        b = box.box()
        self.draw_left_column(scene, b)

        b = box.box()
        self.draw_center_column(scene, b)

        if context.mode in ['OBJECT', 'EDIT_MESH']:
            b = box.box()
            self.draw_right_column(context, scene, active, b)

        pie.separator()

        pie.separator()

        ori = 'NORMAL' if context.mode in ['EDIT_MESH', 'EDIT_ARMATURE'] else 'LOCAL'
        op = pie.operator('machin3.set_transform_preset', text='Individual', depress=pivot == 'INDIVIDUAL_ORIGINS' and orientation == ori)
        op.pivot = 'INDIVIDUAL_ORIGINS'
        op.orientation = ori

        op = pie.operator('machin3.set_transform_preset', text='Cursor', depress=pivot == 'CURSOR' and orientation == 'CURSOR')
        op.pivot = 'CURSOR'
        op.orientation = 'CURSOR'

    def draw_left_column(self, scene, layout):
        column = layout.column()

        column.scale_x = 3

        col = column.column(align=True)
        col.label(text="Pivot Point")

        col.prop(scene.tool_settings, "transform_pivot_point", expand=True)

    def draw_center_column(self, scene, layout):
        column = layout.column()

        slot = scene.transform_orientation_slots[0]
        custom = slot.custom_orientation

        col = column.column(align=True)
        col.label(text="Orientation")

        col.prop(slot, "type", expand=True)

        col = column.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.operator("transform.create_orientation", text="Custom", icon='ADD', emboss=True).use = True

        if custom:
            row = col.row(align=True)
            row.prop(custom, "name", text="")
            row.operator("transform.delete_orientation", text="X", emboss=True)

    def draw_right_column(self, context, scene, active, layout):
        column = layout.column()

        col = column.column(align=True)

        if context.mode == 'OBJECT':
            col.label(text="Affect Only")

            c = col.column(align=True)
            c.scale_y = 1.2
            c.prop(scene.tool_settings, "use_transform_data_origin", text="Origins")
            c.prop(scene.tool_settings, "use_transform_pivot_point_align", text="Locations")
            c.prop(scene.tool_settings, "use_transform_skip_children", text="Parents")

            if get_prefs().activate_group_tools and (context.active_object and context.active_object.M3.is_group_empty) or context.scene.M3.group_origin_mode:
                c.prop(scene.M3, "group_origin_mode", text="Group Origin")

        elif context.mode == 'EDIT_MESH':
            col.label(text="Transform")

            col.prop(scene.tool_settings, "use_transform_correct_face_attributes")

            row = col.row(align=True)
            row.active = scene.tool_settings.use_transform_correct_face_attributes
            row.prop(scene.tool_settings, "use_transform_correct_keep_connected")

            col.label(text="Mirror")

            row = col.row(align=True)
            row.prop(active.data, "use_mirror_x")
            row.prop(active.data, "use_mirror_y")
            row.prop(active.data, "use_mirror_z")

            row = col.row(align=True)
            row.active = any([active.data.use_mirror_x, active.data.use_mirror_y, active.data.use_mirror_z])
            row.prop(active.data, "use_mirror_topology", toggle=True)

class PieSnapping(Menu):
    bl_idname = "MACHIN3_MT_snapping_pie"
    bl_label = "Snapping"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        scene = context.scene
        ts = scene.tool_settings
        p = get_prefs()

        absolute_grid = p.snap_show_absolute_grid
        volume = p.snap_show_volume

        op = pie.operator('machin3.set_snapping_preset', text='Vertex', depress='VERTEX' in ts.snap_elements  and ts.snap_target == p.snap_vert_preset_target and not ts.use_snap_align_rotation, icon='SNAP_VERTEX')
        op.element = 'VERTEX'
        op.target = p.snap_vert_preset_target
        op.align_rotation = False

        if absolute_grid or (absolute_grid and volume):

            depress = 'GRID' in ts.snap_elements and ts.snap_target == p.snap_grid_preset_target

            op = pie.operator('machin3.set_snapping_preset', text='Absolute Grid', depress=depress, icon='SNAP_GRID')
            op.element = 'GRID'
            op.target = p.snap_grid_preset_target

        elif volume:
            op = pie.operator('machin3.set_snapping_preset', text='Volume', depress='VOLUME' in ts.snap_elements and ts.snap_target == p.snap_volume_preset_target, icon='SNAP_VOLUME')
            op.element = 'VOLUME'
            op.target = p.snap_volume_preset_target

        else:
            self.draw_surface_or_face_nearest_preset(pie, ts)

        if absolute_grid or volume:
            self.draw_surface_or_face_nearest_preset(pie, ts)

        else:
            op = pie.operator('machin3.set_snapping_preset', text='Edge', depress='EDGE' in ts.snap_elements and ts.snap_target == p.snap_edge_preset_target and not ts.use_snap_align_rotation, icon='SNAP_EDGE')
            op.element = 'EDGE'
            op.target = p.snap_edge_preset_target
            op.align_rotation = False

        box = pie.split()

        b = box.box()
        column = b.column()
        self.draw_center_column(ts, column)

        pie.separator()

        pie.separator()

        if absolute_grid or volume:
            op = pie.operator('machin3.set_snapping_preset', text='Edge', depress='EDGE' in ts.snap_elements and ts.snap_target == p.snap_edge_preset_target and not ts.use_snap_align_rotation, icon='SNAP_EDGE')
            op.element = 'EDGE'
            op.target = p.snap_edge_preset_target
            op.align_rotation = False

        else:
            pie.separator()

        if absolute_grid and volume:
            op = pie.operator('machin3.set_snapping_preset', text='Volume', depress='VOLUME' in ts.snap_elements and ts.snap_target == p.snap_volume_preset_target, icon='SNAP_VOLUME')
            op.element = 'VOLUME'
            op.target = p.snap_volume_preset_target

        else:
            pie.separator()

    def draw_center_column(self, tool_settings, layout):
        column = layout.column(align=True)

        row = column.row(align=True)
        row.scale_y = 1.25

        r = row.row(align=True)
        r.scale_x = 1.25

        r.prop(tool_settings, 'use_snap', text='')

        row.popover(panel="VIEW3D_PT_snapping", text="More...")
        row.prop(get_prefs(), 'snap_show_volume', text='', icon='SNAP_VOLUME')
        row.prop(get_prefs(), 'snap_show_absolute_grid', text='', icon='SNAP_GRID')

        row = column.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 0.9
        row.prop(tool_settings, 'snap_target', expand=True)

        row = column.row(align=True)
        row.scale_y = 1.25
        row.prop(tool_settings, 'use_snap_align_rotation')

        column.separator()
        row = column.row()
        row.alignment = "CENTER"
        row.label(text=" + ".join(get_sorted_snap_elements(tool_settings)))

    def draw_surface_or_face_nearest_preset(self, pie, ts):
        p = get_prefs()

        if p.snap_toggle_face_nearest:
            is_surface = 'FACE' in ts.snap_elements and ts.snap_target == p.snap_surface_preset_target and ts.use_snap_align_rotation
            is_nearest = 'FACE_NEAREST' in ts.snap_elements and ts.snap_target == p.snap_face_nearest_preset_target and not ts.use_snap_align_rotation

            if is_surface and not is_nearest:
                op = pie.operator('machin3.set_snapping_preset', text='Surface', depress=True, icon='SNAP_FACE')
                op.element = 'FACE_NEAREST'
                op.target = p.snap_face_nearest_preset_target
                op.align_rotation = False

            elif is_nearest and not is_surface:
                op = pie.operator('machin3.set_snapping_preset', text='Face Nearest', depress=True, icon='SNAP_FACE_NEAREST')
                op.element = 'FACE'
                op.target = p.snap_surface_preset_target
                op.align_rotation = True

            else:
                op = pie.operator('machin3.set_snapping_preset', text='Surface', depress=False, icon='SNAP_FACE')
                op.element = 'FACE'
                op.target = p.snap_surface_preset_target
                op.align_rotation = True

        else:
            is_surface = 'FACE' in ts.snap_elements and ts.snap_target == p.snap_surface_preset_target and ts.use_snap_align_rotation

            op = pie.operator('machin3.set_snapping_preset', text='Surface', depress=is_surface, icon='SNAP_FACE')
            op.element = 'FACE'
            op.target = p.snap_surface_preset_target
            op.align_rotation = True

class PieCollections(Menu):
    bl_idname = "MACHIN3_MT_collections_pie"
    bl_label = "Collections"

    def draw(self, context):
        sel = context.selected_objects

        if sel:
            collections = list(set(col for obj in sel for col in obj.users_collection if not (M3.get_addon("DECALmachine") and (col.DM.isdecaltypecol or col.DM.isdecalparentcol))))[:10]

            if M3.get_addon("DECALmachine"):
                decalparentcollections = list(set(col for obj in sel for col in obj.users_collection if col.DM.isdecalparentcol))[:10]

        else:
            if context.scene.collection.objects:
                collections = get_scene_collections_old(context.scene)[:9]
                collections.insert(0, context.scene.collection)

            else:
                collections = get_scene_collections_old(context.scene)[:10]

            if M3.get_addon("DECALmachine"):
                decalparentcollections = [col for col in get_scene_collections_old(context.scene, ignore_decals=False) if col.DM.isdecalparentcol][:10]

        if M3.get_addon("DECALmachine"):
            decalsname = ".Decals" if context.scene.DM.hide_decaltype_collections else "Decals"
            dcol = bpy.data.collections.get(decalsname)

        layout = self.layout
        pie = layout.menu_pie()

        if sel:
            pie.operator("machin3.remove_from_collection", text="Remove from", icon="REMOVE")

        else:
            pie.separator()

        if sel:
            pie.operator("object.link_to_collection", text="Add to", icon="ADD")

        else:
            pie.separator()

        if sel:
            pie.operator("object.move_to_collection", text="Move to", icon="ADD")

        else:
            pie.operator("machin3.create_collection", text="Create", icon="GROUP")

        if M3.get_addon("DECALmachine") and (decalparentcollections or dcol):

            if len(collections) <= 5 and len(decalparentcollections) <= 5:
                row = pie.split(factor=0.34)

            elif len(collections) > 5 and len(decalparentcollections) <= 5:
                row = pie.split(factor=0.25)
                row.scale_x = 0.8

            elif len(collections) <= 5 and len(decalparentcollections) > 5:
                row = pie.split(factor=0.25)
                row.scale_x = 0.8

            else:
                row = pie.split(factor=0.20)
                row.scale_x = 0.8

        else:
            if len(collections) <= 5:
                row = pie.split(factor=0.5)
                row.scale_x = 1.5

            elif len(collections) > 5:
                row = pie.split(factor=0.33)
                row.scale_x = 0.8

        column = row.column()

        box = column.box()
        self.draw_left_top_column(context, box)

        if M3.get_addon("DECALmachine") and (decalparentcollections or dcol):

            if len(collections) <= 5 and len(decalparentcollections) <= 5:
                r = row.split(factor=0.5)

            elif len(collections) > 5 and len(decalparentcollections) <= 5:
                r = row.split(factor=0.66)

            elif len(collections) <= 5 and len(decalparentcollections) > 5:
                r = row.split(factor=0.33)

            else:
                r = row.split(factor=0.5)

        else:
            r = row

        box = r.box()
        self.draw_center_column(context, sel, collections, box)

        if M3.get_addon("DECALmachine") and (decalparentcollections or dcol):
            column = r.column()

            if decalparentcollections:
                box = column.box()
                self.draw_right_top_column(context, sel, decalparentcollections, box)

            if dcol and dcol.DM.isdecaltypecol:
                box = column.box()
                self.draw_right_bottom_column(context, box)

        pie.separator()

        pie.separator()

        pie.separator()

        pie.separator()

    def draw_left_top_column(self, context, layout):
        column = layout.column()

        row = column.row()
        row.scale_y = 1.5
        row.operator("machin3.purge_collections", text="Purge", icon='MONKEY')

    def draw_center_column(self, context, sel, collections, layout):
        if sel:
            layout.label(text="Scene Collections (Selection)")

        else:
            layout.label(text="Scene Collections")

        if len(collections) <= 5:
            column = layout.column(align=True)

            for col in collections:
                row = column.row(align=True)

                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")

                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™") and col != context.scene.collection:
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

        else:
            layout.scale_x = 2

            cols1 = collections[:5]
            cols2 = collections[5:10]

            split = layout.split(factor=0.5)
            column = split.column(align=True)

            for col in cols1:
                row = column.row(align=True)
                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")

                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™"):
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

            column = split.column(align=True)

            for col in cols2:
                row = column.row(align=True)
                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")
                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™"):
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

    def draw_right_top_column(self, context, sel, collections, layout):
        if sel:
            layout.label(text="Decal Parent Collections (Selection)")

        else:
            layout.label(text="Decal Parent Collections")

        if len(collections) <= 5:
            column = layout.column(align=True)

            for col in collections:
                row = column.row(align=True)

                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")

                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™"):
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

        else:
            layout.scale_x = 2

            cols1 = collections[:5]
            cols2 = collections[5:10]

            split = layout.split(factor=0.5)
            column = split.column(align=True)

            for col in cols1:
                row = column.row(align=True)
                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")

                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™"):
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

            column = split.column(align=True)

            for col in cols2:
                row = column.row(align=True)
                if col.children or col.objects:
                    icon = "RESTRICT_SELECT_ON" if col.objects and col.objects[0].hide_select else "RESTRICT_SELECT_OFF"
                    row.operator("machin3.select_collection", text=col.name, icon=icon).name = col.name
                    row.prop(col, "hide_viewport", text="", icon="HIDE_OFF")
                else:
                    row.label(text=col.name)

                if M3.get_addon("Batch Operations™"):
                    row.operator("batch_ops_collections.contextual_click", text="", icon="GROUP").idname = col.name

    def draw_right_bottom_column(self, context, layout):
        layout.label(text="Decal Type Collections")

        row = layout.row(align=True)

        decalsname = ".Decals" if context.scene.DM.hide_decaltype_collections else "Decals"
        simplename = ".Simple" if context.scene.DM.hide_decaltype_collections else "Simple"
        subsetname = ".Subset" if context.scene.DM.hide_decaltype_collections else "Subset"
        infoname = ".Info" if context.scene.DM.hide_decaltype_collections else "Info"
        panelname = ".Panel" if context.scene.DM.hide_decaltype_collections else "Panel"

        op = row.operator("machin3.select_collection", text="Decals")
        op.name = decalsname
        op.force_all = True

        decals = bpy.data.collections.get(decalsname)
        simple = bpy.data.collections.get(simplename)
        subset = bpy.data.collections.get(subsetname)
        info = bpy.data.collections.get(infoname)
        panel = bpy.data.collections.get(panelname)

        row.prop(decals, "hide_viewport", text="", icon="HIDE_OFF")

        if simple and simple.DM.isdecaltypecol and simple.objects:
            row.operator("machin3.select_collection", text="Simple").name = simplename
            row.prop(simple, "hide_viewport", text="", icon="HIDE_OFF")
        else:
            row.label(text="Simple")

        if subset and subset.DM.isdecaltypecol and subset.objects:
            row.operator("machin3.select_collection", text="Subset").name = subsetname
            row.prop(subset, "hide_viewport", text="", icon="HIDE_OFF")
        else:
            row.label(text="Subset")

        if panel and panel.DM.isdecaltypecol and panel.objects:
            row.operator("machin3.select_collection", text="Panel").name = panelname
            row.prop(panel, "hide_viewport", text="", icon="HIDE_OFF")
        else:
            row.label(text="Panel")

        if info and info.DM.isdecaltypecol and info.objects:
            row.operator("machin3.select_collection", text="Info").name = infoname
            row.prop(info, "hide_viewport", text="", icon="HIDE_OFF")
        else:
            row.label(text="Info")

class PieWorkspace(Menu):
    bl_idname = "MACHIN3_MT_workspace_pie"
    bl_label = "Workspaces"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        p = get_prefs()

        for piedir in ['left', 'right', 'bottom', 'top', 'top_left', 'top_right', 'bottom_left', 'bottom_right']:
            name = getattr(p, f'pie_workspace_{piedir}_name')
            text = getattr(p, f'pie_workspace_{piedir}_text')
            icon = getattr(p, f'pie_workspace_{piedir}_icon')

            if name:
                pie.operator("machin3.switch_workspace", text=text if text else name, icon=icon if icon else 'BLENDER').name=name

            else:
                pie.separator()

class PieTools(Menu):
    bl_idname = "MACHIN3_MT_tools_pie"
    bl_label = "Tools"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        m3 = context.scene.M3
        ts = context.scene.tool_settings

        tools = get_tools_from_context(context)

        active = context.active_object

        active_tool = get_active_tool(context).idname

        annotate_layer = context.active_annotation_layer

        is_annotate = active_tool in ['builtin.annotate', 'builtin.annotate_line', 'builtin.annotate_eraser']

        is_grease_pencil = active and active.type in ['GPENCIL', 'GREASEPENCIL']

        hops_tool_name = 'Hops' if (hops := M3.get_addon('Hard Ops 9')) and context.mode == 'OBJECT' else 'Hopsedit' if hops and context.mode == 'EDIT_MESH' else None
        bc_tool_name = M3.addons["boxcutter"]['foldername'] if M3.get_addon('BoxCutter') else None

        show_hardops = M3.get_addon("Hard Ops 9") and get_prefs().tools_show_hardops and hops_tool_name in tools and not (is_annotate and is_grease_pencil)
        show_boxcutter = M3.get_addon("BoxCutter") and get_prefs().tools_show_boxcutter and bc_tool_name in tools

        show_hardops_menu = show_hardops and get_prefs().tools_show_hardops_menu and not is_annotate and not is_grease_pencil
        show_boxcutter_presets = show_boxcutter and get_prefs().tools_show_boxcutter_presets

        modes = ['OBJECT', 'EDIT_MESH']

        if is_grease_pencil:
            if bpy.app.version < (4, 3, 0):
                modes.extend(["EDIT_GPENCIL", "PAINT_GPENCIL", "SCULPT_GPENCIL"])

            else:
                modes.extend(["EDIT_GREASE_PENCIL", "PAINT_GREASE_PENCIL", "SCULPT_GREASE_PENCIL"])

        if context.mode in modes:

            if is_grease_pencil and context.mode in ["PAINT_GPENCIL", "PAINT_GREASE_PENCIL"]:
                name = "builtin_brush.Draw" if bpy.app.version < (4, 3, 0) else "builtin.brush"
                tool = tools[name]

                pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = name

            elif show_boxcutter:
                tool = tools[bc_tool_name]
                pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = bc_tool_name

            else:
                pie.separator()

            if is_grease_pencil and context.mode in ["PAINT_GPENCIL", "PAINT_GREASE_PENCIL"]:
                name = "builtin.line"
                tool = tools[name]

                pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = name

            elif show_hardops:
                tool = tools[hops_tool_name]
                pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = hops_tool_name
            else:
                pie.separator()

            if is_grease_pencil and context.mode in ["PAINT_GPENCIL", "PAINT_GREASE_PENCIL"]:
                name = "builtin_brush.Erase"
                tool = tools[name]

                pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = name

            elif get_prefs().tools_show_annotate or (get_prefs().tools_show_surfacedraw and context.mode == 'OBJECT'):
                col = pie.column(align=True)
                col.scale_y = 1.5

                if get_prefs().tools_show_annotate:
                    if all(tool in tools for tool in ['builtin.annotate', 'builtin.annotate_line', 'builtin.annotate_eraser']):

                        row = col.row(align=True)
                        tool = tools['builtin.annotate']
                        row.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name = 'builtin.annotate'

                        tool = tools['builtin.annotate_line']
                        row.operator("machin3.set_tool_by_name", text="   " + "Line", depress=tool['active'], icon_value=tool['icon_value']).name = 'builtin.annotate_line'

                        split = col.split(factor=0.5, align=True)
                        tool = tools['builtin.annotate_eraser']
                        split.operator("machin3.set_tool_by_name", text="   " + "Erase", depress=tool['active'], icon_value=tool['icon_value']).name = 'builtin.annotate_eraser'

                        split.operator("machin3.annotate", text="Note", icon="OUTLINER_OB_FONT")

                        if bpy.app.version < (4, 3, 0):
                            is_visible = any(not layer.hide for layer in context.annotation_data.layers) if context.annotation_data else False

                            if context.annotation_data:
                                row = col.row(align=True)
                                row.scale_y = 0.75
                                action, icon = ('Hide', 'HIDE_OFF') if is_visible else ('Show', 'HIDE_ON')
                                row.operator("machin3.toggle_annotation", text=f"{action} Annotations", icon=icon)

                        else:
                            is_annotation_visible = any(not layer.annotation_hide for layer in context.annotation_data.layers) if context.annotation_data else False

                            note_gps = [obj for obj in context.visible_objects if obj.type == 'GREASEPENCIL' and 'Annotation' in obj.name]
                            is_gp_visible = any([not layer.hide for obj in note_gps for layer in obj.data.layers])

                            is_visible = is_annotation_visible or is_gp_visible

                            if context.annotation_data or note_gps:
                                row = col.row(align=True)
                                row.scale_y = 0.75
                                action, icon = ('Hide', 'HIDE_OFF') if is_visible else ('Show', 'HIDE_ON')
                                row.operator("machin3.toggle_annotation", text=f"{action} Annotations", icon=icon)

                if get_prefs().tools_show_surfacedraw and context.mode == 'OBJECT':
                    col.separator()
                    col.operator("machin3.surface_draw", text="Surface Draw", icon='GREASEPENCIL')

            else:
                pie.separator()

            if 'builtin.select_box' in tools:
                if M3.get_addon("HyperCursor") and context.mode in ['OBJECT', 'EDIT_MESH']:
                    if 'machin3.tool_hyper_cursor' in active_tool:
                        name = 'builtin.select_box'

                    else:
                        name = 'machin3.tool_hyper_cursor'

                    tool = tools[name]
                    pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name=name

                else:
                    tool = tools['builtin.select_box']
                    pie.operator("machin3.set_tool_by_name", text="   " + tool['label'], depress=tool['active'], icon_value=tool['icon_value']).name='builtin.select_box'

            else:
                pie.separator()

            if get_prefs().tools_show_quick_favorites:
                action = '(F) Quick Favorites' if show_hardops_menu else 'Quick Favorites'
                pie.operator("wm.call_menu", text=action).name="SCREEN_MT_user_menu"
            else:
                pie.separator()

            if get_prefs().tools_show_tool_bar:
                pie.operator("wm.toolbar", text="Tool Bar")
            else:
                pie.separator()

            if show_boxcutter_presets:
                box = pie.split()

                column = box.column(align=True)
                column.separator(factor=6)

                split = column.split(factor=0.9, align=True)
                row = split.split(factor=0.25, align=True)
                row.scale_y = 1.25
                row.label(text='Box')
                op = row.operator('machin3.set_boxcutter_preset', text='Add')
                op.shape_type = 'BOX'
                op.mode = 'MAKE'
                op.set_origin = 'BBOX'
                op = row.operator('machin3.set_boxcutter_preset', text='Cut')
                op.shape_type = 'BOX'
                op.mode = 'CUT'

                split.separator()

                split = column.split(factor=0.9, align=True)
                row = split.split(factor=0.25, align=True)
                row.scale_y = 1.25
                row.label(text='Circle')
                op = row.operator('machin3.set_boxcutter_preset', text='Add')
                op.shape_type = 'CIRCLE'
                op.mode = 'MAKE'
                op.set_origin = 'BBOX'
                op = row.operator('machin3.set_boxcutter_preset', text='Cut')
                op.shape_type = 'CIRCLE'
                op.mode = 'CUT'

                split.separator()

                split = column.split(factor=0.9, align=True)
                row = split.split(factor=0.25, align=True)
                row.scale_y = 1.25
                row.label(text='NGon')
                op = row.operator('machin3.set_boxcutter_preset', text='Add')
                op.shape_type = 'NGON'
                op.mode = 'MAKE'
                op.set_origin = 'BBOX'
                op = row.operator('machin3.set_boxcutter_preset', text='Cut')
                op.shape_type = 'NGON'
                op.mode = 'CUT'
                split.separator()

                column.separator()

                split = column.split(factor=0.9, align=True)
                row = split.row(align=True)
                row.prop(m3, 'bcorientation', expand=True)
                split.separator()

                column.separator()

                split = column.split(factor=0.9, align=True)
                row = split.row(align=True)
                row.scale_y = 1.25
                row.operator('bc.smart_apply', icon='IMPORT')
                split.separator()

            else:
                pie.separator()

            if is_grease_pencil:
                column = self.draw_grease_pencil_extra(context, active, active_tool, ts, pie)

                if is_annotate:
                    column.separator()

                    self.draw_annotation_extras(context, active_tool, annotate_layer, ts, column)

            elif is_annotate:
                column = pie.column(align=True)

                self.draw_annotation_extras(context, active_tool, annotate_layer, ts, column)

            elif show_hardops_menu:
                icon = M3.addons["hard ops 9"]['module'].icons.get('sm_logo_white')
                pie.operator("wm.call_menu", text="(Q) Menu", icon_value=icon.icon_id).name="HOPS_MT_MainMenu"

            else:
                pie.separator()

    def draw_annotation_extras(self, context, active_tool, annotate_layer, tool_settings, layout):
        layout.scale_x = 1.2

        split = layout.split(factor=0.1, align=True)
        split.scale_y = 1.2
        split.separator()

        if active_tool in ['builtin.annotate', 'builtin.annotate_line']:
            split.prop(tool_settings, 'annotation_stroke_placement_view3d', expand=True)

        elif active_tool == 'builtin.annotate_eraser':
            split.prop(context.preferences.edit, "grease_pencil_eraser_radius", text="Radius")

        split = layout.split(factor=0.1, align=True)
        split.separator()

        s = split.split(factor=0.33, align=True)
        s.alignment = 'RIGHT'
        s.label(text="Layer:")

        col = s.column(align=True)
        row = col.row(align=True)

        if annotate_layer is None:
            data_owner = context.annotation_data_owner

            if context.annotation_data_owner is None:
                row.label(text="No annotation source")
                return

            row.template_ID(data_owner, "grease_pencil", new="gpencil.annotation_add", unlink="gpencil.data_unlink")

        else:
            row.popover(panel="TOPBAR_PT_annotation_layers", text=annotate_layer.info)

    def draw_grease_pencil_extra(self, context, active, tool, toolsettings, pie):
        box = pie.split()
        column = box.column(align=True)

        if tool == 'builtin.line':
            split = column.split(factor=0.1, align=True)
            split.separator()

            if bpy.app.version < (4, 3, 0):
                props = get_tool_options(context, 'builtin.line', "GPENCIL_OT_primitive_line")
            else:
                props = get_tool_options(context, 'builtin.line', "GREASE_PENCIL_OT_primitive_line")

            split.prop(props, "subdivision", text="Line Subdivision")

            column.separator()

        if context.mode in ['EDIT_GPENCIL', 'EDIT_GREASE_PENCIL']:
            split = column.split(factor=0.1, align=True)
            split.separator()

            if bpy.app.version < (4, 3, 0):
                split.operator("gpencil.stroke_simplify")

            else:
                split.operator("grease_pencil.stroke_simplify")

            column.separator()

        split = column.split(factor=0.1, align=True)
        split.scale_y = 1.5
        split.separator()

        row = split.row(align=True)
        row.operator('machin3.shrinkwrap_grease_pencil', text='Shrinkwrap')

        if bpy.app.version < (4, 3, 0):
            row.prop(active.data, "zdepth_offset", text='')

        else:
            row.prop(toolsettings, "gpencil_surface_offset", text='')

        if bpy.app.version < (4, 3, 0):
            opacity = [mod for mod in active.grease_pencil_modifiers if mod.type == 'GP_OPACITY']
            thickness = [mod for mod in active.grease_pencil_modifiers if mod.type == 'GP_THICK']

        else:
            opacity = [mod for mod in active.modifiers if mod.type == 'GREASE_PENCIL_OPACITY']
            thickness = [mod for mod in active.modifiers if mod.type == 'GREASE_PENCIL_THICKNESS']

        if opacity:
            split = column.split(factor=0.1, align=True)
            split.separator()

            row = split.row(align=True)

            factor = 'factor' if bpy.app.version < (4, 3, 0) else 'color_factor'
            row.prop(opacity[0], factor, text='Opacity')

        if thickness:
            split = column.split(factor=0.1, align=True)
            split.separator()

            row = split.row(align=True)
            row.prop(thickness[0], 'thickness_factor', text='Thickness')

        column.separator()

        split = column.split(factor=0.1, align=True)
        split.separator()

        row = split.row(align=True)
        row.popover(panel="MACHIN3_PT_grease_pencil_extras", text="Grease Pencil Layers")

        if active.type == 'GREASEPENCIL' and '_Annotation' in active.name:
            gpd = active.data
            layer = gpd.layers.active

            if layer:
                column.separator()

                split = column.split(factor=0.1, align=True)
                split.separator()

                s = split.split(factor=0.33, align=True)
                s.alignment = 'RIGHT'
                s.label(text="Color:")

                s.prop(layer, "tint_color", text="")

        return column
