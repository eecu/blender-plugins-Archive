from . bmesh import ensure_custom_data_layers

def get_wedge_data(context, index=None):
    import bmesh

    active = context.active_object

    if context.mode == 'OBJECT':
        bm = bmesh.new()
        bm.from_mesh(active.data)
        bm.edges.ensure_lookup_table()
        bw = ensure_custom_data_layers(bm)[1]

        edge = bm.edges[index]

    else:
        bm = bmesh.from_edit_mesh(active.data)

        bw = ensure_custom_data_layers(bm)[1]

        selected = [e for e in bm.edges if e.select]

        if len(selected) == 1:
            edge = selected[0]

        else:
            print("WARNING: One edge needs to be selected")
            return

    bm.faces.ensure_lookup_table()
    bm.normal_update()

    data = {'mx': active.matrix_world,

            'edge': None,
            'edge_sharp': False,
            'edge_bw': 0,
            'edge_coords': [],

            'side_faces': [],

            'end1': {'edge': {},
                     'other_edge': {},
                     'edge_coords': {},
                     'other_edge_coords': {},

                     'face': None,
                     'face_no': None,

                     'vert': None,
                     'vert_co': None
                     },
            'end2': {'edge': {},
                     'other_edge': {},
                     'edge_coords': {},
                     'other_edge_coords': {},

                     'face': None,
                     'face_no': None,

                     'vert': None,
                     'vert_co': None
                     },
            }

    side_faces = [f for f in edge.link_faces]

    if len(side_faces) == 2:
        end1_faces = [f for f in edge.verts[0].link_faces if f not in side_faces]
        end2_faces = [f for f in edge.verts[1].link_faces if f not in side_faces]

        end1_face = end1_faces[0] if len(end1_faces) == 1 else None
        end2_face = end2_faces[0] if len(end2_faces) == 1 else None

        if end1_face or end2_face:

            if end1_face:
                end1_vert = [v for v in edge.verts if v in end1_face.verts][0]

                end1_edge = [e for e in end1_vert.link_edges if e != edge and e in side_faces[0].edges][0]
                end1_other_edge = [e for e in end1_vert.link_edges if e != edge and e != end1_edge][0]

            if end2_face:
                end2_vert = [v for v in edge.verts if v in end2_face.verts][0]

                end2_edge = [e for e in end2_vert.link_edges if e != edge and e in side_faces[0].edges][0]
                end2_other_edge = [e for e in end2_vert.link_edges if e != edge and e != end2_edge][0]

            data['edge'] = edge.index
            data['edge_sharp'] = not edge.smooth
            data['edge_bw'] = edge[bw]
            data['edge_coords'] = [v.co.copy() for v in edge.verts]

            data['side_faces'] = [f.index for f in side_faces]

            if end1_face:
                data['end1']['face'] = end1_face.index
                data['end1']['face_no'] = end1_face.normal.copy()

                data['end1']['vert'] = end1_vert.index
                data['end1']['vert_co'] = end1_vert.co.copy()

                for idx, face in enumerate(side_faces):
                    if idx == 0:
                        data['end1']['edge'][face.index] = end1_edge.index
                        data['end1']['other_edge'][face.index] = end1_other_edge.index

                        data['end1']['edge_coords'][face.index] = [v.co.copy() for v in end1_edge.verts]
                        data['end1']['other_edge_coords'][face.index] = [v.co.copy() for v in end1_other_edge.verts]

                    else:
                        data['end1']['edge'][face.index] = end1_other_edge.index
                        data['end1']['other_edge'][face.index] = end1_edge.index

                        data['end1']['edge_coords'][face.index] = [v.co.copy() for v in end1_other_edge.verts]
                        data['end1']['other_edge_coords'][face.index] = [v.co.copy() for v in end1_edge.verts]

            if end2_face:
                data['end2']['face'] = end2_face.index
                data['end2']['face_no'] = end2_face.normal.copy()

                data['end2']['vert'] = end2_vert.index
                data['end2']['vert_co'] = end2_vert.co.copy()

                for idx, face in enumerate(side_faces):
                    if idx == 0:
                        data['end2']['edge'][face.index] = end2_edge.index
                        data['end2']['other_edge'][face.index] = end2_other_edge.index

                        data['end2']['edge_coords'][face.index] = [v.co.copy() for v in end2_edge.verts]
                        data['end2']['other_edge_coords'][face.index] = [v.co.copy() for v in end2_other_edge.verts]

                    else:
                        data['end2']['edge'][face.index] = end2_other_edge.index
                        data['end2']['other_edge'][face.index] = end2_edge.index

                        data['end2']['edge_coords'][face.index] = [v.co.copy() for v in end2_other_edge.verts]
                        data['end2']['other_edge_coords'][face.index] = [v.co.copy() for v in end2_edge.verts]

            return data

        print("WARNING: Edge doesn't have at least one end face")
        return None

    print("WARNING: Edge doesn't have exactly two side faces")
    return None
