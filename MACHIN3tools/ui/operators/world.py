import bpy
from ... utils.render import is_volume
from ... utils.world import get_world_output, set_use_world

class AddWorld(bpy.types.Operator):
    bl_idname = "machin3.add_world"
    bl_label = "MACHIN3: Add World"
    bl_description = "Add new World"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.scene:
            return not context.scene.world

    def execute(self, context):

        if bpy.data.worlds:
            context.scene.world = bpy.data.worlds[0]

        else:
            world = bpy.data.worlds.new(name="World")
            world.use_nodes = True
            context.scene.world = world

        return {'FINISHED'}

class SetupVolumetricWorld(bpy.types.Operator):
    bl_idname = "machin3.setup_volumetric_world"
    bl_label = "MACHIN3: Setup Volumetric World"
    bl_description = "Setup Volumetric World"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.area and context.area.type == 'VIEW_3D':
            return context.space_data and context.space_data.shading.type in ['MATERIAL', 'RENDERED']

    def invoke(self, context, event):
        data = is_volume(context, simple=False)

        if data['world_volume']:
            return {'CANCELLED'}

        if data['volume_objects'] and not event.shift:
            return {'CANCELLED'}

        if not (world := context.scene.world):
            world = bpy.data.worlds.new(name="Volumetric World")
            context.scene.world = world

        if not world.use_nodes:
            world.use_nodes = True

        output = get_world_output(world)

        if output:
            tree = world.node_tree

            volume = tree.nodes.new('ShaderNodeVolumePrincipled')
            volume.location = (-90, 100)

            volume.inputs[0].default_value = (0.440198, 0.545031, 1.000000, 1.000000)   # color
            volume.inputs[2].default_value = 0.04                                       # density
            volume.inputs[6].default_value = 0.02                                       # emission strength
            volume.inputs[7].default_value = (0.193403, 0.204471, 0.287355, 1.000000)   # emission color
            tree.links.new(volume.outputs[0], output.inputs[1])

            set_use_world(context, True)

        return {'FINISHED'}
