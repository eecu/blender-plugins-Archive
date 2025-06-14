import bpy
from bpy.props import IntProperty, StringProperty, BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty

import os
import shutil

from . utils.draw import draw_split_row, draw_empty_split_row
from . utils.registration import activate, get_path, get_name
from . utils.system import get_bl_info_from_file, remove_folder, get_update_files
from . utils.ui import draw_keymap_item, find_kmi_from_idname, get_icon, draw_keymap_items, get_keymap_item, get_panel_fold, get_user_keymap_items

from . items import preferences_tabs, matcap_background_type_items, snap_target_items, quadsphere_unwrap_items
from . registration import keys

from . import bl_info
from . import MACHIN3toolsManager as M3

has_sidebar = [
    'OT_smart_drive',
    'OT_group',
    'OT_create_assembly_asset',
    'OT_prepare_unity_export',
    'OT_cursor_spin',               # NOTE: cursor spin instead of punch_it bc cursor spin exists in both variants
]

has_hud = [
    'MT_tools_pie',

    'OT_align_relative',
    'OT_clean_up',
    'OT_clipping_toggle',
    'OT_focus',
    'OT_group',
    'OT_material_picker',
    'OT_mirror',
    'OT_punch_it',                  # NOTE: but then only the full Punch It has a HUD (unlike PunchIt A Little), NOTE: DeuxEx-only
    'OT_select_hierarchy',
    'OT_smart_vert',
    'OT_smart_face',
    'OT_surface_slide',
    'OT_transform_edge_constrained'
]

hud_shadow_items = [
    ('0', '0', "Don't Blur Shadow"),
    ('3', '3', 'Shadow Blur Level 3'),
    ('5', '5', 'Shadow Blur level 5')
]

has_fading_hud = [
    'MT_tools_pie'

    'OT_clean_up',
    'OT_clipping_toggle',
    'OT_group',
    'OT_select_hierarchy'
]

has_pie_settings = [
    'MT_cursor_pie',
    'MT_modes_pie',
    'MT_save_pie',
    'MT_shading_pie',
    'MT_snapping_pie',
    'MT_tools_pie',
    'MT_viewport_pie',
    'MT_workspace_pie',
]

has_tool_settings = [
    'OT_smart_face',
    'OT_create_assembly_asset',
    'OT_cursor_spin',               # NOTE: cursor spin instead of punch_it bc cursor spin exists in both variant, used to expose the native Extrude menu keymap
    'OT_customize',
    'OT_focus',
    'OT_group',
    'OT_material_picker',
    'OT_render',
    'OT_toggle_view3d_region',
]

has_settings = set(has_sidebar + has_hud + has_pie_settings + has_tool_settings)

has_skribe = None

class MACHIN3toolsPreferences(bpy.types.AddonPreferences):
    path = get_path()
    bl_idname = get_name()

    def update_update_path(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.update_path:
            if os.path.exists(self.update_path):
                filename = os.path.basename(self.update_path)

                if filename.endswith('.zip'):
                    split = filename.split('_')

                    if len(split) == 2:
                        addon_name, tail = split

                        if addon_name == bl_info['name']:
                            split = tail.split('.')

                            if len(split) >= 3:
                                dst = os.path.join(self.path, '_update')

                                from zipfile import ZipFile

                                with ZipFile(self.update_path, mode="r") as z:
                                    print(f"INFO: extracting {addon_name} update to {dst}")
                                    z.extractall(path=dst)

                                blinfo = get_bl_info_from_file(os.path.join(dst, addon_name, '__init__.py'))

                                if blinfo:
                                    self.update_msg = f"{blinfo['name']} {'.'.join(str(v) for v in blinfo['version'])} is ready to be installed."

                                else:
                                    remove_folder(dst)

            self.avoid_update = True
            self.update_path = ''

    update_path: StringProperty(name="Update File Path", subtype="FILE_PATH", update=update_update_path)
    update_msg: StringProperty(name="Update Message")

    registration_debug: BoolProperty(name="Addon Terminal Registration Output", default=True)

    def update_switchmatcap1(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        matcaps = [mc.name for mc in context.preferences.studio_lights if os.path.basename(os.path.dirname(mc.path)) == "matcap"]
        if self.switchmatcap1 not in matcaps:
            self.avoid_update = True
            self.switchmatcap1 = "NOT FOUND"

    def update_switchmatcap2(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        matcaps = [mc.name for mc in context.preferences.studio_lights if os.path.basename(os.path.dirname(mc.path)) == "matcap"]
        if self.switchmatcap2 not in matcaps:
            self.avoid_update = True
            self.switchmatcap2 = "NOT FOUND"

    def update_auto_smooth_angle_presets(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        try:
            [int(a) for a in self.auto_smooth_angle_presets.split(',')]

        except:
            self.avoid_update = True
            self.auto_smooth_angle_presets = "10, 15, 20, 30, 60, 180"

    def update_activate_smart_vert(self, context):
        activate(self, register=self.activate_smart_vert, tool="smart_vert")

    def update_activate_smart_edge(self, context):
        activate(self, register=self.activate_smart_edge, tool="smart_edge")

    def update_activate_smart_face(self, context):
        activate(self, register=self.activate_smart_face, tool="smart_face")

    def update_activate_clean_up(self, context):
        activate(self, register=self.activate_clean_up, tool="clean_up")

    def update_activate_edge_constraint(self, context):
        activate(self, register=self.activate_edge_constraint, tool="edge_constraint")

    def update_activate_extrude(self, context):
        activate(self, register=self.activate_extrude, tool="extrude")

    def update_activate_focus(self, context):
        activate(self, register=self.activate_focus, tool="focus")

    def update_activate_mirror(self, context):
        activate(self, register=self.activate_mirror, tool="mirror")

    def update_activate_align(self, context):
        activate(self, register=self.activate_align, tool="align")

    def update_activate_group_tools(self, context):
        activate(self, register=self.activate_group_tools, tool="group")

    def update_activate_smart_drive(self, context):
        activate(self, register=self.activate_smart_drive, tool="smart_drive")

    def update_activate_assetbrowser_tools(self, context):
        activate(self, register=self.activate_assetbrowser_tools, tool="assetbrowser")

    def update_activate_filebrowser_tools(self, context):
        activate(self, register=self.activate_filebrowser_tools, tool="filebrowser")

    def update_activate_render(self, context):
        activate(self, register=self.activate_render, tool="render")

    def update_activate_smooth(self, context):
        activate(self, register=self.activate_smooth, tool="smooth")

    def update_activate_clipping_toggle(self, context):
        activate(self, register=self.activate_clipping_toggle, tool="clipping_toggle")

    def update_activate_surface_slide(self, context):
        activate(self, register=self.activate_surface_slide, tool="surface_slide")

    def update_activate_material_picker(self, context):
        activate(self, register=self.activate_material_picker, tool="material_picker")

    def update_activate_apply(self, context):
        activate(self, register=self.activate_apply, tool="apply")

    def update_activate_select(self, context):
        activate(self, register=self.activate_select, tool="select")

    def update_activate_mesh_cut(self, context):
        activate(self, register=self.activate_mesh_cut, tool="mesh_cut")

    def update_activate_region(self, context):
        activate(self, register=self.activate_region, tool="region")

    def update_activate_thread(self, context):
        activate(self, register=self.activate_thread, tool="thread")

    def update_activate_unity(self, context):
        activate(self, register=self.activate_unity, tool="unity")

    def update_activate_customize(self, context):
        activate(self, register=self.activate_customize, tool="customize")

    def update_activate_modes_pie(self, context):
        activate(self, register=self.activate_modes_pie, tool="modes_pie")

    def update_activate_save_pie(self, context):
        activate(self, register=self.activate_save_pie, tool="save_pie")

    def update_activate_shading_pie(self, context):
        activate(self, register=self.activate_shading_pie, tool="shading_pie")

    def update_activate_views_pie(self, context):
        activate(self, register=self.activate_views_pie, tool="views_pie")

    def update_activate_align_pie(self, context):
        activate(self, register=self.activate_align_pie, tool="align_pie")

    def update_activate_cursor_pie(self, context):
        activate(self, register=self.activate_cursor_pie, tool="cursor_pie")

    def update_activate_transform_pie(self, context):
        activate(self, register=self.activate_transform_pie, tool="transform_pie")

    def update_activate_snapping_pie(self, context):
        activate(self, register=self.activate_snapping_pie, tool="snapping_pie")

    def update_activate_collections_pie(self, context):
        activate(self, register=self.activate_collections_pie, tool="collections_pie")

    def update_activate_workspace_pie(self, context):
        activate(self, register=self.activate_workspace_pie, tool="workspace_pie")

    def update_activate_tools_pie(self, context):
        activate(self, register=self.activate_tools_pie, tool="tools_pie")

    def update_quadsphere_default(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if 'MACHIN3_OT_quadsphere' in M3.defaults:
            M3.defaults.remove('MACHIN3_OT_quadsphere')
    quadsphere_default_shade_smooth: BoolProperty(name="Shade Smooth", description="Default Shading of newly created Quadsphere", default=True, update=update_quadsphere_default)
    quadsphere_default_subdivisions: IntProperty(name="Subdivisions", description="Default Subdivisions of newly created Quadsphere", default=4, min=1, max=8, update=update_quadsphere_default)
    quadsphere_default_align_rotation: BoolProperty(name="Align Rotation", description="Default (Cursor) Alignment of newly created Quadsphere", default=True, update=update_quadsphere_default)
    quadsphere_default_unwrap: EnumProperty(name="Unwrap", description="Default Unwrapping Method of newly created Quadsphere", items=quadsphere_unwrap_items, default='CROSS', update=update_quadsphere_default)

    smart_face_use_topo_mode: BoolProperty(name="Smart Face Topo Mode", description="Immediately translate the newly created Vert, and only once finished or aborted prepare Selection for next Invocation", default=True)
    smart_face_topo_mode_face_snapping: BoolProperty(name="Only use use Topo Mode, when on Face Snapping is used", description="Check Face Snapping to determine whether the Tool should enter Topo Mode", default=False)
    smart_face_topo_mode_retopology_overlay: BoolProperty(name="Only use Topo Mode, when on Retopology Overlays are used", description="Check Retopology Overlays to determine whether the Tool should enter Topo Mode", default=True)

    focus_view_transition: BoolProperty(name="Viewport Tweening", default=True)
    focus_lights: BoolProperty(name="Ignore Lights (keep them always visible)", default=False)

    group_tools_auto_name: BoolProperty(name="Auto Name Groups", description="Automatically add a Prefix and/or Suffix to any user-given Group Name", default=True)
    group_tools_basename: StringProperty(name="Group Basename", default="GROUP")
    group_tools_prefix: StringProperty(name="Prefix to add to Group Names", default="_")
    group_tools_suffix: StringProperty(name="Suffix to add to Group Names", default="_grp")
    group_tools_size: FloatProperty(name="Group Empty Draw Size", description="Default Group Size", default=0.2)
    group_tools_fade_sizes: BoolProperty(name="Fade Group Empty Sizes", description="Make Sub Group's Emtpies smaller than their Parents", default=True)
    group_tools_fade_factor: FloatProperty(name="Fade Group Size Factor", description="Factor by which to decrease each Group Empty's Size", default=0.8, min=0.1, max=0.9)
    group_tools_remove_empty: BoolProperty(name="Remove Empty Groups", description="Automatically remove Empty Groups in each Cleanup Pass", default=True)
    group_tools_group_mode_disable_auto_select: BoolProperty(name="Group Mode: Disable Auto-Select", description="When switching into Group Mode in the Outliner, disable Auto-Select", default=True)
    group_tools_group_mode_disable_recursive_select: BoolProperty(name="Group Mode: Disable Recursive-Selections", description="When switching into Group Mode in the Outliner, disable Recursive-Selections", default=True)
    group_tools_group_mode_disable_group_hide: BoolProperty(name="Group Mode: Disable Group-Hiding", description="When switching into Group Mode in the Outliner, disable Group-Hiding", default=True)
    group_tools_group_mode_disable_group_gizmos: BoolProperty(name="Group Mode: Disable Group Gizmos", description="When switching into Group Mode in the Outliner, disable Group Gizmos", default=True)
    group_tools_group_mode_enable_group_draw_relations: BoolProperty(name="Group Mode: Draw Group Relations", description="When switching into Group Mode in the Outliner, draw Group Relations", default=True)
    group_tools_show_context_sub_menu: BoolProperty(name="Use Group Sub-Menu", default=False)
    group_tools_show_outliner_parenting_toggle: BoolProperty(name="Show Outliner Parenting Toggle", default=True)
    group_tools_show_outliner_group_selection_toggles: BoolProperty(name="Show Outliner Group Selection Toggles", default=True)
    group_tools_show_outliner_group_gizmos_toggle: BoolProperty(name="Show Outliner Group Gizmo Toggles", default=True)

    assetbrowser_tools_preferred_default_catalog: StringProperty(name="Preferred default catalog", default="Assembly")
    assetbrowser_tools_use_originals: BoolProperty(name="Allow using original objects, instead of creating copies", description="Duplication ensures the Asset Objects become fully independent, and the Objects in the initial Selection remain ontouched.\n\nDuplication supports Assembly Creaton from parts of a Hierarchy, and removal of potential Decal Backups and Stash Objects.\nDisabling Duplication forces Assembly Creation of the entire Hierarchy.", default=False)
    assetbrowser_tools_meta_author: StringProperty(name="Asset Author", default="MACHIN3")
    assetbrowser_tools_meta_copyright: StringProperty(name="Asset Copyright", default="")
    assetbrowser_tools_meta_license: StringProperty(name="Asset License", default="")
    assetbrowser_tools_show_assembly_creation_in_save_pie: BoolProperty(name="Show Assembly Asset Creation in Save Pie", default=True)

    toggle_region_prefer_left_right: BoolProperty(name="Prefer Left/Right over Bottom/Top", default=True)
    toggle_region_close_range: FloatProperty(name="Close Range", subtype='PERCENTAGE', default=30, min=1, max=50)
    toggle_region_assetshelf: BoolProperty(name="Toggle the Asset Shelf, instead of the Browser", default=True)
    toggle_region_assetbrowser_top: BoolProperty(name="Toggle the Asset Browser at the Top", default=True)
    toggle_region_assetbrowser_bottom: BoolProperty(name="Toggle the Asset Browser at the Bottom", default=True)
    toggle_region_warp_mouse_to_asset_border: BoolProperty(name="Warp Mouse to Asset Browser Border", default=False)

    render_folder_name: StringProperty(name="Render Folder Name", description="Folder used to stored rended images relative to the Location of the .blend file", default='out')
    render_seed_count: IntProperty(name="Seed Render Count", description="Set the Amount of Seed Renderings used to remove Fireflies", default=3, min=2, max=9)
    render_keep_seed_renderings: BoolProperty(name="Keep Individual Renderings", description="Keep the individual Seed Renderings, after they've been combined into a single Image", default=False)
    render_use_clownmatte_naming: BoolProperty(name="Use Clownmatte Name", description="""It's a better name than "Cryptomatte", believe me""", default=True)
    render_show_buttons_in_light_properties: BoolProperty(name="Show Render Buttons in Light Properties Panel", description="Show Render Buttons in Light Properties Panel", default=True)
    render_sync_light_visibility: BoolProperty(name="Sync Light visibility/renderability", description="Sync Light hide_render props based on hide_viewport props", default=True)
    render_adjust_lights_on_render: BoolProperty(name="Ajust Area Lights when Rendering in Cycles", description="Adjust Area Lights when Rendering, to better match Eevee and Cycles", default=True)
    render_enforce_hide_render: BoolProperty(name="Enforce hide_render setting when Viewport Rendering", description="Hide Objects based on their hide_render props, when Viewport Rendering with Cyclces", default=True)
    render_use_bevel_shader: BoolProperty(name="Automatically set up Bevel Shader when Cycles Rendering", description="Set up Bevel Shader on all visible Materials when Cycles Renderings", default=True)

    matpick_workspace_names: StringProperty(name="Workspaces the Material Picker should appear on", default="Shading, Material")
    matpick_shading_type_material: BoolProperty(name="Show Material Picker in all Material Shading Viewports", default=True)
    matpick_shading_type_render: BoolProperty(name="Show Material Picker in all Render Shading Viewports", default=False)
    matpick_spacing_obj: FloatProperty(name="Object Mode Spacing", min=0, default=20)
    matpick_spacing_edit: FloatProperty(name="Edit Mode Spacing", min=0, default=5)
    matpick_draw_in_top_level_context_menu: BoolProperty(name="Add Material Picker at Top Level in the Context Menu", description="Add Material Picker to Top Level in the the Context Menu, not in the MACHIN3tools Sub Menu", default=False)
    matpick_ignore_wire_objects: BoolProperty(name="Ignore Wire Objects", description="Ignore Wire Objects when picking Materials.\nNOTE: Can cause a slight lag on tool-invocation, if wire objects are mod objects of complex and slow-to-evaluate mod stacks", default=True)

    custom_startup: BoolProperty(name="Startup Scene", default=False)
    custom_theme: BoolProperty(name="Theme", default=True)
    custom_matcaps: BoolProperty(name="Matcaps", default=True)
    custom_shading: BoolProperty(name="Shading", default=False)
    custom_overlays: BoolProperty(name="Overlays", default=False)
    custom_outliner: BoolProperty(name="Outliner", default=False)
    custom_preferences_interface: BoolProperty(name="Preferences: Interface", default=False)
    custom_preferences_viewport: BoolProperty(name="Preferences: Viewport", default=False)
    custom_preferences_input_navigation: BoolProperty(name="Preferences: Input & Navigation", default=False)
    custom_preferences_keymap: BoolProperty(name="Preferences: Keymap", default=False)
    custom_preferences_system: BoolProperty(name="Preferences: System", default=False)
    custom_preferences_save: BoolProperty(name="Preferences: Save & Load", default=False)

    modes_pie_object_mode_top_show_edit: BoolProperty(name="Show Edit", description="In Object Mode show the Edit Mode Toggle on top", default=False)
    modes_pie_object_mode_top_show_sculpt: BoolProperty(name="Show Sculpt Mode Toggle", description="In Object Mode show the Sculpt Mode Toggle on top", default=True)
    modes_pie_object_mode_top_show_ungroup: BoolProperty(name="Show Ungroup", description="In Object Mode show Ungroup on top, if the active is a Group Empty", default=True)
    modes_pie_object_mode_top_show_select_group: BoolProperty(name="Show Select Group", description="In Object Mode show Select Ggroup on top, if the active is a Group Object", default=True)
    modes_pie_object_mode_top_show_create_group: BoolProperty(name="Show Group", description="In Object Mode with a Multi-Object Selecton, show the Group Tool on top", default=True)
    if True:
        object_mode_show_assembly_edit: BoolProperty(name="Show Assembly Edit", description="In Object Mode show Assembly Edit Button at the bottom, when Active as an Assembly", default=True)
        object_mode_show_assembly_edit_finish: BoolProperty(name="Show Assembly Edit Finish", description="In Object Mode when in Assembly Edit Mode, show Assembly Edit Finish Button on top", default=True)
    toggle_cavity: BoolProperty(name="Toggle Cavity/Curvature OFF in Edit Mode, ON in Object Mode", default=True)
    toggle_xray: BoolProperty(name="Toggle X-Ray ON in Edit Mode, OFF in Object Mode, if Pass Through or Wireframe was enabled in Edit Mode", default=True)
    sync_tools: BoolProperty(name="Sync Tool if possible, when switching Modes", default=True)

    save_pie_show_obj_export: BoolProperty(name="Show .obj Export", default=True)
    save_pie_show_plasticity_export: BoolProperty(name="Show Plasticity Export", default=True)
    save_pie_show_fbx_export: BoolProperty(name="Show .fbx Export", default=True)
    save_pie_show_better_fbx_export: BoolProperty(name="Show Better .fbx Export", default=False)
    save_pie_show_usd_export: BoolProperty(name="Show .usd Export", default=True)
    save_pie_show_stl_export: BoolProperty(name="Show .stl Export", default=False)
    save_pie_show_gltf_export: BoolProperty(name="Show .glTF Export", default=False)
    save_pie_obj_folder: StringProperty(name=".obj Folder", subtype='DIR_PATH', default='')
    save_pie_plasticity_folder: StringProperty(name=".plasticity Folder", subtype='DIR_PATH', default='')
    save_pie_fbx_folder: StringProperty(name=".fbx Folder", subtype='DIR_PATH', default='')
    save_pie_better_fbx_folder: StringProperty(name="Better .fbx Folder", subtype='DIR_PATH', default='')
    save_pie_usd_folder: StringProperty(name=".usd Folder", subtype='DIR_PATH', default='')
    save_pie_stl_folder: StringProperty(name=".stl Folder", subtype='DIR_PATH', default='')
    save_pie_gltf_folder: StringProperty(name=".glTF Folder", subtype='DIR_PATH', default='')
    fbx_export_apply_scale_all: BoolProperty(name="Use 'Fbx All' for Applying Scale", description="This is useful for Unity, but bad for Unreal Engine", default=False)
    show_screencast: BoolProperty(name="Show Screencast in Save Pie", description="Show Screencast in Save Pie", default=True)
    screencast_operator_count: IntProperty(name="Operator Count", description="Maximum number of Operators displayed when Screen Casting", default=12, min=1, max=100)
    screencast_fontsize: IntProperty(name="Font Size", default=12, min=2)
    screencast_highlight_machin3: BoolProperty(name="Highlight MACHIN3 operators", description="Highlight Operators from MACHIN3 addons", default=True)
    screencast_show_addon: BoolProperty(name="Display Operator's Addons", description="Display Operator's Addon", default=True)
    screencast_show_idname: BoolProperty(name="Display Operator's idnames", description="Display Operator's bl_idname", default=False)
    screencast_use_screencast_keys: BoolProperty(name="Use Screencast Keys (Extension, pereferred)", default=True)
    screencast_use_skribe: BoolProperty(name="Use SKRIBE (external)", default=True)
    screencast_use_ffmpeg_screenrecord: BoolProperty(name="Use ffmpeg for Screen Recording", description="Use ffmpeg for Screen Recording", default=False)
    save_pie_use_undo_save: BoolProperty(name="Make Pre-Undo Saving available in the Pie", default=False)

    overlay_solid: BoolProperty(name="Show Overlays in Solid Shading by default", description="For a newly created scene, or a .blend file where where it wasn't set before, show Overlays for Solid shaded 3D views", default=True)
    overlay_material: BoolProperty(name="Show Overlays in Material Shading by default", description="For a newly created scene, or a .blend file where where it wasn't set before, show Overlays for Material shaded 3D views", default=False)
    overlay_rendered: BoolProperty(name="Show Overlays in Rendered Shading by default", description="For a newly created scene, or a .blend file where where it wasn't set before, show Overlays for Rendered shaded 3D views", default=False)
    overlay_wire: BoolProperty(name="Show Overlays in Wire Shading by default", description="For a newly created scene, or a .blend file where where it wasn't set before, show Overlays for Wire shaded 3D views", default=True)
    switchmatcap1: StringProperty(name="Matcap 1", update=update_switchmatcap1)
    switchmatcap2: StringProperty(name="Matcap 2", update=update_switchmatcap2)
    matcap2_force_single: BoolProperty(name="Force Single Color Shading for Matcap 2", default=True)
    matcap2_disable_overlays: BoolProperty(name="Disable Overlays for Matcap 2", default=True)
    matcap_switch_background: BoolProperty(name="Switch Background too", default=False)
    matcap1_switch_background_type: EnumProperty(name="Matcap 1 Background Type", items=matcap_background_type_items, default="THEME")
    matcap1_switch_background_viewport_color: FloatVectorProperty(name="Matcap 1 Background Color", subtype='COLOR', default=[0.05, 0.05, 0.05], size=3, min=0, max=1)
    matcap2_switch_background_type: EnumProperty(name="Matcap 2 Background Type", items=matcap_background_type_items, default="THEME")
    matcap2_switch_background_viewport_color: FloatVectorProperty(name="Matcap 2 Background Color", subtype='COLOR', default=[0.05, 0.05, 0.05], size=3, min=0, max=1)
    auto_smooth_angle_presets: StringProperty(name="Autosmooth Angle Preset", default="10, 15, 20, 30, 60, 180", update=update_auto_smooth_angle_presets)
    auto_smooth_show_expanded: BoolProperty(name="Show Autosmooth Mod Expanded", default=False)

    obj_mode_rotate_around_active: BoolProperty(name="Rotate Around Selection, but only in Object Mode", default=False)
    custom_views_use_trackball: BoolProperty(name="Force Trackball Navigation when using Custom Views", default=True)
    custom_views_set_transform_preset: BoolProperty(name="Set Transform Preset when using Custom Views", default=False)
    show_orbit_selection: BoolProperty(name="Show Orbit around Active", default=True)
    show_orbit_method: BoolProperty(name="Show Orbit Method Selection", default=True)
    smart_cam_perfectly_match_viewport: BoolProperty(name="Match Resolution and Camera Lens to Viewport", description="Adjust Render Resulution ratio, to match the 3D View's region width/height ratio. Also sync the Camera Lens to the 3D View's Lens and set the Camera Sensor Width to 72, all of which creates a perfectly matching Camera View", default=True)

    cursor_show_to_grid: BoolProperty(name="Show Cursor and Selected to Grid", default=False)
    cursor_set_transform_preset: BoolProperty(name="Set Transform Preset when Setting Cursor", default=False)
    cursor_ensure_visibility: BoolProperty(name="Ensure Cursor Visibility", description="Ensure Cursor Visibility when setting Cursor to Origin or Selection", default=True)

    snap_vert_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='CLOSEST')
    snap_edge_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='CLOSEST')
    snap_surface_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='MEDIAN')
    snap_face_nearest_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='MEDIAN')
    snap_volume_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='CLOSEST')
    snap_grid_preset_target: EnumProperty(name="Vert Snapping Preset's Target", items=snap_target_items, default='ACTIVE')
    snap_show_absolute_grid: BoolProperty(name="Show Absolute Grid Snapping", default=True)
    snap_show_volume: BoolProperty(name="Show Volume Snapping", default=False)
    snap_toggle_face_nearest: BoolProperty(name="Toggle Nearest when Face Snapping already and calling it again", default=True)
    snap_draw_HUD: BoolProperty(name="Draw Fading HUD", default=True)

    pie_workspace_left_name: StringProperty(name="Left Workspace Name", default="Layout")
    pie_workspace_left_text: StringProperty(name="Left Workspace Custom Label", default="MACHIN3")
    pie_workspace_left_icon: StringProperty(name="Left Workspace Icon", default="VIEW3D")
    pie_workspace_top_left_name: StringProperty(name="Top-Left Workspace Name", default="UV Editing")
    pie_workspace_top_left_text: StringProperty(name="Top-Left Workspace Custom Label", default="UVs")
    pie_workspace_top_left_icon: StringProperty(name="Top-Left Workspace Icon", default="GROUP_UVS")
    pie_workspace_top_name: StringProperty(name="Top Workspace Name", default="Shading")
    pie_workspace_top_text: StringProperty(name="Top Workspace Custom Label", default="Materials")
    pie_workspace_top_icon: StringProperty(name="Top Workspace Icon", default="MATERIAL_DATA")
    pie_workspace_top_right_name: StringProperty(name="Top-Right Workspace Name", default="")
    pie_workspace_top_right_text: StringProperty(name="Top-Right Workspace Custom Label", default="")
    pie_workspace_top_right_icon: StringProperty(name="Top-Right Workspace Icon", default="")
    pie_workspace_right_name: StringProperty(name="Right Workspace Name", default="Rendering")
    pie_workspace_right_text: StringProperty(name="Right Workspace Custom Label", default="")
    pie_workspace_right_icon: StringProperty(name="Right Workspace Icon", default="")
    pie_workspace_bottom_right_name: StringProperty(name="Bottom-Right Workspace Name", default="")
    pie_workspace_bottom_right_text: StringProperty(name="Bottom-Right Workspace Custom Label", default="")
    pie_workspace_bottom_right_icon: StringProperty(name="Bottom-Right Workspace Icon", default="")
    pie_workspace_bottom_name: StringProperty(name="Bottom Workspace Name", default="Scripting")
    pie_workspace_bottom_text: StringProperty(name="Bottom Workspace Custom Label", default="")
    pie_workspace_bottom_icon: StringProperty(name="Bottom Workspace Icon", default="CONSOLE")
    pie_workspace_bottom_left_name: StringProperty(name="Bottom-Left Workspace Name", default="Geo Nodes")
    pie_workspace_bottom_left_text: StringProperty(name="Bottom-Left Workspace Custom Label", default="GeoNodes")
    pie_workspace_bottom_left_icon: StringProperty(name="Bottom-Left Workspace Icon", default="GEOMETRY_NODES")

    tools_show_hardops: BoolProperty(name="Show Hard Ops Tool", default=True)
    tools_show_hardops_menu: BoolProperty(name="Show Hard Ops Menu", default=True)
    tools_show_boxcutter: BoolProperty(name="Show BoxCutter Tool", default=True)
    tools_show_boxcutter_presets: BoolProperty(name="Show BoxCutter Presets", default=True)
    tools_show_quick_favorites: BoolProperty(name="Show Quick Favorites", default=False)
    tools_show_tool_bar: BoolProperty(name="Show Tool Bar", default=False)
    tools_show_annotate: BoolProperty(name="Show Annotate", description="Show Annotation Tools", default=True)
    tools_show_surfacedraw: BoolProperty(name="Show Surface Draw", description="Show GreasePencil Surface Draw Tool", default=False)

    activate_smart_vert: BoolProperty(name="Smart Vert", default=False, update=update_activate_smart_vert)
    activate_smart_edge: BoolProperty(name="Smart Edge", default=False, update=update_activate_smart_edge)
    activate_smart_face: BoolProperty(name="Smart Face", default=False, update=update_activate_smart_face)
    activate_clean_up: BoolProperty(name="Clean Up", default=False, update=update_activate_clean_up)
    activate_edge_constraint: BoolProperty(name="Edge Constraint", default=True, update=update_activate_edge_constraint)
    activate_extrude: BoolProperty(name="Extrude", default=True, update=update_activate_extrude)
    activate_focus: BoolProperty(name="Focus", default=True, update=update_activate_focus)
    activate_mirror: BoolProperty(name="Mirror", default=False, update=update_activate_mirror)
    activate_align: BoolProperty(name="Align", default=False, update=update_activate_align)
    activate_group_tools: BoolProperty(name="Group Tools", default=True, update=update_activate_group_tools)
    activate_smart_drive: BoolProperty(name="Smart Drive", default=False, update=update_activate_smart_drive)
    activate_filebrowser_tools: BoolProperty(name="File Browser Tools", default=False, update=update_activate_filebrowser_tools)
    activate_assetbrowser_tools: BoolProperty(name="Asset Browser Tools", default=True, update=update_activate_assetbrowser_tools)
    activate_region: BoolProperty(name="Toggle Region", default=False, update=update_activate_region)
    activate_render: BoolProperty(name="Render", default=False, update=update_activate_render)
    activate_smooth: BoolProperty(name="Smooth", default=False, update=update_activate_smooth)
    activate_clipping_toggle: BoolProperty(name="Clipping Toggle", default=False, update=update_activate_clipping_toggle)
    activate_surface_slide: BoolProperty(name="Surface Slide", default=False, update=update_activate_surface_slide)
    activate_material_picker: BoolProperty(name="Material Picker", default=False, update=update_activate_material_picker)
    activate_apply: BoolProperty(name="Apply Transform", default=False, update=update_activate_apply)
    activate_select: BoolProperty(name="Select", default=False, update=update_activate_select)
    activate_mesh_cut: BoolProperty(name="Mesh Cut", default=False, update=update_activate_mesh_cut)
    activate_thread: BoolProperty(name="Thread", default=False, update=update_activate_thread)
    activate_unity: BoolProperty(name="Unity", default=False, update=update_activate_unity)
    activate_customize: BoolProperty(name="Customize", default=False, update=update_activate_customize)

    activate_modes_pie: BoolProperty(name="Modes Pie", default=True, update=update_activate_modes_pie)
    activate_save_pie: BoolProperty(name="Save Pie", default=False, update=update_activate_save_pie)
    activate_shading_pie: BoolProperty(name="Shading Pie", default=False, update=update_activate_shading_pie)
    activate_views_pie: BoolProperty(name="Views Pie", default=False, update=update_activate_views_pie)
    activate_align_pie: BoolProperty(name="Align Pies", default=False, update=update_activate_align_pie)
    activate_cursor_pie: BoolProperty(name="Cursor and Origin Pie", default=False, update=update_activate_cursor_pie)
    activate_transform_pie: BoolProperty(name="Transform Pie", default=False, update=update_activate_transform_pie)
    activate_snapping_pie: BoolProperty(name="Snapping Pie", default=False, update=update_activate_snapping_pie)
    activate_collections_pie: BoolProperty(name="Collections Pie", default=False, update=update_activate_collections_pie)
    activate_workspace_pie: BoolProperty(name="Workspace Pie", default=False, update=update_activate_workspace_pie)
    activate_tools_pie: BoolProperty(name="Tools Pie", default=False, update=update_activate_tools_pie)

    show_sidebar_panel: BoolProperty(name="Show Sidebar Panel", description="Show MACHIN3tools Panel in 3D View's Sidebar", default=True)
    show_help_in_sidebar_panel: BoolProperty(name="Show Help and Documentation Panels in Sidebar", description="Show Support and Documentation panels in MACHIN3tools Sidebar Panel", default=True)

    modal_hud_scale: FloatProperty(name="HUD Scale", description="Scale of HUD elements", default=1, min=0.1)
    modal_hud_timeout: FloatProperty(name="HUD timeout", description="Global Timeout Modulation (not exposed in MACHIN3tools)", default=1, min=0.1)
    modal_hud_shadow: BoolProperty(name="HUD Shadow", description="HUD Shadow", default=False)
    modal_hud_shadow_blur: EnumProperty(name="HUD Shadow Blur", items=hud_shadow_items, default='3')
    modal_hud_shadow_offset: IntProperty(name="HUD Shadow Offset", default=1, min=0)
    HUD_fade_clean_up: FloatProperty(name="Clean Up HUD Fade Time (seconds)", default=1, min=0.1)
    HUD_fade_select_hierarchy: FloatProperty(name="Select Hierarchy HUD Fade Time (seconds)", default=1.5, min=0.1)
    HUD_fade_clipping_toggle: FloatProperty(name="Clipping Toggle HUD Fade Time (seconds)", default=1, min=0.1)
    HUD_fade_group: FloatProperty(name="Group HUD Fade Time (seconds)", default=1, min=0.1)
    HUD_fade_tools_pie: FloatProperty(name="Tools Pie HUD Fade Time (seconds)", default=0.75, min=0.1)
    mirror_flick_distance: IntProperty(name="Flick Distance", default=75, min=20, max=1000)

    update_available: BoolProperty(name="Update is available", default=False)

    def update_show_update(self, context):
        if self.show_update:
            get_update_files(force=True)

    tabs: EnumProperty(name="Tabs", items=preferences_tabs, default="GENERAL")
    show_update: BoolProperty(default=False, update=update_show_update)
    avoid_update: BoolProperty(default=False)
    dirty_keymaps: BoolProperty(default=False)
    def draw(self, context):
        layout = self.layout

        column = layout.column(align=True)

        self.draw_update(column)

        self.draw_support(column)

        column = layout.column(align=True)

        row = column.row()
        row.prop(self, "tabs", expand=True)

        box = column.box()

        if self.tabs == "GENERAL":
            self.draw_general(context, box)

        elif self.tabs == "KEYMAPS":
            self.draw_keymaps(context, box)

        elif self.tabs == "ABOUT":
            self.draw_about(box)

    def draw_update(self, layout):

        if self.update_available:
            row = layout.row()
            row.scale_y = 1.2
            row.alignment = "CENTER"
            row.label(text="An Update is Available", icon_value=get_icon("refresh_green"))
            row.operator("wm.url_open", text="What's new?").url = f"https://machin3.io/{bl_info['name']}/docs/whatsnew"

            layout.separator(factor=2)

        row = layout.row()
        row.scale_y = 1.25
        row.prop(self, 'show_update', text="Install MACHIN3tools Update from .zip File", icon='TRIA_DOWN' if self.show_update else 'TRIA_RIGHT')

        if self.show_update:
            update_files = get_update_files()

            box = layout.box()
            box.separator()

            if self.update_msg:
                row = box.row()
                row.scale_y = 1.5

                split = row.split(factor=0.4, align=True)
                split.label(text=self.update_msg, icon_value=get_icon('refresh_green'))

                s = split.split(factor=0.3, align=True)
                s.operator('machin3.remove_machin3tools_update', text='Remove Update', icon='CANCEL')
                s.operator('wm.quit_blender', text='Quit Blender + Install Update', icon='FILE_REFRESH')

            else:
                b = box.box()
                col = b.column(align=True)

                row = col.row()
                row.alignment = 'LEFT'

                if update_files:
                    row.label(text="Found the following Updates in your home and/or Downloads folder: ")
                    row.operator('machin3.rescan_machin3tools_updates', text="Re-Scan", icon='FILE_REFRESH')

                    col.separator()

                    for path, tail, _ in update_files:
                        row = col.row()
                        row.alignment = 'LEFT'

                        r = row.row()
                        r.active = False

                        r.alignment = 'LEFT'
                        r.label(text="found")

                        op = row.operator('machin3.use_machin3tools_update', text=f"MACHIN3tools {tail}")
                        op.path = path
                        op.tail = tail

                        r = row.row()
                        r.active = False
                        r.alignment = 'LEFT'
                        r.label(text=path)
                else:
                    row.label(text="No Update was found. Neither in your Home directory, nor in your Downloads folder.")
                    row.operator('machin3.rescan_machin3tools_updates', text="Re-Scan", icon='FILE_REFRESH')

                row = box.row()

                split = row.split(factor=0.4, align=True)
                split.prop(self, 'update_path', text='')

                text = "Select MACHIN3tools_x.x.x.zip file"

                if update_files:
                    if len(update_files) > 1:
                        text += " or pick one from above"

                    else:
                        text += " or pick the one above"

                split.label(text=text)

            box.separator()

    def draw_support(self, layout):
        layout.separator()

        box = layout.box()
        row = box.row()
        row.label(text="Support")
        r = row.row()
        r.alignment = 'RIGHT'
        r.label(text="", icon='INFO')
        r = row.row()
        r.alignment = 'RIGHT'
        r.active = False
        r.label(text="Click this Support Button and send me the files it creates, if you ever need Product Support")

        column = box.column()
        row = column.row()
        row.scale_y = 1.5
        row.alert = True
        row.operator('machin3.get_machin3tools_support', text='Get Support', icon='GREASEPENCIL')

    def draw_general(self, context, layout):
        global has_skribe

        if has_skribe is None:
            has_skribe = bool(shutil.which('skribe'))

        split = layout.split()

        self.draw_activate(split)

        self.draw_settings(context, split)

    def draw_activate(self, layout):
        b = layout.box()
        b.label(text="Activate")

        bb = b.box()
        row = bb.row()
        row.label(text="Tools")

        self.draw_activate_stats(row, "TOOLS")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='activate_smart_vert', text='Smart Vert', label='Smart Vertex Merging, Connecting and Sliding', factor=0.25)
        draw_split_row(self, column, prop='activate_smart_edge', text='Smart Edge', label='Smart Edge Creation, Manipulation, Projection and Selection Conversion', factor=0.25)
        draw_split_row(self, column, prop='activate_smart_face', text='Smart Face', label='Smart Face Creation and Object-from-Face Creation', factor=0.25)
        draw_split_row(self, column, prop='activate_clean_up', text='Clean Up', label='Quick Geometry Clean-up', factor=0.25)
        draw_split_row(self, column, prop='activate_edge_constraint', text='Edge Constrained', label='Edge Constrained Rotation and Scaling', factor=0.25)
        draw_split_row(self, column, prop='activate_extrude', text='Extrude Tools', label="PunchIt Manifold Extrusion and Cursor Spin", factor=0.25)
        draw_split_row(self, column, prop='activate_focus', text='Focus', label='Object Focus and Multi-Level Isolation', factor=0.25)
        draw_split_row(self, column, prop='activate_mirror', text='Mirror', label='Flick Object Mirroring and Un-Mirroring', factor=0.25)
        draw_split_row(self, column, prop='activate_align', text='Align', label='Object per-axis Location, Rotation and Scale Alignment, as well as Object-Inbetween-Alignment', factor=0.25)
        draw_split_row(self, column, prop='activate_group_tools', text='Group Tools', label='Group Objects using Empties as Parents', factor=0.25)
        draw_split_row(self, column, prop='activate_smart_drive', text='Smart Drive', label='Use one Object to drive another', factor=0.25)
        draw_split_row(self, column, prop='activate_assetbrowser_tools', text='Assetbrowser Tools', label='Easy Assemly Asset Creation and Import via the Asset Browser', factor=0.25)
        draw_split_row(self, column, prop='activate_filebrowser_tools', text='Filebrowser Tools', label='Additional Tools/Shortcuts for the Filebrowser (and Assetbrowser)', factor=0.25)
        draw_split_row(self, column, prop='activate_region', text='Toggle Region', label='Toggle 3D View Toolbar, Sidebar and Asset Browsers using a single T keymap, depending on mouse position', factor=0.25)
        draw_split_row(self, column, prop='activate_render', text='Render', label='Tools for efficient, iterative rendering and automatic Bevel Shader Setup through the Shading Pie', factor=0.25)
        draw_split_row(self, column, prop='activate_smooth', text='Smooth', label='Toggle Smoothing in Korean Bevel and SubD workflows', factor=0.25)
        draw_split_row(self, column, prop='activate_clipping_toggle', text='Clipping Toggle', label='Viewport Clipping Plane Toggle', factor=0.25)
        draw_split_row(self, column, prop='activate_surface_slide', text='Surface Slide', label='Easily modify Mesh Topology, while maintaining Form', factor=0.25)
        draw_split_row(self, column, prop='activate_material_picker', text='Material Picker', label="Pick Materials for the Shader Editor and Assign Materials from other Objects or from the Asset Browser", factor=0.25)
        draw_split_row(self, column, prop='activate_apply', text='Apply Transform', label='Apply Transformations while keeping the Bevel Width as well as the Child Transformations unchanged', factor=0.25)
        draw_split_row(self, column, prop='activate_select', text='Select', label='Select Center Objects, Select/Hide Wire Objects, Select Hierarchy', factor=0.25)
        draw_split_row(self, column, prop='activate_mesh_cut', text='Mesh Cut', label='Knife Intersect a Mesh-Object, using another one', factor=0.25)
        draw_split_row(self, column, prop='activate_thread', text='Thread', label='Easily turn Cylinder Faces into Thread', factor=0.25)
        draw_split_row(self, column, prop='activate_unity', text='Unity Tools', label='Unity related Export Tools', factor=0.25)

        column.separator()

        draw_split_row(self, column, prop='activate_customize', text='Customize', label="Customize various Blender preferences, settings and keymaps (MACHIN3's config)", factor=0.25)

        bb = b.box()

        row = bb.row()
        row.label(text="Pie Menus")

        self.draw_activate_stats(row, "PIES")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='activate_modes_pie', text='Modes Pie', label='Quick mode changing', factor=0.25)
        draw_split_row(self, column, prop='activate_save_pie', text='Save Pie', label='Save, Open, Append and Link. Load Recent, Previous and Next. Purge and Clean Out. ScreenCast and Versioned Startup file', factor=0.25)
        draw_split_row(self, column, prop='activate_shading_pie', text='Shading Pie', label='Control shading, overlays, eevee and some object properties', factor=0.25)
        draw_split_row(self, column, prop='activate_views_pie', text='Views Pie', label='Control views. Create and manage cameras', factor=0.25)
        draw_split_row(self, column, prop='activate_align_pie', text='Alignments Pie', label='Edit mesh and UV alignments', factor=0.25)
        draw_split_row(self, column, prop='activate_cursor_pie', text='Cursor and Origin Pie', label='Cursor and Origin manipulation', factor=0.25)
        draw_split_row(self, column, prop='activate_transform_pie', text='Transform Pie', label='Transform Orientations and Pivots', factor=0.25)
        draw_split_row(self, column, prop='activate_snapping_pie', text='Snapping Pie', label='Snapping', factor=0.25)
        draw_split_row(self, column, prop='activate_collections_pie', text='Collections Pie', label='Collection management', factor=0.25)
        draw_split_row(self, column, prop='activate_workspace_pie', text='Workspace Pie', label='Switch Workplaces. If enabled, customize it in ui/pies.py', factor=0.25)

        column.separator()

        draw_split_row(self, column, prop='activate_tools_pie', text='Tools Pie', label='Switch Tools and Annotate, with BoxCutter/HardOps and HyperCursor support', factor=0.25)

    def draw_activate_stats(self, layout, type):
        r = layout.row()
        r.alignment = "RIGHT"

        rr = r.row(align=True)
        rr.active = False
        rr.alignment = "RIGHT"
        rr.label(text="Operators: ")
        r.label(text=str(M3.props['operators'][type.lower()]))

        rr = r.row(align=True)
        rr.active = False
        rr.alignment = "RIGHT"
        rr.label(text="Keymaps: ")
        r.label(text=str(M3.props['keymaps'][type.lower()]))

    def draw_settings(self, context, layout):
        b = layout.box()
        b.label(text="Settings")

        self.draw_addon_settings(context, b)

        self.draw_quadsphere_settings(b)

        if any([getattr(bpy.types, f'MACHIN3_{name}', False) for name in has_tool_settings]):
            self.draw_tool_settings(context, b)

        if any([getattr(bpy.types, f'MACHIN3_{name}', False) for name in has_pie_settings]):

            self.draw_pie_settings(b)

        if not any([getattr(bpy.types, f'MACHIN3_{name}', False) for name in has_settings]):
            b.label(text="No tools or pie menus with settings have been activated.", icon='ERROR')

    def draw_addon_settings(self, context, layout):
        bb = layout.box()
        bb.label(text="Addon")

        column = bb.column()
        draw_split_row(self, column, prop='registration_debug', label='Print Addon Registration Output in System Console')

        bb = layout.box()
        bb.label(text="View 3D")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='show_sidebar_panel', label='Show Sidebar Panel')

        if self.show_sidebar_panel:
            draw_split_row(self, column, prop='show_help_in_sidebar_panel', label='Show Support and Documentation Panels in Sidebar')

        if any([getattr(bpy.types, f'MACHIN3_{name}', False) for name in has_hud]):
            bb = layout.box()
            bb.label(text="HUD")

            column = bb.column(align=True)
            factor = 0.404 if getattr(bpy.types, 'MACHIN3_OT_mirror', False) else 0.2

            row = draw_split_row(self, column, prop='modal_hud_scale', label='HUD Scale', factor=factor)

            if getattr(bpy.types, "MACHIN3_OT_mirror", False):
                draw_split_row(self, row, prop='mirror_flick_distance', label='Mirror Flick Distance', factor=factor)

            draw_split_row(self, column, prop='modal_hud_shadow', label='Shadow')

            if self.modal_hud_shadow:
                row = column.split(factor=0.2, align=True)
                row.separator()
                s = row.split(factor=0.55)
                rs = s.row()
                rs.prop(self, "modal_hud_shadow_blur", expand=True)
                rs.label(text="Blur")
                rs.prop(self, "modal_hud_shadow_offset", text='')
                rs.label(text="Offset")

            if any([getattr(bpy.types, f'MACHIN3_{name}', False) for name in has_fading_hud]):
                column = bb.column()
                column.label(text="Fade times")

                column = bb.column()
                row = column.row(align=True)

                if getattr(bpy.types, "MACHIN3_OT_clean_up", False):
                    row.prop(self, "HUD_fade_clean_up", text="Clean Up")

                if getattr(bpy.types, "MACHIN3_OT_clipping_toggle", False):
                    row.prop(self, "HUD_fade_clipping_toggle", text="Clipping Toggle")

                if getattr(bpy.types, "MACHIN3_OT_group", False):
                    row.prop(self, "HUD_fade_group", text="Group")

                if getattr(bpy.types, "MACHIN3_OT_select_hierarchy", False):
                    row.prop(self, "HUD_fade_select_hierarchy", text="Select Hierarchy")

                if getattr(bpy.types, "MACHIN3_MT_tools_pie", False):
                    row.prop(self, "HUD_fade_tools_pie", text="Tools Pie")

    def draw_quadsphere_settings(self, layout):
        bb = layout.box()
        row = bb.row(align=True)
        row.alignment = 'LEFT'
        row.label(text="Quad Sphere")
        r = row.row(align=True)
        r.active = False
        r.label(text="Defaults")

        column = bb.column(align=True)
        draw_split_row(self, column, prop='quadsphere_default_subdivisions', label='Subdivisions')
        draw_split_row(self, column, prop='quadsphere_default_shade_smooth', label='Shade Smooth')
        draw_split_row(self, column, prop='quadsphere_default_align_rotation', label='Align Rotation')
        draw_split_row(self, column, prop='quadsphere_default_unwrap', label='Unwrap Method', expand=False, active=self.quadsphere_default_unwrap != 'NONE')
    def draw_tool_settings(self, context, layout):
        bb = layout.box()
        bb.label(text="Tool Settings")

        if getattr(bpy.types, "MACHIN3_OT_smart_face", False):
            panel = get_panel_fold(bb, "smart_face", "Smart Face", default_closed=True)
            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='smart_face_use_topo_mode', label="Use Topo Mode for Face-from-Vert Creation")

                if self.smart_face_use_topo_mode:
                    if not self.smart_face_topo_mode_face_snapping:
                        draw_split_row(self, column, prop='smart_face_topo_mode_retopology_overlay', label="Only use Topo Mode, when when Retopolgy Overlay is used")

                    if not self.smart_face_topo_mode_retopology_overlay:
                        draw_split_row(self, column, prop='smart_face_topo_mode_face_snapping', label="Only use Topo Mode, when when Face Snapping is set up")

        if getattr(bpy.types, "MACHIN3_OT_cursor_spin", False):
            panel = get_panel_fold(bb, "extrude", "Extrude tools", default_closed=False)
            if panel:
                column = panel.column(align=True)

                column.label(text="The PunchIt and Cursor Spin tools are both found in the 3D View's sidebar (in edit mesh mode), or the Blender-native Extrude Menu!", icon='INFO')

                drawn = False

                wm = context.window_manager
                kc = wm.keyconfigs.user

                km = kc.keymaps.get('Mesh')

                if km:
                    kmi = find_kmi_from_idname(km, 'wm.call_menu', properties=[('name', 'VIEW3D_MT_edit_mesh_extrude')])

                    if kmi:
                        draw_keymap_item(column, kc, km, kmi, label="Extrude Menu Popup")
                        drawn = True

                if not drawn:
                    row = column.row()
                    row.alert = True

                    if context.window_manager.keyconfigs.active.name == 'Industry_Compatible':
                        row.label(text="Unfortunately, your 'Industry Compatible' keymap does not define a keymap item for said menu!", icon='ERROR')
                    else:
                        row.label(text="Unfortunately it appears that you have removed the native key mapping for said menu!", icon='ERROR')

        if getattr(bpy.types, "MACHIN3_OT_focus", False):
            panel = get_panel_fold(bb, "focus", "Focus", default_closed=False)
            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='focus_view_transition', label='Viewport Tweening')
                draw_split_row(self, column, prop='focus_lights', label='Ignore Lights (keep them always visible)')

        if getattr(bpy.types, "MACHIN3_OT_group", False):
            panel = get_panel_fold(bb, "group", "Group Tools")

            if panel:
                column = panel.column(align=True)

                column.label(text="Group Naming")

                row = column.row()
                r = row.split(factor=0.2)
                r.label(text="Basename")
                r.prop(self, "group_tools_basename", text="")

                row = column.row()
                r = row.split(factor=0.2)
                r.prop(self, "group_tools_auto_name", text='Auto Name', toggle=True)

                rr = r.row()
                rr.active = self.group_tools_auto_name
                rr.prop(self, "group_tools_prefix", text="Prefix")
                rr.prop(self, "group_tools_suffix", text="Suffix")

                column.separator(factor=2)
                column.label(text="Group Empties")

                r = draw_split_row(self, column, prop='group_tools_size', label='Default Empty Draw Size', factor=0.4)
                draw_split_row(self, r, prop='group_tools_fade_sizes', label='Fade Sub Group Sizes', factor=0.4)

                rr = r.row()
                rr.active = self.group_tools_fade_sizes
                rr.prop(self, "group_tools_fade_factor", text='Factor')

                column.separator(factor=2)
                column.label(text="Group Menus")

                draw_split_row(self, column, prop='group_tools_show_context_sub_menu', text='', label='Use dedicated Group Sub-Menu in Object Context Menu')

                column.separator()

                draw_split_row(self, column, prop='group_tools_show_outliner_parenting_toggle', text='', label='Show Parenting Toggle in Outliner Header')
                draw_split_row(self, column, prop='group_tools_show_outliner_group_selection_toggles', text='', label='Show Group Selection Toggles in Outliner Header', info="While in Group Mode only!", factor=0.202)
                draw_split_row(self, column, prop='group_tools_show_outliner_group_gizmos_toggle', text='', label='Show Group Gizmos Toggle in Outliner Header')

                if self.activate_modes_pie:
                    column.separator()
                    column.label(text="There are additional options for Group tools in the Modes Pie's Settings!", icon='INFO')

                column.separator(factor=2)
                row = column.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Outliner")
                r = row.row(align=True)
                r.active = False
                r.label(text="Group Mode")

                draw_split_row(self, column, prop='group_tools_group_mode_disable_auto_select', text='', label='Disable Auto-Select')
                draw_split_row(self, column, prop='group_tools_group_mode_disable_recursive_select', text='', label='Disable Recursive-Select')
                draw_split_row(self, column, prop='group_tools_group_mode_disable_group_hide', text='', label='Disable Group-Hiding')
                draw_split_row(self, column, prop='group_tools_group_mode_disable_group_gizmos', text='', label='Disable Group Gizmos')
                draw_split_row(self, column, prop='group_tools_group_mode_enable_group_draw_relations', text='', label='Draw Group Relations')

                column.separator(factor=2)
                column.label(text="Group Behavior")
                draw_split_row(self, column, prop='group_tools_remove_empty', text='', label='Automatically remove Empty Groups in each Cleanup Pass')

        if getattr(bpy.types, "MACHIN3_OT_create_assembly_asset", False):
            panel = get_panel_fold(bb, "assetbrowser_tools", "Assetbrowser Tools")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='assetbrowser_tools_preferred_default_catalog', label='Preferred Default Catalog (must exist already)')
                draw_split_row(self, column, prop='assetbrowser_tools_use_originals', label='Allow using original objects, instead of creating copies', factor=0.202 if self.assetbrowser_tools_use_originals else 0.2, info="More limited, but may be better for simple assemblies." if self.assetbrowser_tools_use_originals else None)

                column.separator(factor=2)

                row = column.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Asset")
                r = row.row(align=True)
                r.alignment = 'LEFT'
                r.active = False
                r.label(text="Meta Data")

                if not any((self.assetbrowser_tools_meta_author, self.assetbrowser_tools_meta_copyright, self.assetbrowser_tools_meta_license)):
                    r.separator(factor=1)

                    r = row.row(align=True)
                    r.alignment = 'LEFT'
                    r.label(text="No Meta Data will be set on Asset Creation", icon='INFO')

                is_machin3 = 'machin3' in self.assetbrowser_tools_meta_author.lower()
                is_machin3_sucks = is_machin3 and "sucks" in self.assetbrowser_tools_meta_author.lower()

                draw_split_row(self, column, prop='assetbrowser_tools_meta_author', text='', label='Author', factor=0.202 if is_machin3 else 0.2, active=bool(self.assetbrowser_tools_meta_author), info="Haha, very funny :(" if is_machin3_sucks else "Replace with your own or clear completely!" if is_machin3 else None)
                draw_split_row(self, column, prop='assetbrowser_tools_meta_copyright', text='', label='Copyright', factor=0.2, active=bool(self.assetbrowser_tools_meta_copyright))
                draw_split_row(self, column, prop='assetbrowser_tools_meta_license', text='', label='License', factor=0.2, active=bool(self.assetbrowser_tools_meta_license))

                if getattr(bpy.types, "MACHIN3_MT_save_pie", False):
                    column.separator(factor=2)

                    row = column.row(align=True)
                    row.label(text="Save Pie")

                    draw_split_row(self, column, prop='assetbrowser_tools_show_assembly_creation_in_save_pie', label='Show Assembly Asset Creation in Save Pie')

        if getattr(bpy.types, "MACHIN3_OT_toggle_view3d_region", False):
            panel = get_panel_fold(bb, "toggle_region", "Toggle Region")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='toggle_region_prefer_left_right', label='Prefer Left/Right toggle, over Bottom/Top, before Close Range is used to determine whether the other pair is toggled')
                draw_split_row(self, column, prop='toggle_region_close_range', label='Close Range - Proximity to Boundary as Percentages of the Area Width/Height')

                column.separator()

                draw_split_row(self, column, prop='toggle_region_assetshelf', label='If available toggle the Asset Shelf instead of the Browser', info='Asset Shelfs are used to access Brushes, but only starting in 4.3', factor=0.202)

                column.separator()

                draw_split_row(self, column, prop='toggle_region_assetbrowser_top', label='Toggle Asset Browser at Top of 3D View')
                draw_split_row(self, column, prop='toggle_region_assetbrowser_bottom', label='Toggle Asset Browser at Bottom of 3D View')

                if any([self.toggle_region_assetbrowser_top, self.toggle_region_assetbrowser_bottom]):
                    draw_split_row(self, column, prop='toggle_region_warp_mouse_to_asset_border', label='Warp Mouse to Asset Browser Border')

        if getattr(bpy.types, "MACHIN3_OT_render", False):
            panel = get_panel_fold(bb, "render", "Render")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='render_folder_name', label='Folder Name (relative to the .blend file)')
                draw_split_row(self, column, prop='render_seed_count', label='Seed Render Count')
                draw_split_row(self, column, prop='render_keep_seed_renderings', label='Keep Individual Seed Renderings')
                draw_split_row(self, column, prop='render_use_clownmatte_naming', label='Use Clownmatte Naming')
                draw_split_row(self, column, prop='render_show_buttons_in_light_properties', label='Show Render Buttons in Light Properties Panel')
                draw_split_row(self, column, prop='render_sync_light_visibility', label='Sync Light visibility/renderability')

                column.separator()
                column.separator()
                column.separator()

                if self.activate_shading_pie:
                    column.label(text="NOTE: The following are all controlled from the Shading Pie", icon='INFO')
                    column.separator()

                    draw_split_row(self, column, prop='render_adjust_lights_on_render', label='Adjust Area Lights when Rendering in Cycles')
                    draw_split_row(self, column, prop='render_enforce_hide_render', label='Enforce hide_render settign when Viewport Rendering')
                    draw_split_row(self, column, prop='render_use_bevel_shader', label='Automatically Set Up Bevel Shader')

                else:
                    column.label(text="Enable the Shading Pie for additional options", icon='INFO')

        if getattr(bpy.types, "MACHIN3_OT_material_picker", False):
            panel = get_panel_fold(bb, "material_picker", "Material Picker")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='matpick_workspace_names', label='Show Material Picker in these Workspaces')
                draw_split_row(self, column, prop='matpick_shading_type_material', label='Show Material Picker in Views set to Material Shading')
                draw_split_row(self, column, prop='matpick_shading_type_render', label='Show Material Picker in Views set to Rendered Shading')
                draw_split_row(self, column, prop='matpick_spacing_obj', label='Object Mode Header Spacing')
                draw_split_row(self, column, prop='matpick_spacing_edit', label='Edit Mode Header Spacing')

                column.separator()
                column = panel.column(align=True)
                draw_split_row(self, column, prop='matpick_ignore_wire_objects', label='Ignore Wire Objects', info="Disable if you notice intolerable lag on tool-invocation", factor=0.202)

                kmi = get_keymap_item('3D View Generic', 'machin3.material_picker')

                if kmi:
                    bb.separator()
                    bb.label(text='Right Mouse Button Keymap')

                    column = bb.column(align=True)
                    draw_split_row(kmi, column, prop='active', text='Enabled' if kmi.active else 'Disabled', label='Use RMB to Assign Material to selection in Material and Rendered shading modes')

                    if not kmi.active:
                        draw_split_row(self, column, prop='matpick_draw_in_top_level_context_menu', label='Add Material Picker to Top-Level of Context Menu')

                else:
                    draw_split_row(self, column, prop='matpick_draw_in_top_level_context_menu', label='Add Material Picker to Top-Level of Context Menu')

        if getattr(bpy.types, "MACHIN3_OT_customize", False):
            panel = get_panel_fold(bb, "customize", text="Customize")

            if panel:

                panel.label(text='General')

                column = panel.column(align=True)

                row = draw_split_row(self, column, prop='custom_theme', label='Theme', factor=0.4)
                row = draw_split_row(self, row, prop='custom_matcaps', label='Matcaps', factor=0.4)
                draw_split_row(self, row, prop='custom_shading', label='Shading', factor=0.4)

                row = draw_split_row(self, column, prop='custom_overlays', label='Overlays', factor=0.4)
                row = draw_split_row(self, row, prop='custom_outliner', label='Outliner', factor=0.4)
                draw_split_row(self, row, prop='custom_startup', label='Startup', factor=0.4)

                panel.separator()
                panel.label(text='Preferences')

                column = panel.column(align=True)

                row = draw_split_row(self, column, prop='custom_preferences_interface', label='Interface', factor=0.4)
                draw_split_row(self, row, prop='custom_preferences_keymap', label='Keymaps', factor=0.4)
                draw_split_row(self, row, prop='custom_preferences_viewport', label='Viewport', factor=0.4)

                row = draw_split_row(self, column, prop='custom_preferences_system', label='System', factor=0.4)
                draw_split_row(self, row, prop='custom_preferences_input_navigation', label='Input & Navigation', factor=0.4)
                draw_split_row(self, row, prop='custom_preferences_save', label='Save', factor=0.4)

                panel.separator()

                column = panel.column()
                row = column.row()
                row.label()
                row.operator("machin3.customize", text="Customize")
                row.label()

    def draw_pie_settings(self, layout):
        bb = layout.box()
        bb.label(text="Pie Settings")

        if getattr(bpy.types, "MACHIN3_MT_modes_pie", False):
            panel = get_panel_fold(bb, "modes_pie", text="Modes Pie", default_closed=False)
            if panel:
                column = panel.column(align=True)

                split = column.split(factor=0.2)
                row = split.row(align=True)

                row.alignment = 'LEFT'
                row.label(text="Adjustable")
                r = row.row()
                r.alignment = 'LEFT'
                r.active = False
                r.label(text="Top Button")
                split.label(text="Pick the button(s) at the top of the Pie in Object Mode", icon='INFO')

                draw_split_row(self, column, prop='modes_pie_object_mode_top_show_edit', label='Show Edit Mode Toggle', factor=0.202, warning="Legacy behavior, now disabled by default!")
                draw_split_row(self, column, prop='modes_pie_object_mode_top_show_sculpt', label='Show Sculpt Mode Toggle for Mesh Objects', factor=0.2)

                if self.activate_group_tools:
                    column.separator()
                    row = column.row(align=True)
                    row.alignment = 'LEFT'

                    row.label(text="Group")
                    r = row.row()
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text="Buttons")

                    draw_split_row(self, column, prop='modes_pie_object_mode_top_show_ungroup', label='Show Ungroup if Active is a Group Empty', factor=0.202, info="Only one of these 3 is ever shown at one time")
                    draw_split_row(self, column, prop='modes_pie_object_mode_top_show_select_group', label='Show Select Group Button, if Active is a Group Object', factor=0.2)
                    draw_split_row(self, column, prop='modes_pie_object_mode_top_show_create_group', label='Show Create Group Button', factor=0.2)

                if True and self.activate_assetbrowser_tools:
                    column.separator()
                    row = column.row(align=True)
                    row.alignment = 'LEFT'

                    row.label(text="Assembly Edit")
                    r = row.row()
                    r.alignment = 'LEFT'
                    r.active = False
                    r.label(text="Buttons")

                    draw_split_row(self, column, prop='object_mode_show_assembly_edit', label='Show Assembly Edit Button at the bottom, when Active is an Assembly', factor=0.2)
                    draw_split_row(self, column, prop='object_mode_show_assembly_edit_finish', label='Show Assembly Edit Finish Button at the top, when in Assembly Edit Mode', factor=0.2)

                column.separator()
                row = column.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Cavity, Curvature and XRay")
                r = row.row(align=True)
                r.active = False
                r.label(text="Automation")

                draw_split_row(self, column, prop='toggle_cavity', label='Toggle Cavity/Curvature OFF in Edit Mode, ON in Object Mode')
                draw_split_row(self, column, prop='toggle_xray', label='Toggle X-Ray ON in Edit Mode, OFF in Object Mode, if Pass Through or Wireframe was enabled in Edit Mode')

                column.separator()
                row = column.row(align=True)
                row.label(text="Tool Syncing")

                draw_split_row(self, column, prop='sync_tools', label='Sync Tool if present in both modes, when switching Modes')

        if getattr(bpy.types, "MACHIN3_MT_save_pie", False):
            panel = get_panel_fold(bb, "save_pie", text="Save Pie")

            if panel:
                extensions = []

                panel.label(text='Import / Export')

                column = panel.column(align=True)

                extensions.append("obj")

                row = column.row(align=True)
                split = row.split(factor=0.5, align=True)

                r = split.split(factor=0.42, align=True)
                r.prop(self, "save_pie_show_obj_export", text=str(self.save_pie_show_obj_export), toggle=True)
                r.label(text="Show .obj Import/Export")

                split.separator()

                extensions.append("plasticity")

                row = column.row(align=True)
                split = row.split(factor=0.5, align=True)

                r = split.split(factor=0.42, align=True)
                r.prop(self, "save_pie_show_plasticity_export", text=str(self.save_pie_show_plasticity_export), toggle=True)
                r.label(text="Show Plasticity Import/Export")

                if self.save_pie_show_plasticity_export:
                    split.label(text=".obj import/export with Axes set up already", icon='INFO')

                else:
                    split.separator()

                if M3.get_addon('FBX format'):
                    extensions.append("fbx")

                    row = column.row(align=True)
                    split = row.split(factor=0.5, align=True)

                    r = split.split(factor=0.42, align=True)
                    r.prop(self, "save_pie_show_fbx_export", text=str(self.save_pie_show_fbx_export), toggle=True)
                    r.label(text="Show .fbx Import/Export")

                    if self.save_pie_show_fbx_export:
                        r = split.split(factor=0.42, align=True)
                        r.prop(self, "fbx_export_apply_scale_all", text=str(self.fbx_export_apply_scale_all), toggle=True)
                        r.label(text="Use 'Fbx All' for Applying Scale")

                    else:
                        split.separator()

                if M3.get_addon("Better FBX Importer & Exporter"):
                    extensions.append("better_fbx")

                    row = column.row(align=True)
                    split = row.split(factor=0.5, align=True)

                    r = split.split(factor=0.42, align=True)
                    r.prop(self, "save_pie_show_better_fbx_export", text=str(self.save_pie_show_fbx_export), toggle=True)
                    r.label(text="Show Better .fbx Import/Export")

                    split.separator()

                extensions.append("usd")

                row = column.row(align=True)
                split = row.split(factor=0.5, align=True)

                r = split.split(factor=0.42, align=True)
                r.prop(self, "save_pie_show_usd_export", text=str(self.save_pie_show_usd_export), toggle=True)
                r.label(text="Show .usd Import/Export")

                split.separator()

                extensions.append("stl")

                row = column.row(align=True)
                split = row.split(factor=0.5, align=True)

                r = split.split(factor=0.42, align=True)
                r.prop(self, "save_pie_show_stl_export", text=str(self.save_pie_show_stl_export), toggle=True)
                r.label(text="Show .stl Import/Export")

                split.separator()

                if M3.get_addon("glTF 2.0 format"):
                    extensions.append("gltf")

                    row = column.row(align=True)
                    split = row.split(factor=0.5, align=True)

                    r = split.split(factor=0.42, align=True)
                    r.prop(self, "save_pie_show_gltf_export", text=str(self.save_pie_show_gltf_export), toggle=True)
                    r.label(text="Show .glTF Import/Export")

                    split.separator()

                if any(getattr(self, f"save_pie_show_{ext}_export") for ext in extensions):

                    bbb = panel.box()
                    bbb.label(text="Export Root Folders")

                    col = bbb.column(align=True)

                    for ext in ['obj', 'plasticity', 'fbx', 'better_fbx', 'usd', 'stl', 'gltf']:
                        if getattr(self, f"save_pie_show_{ext}_export"):
                            split = col.split(factor=0.2, align=True)

                            row = split.row(align=True)
                            row.alignment = 'RIGHT'
                            row.active = bool(getattr(self, f"save_pie_{ext}_folder"))

                            if ext == 'plasticity':
                                row.label(text="Plasticity")

                            elif ext == 'better_fbx':
                                row.label(text="Better .fbx")

                            else:
                                row.label(text=f".{ext}")

                            split.prop(self, f"save_pie_{ext}_folder", text='')

                panel.separator()
                panel.label(text='Screen Cast')

                column = panel.column(align=True)

                draw_split_row(self, column, prop='show_screencast', label='Show Screencast in Save Pie')

                if self.show_screencast:
                    split = panel.split(factor=0.5)
                    col = split.column(align=True)

                    draw_split_row(self, col, prop='screencast_operator_count', label='Operator Count', factor=0.4)
                    draw_split_row(self, col, prop='screencast_fontsize', label='Font Size', factor=0.4)

                    col = split.column(align=True)

                    draw_split_row(self, col, prop='screencast_highlight_machin3', label='Highlight Operators from MACHIN3 addons', factor=0.3)
                    draw_split_row(self, col, prop='screencast_show_addon', label="Display Operator's Addon", factor=0.3)
                    draw_split_row(self, col, prop='screencast_show_idname', label="Display Operator's bl_idname", factor=0.3)

                    if (has_sk := M3.get_addon('Screencast Keys')) or has_skribe:
                        col.separator()

                        if has_sk:
                            draw_split_row(self, col, prop='screencast_use_screencast_keys', label='Use Screencast Keys (Extension, preferred)', factor=0.3)

                        if has_skribe:
                            draw_split_row(self, col, prop='screencast_use_skribe', label='Use SKRIBE (external)', factor=0.3)

                panel.separator()
                panel.label(text='Pre-Undo Save')

                column = panel.column(align=True)
                draw_split_row(self, column, prop='save_pie_use_undo_save', label='Make Pre-Undo Saving available in the Pie', info='Useful if you notice Undo causing crashes')

                kmi = get_keymap_item('Window', 'machin3.save_versioned_startup_file')

                if kmi:
                    panel.separator()
                    panel.label(text='Versioned Startup File')

                    column = panel.column(align=True)
                    draw_split_row(kmi, column, prop='active', text='Enabled' if kmi.active else 'Disabled', label='Use CTRL + U keymap override')

        if getattr(bpy.types, "MACHIN3_MT_shading_pie", False):
            panel = get_panel_fold(bb, "shading_pie", text="Shading Pie")

            if panel:

                panel.label(text='Overlay Visibility (per-shading type)')
                column = panel.column(align=True)

                row = draw_split_row(self, column, prop='overlay_solid', label='Solid Shading', factor=0.5)
                draw_split_row(self, row, prop='overlay_material', label='Material Shading', factor=0.5)
                draw_split_row(self, row, prop='overlay_rendered', label='Rendered Shading', factor=0.5)
                draw_split_row(self, row, prop='overlay_wire', label='Wire Shading', factor=0.5)

                panel.separator()
                panel.label(text='Autosmooth')

                column = panel.column(align=True)

                draw_split_row(self, column, prop='auto_smooth_angle_presets', label='Auto Smooth Angle Presets shown in the Shading Pie as buttons', factor=0.25)
                draw_split_row(self, column, prop='auto_smooth_show_expanded', label="Leave Auto Smooth Modifier open, and don't collapse it", factor=0.25)

                panel.separator()
                panel.label(text='Matcap Switch')

                column = panel.column()

                row = column.row()
                row.prop(self, "switchmatcap1")
                row.prop(self, "switchmatcap2")

                split = column.split(factor=0.5)

                draw_split_row(self, split, prop='matcap_switch_background', label='Switch Background too', factor=0.25)

                col = split.column(align=True)

                draw_split_row(self, col, prop='matcap2_force_single', label='Force Single Color Shading for Matcap 2', factor=0.25)
                draw_split_row(self, col, prop='matcap2_disable_overlays', label='Disable Overlays for Matcap 2', factor=0.25)

                if self.matcap_switch_background:
                    row = column.row()
                    row.prop(self, "matcap1_switch_background_type", expand=True)
                    row.prop(self, "matcap2_switch_background_type", expand=True)

                    if any([bg == 'VIEWPORT' for bg in [self.matcap1_switch_background_type, self.matcap2_switch_background_type]]):
                        row = column.split(factor=0.5)

                        if self.matcap1_switch_background_type == 'VIEWPORT':
                            row.prop(self, "matcap1_switch_background_viewport_color", text='')

                        else:
                            row.separator()

                        if self.matcap2_switch_background_type == 'VIEWPORT':
                            row.prop(self, "matcap2_switch_background_viewport_color", text='')

                        else:
                            row.separator()

        if getattr(bpy.types, "MACHIN3_MT_viewport_pie", False):
            panel = get_panel_fold(bb, "views_pie", text="Views Pie")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='custom_views_use_trackball', label='Force Trackball Navigation when using Custom Views')

                if self.activate_transform_pie:
                    draw_split_row(self, column, prop='custom_views_set_transform_preset', label='Set Transform Preset when using Custom Views')

                draw_split_row(self, column, prop='show_orbit_selection', label='Show Orbit around Active')
                draw_split_row(self, column, prop='show_orbit_method', label='Show Turntable/Trackball Orbit Method Selection')

                panel.separator()
                column = panel.column(align=True)

                row = column.row(align=True)
                row.alignment = 'LEFT'
                row.label(text="Smart Cam")
                r = row.row(align=True)
                r.active = False
                r.label(text="Camera Creation")

                draw_split_row(self, column, prop='smart_cam_perfectly_match_viewport', label='Match Resolution and Camera Lens to Viewport')

        if getattr(bpy.types, "MACHIN3_MT_cursor_pie", False):
            panel = get_panel_fold(bb, "cursor_pie", text="Cursor and Origin Pie")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='cursor_ensure_visibility', label='Ensure Cursor Visibility')
                draw_split_row(self, column, prop='cursor_show_to_grid', label='Show Cursor and Selected to Grid')

                if self.activate_transform_pie or self.activate_shading_pie:
                        if self.activate_transform_pie:
                            draw_split_row(self, column, prop='cursor_set_transform_preset', label='Set Transform Preset when Setting Cursor')

        if getattr(bpy.types, "MACHIN3_MT_snapping_pie", False):
            panel = get_panel_fold(bb, "snapping_pie", text="Snapping Pie")

            if panel:
                column = panel.column(align=True)

                draw_split_row(self, column, prop='snap_show_absolute_grid', label='Show Absolute Grid Snapping')
                draw_split_row(self, column, prop='snap_show_volume', label='Show Volume Snapping')
                draw_split_row(self, column, prop='snap_toggle_face_nearest', label='Switch to Face Nearest when Surface Snapping is chosen and invoked a second time')
                draw_split_row(self, column, prop='snap_draw_HUD', label='Draw Fading HUD')

                column.separator()

                row = column.row(align=True)
                row.alignment = 'LEFT'
                row.label(text='Snap Preset')
                r = row.row(align=True)
                r.active = False
                r.label(text='Targets')

                draw_split_row(self, column, prop='snap_vert_preset_target', label='Vert Preset', expand=False)
                draw_split_row(self, column, prop='snap_edge_preset_target', label='Edge Preset', expand=False)
                draw_split_row(self, column, prop='snap_surface_preset_target', label='Surface Preset', expand=False)

                if self.snap_toggle_face_nearest:
                    draw_split_row(self, column, prop='snap_face_nearest_preset_target', label='Face Nearest Preset', expand=False)

                if self.snap_show_volume:
                    draw_split_row(self, column, prop='snap_volume_preset_target', label='Volume Preset', expand=False)

                if self.snap_show_absolute_grid:
                    draw_split_row(self, column, prop='snap_grid_preset_target', label='Grid Preset', expand=False)

        if getattr(bpy.types, "MACHIN3_MT_workspace_pie", False):
            panel = get_panel_fold(bb, "workspace_pie", text="Workspace Pie")

            if panel:
                column = panel.column(align=True)
                column.label(text="It's your responsibility to pick workspace- and icon names that actually exist!", icon='ERROR')

                first = column.split(factor=0.2)
                first.separator()

                second = first.split(factor=0.25)
                second.separator()

                third = second.split(factor=0.33)

                col = third.column()
                col.label(text="Top")

                col.prop(self, 'pie_workspace_top_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_top_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_top_icon', text="", icon='IMAGE_DATA')

                fourth = third.split(factor=0.5)
                fourth.separator()

                fifth = fourth
                fifth.separator()

                first = column.split(factor=0.2)
                first.separator()

                second = first.split(factor=0.25)

                col = second.column()
                col.label(text="Top-Left")

                col.prop(self, 'pie_workspace_top_left_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_top_left_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_top_left_icon', text="", icon='IMAGE_DATA')

                third = second.split(factor=0.33)
                third.separator()

                fourth = third.split(factor=0.5)

                col = fourth.column()
                col.label(text="Top-Right")

                col.prop(self, 'pie_workspace_top_right_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_top_right_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_top_right_icon', text="", icon='IMAGE_DATA')

                fifth = fourth
                fifth.separator()

                first = column.split(factor=0.2)

                col = first.column()
                col.label(text="Left")

                col.prop(self, 'pie_workspace_left_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_left_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_left_icon', text="", icon='IMAGE_DATA')

                second = first.split(factor=0.25)
                second.separator()

                third = second.split(factor=0.33)

                col = third.column()
                col.label(text="")
                col.label(text="")
                col.operator('machin3.get_icon_name_help', text="Icon Names?", icon='INFO')

                fourth = third.split(factor=0.5)
                fourth.separator()

                fifth = fourth

                col = fifth.column()
                col.label(text="Right")

                col.prop(self, 'pie_workspace_right_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_right_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_right_icon', text="", icon='IMAGE_DATA')

                first = column.split(factor=0.2)
                first.separator()

                second = first.split(factor=0.25)

                col = second.column()
                col.label(text="Bottom-Left")

                col.prop(self, 'pie_workspace_bottom_left_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_bottom_left_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_bottom_left_icon', text="", icon='IMAGE_DATA')

                third = second.split(factor=0.33)
                third.separator()

                fourth = third.split(factor=0.5)

                col = fourth.column()
                col.label(text="Bottom-Right")

                col.prop(self, 'pie_workspace_bottom_right_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_bottom_right_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_bottom_right_icon', text="", icon='IMAGE_DATA')

                fifth = fourth
                fifth.separator()

                first = column.split(factor=0.2)
                first.separator()

                second = first.split(factor=0.25)
                second.separator()

                third = second.split(factor=0.33)

                col = third.column()
                col.label(text="Bottom")

                col.prop(self, 'pie_workspace_bottom_name', text="", icon='WORKSPACE')
                col.prop(self, 'pie_workspace_bottom_text', text="", icon='SMALL_CAPS')
                col.prop(self, 'pie_workspace_bottom_icon', text="", icon='IMAGE_DATA')

                fourth = third.split(factor=0.5)
                fourth.separator()

                fifth = fourth
                fifth.separator()

        if getattr(bpy.types, "MACHIN3_MT_tools_pie", False):
            panel = get_panel_fold(bb, "tools_pie", text="Tools Pie")

            if panel:
                col = bb.column(align=True)

                row = draw_split_row(self, col, prop='tools_show_quick_favorites', label='Show Quick Favorites', factor=0.4)
                row = draw_split_row(self, row, prop='tools_show_tool_bar', label='Show Tool Bar', factor=0.4)
                draw_empty_split_row(self, row, factor=0.4)

                row = draw_split_row(self, col, prop='tools_show_annotate', label='Show Annotate', factor=0.4)
                draw_split_row(self, row, prop='tools_show_surfacedraw', label='Show SurfaceDraw', factor=0.4)
                draw_empty_split_row(self, row, factor=0.4)

                col.separator()

                if M3.get_addon("Hard Ops 9"):
                    row = draw_split_row(self, col, prop='tools_show_hardops', label='Show Hard Ops', factor=0.4)

                    r = row.row(align=True)
                    r.enabled = self.tools_show_hardops
                    row = draw_split_row(self, r, prop='tools_show_hardops_menu', label='Show Hard Ops Menu', factor=0.4)
                    draw_empty_split_row(self, row, factor=0.4)

                if M3.get_addon("BoxCutter"):
                    row = draw_split_row(self, col, prop='tools_show_boxcutter', label='Show BoxCutter', factor=0.4)

                    r = row.row(align=True)
                    r.enabled = self.tools_show_boxcutter
                    row = draw_split_row(self, r, prop='tools_show_boxcutter_presets', label='Show BoxCutter Presets', factor=0.4)
                    draw_empty_split_row(self, row, factor=0.4)

    def draw_keymaps(self, context, layout):
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user

        km = kc.keymaps.get('Sculpt')
        km3d = kc.keymaps.get('3D View Generic')

        shading_pie_conflict = False
        views_pie_conflict = False

        if self.activate_shading_pie:
            grow_sculpt_kmi = find_kmi_from_idname(km, "paint.visibility_filter", properties=[('action', 'GROW')])

            if grow_sculpt_kmi:
                shading_pie_kmi = find_kmi_from_idname(km3d, "machin3.call_machin3tools_pie", properties=[('idname', 'shading_pie')])

                if shading_pie_kmi and shading_pie_kmi.compare(grow_sculpt_kmi):
                    shading_pie_conflict = True

        if self.activate_views_pie:
            shrink_sculpt_kmi = find_kmi_from_idname(km, "paint.visibility_filter", properties=[('action', 'SHRINK')])

            if shrink_sculpt_kmi:
                views_pie_kmi = find_kmi_from_idname(km3d, "wm.call_menu_pie", properties=[('name', 'MACHIN3_MT_viewport_pie')])

                if views_pie_kmi and views_pie_kmi.compare(shrink_sculpt_kmi):
                    views_pie_conflict = True

        if shading_pie_conflict or views_pie_conflict:
            layout.separator()

            box = layout.box()
            box.label(text="Sculpt Mode Conflicts")
            column = box.column(align=True)

            if shading_pie_conflict:
                row = column.row(align=True)
                row.alert = True

                row.label(text="There is a conflicting keymap, preventing the Shading Pie from coming up in Sculpt mode. I suggest you remap it, maybe by adding a mod key?")

                row = column.row(align=True)
                draw_keymap_item(row, kc, km, grow_sculpt_kmi)

            if views_pie_conflict:
                row = column.row(align=True)
                row.alert = True

                row.label(text="There is a conflicting keymap, preventing the Views Pie from coming up in Sculpt mode. I suggest you remap it, maybe by adding a mod key?")

                row = column.row(align=True)
                draw_keymap_item(row, kc, km, shrink_sculpt_kmi)

        modified, missing = get_user_keymap_items(context)

        if modified or missing:
            column = layout.column(align=True)

            column.separator()

            row = column.row(align=True)
            row.scale_y = 1.5
            row.alert = True

            column.separator()

            if modified:
                row.operator('machin3.reset_machin3tools_keymaps', text='Reset Modified Keymaps to Default')

            if missing:
                row.operator('machin3.restore_machin3tools_keymaps', text='Restore Missing Keymaps')

        split = layout.split()

        b = split.box()
        col = b.column(align=True)
        col.label(text="Tools")

        if not self.draw_tool_keymaps(kc, keys, col):
            b.label(text="No keymappings available, because none of the tools have been activated.", icon='ERROR')

        b = split.box()
        col = b.column(align=True)
        col.label(text="Pie Menus")

        if not self.draw_pie_keymaps(kc, keys, col):
            b.label(text="No keymappings created, because none of the pies have been activated.", icon='ERROR')

    def draw_tool_keymaps(self, kc, keysdict, layout):
        drawn = False

        for name in keysdict:
            if "PIE" not in name:
                keylist = keysdict.get(name)

                if draw_keymap_items(kc, name, keylist, layout) and not drawn:
                    drawn = True

        return drawn

    def draw_pie_keymaps(self, kc, keysdict, layout):
        drawn = False

        for name in keysdict:
            if "PIE" in name:
                keylist = keysdict.get(name)

                if draw_keymap_items(kc, name, keylist, layout):
                    drawn = True

        return drawn

    def draw_about(self, layout):
        column = layout.column(align=True)

        row = column.row(align=True)

        row.scale_y = 1.5
        row.operator("wm.url_open", text='MACHIN3tools', icon='INFO').url = 'https://machin3.io/MACHIN3tools/'
        row.operator("wm.url_open", text='MACHINƎ.io', icon='WORLD').url = 'https://machin3.io'
        row.operator("wm.url_open", text='blenderartists', icon_value=get_icon('blenderartists')).url = 'https://blenderartists.org/t/machin3tools/1135716/'

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='Patreon', icon_value=get_icon('patreon')).url = 'https://patreon.com/machin3'
        row.operator("wm.url_open", text='Twitter', icon_value=get_icon('twitter')).url = 'https://twitter.com/machin3io'
        row.operator("wm.url_open", text='Youtube', icon_value=get_icon('youtube')).url = 'https://www.youtube.com/c/MACHIN3/'
        row.operator("wm.url_open", text='Artstation', icon_value=get_icon('artstation')).url = 'https://www.artstation.com/machin3'

        column.separator()

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='DECALmachine', icon_value=get_icon('save' if M3.get_addon("DECALmachine") else 'cancel_grey')).url = 'https://decal.machin3.io'
        row.operator("wm.url_open", text='MESHmachine', icon_value=get_icon('save' if M3.get_addon("MESHmachine") else 'cancel_grey')).url = 'https://mesh.machin3.io'
        row.operator("wm.url_open", text='PUNCHit', icon_value=get_icon('save' if M3.get_addon("PUNCHit") else 'cancel_grey')).url = 'https://machin3.io/PUNCHit'
        row.operator("wm.url_open", text='CURVEmachine', icon_value=get_icon('save' if M3.get_addon("CURVEmachine") else 'cancel_grey')).url = 'https://machin3.io/CURVEmachine'
        row.operator("wm.url_open", text='HyperCursor', icon_value=get_icon('save' if M3.get_addon("HyperCursor") else 'cancel_grey')).url = 'https://www.youtube.com/playlist?list=PLcEiZ9GDvSdWs1w4ZrkbMvCT2R4F3O9yD'
