import bpy
from bpy.props import BoolProperty
from mathutils import Matrix, Quaternion, Vector
from .. utils.registration import get_addon

hypercursor = None

class AddSinglePointPOLYCurve(bpy.types.Operator):
    bl_idname = "machin3.add_single_point_poly_curve"
    bl_label = "MACHIN3: Add Single Point Poly Curve"
    bl_description = "Add single-point POLY curve at Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    align_rotation: BoolProperty(name="Align to Cursor Rotation", default=True)
    def draw(self, context):
        layout = self.layout
        column = layout.column()

        column.prop(self, 'align_rotation', toggle=True)

    def execute(self, context):
        global hypercursor

        if hypercursor is None:
            hypercursor = get_addon('HyperCursor')[0]

        bpy.ops.object.select_all(action='DESELECT')

        mcol = context.scene.collection
        cmx = context.scene.cursor.matrix

        curve = bpy.data.curves.new(name="Curve", type='CURVE')
        curve.dimensions = '3D'
        curve.use_fill_caps = True

        spline = curve.splines.new('POLY')

        point = spline.points[0]
        point.co = Vector((0, 0, 0, 1))

        point.select = True

        obj = bpy.data.objects.new(name="Curve", object_data=curve)

        if hypercursor:
            obj.HC.ishyper = True

        mcol.objects.link(obj)

        if self.align_rotation:
            obj.matrix_world = cmx

        else:
            loc, _, _ = cmx.decompose()
            obj.matrix_world = Matrix.LocRotScale(loc, Quaternion(), Vector((1, 1, 1)))

        obj.select_set(True)
        context.view_layer.objects.active = obj

        bpy.ops.object.mode_set(mode='EDIT')
        
        return {'FINISHED'}
