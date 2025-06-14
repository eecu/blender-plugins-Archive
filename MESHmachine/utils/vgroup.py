import bpy

def add_vgroup(obj, name="", ids=[], weight=1, debug=False):
    vgroup = obj.vertex_groups.new(name=name)

    if debug:
        print("INFO: Created new vertex group: %s" % (name))

    if ids:
        vgroup.add(ids, weight, "ADD")

    else:
        obj.vertex_groups.active_index = vgroup.index
        bpy.ops.object.vertex_group_assign()

    return vgroup

def set_vgroup(self, vgroup, name, init=False, debug=False):
    vgroups = getattr(self, 'stored_vgroups', None)

    if not vgroups or init:
        self.stored_vgroups = {}
        vgroups = self.stored_vgroups

    vgroups[name] = vgroup.name

def get_vgroup(self, obj, name, debug=False):
    vgroups = getattr(self, 'stored_vgroups', None)

    if vgroups and name in vgroups:
        return obj.vertex_groups.get(vgroups[name])
