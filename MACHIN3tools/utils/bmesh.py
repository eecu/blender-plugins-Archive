from mathutils import Matrix

def ensure_custom_data_layers(bm, vertex_groups=True, bevel_weights=True, crease=True):

    vert_vg_layer = bm.verts.layers.deform.verify() if vertex_groups else None

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

    return [layer for layer in [vert_vg_layer, edge_bw_layer, edge_crease_layer] if layer is not None]

def get_loop_triangles(bm, faces=None):
    if faces:
        return [lt for lt in bm.calc_loop_triangles() if lt[0].face in faces]
    return bm.calc_loop_triangles()

def get_tri_coords(loop_triangles, faces, mx=Matrix()):
    return [mx @ l.vert.co for tri in loop_triangles if tri[0].face in faces for l in tri]
