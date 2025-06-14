import bpy
from mathutils import Matrix
from math import radians

from .. utils.registration import get_prefs
from .. utils.workspace import is_3dview

from .. colors import yellow

class GizmoGroupGroupTransform(bpy.types.GizmoGroup):
    bl_idname = "MACHIN3_GGT_group_transform"
    bl_label = "Group Transform Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'SCALE', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        if get_prefs().activate_group_tools:
            if context.mode == 'OBJECT':
                if context.scene.M3.show_group_gizmos:
                    return [obj for obj in context.visible_objects if obj.M3.is_group_empty and obj.M3.show_group_gizmo]

    def setup(self, context):
        self.group_gizmos = self.create_group_empty_gizmos(context)

    def refresh(self, context):

        if not self.is_modal():
            self.gizmos.clear()
            self.group_gizmos = self.create_group_empty_gizmos(context)

    def draw_prepare(self, context):

        if self.is_modal():
            for gzm in self.gizmos:

                if gzm.is_modal:
                    gzm.line_width = 1
                    gzm.arc_inner_factor = 0.4
                    gzm.draw_options = {'ANGLE_VALUE'}

                else:
                    gzm.hide = True

        else:
            for name, axes in self.group_gizmos.items():
                for gzm in axes.values():
                    gzm.draw_options = {'CLIP' if len(axes.values()) > 1 else 'ANGLE_START_Y'}

    def is_modal(self):
        return any(gzm.is_modal for gzm in self.gizmos)

    def create_group_empty_gizmos(self, context):
        group_gizmos = {}

        group_empties = [obj for obj in context.visible_objects if obj.M3.is_group_empty and obj.M3.show_group_gizmo]

        for empty in group_empties:
            gizmos = {}

            for axis in self.get_group_axes(empty):
                gzm = self.create_rotation_gizmo(context, empty, axis=axis, scale=5, line_width=2, alpha=0.25, alpha_highlight=1, hover=False)

                gizmos[axis] = gzm

            group_gizmos[empty.name] = gizmos

        return group_gizmos

    def get_group_axes(self, group_empty):
        axes = []

        if group_empty.M3.show_group_x_rotation:
            axes.append('X')

        if group_empty.M3.show_group_y_rotation:
            axes.append('Y')

        if group_empty.M3.show_group_z_rotation:
            axes.append('Z')

        return axes

    def create_rotation_gizmo(self, context, empty, axis='Z', scale=5, line_width=2, alpha=0.5, alpha_highlight=1, hover=False):
        gzm = self.gizmos.new("GIZMO_GT_dial_3d")

        op = gzm.target_set_operator("machin3.transform_group")
        op.name = empty.name
        op.axis = axis

        gzm.matrix_basis = empty.matrix_world @ self.get_gizmo_rotation_matrix(axis)

        gzm.draw_options = {'ANGLE_START_Y'}
        gzm.use_draw_value = True
        gzm.use_draw_hover = hover

        gzm.line_width = line_width

        gzm.scale_basis = context.scene.M3.group_gizmo_size * empty.M3.group_size * empty.M3.group_gizmo_size * scale

        gzm.color = (1, 0.3, 0.3) if axis == 'X' else (0.3, 1, 0.3) if axis == 'Y' else (0.3, 0.3, 1)
        gzm.alpha = alpha
        gzm.color_highlight = (1, 0.5, 0.5) if axis == 'X' else (0.5, 1, 0.5) if axis == 'Y' else (0.5, 0.5, 1)
        gzm.alpha_highlight = alpha_highlight

        return gzm

    def get_gizmo_rotation_matrix(self, axis):
        if axis == 'X':
            return Matrix.Rotation(radians(90), 4, 'Y')

        if axis == 'Y':
            return Matrix.Rotation(radians(-90), 4, 'X')

        elif axis == 'Z':
            return Matrix()

class GizmoGroupAssetThumbnailHelper(bpy.types.GizmoGroup):
    bl_idname = "MACHIN3_GGT_asset_thumbnail_helper"
    bl_label = "Test Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and is_3dview(context):
            active = context.active_object

            if active and active.select_get():
                return active.M3.use_asset_thumbnail_helper

    def setup(self, context):
        self.obj = context.active_object if context.active_object and context.active_object.select_get() else None

        if self.obj:
            self.gzm = self.create_thumbnail_helper()

    def refresh(self, context):
        active = context.active_object if context.active_object and context.active_object.select_get() else None

        if self.obj != active:
            self.obj = active

            self.gizmos.clear()

            if self.obj:
                self.gzm = self.create_thumbnail_helper()

        if self.gzm and self.obj:
            loc, rot, sca = self.obj.matrix_world.decompose()
            self.gzm.matrix_basis = Matrix.LocRotScale(loc + self.obj.M3.asset_thumbnail_helper_location_offset, self.obj.M3.asset_thumbnail_helper_rotation, sca)

    def create_thumbnail_helper(self):
        self.gizmos.clear()

        gzm = self.gizmos.new("GIZMO_GT_cage_2d")

        gzm.draw_style = 'BOX'

        gzm.transform = {'TRANSLATE', 'SCALE'}

        gzm.use_draw_modal = True  # draw when dragging too
        gzm.use_draw_hover = False  # only draw when hovering

        gzm.color = (0.6, 0.6, 0.6)
        gzm.color_highlight = yellow

        gzm.alpha = 0.2
        gzm.alpha_highlight = 0.5

        loc, rot, sca = self.obj.matrix_world.decompose()
        gzm.matrix_basis = Matrix.LocRotScale(loc + self.obj.M3.asset_thumbnail_helper_location_offset, self.obj.M3.asset_thumbnail_helper_rotation, sca)

        gzm.target_set_prop("matrix", self.obj.M3, "asset_thumbnail_helper_matrix")
        return gzm
