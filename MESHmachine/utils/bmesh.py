import bpy

def ensure_custom_data_layers(bm, vertex_groups=True, bevel_weights=True, crease=True):

    vert_vg_layer = bm.verts.layers.deform.verify() if vertex_groups else None
    if bpy.app.version >= (4, 0, 0):

        if bevel_weights:
            edge_bw_layer = bm.edges.layers.float.get('bevel_weight_edge')

            if not edge_bw_layer:
                edge_bw_layer = bm.edges.layers.float.new('bevel_weight_edge')
        else:
            edge_bw_layer = None

        if crease:
            edge_crease_layer = bm.edges.layers.float.get('crease_edge')

            if not edge_crease_layer:
                edge_crease_layer = bm.edges.layers.float.new('crease_edge')
        else:
            edge_crease_layer = None
    else:
        edge_bw_layer = bm.edges.layers.bevel_weight.verify() if bevel_weights else None
        edge_crease_layer = bm.edges.layers.crease.verify() if crease else None

    return [layer for layer in [vert_vg_layer, edge_bw_layer, edge_crease_layer] if layer is not None]

def loop_index_update(bm, debug=False):
    lidx = 0
    for f in bm.faces:
        if debug:
            print(f)
        for l in f.loops:
            l.index = lidx
            lidx += 1
            if debug:
                print(" •", l)
