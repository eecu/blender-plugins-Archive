import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, CollectionProperty, PointerProperty, EnumProperty, FloatProperty, FloatVectorProperty
import bmesh

from mathutils import Matrix

from . utils.light import adjust_lights_for_rendering, get_area_light_poll
from . utils.material import adjust_bevel_shader
from . utils.math import flatten_matrix
from . utils.object import is_decal
from . utils.registration import get_prefs, get_addon_prefs
from . utils.render import is_volume, set_device, is_cycles, is_eevee, set_render_engine
from . utils.scene import ensure_composite_input_and_output, get_composite_dispersion, get_composite_glare
from . utils.system import abspath, dprint, dprintd
from . utils.tools import get_active_tool
from . utils.ui import force_ui_update
from . utils.view import sync_light_visibility
from . utils.world import get_world_output, is_volume_only_world, set_use_world
from . utils.group import finish_group_origin_adjustment, get_group_hierarchy, get_batch_pose_name, init_group_origin_adjustment, is_inception_pose, process_group_poses, propagate_pose_preview_alpha

from . items import eevee_next_preset_items, eevee_passes_preset_items, align_mode_items, render_engine_items, cycles_device_items, driver_limit_items, axis_items, driver_transform_items, driver_space_items, bc_orientation_items, shading_light_items, eevee_next_raytrace_resolution_items

class HistoryObjectsCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    obj: PointerProperty(name="History Object", type=bpy.types.Object)

class HistoryUnmirroredCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    obj: PointerProperty(name="History Unmirror", type=bpy.types.Object)

class HistoryEpochCollection(bpy.types.PropertyGroup):
    name: StringProperty()
    objects: CollectionProperty(type=HistoryObjectsCollection)
    unmirrored: CollectionProperty(type=HistoryUnmirroredCollection)

class GroupPoseCollection(bpy.types.PropertyGroup):
    def update_name(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        empty = active if (active := context.active_object) and active.type == 'EMPTY' and active.M3.is_group_empty else None

        if empty:
            is_batch = self.batch

            if is_batch:

                group_empties = get_group_hierarchy(empty, up=True)
                other_empties = [obj for obj in group_empties if obj != empty]

                skip_get_batch_pose_name = False

                if self.name.strip():
                    pose_name = self.name.strip()

                    if pose_name == 'Inception':

                        matching_empties = [e for e in group_empties if any(p.uuid == self.uuid for p in e.M3.group_pose_COL)]

                        if any(is_inception_pose(p) for e in matching_empties for p in e.M3.group_pose_COL):

                            self.avoid_update = True
                            self.name = 'BatchPose'
                            pose_name = 'BatchPose'

                        else:
                            skip_get_batch_pose_name = True
                            name = 'Inception'

                            for e in matching_empties:
                                for p in e.M3.group_pose_COL:
                                    if p.axis:
                                        p.axis = ''

                else:
                    pose_name = 'BatchPose'

                if not skip_get_batch_pose_name:
                    name = get_batch_pose_name(other_empties, basename=pose_name)

                empties = other_empties + [empty] if name != self.name else other_empties

                for obj in empties:
                    for pose in obj.M3.group_pose_COL:
                        if pose.uuid == self.uuid:
                            pose.avoid_update = True
                            pose.name = name
                            break

            else:
                if not self.name.strip():
                    self.avoid_update = True
                    self.name = f"Pose.{str(self.index).zfill(3)}"

                elif self.name == 'Inception':
                    other_inception_pose = any(is_inception_pose(pose) for pose in empty.M3.group_pose_COL)

                    if other_inception_pose:
                        self.avoid_update = True
                        self.name = f"Pose.{str(self.index).zfill(3)}"

                    else:
                        for pose in empty.M3.group_pose_COL:
                            if pose.axis:
                                pose.axis = ''

            process_group_poses(empty)

    name: StringProperty(update=update_name)
    index: IntProperty()

    mx: FloatVectorProperty(name="Group Pose Matrix", subtype="MATRIX", size=(4, 4))

    remove: BoolProperty(name="Remove Pose", default=False)
    axis: StringProperty()
    angle: FloatProperty()

    uuid: StringProperty()
    batch: BoolProperty(default=False)
    batchlinked: BoolProperty(name="Batch Pose", description="Toggle Connection to Other Batch Poses in this Group Hierarchy\n\nIf the active pose is disconnected, it will be retrieved like a regular single Pose.\nDisconnected Batch Poses in the Group Hierarchy below, will not be previewed, retrieved or removed, unless overriden in the Retrieve/Remove ops", default=True)
    avoid_update: BoolProperty()
    forced_preview_update: BoolProperty()

selected = []

class M3SceneProperties(bpy.types.PropertyGroup):

    focus_history: CollectionProperty(type=HistoryEpochCollection)

    use_undo_save: BoolProperty(name="Use Undo Save", description="Save before Undoing\nBe warned, depending on your scene complexity, this can noticably affect your undo speed", default=False)
    use_redo_save: BoolProperty(name="Use Redo Save", description="Also save before first Operator Redos", default=False)

    def update_xray(self, context):
        x = (self.pass_through, self.show_edit_mesh_wire)
        shading = context.space_data.shading

        shading.show_xray = True if any(x) else False

        if self.show_edit_mesh_wire:
            shading.xray_alpha = 0.1

        elif self.pass_through:
            shading.xray_alpha = 1 if context.active_object and context.active_object.type == "MESH" else 0.5

    def update_uv_sync_select(self, context):
        ts = context.scene.tool_settings
        ts.use_uv_select_sync = self.uv_sync_select

        global selected
        active = context.active_object

        if ts.use_uv_select_sync:
            bpy.ops.mesh.select_all(action='DESELECT')

            bm = bmesh.from_edit_mesh(active.data)
            bm.normal_update()
            bm.verts.ensure_lookup_table()

            if selected:
                for v in bm.verts:
                    if v.index in selected:
                        v.select_set(True)

            bm.select_flush(True)

            bmesh.update_edit_mesh(active.data)

        else:
            bm = bmesh.from_edit_mesh(active.data)
            bm.normal_update()
            bm.verts.ensure_lookup_table()

            selected = [v.index for v in bm.verts if v.select]

            bpy.ops.mesh.select_all(action="SELECT")

            mode = tuple(ts.mesh_select_mode)

            if mode == (False, True, False):
                ts.uv_select_mode = "EDGE"

            else:
                ts.uv_select_mode = "VERTEX"

    pass_through: BoolProperty(name="Pass Through", default=False, update=update_xray)
    show_edit_mesh_wire: BoolProperty(name="Show Edit Mesh Wireframe", default=False, update=update_xray)
    uv_sync_select: BoolProperty(name="Synce Selection", default=False, update=update_uv_sync_select)
    def update_show_cavity(self, context):
        t = (self.show_cavity, self.show_curvature)
        shading = context.space_data.shading

        shading.show_cavity = True if any(t) else False

        if t == (True, True):
            shading.cavity_type = "BOTH"

        elif t == (True, False):
            shading.cavity_type = "WORLD"

        elif t == (False, True):
            shading.cavity_type = "SCREEN"

    show_cavity: BoolProperty(name="Cavity", default=True, update=update_show_cavity)
    show_curvature: BoolProperty(name="Curvature", default=False, update=update_show_cavity)

    draw_axes_size: FloatProperty(name="Draw_Axes Size", default=0.1, min=0)
    draw_axes_alpha: FloatProperty(name="Draw Axes Alpha", default=0.5, min=0, max=1)
    draw_axes_screenspace: BoolProperty(name="Draw Axes in Screen Space", default=True)
    draw_active_axes: BoolProperty(name="Draw Active Axes", description="Draw Active's Object Axes", default=False)
    draw_cursor_axes: BoolProperty(name="Draw Cursor Axes", description="Draw Cursor's Axes", default=False)

    def update_shading_light(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        shading = context.space_data.shading
        shading.light = self.shading_light

        if self.use_flat_shadows:
            shading.show_shadows = shading.light == 'FLAT'

    def update_use_flat_shadows(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        shading = context.space_data.shading

        if shading.light == 'FLAT':
            shading.show_shadows = self.use_flat_shadows

    shading_light: EnumProperty(name="Lighting Method", description="Lighting Method for Solid/Texture Viewport Shading", items=shading_light_items, default='MATCAP', update=update_shading_light)
    use_flat_shadows: BoolProperty(name="Use Flat Shadows", description="Use Shadows when in Flat Lighting", default=True, update=update_use_flat_shadows)

    def update_eevee_next_preset(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        eevee = context.scene.eevee
        shading = context.space_data.shading

        if self.eevee_next_preset == 'NONE':
            eevee.use_shadows = False
            eevee.use_volumetric_shadows = False

            eevee.use_raytracing = False

            self.use_bloom = False
            self.use_volumes = False

            eevee.volumetric_tile_size = "16"
            eevee.volumetric_samples = 16

        elif self.eevee_next_preset == 'LOW':
            eevee.use_shadows = True
            eevee.shadow_step_count = 2
            eevee.use_volumetric_shadows = False

            eevee.use_raytracing = True
            eevee.ray_tracing_options.resolution_scale = "4"
            eevee.ray_tracing_options.screen_trace_quality = 0.1

            eevee.fast_gi_step_count = 16
            eevee.fast_gi_quality = 0.1
            eevee.fast_gi_resolution = "4"

            self.use_bloom = False

            eevee.volumetric_tile_size = "8"
            eevee.volumetric_samples = 32

        elif self.eevee_next_preset == 'HIGH':
            eevee.use_shadows = True
            eevee.shadow_step_count = 4
            eevee.use_volumetric_shadows = True

            eevee.use_raytracing = True
            eevee.ray_tracing_options.resolution_scale = "2"
            eevee.ray_tracing_options.screen_trace_quality = 0.25

            eevee.fast_gi_step_count = 32
            eevee.fast_gi_quality = 0.25
            eevee.fast_gi_resolution = "2"

            self.use_bloom = True

            eevee.volumetric_tile_size = "4"
            eevee.volumetric_samples = 64

        elif self.eevee_next_preset == 'ULTRA':
            eevee.use_shadows = True
            eevee.shadow_step_count = 6
            eevee.use_volumetric_shadows = True

            eevee.use_raytracing = True
            eevee.ray_tracing_options.resolution_scale = "1"
            eevee.ray_tracing_options.screen_trace_quality = 0.5

            eevee.fast_gi_step_count = 32
            eevee.fast_gi_quality = 0.5
            eevee.fast_gi_resolution = "1"

            self.use_bloom = True

            eevee.volumetric_tile_size = "2"
            eevee.volumetric_samples = 128

        if shading.render_pass != 'COMBINED':
            shading.render_pass = 'COMBINED'

        if self.eevee_passes_preset != 'COMBINED':
            self.avoid_update = True
            self.eevee_passes_preset = 'COMBINED'

        return

        if self.eevee_preset == 'NONE':
            eevee.use_ssr = False
            eevee.use_gtao = False
            eevee.use_bloom = False
            eevee.use_volumetric_lights = False

            if self.eevee_next_preset_set_use_scene_lights:
                shading.use_scene_lights = False

            if self.eevee_next_preset_set_use_scene_world:
                shading.use_scene_world = False

            if context.scene.render.engine == 'BLENDER_EEVEE':
                if self.eevee_next_preset_set_use_scene_lights:
                    shading.use_scene_lights_render = False

                if self.eevee_next_preset_set_use_scene_world:
                    shading.use_scene_world_render = False

        elif self.eevee_preset == 'LOW':
            eevee.use_ssr = True
            eevee.use_ssr_halfres = True
            eevee.use_ssr_refraction = False
            eevee.use_gtao = True
            eevee.use_bloom = False
            eevee.use_volumetric_lights = False

            if self.eevee_next_preset_set_use_scene_lights:
                shading.use_scene_lights = True

            if self.eevee_next_preset_set_use_scene_world:
                shading.use_scene_world = False

            if context.scene.render.engine == 'BLENDER_EEVEE':
                if self.eevee_next_preset_set_use_scene_lights:
                    shading.use_scene_lights_render = True

                if self.eevee_next_preset_set_use_scene_world:
                    shading.use_scene_world_render = False

        elif self.eevee_preset == 'HIGH':
            eevee.use_ssr = True
            eevee.use_ssr_halfres = False
            eevee.use_ssr_refraction = True
            eevee.use_gtao = True
            eevee.use_bloom = True
            eevee.use_volumetric_lights = False

            if self.eevee_next_preset_set_use_scene_lights:
                shading.use_scene_lights = True

            if self.eevee_next_preset_set_use_scene_world:
                shading.use_scene_world = False

            if context.scene.render.engine == 'BLENDER_EEVEE':
                if self.eevee_next_preset_set_use_scene_lights:
                    shading.use_scene_lights_render = True

                if self.eevee_next_preset_set_use_scene_world:
                    shading.use_scene_world_render = False

        elif self.eevee_preset == 'ULTRA':
            eevee.use_ssr = True
            eevee.use_ssr_halfres = False
            eevee.use_ssr_refraction = True
            eevee.use_gtao = True
            eevee.use_bloom = True
            eevee.use_volumetric_lights = True

            if self.eevee_next_preset_set_use_scene_lights:
                shading.use_scene_lights = True

            if context.scene.render.engine == 'BLENDER_EEVEE':
                if self.eevee_next_preset_set_use_scene_lights:
                    shading.use_scene_lights_render = True

            if self.eevee_next_preset_set_use_scene_lights:
                world = context.scene.world
                if world:
                    shading.use_scene_world = True

                    if context.scene.render.engine == 'BLENDER_EEVEE':
                        shading.use_scene_world_render = True

                    output = get_world_output(world)
                    links = output.inputs[1].links

                    if not links:
                        tree = world.node_tree

                        volume = tree.nodes.new('ShaderNodeVolumePrincipled')
                        tree.links.new(volume.outputs[0], output.inputs[1])

                        volume.inputs[2].default_value = 0.1
                        volume.location = (-200, 200)

    def update_eevee_passes_preset(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        eevee = context.scene.eevee
        shading = context.space_data.shading

        if self.eevee_passes_preset == 'COMBINED':
            shading.render_pass = 'COMBINED'

        elif self.eevee_passes_preset == 'SHADOW':
            shading.render_pass = 'SHADOW'

            if not eevee.use_shadows:
                eevee.use_shadows = True

            if self.eevee_next_preset != 'NONE':
                self.avoid_update = True
                self.eevee_next_preset = 'NONE'

            if shading.use_compositor != 'DISABLED':
                shading.use_compositor = 'DISABLED'

        elif self.eevee_passes_preset == 'AO':
            shading.render_pass = 'AO'

            if self.eevee_next_preset != 'NONE':
                self.avoid_update = True
                self.eevee_next_preset = 'NONE'

            if shading.use_compositor != 'DISABLED':
                shading.use_compositor = 'DISABLED'

    def update_eevee_next_resolution(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        eevee = context.scene.eevee

        eevee.ray_tracing_options.resolution_scale = self.eevee_next_resolution
        eevee.fast_gi_resolution = self.eevee_next_resolution

    def update_eevee_next_thickness(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        eevee = context.scene.eevee

        eevee.ray_tracing_options.screen_trace_thickness = self.eevee_next_thickness
        eevee.fast_gi_thickness_near = self.eevee_next_thickness

    def update_eevee_next_quality(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        eevee = context.scene.eevee

        eevee.ray_tracing_options.screen_trace_quality = self.eevee_next_quality
        eevee.fast_gi_quality = self.eevee_next_quality

    eevee_next_preset: EnumProperty(name="Eevee Preset", description="Eevee Quality Presets", items=eevee_next_preset_items, default='NONE', update=update_eevee_next_preset)
    eevee_passes_preset: EnumProperty(name="Eevee Passes Preset", description="Eevee Passes Presets", items=eevee_passes_preset_items, default='COMBINED', update=update_eevee_passes_preset)
    eevee_next_preset_set_use_scene_lights: BoolProperty(name="Set Use Scene Lights", description="Set Use Scene Lights when changing Eevee Preset", default=False)
    eevee_next_preset_set_use_scene_world: BoolProperty(name="Set Use Scene World", description="Set Use Scene World when changing Eevee Preset", default=False)
    eevee_next_resolution: EnumProperty(name="Eevee Thickness", description="Eevee Ray-Trace and Fast GI Resolution", items=eevee_next_raytrace_resolution_items, default="2", update=update_eevee_next_resolution)
    eevee_next_thickness: FloatProperty(name="Eevee Thickness", description="Eevee Screen-Trace Thickness + Fast GI Near Thickness", unit='LENGTH', update=update_eevee_next_thickness, min=0)
    eevee_next_quality: FloatProperty(name="Eevee Precision", description="Eevee Screen-Trace Precision + Fast GI Precision", update=update_eevee_next_quality)

    def update_use_volumes(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        debug = False

        data = is_volume(context, simple=False, debug=False)

        dprint("toggling volumes to:", self.use_volumes, debug=debug)
        dprintd(data, debug=False)

        if self.use_volumes:
            dprint("enabling volumes", debug=debug)

            if node := data['world_volume']:
                dprint(" enabling world volume", debug=debug)

                if not data['use_world']:
                    set_use_world(context, True)

                if node.mute:
                    node.mute = False

            if data['volume_objects']:
                dprint(" enabling object volume", debug=debug)
                context.space_data.show_object_viewport_volume = True

            if not data['world_volume']:
                dprint(" attempting volumetric world setup", debug=debug)
                bpy.ops.machin3.setup_volumetric_world('INVOKE_DEFAULT')

        else:
            dprint("disabling volumes", debug=debug)

            if data['is_world_volume']:
                dprint(" disabling world volume", debug=debug)

                node = data['world_volume']
                node.mute = True

                if is_volume_only_world(context.scene.world):
                    dprint(" disabling use_world too, as world appears to be volume only", debug=debug)
                    set_use_world(context, False)

            if data['is_object_volume']:
                context.space_data.show_object_viewport_volume = False

    def update_use_bloom(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        shading = context.space_data.shading
        scene = context.scene

        if self.use_bloom:
            if shading.use_compositor != 'ALWAYS':
                shading.use_compositor = 'ALWAYS'

            if not scene.use_nodes:
                scene.use_nodes = True

            tree, input, output = ensure_composite_input_and_output(scene)

            glare = get_composite_glare(scene, glare_type="BLOOM", force=True)

            if glare.mute:
                glare.mute = False

            if (disp := get_composite_dispersion(scene, force=False)) and disp.mute:
                disp.mute = False

                if not self.use_dispersion:
                    self.avoid_update = True
                    self.use_dispersion = True

        else:
            glare = get_composite_glare(scene, glare_type="BLOOM")

            if glare:
                glare.mute = True

            if self.use_dispersion:
                self.use_dispersion = False

    def update_use_dispersion(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        shading = context.space_data.shading
        scene = context.scene

        if self.use_dispersion:
            if shading.use_compositor != 'ALWAYS':
                shading.use_compositor = 'ALWAYS'

            if not scene.use_nodes:
                scene.use_nodes = True

            tree, input, output = ensure_composite_input_and_output(scene)

            disp = get_composite_dispersion(scene, force=True)

            if disp.mute:
                disp.mute = False

        else:
            disp = get_composite_dispersion(scene)

            if disp:
                disp.mute = True

    use_volumes: BoolProperty(name="Use Volumes", default=False, description="Toggle Volume Rendering\n\n Object Volumes are toggled by filtering them in the viewport\n World Volume is toggled by (un)muting the Volume node\n\nWithout Object Volumes and without a World Volume present, enabling this will set up a World Volume\nHold SHIFT to force set up a World Volume, even though Object Volumes are present", update=update_use_volumes)
    use_bloom: BoolProperty(name="Use Bloom", default=False, description="Toggle Bloom Post Effect", update=update_use_bloom)
    use_dispersion: BoolProperty(name="Use Dispersion", default=False, description="Toggle Dispersion Post Effect", update=update_use_dispersion)

    adjust_lights_on_render: BoolProperty(name="Adjust Lights when Rendering", description="Adjust Lights Area Lights when Rendering, to better match Eevee and Cycles", default=False)
    adjust_lights_on_render_divider: FloatProperty(name="Divider used to calculate Cycles Light Strength from Eeeve Light Strength", default=4, min=1)
    adjust_lights_on_render_last: StringProperty(name="Last Light Adjustment", default='NONE')
    is_light_decreased_by_handler: BoolProperty(name="Have Lights been decreased by the init render handler?", default=False)

    def update_render_engine(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        set_render_engine(context, self.render_engine)

        if get_prefs().activate_render and get_prefs().activate_shading_pie and get_prefs().render_adjust_lights_on_render and get_area_light_poll() and self.adjust_lights_on_render:
            last = self.adjust_lights_on_render_last

            debug = False

            if last in ['NONE', 'INCREASE'] and is_cycles(context):
                self.adjust_lights_on_render_last = 'DECREASE'

                if debug:
                    print("decreasing on switch to cycies engine")

                adjust_lights_for_rendering(mode='DECREASE')

            elif last == 'DECREASE' and is_eevee(context):
                self.adjust_lights_on_render_last = 'INCREASE'

                if debug:
                    print("increasing on switch to eevee engine")

                adjust_lights_for_rendering(mode='INCREASE')

        if get_prefs().activate_render and get_prefs().render_sync_light_visibility:
            sync_light_visibility(context.scene)

        if get_prefs().activate_render and get_prefs().activate_shading_pie and get_prefs().render_use_bevel_shader and self.use_bevel_shader:
            if context.scene.render.engine == 'CYCLES':
                adjust_bevel_shader(context)

    def update_cycles_device(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        set_device(context, self.cycles_device)

    render_engine: EnumProperty(name="Render Engine", description="Render Engine", items=render_engine_items, default='BLENDER_EEVEE_NEXT', update=update_render_engine)
    cycles_device: EnumProperty(name="Render Device", description="Render Device", items=cycles_device_items, default='CPU', update=update_cycles_device)

    def update_enforce_hide_render(self, context):
        from . ui.operators import shading

        for _, name in shading.render_visibility:
            obj = bpy.data.objects.get(name)

            if obj:
                obj.hide_set(obj.visible_get())

    enforce_hide_render: BoolProperty(name="Enforce hide_render setting when Viewport Rendering", description="Enfore hide_render setting for objects when Viewport Rendering", default=True, update=update_enforce_hide_render)

    def update_use_bevel_shader(self, context):
        adjust_bevel_shader(context)

    def update_bevel_shader(self, context):
        if self.use_bevel_shader:
            adjust_bevel_shader(context)

    use_bevel_shader: BoolProperty(name="Use Bevel Shader", description="Batch Apply Bevel Shader to visible Materials", default=False, update=update_use_bevel_shader)
    bevel_shader_use_dimensions: BoolProperty(name="Consider Object Dimensions for Bevel Radius Modulation", description="Consider Object Dimensions for Bevel Radius Modulation", default=True, update=update_bevel_shader)
    bevel_shader_samples: IntProperty(name="Samples", description="Bevel Shader Samples", default=16, min=2, max=32, update=update_bevel_shader)
    bevel_shader_radius: FloatProperty(name="Radius", description="Bevel Shader Global Radius", default=0.015, min=0, precision=3, step=0.01, update=update_bevel_shader)

    def update_custom_views_local(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.custom_views_local and self.custom_views_cursor:
            self.avoid_update = True
            self.custom_views_cursor = False

        context.space_data.overlay.show_ortho_grid = not self.custom_views_local

        if get_prefs().custom_views_use_trackball:
            context.preferences.inputs.view_rotate_method = 'TRACKBALL' if self.custom_views_local else 'TURNTABLE'

        if get_prefs().activate_transform_pie and get_prefs().custom_views_set_transform_preset:
            bpy.ops.machin3.set_transform_preset(pivot='MEDIAN_POINT', orientation='LOCAL' if self.custom_views_local else 'GLOBAL')

    def update_custom_views_cursor(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.custom_views_cursor and self.custom_views_local:
            self.avoid_update = True
            self.custom_views_local = False

        context.space_data.overlay.show_ortho_grid = not self.custom_views_cursor

        if get_prefs().custom_views_use_trackball:
            context.preferences.inputs.view_rotate_method = 'TRACKBALL' if self.custom_views_cursor else 'TURNTABLE'

        if 'machin3.tool_hyper_cursor' not in get_active_tool(context).idname:

            if get_prefs().activate_transform_pie and get_prefs().custom_views_set_transform_preset:
                bpy.ops.machin3.set_transform_preset(pivot='CURSOR' if self.custom_views_cursor else 'MEDIAN_POINT', orientation='CURSOR' if self.custom_views_cursor else 'GLOBAL')

    custom_views_local: BoolProperty(name="Custom Local Views", description="Use Custom Views, based on the active object's orientation", default=False, update=update_custom_views_local)
    custom_views_cursor: BoolProperty(name="Custom Cursor Views", description="Use Custom Views, based on the cursor's orientation", default=False, update=update_custom_views_cursor)

    align_mode: EnumProperty(name="Align Mode", items=align_mode_items, default="VIEW")

    driver_start: FloatProperty(name="Driver Start Value", precision=3)
    driver_end: FloatProperty(name="Driver End Value", precision=3)
    driver_axis: EnumProperty(name="Driver Axis", items=axis_items, default='X')
    driver_transform: EnumProperty(name="Driver Transform", items=driver_transform_items, default='LOCATION')
    driver_space: EnumProperty(name="Driver Space", items=driver_space_items, default='AUTO')
    driven_start: FloatProperty(name="Driven Start Value", precision=3)
    driven_end: FloatProperty(name="Driven End Value", precision=3)
    driven_axis: EnumProperty(name="Driven Axis", items=axis_items, default='X')
    driven_transform: EnumProperty(name="Driven Transform", items=driver_transform_items, default='LOCATION')
    driven_limit: EnumProperty(name="Driven Lmit", items=driver_limit_items, default='BOTH')

    def update_unity_export_path(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        path = self.unity_export_path

        if path:
            if not path.endswith('.fbx'):
                path += '.fbx'

            self.avoid_update = True
            self.unity_export_path = abspath(path)

    unity_export: BoolProperty(name="Export to Unity", description="Enable to do the actual FBX export\nLeave it off to only prepare the Model")
    unity_export_path: StringProperty(name="Unity Export Path", subtype='FILE_PATH', update=update_unity_export_path)
    unity_triangulate: BoolProperty(name="Triangulate before exporting", description="Add Triangulate Modifier to the end of every object's stack", default=False)

    def update_bcorientation(self, context):
        from . import MACHIN3toolsManager as M3

        if M3.get_addon("BoxCutter"):
            bcprefs = get_addon_prefs('BoxCutter')

            if self.bcorientation == 'LOCAL':
                bcprefs.behavior.orient_method = 'LOCAL'
            elif self.bcorientation == 'NEAREST':
                bcprefs.behavior.orient_method = 'NEAREST'
            elif self.bcorientation == 'LONGEST':
                bcprefs.behavior.orient_method = 'TANGENT'

    bcorientation: EnumProperty(name="BoxCutter Orientation", items=bc_orientation_items, default='LOCAL', update=update_bcorientation)

    def update_group_select(self, context):
        if not self.group_select:
            all_empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]
            top_level = [obj for obj in all_empties if obj.parent not in all_empties]

            for obj in context.selected_objects:
                if obj not in top_level:
                    obj.select_set(False)

    def update_group_recursive_select(self, context):
        if not self.group_recursive_select:
            all_empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]
            top_level = [obj for obj in all_empties if obj.parent not in all_empties]

            for obj in context.selected_objects:
                if obj not in top_level:
                    obj.select_set(False)

    def update_group_hide(self, context):
        empties = [obj for obj in context.visible_objects if obj.M3.is_group_empty]

        for e in empties:
            if e == context.active_object or not context.scene.M3.group_hide:
                e.show_name = True
                e.empty_display_size = e.M3.group_size

            else:
                e.show_name = False

                if round(e.empty_display_size, 4) != 0.0001:
                    e.M3.group_size = e.empty_display_size

                e.empty_display_size = 0.0001

    def update_group_origin_mode(self, context):
        if self.group_origin_mode:
            init_group_origin_adjustment(context)

        else:
            finish_group_origin_adjustment(context)

    show_group_gizmos: BoolProperty(name="Show Group Gizmos", description="Toggle Group Gizmos Globally", default=True)
    group_select: BoolProperty(name="Auto Select Groups", description="Automatically select the entire Group, when its Empty is made active", default=True, update=update_group_select)
    group_recursive_select: BoolProperty(name="Recursively Select Groups", description="Recursively select entire Group Hierarchies down", default=True, update=update_group_recursive_select)
    group_hide: BoolProperty(name="Hide Group Empties in 3D View", description="Hide Group Empties in 3D View to avoid Clutter", default=True, update=update_group_hide)
    show_group_select: BoolProperty(name="Show Auto Select Toggle in main Object Context Menu", default=True)
    show_group_recursive_select: BoolProperty(name="Show Recursive Selection Toggle in main Object Context Menu", default=True)
    show_group_hide: BoolProperty(name="Show Group Hide Toggle in main Object Context Menu", default=True)
    group_origin_mode: BoolProperty(name="Transform only the Group Origin(Empty)", description='Transform the Group Origin(Empty) only, disable Group Auto-Select and enable "affect Parents only"', default=False, update=update_group_origin_mode)
    draw_group_relations: BoolProperty(name="Draw Group Relations", description="Draw Group Relationships and Origins", default=False)
    draw_group_relations_active_only: BoolProperty(name="Draw Active's Group Relations Only", description="Draw Active's Group Relationships and Origins only", default=False)
    draw_group_relations_objects: BoolProperty(name="Draw Group Relationships to Group Objects too", default=False)

    def update_group_gizmo_size(self, context):
        force_ui_update(context)

    group_gizmo_size: FloatProperty(name="Global Group Gizmo Size", description="Global Group Gizmo Size", default=1, min=0.01, update=update_group_gizmo_size)

    asset_collect_path: StringProperty(name="Collect Path", subtype="DIR_PATH", default="")
    is_assembly_edit_scene: BoolProperty(name="is Assembly Edit Scene", default=False)
    assembly_edit_collection: PointerProperty(name="Assembly Edit Collection", type=bpy.types.Collection)
    assembly_edit_init_scene: PointerProperty(name="Assembly Edit Initial Scence", type=bpy.types.Scene)
    assembly_edit_delta_view_mx: FloatVectorProperty(name="Assemlby Edit Delta Viewmx", subtype="MATRIX", size=(4, 4))

    avoid_update: BoolProperty()

class M3ObjectProperties(bpy.types.PropertyGroup):
    unity_exported: BoolProperty(name="Exported to Unity")

    pre_unity_export_mx: FloatVectorProperty(name="Pre-Unity-Export Matrix", subtype="MATRIX", size=16, default=flatten_matrix(Matrix()))
    pre_unity_export_mesh: PointerProperty(name="Pre-Unity-Export Mesh", type=bpy.types.Mesh)
    pre_unity_export_armature: PointerProperty(name="Pre-Unity-Export Armature", type=bpy.types.Armature)

    is_group_empty: BoolProperty(name="is group empty", default=False)
    is_group_object: BoolProperty(name="is group object", default=False)
    is_group_anchor: BoolProperty(name="is group anchor", default=False)
    group_size: FloatProperty(name="group empty size", default=0.2, min=0)
    if True:

        def update_show_group_gizmo(self, context):
            if self.avoid_update:
                self.avoid_update = False
                return

            if self.update_show_group_gizmo and not any([self.show_group_x_rotation, self.show_group_y_rotation, self.show_group_z_rotation]):
                self.show_group_x_rotation = True

            force_ui_update(context)

        def update_show_rotation(self, context):
            if any([self.show_group_x_rotation, self.show_group_y_rotation, self.show_group_z_rotation]) and not self.show_group_gizmo:
                self.avoid_update = True
                self.show_group_gizmo = True

            if not any([self.show_group_x_rotation, self.show_group_y_rotation, self.show_group_z_rotation]) and self.show_group_gizmo:
                self.avoid_update = True
                self.show_group_gizmo = False

            force_ui_update(context)

        def update_group_gizmo_size(self, context):
            force_ui_update(context)

        show_group_gizmo: BoolProperty(name="Toggle Local Group Gizmo", default=False, update=update_show_group_gizmo)
        show_group_x_rotation: BoolProperty(name="Show X Rotation Gizmo", default=False, update=update_show_rotation)
        show_group_y_rotation: BoolProperty(name="Show Y Rotation Gizmo", default=False, update=update_show_rotation)
        show_group_z_rotation: BoolProperty(name="Show Z Rotation Gizmo", default=False, update=update_show_rotation)
        group_gizmo_size: FloatProperty(name="Group Gizmo Size", default=1, min=0.1, update=update_group_gizmo_size)

        def update_group_pose_alpha(self, context):
            if self.avoid_update:
                self.avoid_update = False
                return

            empty = self.id_data

            propagate_pose_preview_alpha(empty)

        group_rest_pose: FloatVectorProperty(name="Group Rest Post Matrix", subtype="MATRIX", size=(4, 4))  # NOTE: legacy as of verison 1.7, but keep it around for legacy updates
        group_pose_COL: CollectionProperty(type=GroupPoseCollection)
        group_pose_IDX: IntProperty(name="Pose Name", description="Double Click to Rename", default=-1)
        group_pose_alpha: FloatProperty(name="Pose Preview Alpha", description="Alpha used to preview Poses across the entire Group", min=0.01, max=1, default=0.5, step=0.1, update=update_group_pose_alpha)
        draw_active_group_pose: BoolProperty(description="Draw a Preview of the Active Pose")

    smooth_angle: FloatProperty(name="Smooth Angle", default=30)
    has_smoothed: BoolProperty(name="Has been smoothed", default=False)

    draw_axes: BoolProperty(name="Draw Axes", default=False)

    def update_bevel_shader_radius_mod(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        from . import MACHIN3toolsManager as M3

        if M3.get_addon("DECALmachine"):
            obj = self.id_data

            panel_children = [obj for obj in obj.children if is_decal(obj) and obj.DM.decaltype == 'PANEL']

            for c in panel_children:
                c.M3.avoid_update = True
                c.M3.bevel_shader_radius_mod = obj.M3.bevel_shader_radius_mod

                if c.M3.bevel_shader_toggle != obj.M3.bevel_shader_toggle:
                    c.M3.avoid_update = True
                    c.M3.bevel_shader_toggle = obj.M3.bevel_shader_toggle

    bevel_shader_toggle: BoolProperty(name="Active Object Bevel Toggle", description="Toggle Bevel Shader on Active Object", default=True, update=update_bevel_shader_radius_mod)
    bevel_shader_radius_mod: FloatProperty(name="Active Object Bevel Radius Modulation", description="Factor to modulate the Bevel Shader Radius on the Active Object", default=1, min=0, precision=2, step=0.1, update=update_bevel_shader_radius_mod)
    bevel_shader_dimensions_mod: FloatProperty(name="Active Object Bevel Radius Modulation", description="Factor to modulate the Bevel Shader Radius on the Active Object", default=1, min=0, precision=2, step=0.1)

    dup_hash: StringProperty(description="Hash to find associated objects")

    asset_version: StringProperty(default="1.0")
    hide: BoolProperty(description="Custom Hide prop set in CreateAssemblyAsset, because and objects original visibility gets lost once you drop an asset into a scene")
    hide_viewport: BoolProperty(description="Custom Hide Viewport prop set in CreateAssemblyAsset, because we disable this for some objects in the assets collection, but want to get the original state back when disassembling")

    if True:
        def update_use_asset_thumbnail_helper(self, context):
            if self.use_asset_thumbnail_helper:
                bpy.ops.machin3.update_asset_thumbnail(setup_bbox_helper=True, is_prop_invoke=True)

        use_asset_thumbnail_helper: BoolProperty(name="Toggle Asset Thumbnail Helper", description="Thumbnail Framing is done based on an Selection's BBox and can be imperfect, depending on a number of factors, such as Object Rotation or use of Modifiers like Mirror and Array.\nThe Thumbnail Helper Gizmo can be used to fine-tune and adjust the Framing exactly as needed.", default=False, update=update_use_asset_thumbnail_helper)
        asset_thumbnail_helper_location_offset: FloatVectorProperty(name="Asset Thumbnail Helper Location Offset", subtype="TRANSLATION")
        asset_thumbnail_helper_rotation: FloatVectorProperty(name="Asset Thumbnail Helper Rotation", subtype="QUATERNION", size=4)

        asset_thumbnail_helper_matrix: FloatVectorProperty(name="Asset Thumbnail Helper Matrix", subtype="MATRIX", size=(4, 4), default=Matrix())

    avoid_update: BoolProperty()

class M3CollectionProperties(bpy.types.PropertyGroup):
    is_asset_collection: BoolProperty()
