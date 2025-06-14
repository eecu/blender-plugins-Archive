import bpy
from bpy.props import IntProperty, BoolProperty, EnumProperty

from .. items import quadsphere_unwrap_items
from .. import MACHIN3toolsManager as M3

class QuadSphere(bpy.types.Operator):
    bl_idname = "machin3.quadsphere"
    bl_label = "MACHIN3: Quadsphere"
    bl_description = "Create a Quadsphere"
    bl_options = {'REGISTER', 'UNDO'}

    subdivisions: IntProperty(name='Subdivisions', default=4, min=1, max=8)
    shade_smooth: BoolProperty(name="Shade Smooth", default=True)
    align_rotation: BoolProperty(name="Align Rotation", default=True)
    unwrap: EnumProperty(name="Unwrap", items=quadsphere_unwrap_items, default='CROSS')
    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Properties")

        column = box.column(align=True)
        row = column.row(align=True)

        row.prop(self, "subdivisions")
        row.prop(self, "shade_smooth", toggle=True)

        row = column.row(align=True)
        row.prop(self, "align_rotation", toggle=True)

        box = layout.box()
        box.label(text="Unwrap")
        box.active = self.unwrap != 'NONE'

        row = box.row(align=True)
        row.prop(self, "unwrap", expand=True)

    @classmethod
    def poll(cls, context):
        return context.mode in ['OBJECT', 'EDIT_MESH']

    def execute(self, context):
        M3.init_operator_defaults(self.bl_idname, self.properties, debug=False)
        bpy.ops.mesh.primitive_cube_add(align='CURSOR' if self.align_rotation else 'WORLD')

        mode = bpy.context.mode

        if mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='EDIT')

        if self.shade_smooth:
            bpy.ops.mesh.faces_shade_smooth()

        for sub in range(self.subdivisions):
            bpy.ops.mesh.subdivide(number_cuts=1, smoothness=1)
            bpy.ops.transform.tosphere(value=1)

        if self.unwrap == 'NONE':
            mesh = context.active_object.data

            while mesh.uv_layers:
                mesh.uv_layers.remove(mesh.uv_layers[0])

        else:
            self.unwrap_quadsphere(context)

        if mode == 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}

    def unwrap_quadsphere(self, context):
        if self.unwrap == 'CROSS':
            return

        elif self.unwrap == 'CUBIC':
            bpy.ops.uv.cube_project(cube_size=3.46402)
            bpy.ops.uv.pack_islands(scale=True, rotate=False, margin=0.001, shape_method='AABB')

        elif self.unwrap == 'CYLINDRICAL':
            bpy.ops.uv.cylinder_project(direction='ALIGN_TO_OBJECT', correct_aspect=True, clip_to_bounds=False, scale_to_bounds=True)

        elif self.unwrap == 'SPHERICAL':
            space_data = context.space_data
            r3d = space_data.region_3d

            init_persp = r3d.view_perspective
            init_viewmx = r3d.view_matrix.copy()

            bpy.ops.view3d.view_axis(type='TOP')

            if self.align_rotation:
                r3d.view_matrix = context.scene.cursor.matrix.inverted_safe()

            bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)

            bpy.ops.uv.sphere_project()

            r3d.view_perspective = init_persp
            r3d.view_matrix = init_viewmx
