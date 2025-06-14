import bpy

from mathutils import Vector, Quaternion

def create_scene(context, name="Scene", inherit=True, ensure_user=True):
    if inherit:
        scene = context.scene.copy()
        scene.name = name

        for col in scene.collection.children:
            scene.collection.children.unlink(col)

        for obj in scene.collection.objects:
            scene.collection.objects.unlink(obj)

    else:
        scene = bpy.data.scenes.new(name)

    if ensure_user:
        ensure_compositor_nodes(scene)

    return scene

def ensure_compositor_nodes(scene, use_nodes=False):
    tree, input, output = ensure_composite_input_and_output(scene)

    if input.scene != scene:
        input.scene = scene

    scene.use_nodes = use_nodes

def set_cursor(matrix=None, location=Vector(), rotation=Quaternion()):
    cursor = bpy.context.scene.cursor

    if matrix:
        cursor.location = matrix.to_translation()
        cursor.rotation_quaternion = matrix.to_quaternion()
        cursor.rotation_mode = 'QUATERNION'

    else:
        cursor.location = location

        if cursor.rotation_mode == 'QUATERNION':
            cursor.rotation_quaternion = rotation

        elif cursor.rotation_mode == 'AXIS_ANGLE':
            cursor.rotation_axis_angle = rotation.to_axis_angle()

        else:
            cursor.rotation_euler = rotation.to_euler(cursor.rotation_mode)

def get_composite_output(scene):
    if not scene.use_nodes:
        scene.use_nodes = True

    output = scene.node_tree.nodes.get('Composite')

    if not output:
        for node in scene.node_tree.nodes:
            if node.type == 'COMPOSITE':
                return node

    return output

def get_composite_input(scene):
    if not scene.use_nodes:
        scene.use_nodes = True

    input = scene.node_tree.nodes.get('Render Layers')

    if not input:
        for node in scene.node_tree.nodes:
            if node.type == 'R_LAYERS':
                return node

    return input

def get_composite_glare(scene, glare_type='BLOOM', force=False):
    if not scene.use_nodes:
        scene.use_nodes = True

    for node in scene.node_tree.nodes:
        if node.type == 'GLARE' and node.glare_type == glare_type:
            return node

    if force:
        glare = scene.node_tree.nodes.new('CompositorNodeGlare')
        glare.name = glare_type.title()
        glare.label = glare_type.title()
        glare.glare_type = glare_type
        glare.size = 6

        output = get_composite_output(scene)

        if output and (links := output.inputs[0].links):
            preceding = links[0].from_node

            glare.location = (preceding.location + output.location) / 2

            tree = scene.node_tree
            tree.links.new(links[0].from_socket, glare.inputs[0])
            tree.links.new(glare.outputs[0], output.inputs[0])

        return glare

def get_composite_dispersion(scene, force=False):
    if not scene.use_nodes:
        scene.use_nodes = True

    for node in scene.node_tree.nodes:
        if node.type == 'LENSDIST' and node.name == "Dispersion":
            return node

    if force:
        disp = scene.node_tree.nodes.new('CompositorNodeLensdist')
        disp.name = "Dispersion"
        disp.label = "Dispersion"
        disp.inputs[2].default_value = 0.02
        output = get_composite_output(scene)

        if output and (links := output.inputs[0].links):
            preceding = links[0].from_node

            disp.location = (preceding.location + output.location) / 2

            tree = scene.node_tree
            tree.links.new(links[0].from_socket, disp.inputs[0])
            tree.links.new(disp.outputs[0], output.inputs[0])

        return disp

def ensure_composite_input_and_output(scene):
    output = get_composite_output(scene)
    input = get_composite_input(scene)

    tree = scene.node_tree

    if not output and not input:
        output = tree.nodes.new('CompositorNodeComposite')
        output.location.x = 1200
        output.location.y = 350

        input = tree.nodes.new('CompositorNodeRLayers')
        input.location.y = 350

        tree.links.new(input.outputs[0], output.inputs[0])

    elif not output:
        output = tree.nodes.new('CompositorNodeComposite')
        output.location.x = 1200
        output.location.y = 350

        tree.links.new(input.outputs[0], output.inputs[0])

    elif not input:
        input = tree.nodes.new('CompositorNodeRLayers')
        input.location.y = 350

        tree.links.new(input.outputs[0], output.inputs[0])

    return tree, input, output

def is_bloom(context, simple=True):
    view = context.space_data
    shading = view.shading
    scene = context.scene

    if scene.use_nodes:
        if shading.use_compositor =='ALWAYS' or (view.region_3d.view_perspective == 'CAMERA' and shading.use_compositor == 'CAMERA'):
            glare_nodes = [node for node in scene.node_tree.nodes if node.type == 'GLARE' and node.glare_type == 'BLOOM']
            is_bloom = bool(glare_nodes and not glare_nodes[0].mute)

            if simple:
                return is_bloom

            disp_nodes = [node for node in scene.node_tree.nodes if node.type == 'LENSDIST' and node.name == 'Dispersion']
            is_disp = bool(disp_nodes and not disp_nodes[0].mute)

            return {'is_bloom': is_bloom,
                    'is_dispersion': is_disp}

    if simple:
        return False
    else:
        return {'is_bloom': False,
                'is_dispersion': False}
