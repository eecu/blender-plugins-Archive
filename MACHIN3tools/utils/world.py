from . view import get_shading_type
from . system import printd

def get_world_output(world):
    if not world.use_nodes:
        world.use_nodes = True

    output = world.node_tree.nodes.get('World Outputs')

    if not output:
        for node in world.node_tree.nodes:
            if node.type == 'OUTPUT_WORLD':
                return node

    return output

def get_world_surface_inputs(world, debug=False):
    
    output = get_world_output(world)

    if debug:
        print()
        print("output:", output)

    d = {}

    if output.inputs[0].links:
        node = output.inputs[0].links[0].from_node

        if debug:
            print("node", node, node.type)

        while node.type not in ['BACKGROUND', 'GROUP']:
            shader_inputs = [i for i in node.inputs if i.type == 'SHADER' and i.links]

            if shader_inputs:
                node = shader_inputs[0].links[0].from_node

                if debug:
                    print("going up: ", node, node.type)

            else:
                return

        if debug:
            print("supported node:", node.name, node.label, node.type)

        if node.type == 'BACKGROUND':
            color = node.inputs[0] if not node.inputs[0].links else None
            strength = node.inputs[1] if not node.inputs[1].links else None

            if color:
                d['Color'] =  color

            else:

                if node.inputs[0].links[0].from_node.type == "TEX_ENVIRONMENT":
                    img_node = node.inputs[0].links[0].from_node

                    if debug:
                        print("background's node has color input link with image node:", img_node)

                    if (links := img_node.inputs[0].links) and links[0].from_node.type == 'MAPPING':
                        mapping_node = links[0].from_node

                        if debug:
                            print("image node has mapping node connected", mapping_node)

                        if not mapping_node.inputs[2].links:
                            d['Rotation'] = mapping_node.inputs[2]

            if strength:
                d['Strength'] = strength

        elif node.type == 'GROUP':
            if node.name == 'Easy HDRI':
                for name in ['Sun Strength', 'Sky Strength', 'Custom Background', 'Solid Color', 'Rotation']:
                    i = node.inputs.get(name)

                    if i and not i.links:
                        d[name] = i

                    if name == 'Solid Color' and i and i.default_value is True:
                        i = node.inputs.get("Color")

                        if i and not i.links:
                            d['Color'] = i

                            break

            else:
                for name in ['Power', 'Multiply', 'Rotate Z', 'Rotation', 'Blur']:
                    i = node.inputs.get(name)

                    if i and not i.links:
                        d[name] = i

    if debug:
        printd(d)

    return d

def get_use_world(context):
    if (shading_type := get_shading_type(context)) == 'MATERIAL':
        return context.space_data.shading.use_scene_world

    elif shading_type == 'RENDERED':
        return context.space_data.shading.use_scene_world_render

def set_use_world(context, state):
    if (shading_type := get_shading_type(context)) == 'MATERIAL':
        context.space_data.shading.use_scene_world = state

    elif shading_type == 'RENDERED':
        context.space_data.shading.use_scene_world_render = state

def is_volume_only_world(world):
    output = get_world_output(world)

    if output:
        if links := output.inputs[0].links:
            node = links[0].from_node

            if node.type == 'BACKGROUND' and not any(i.links for i in node.inputs):
                return True

            elif is_image_world(world):
                return False

        else:
            return True

    return False

def is_image_world(world):
    output = get_world_output(world)

    if output and output.inputs[0].links:

        node = output.inputs[0].links[0].from_node
        nodes = [node]
        investigate = [node]

        while investigate:
            node = investigate.pop(0)

            links = [i.links[0] for i in node.inputs if i.links]

            for link in links:
                new_node = link.from_node

                if new_node not in nodes:

                    nodes.append(new_node)
                    investigate.append(new_node)

        if any(node.type in ['TEX_IMAGE', 'TEX_ENVIRONMENT'] for node in nodes):
            return True

        elif any(node.type == 'GROUP' and node.node_tree for node in nodes):
            groups = [node for node in nodes if node.type == 'GROUP' and node.node_tree]

            if any(node.type in ['TEX_IMAGE', 'TEX_ENVIRONMENT'] for group in groups for node in group.node_tree.nodes):
                return True
    return True
