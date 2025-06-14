def get_vgroup_index(obj, vgname):
    if vgname in obj.vertex_groups:
        return [vg.name for vg in obj.vertex_groups].index(vgname)
