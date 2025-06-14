import bpy
import re
from uuid import uuid4
from mathutils import Matrix
from . math import flatten_matrix
from . object import update_local_view, unparent, parent, flatten
from . mesh import get_eval_mesh
from . registration import get_addon
from .. import bl_info

machin3tools = None
decalmachine = None

def get_version_as_tuple(versionstring):
    return tuple(int(v) for v in versionstring.split('.')[:2])

def get_stashobj_basename(name):
    nameRegex = re.compile(r"(.*)_stash_.*")
    mo = nameRegex.match(name)
    basename = mo.group(1)
    return basename

def create_stash(active, source, dg=None, self_stash=False, force_default_name=False, debug=False):
    stashindex = len(active.MM.stashes)
    stashname = source.MM.stashname if source.MM.stashname and not force_default_name else f"stash_{stashindex}"
    stashobj = source.copy()

    if dg:
        stashobj.modifiers.clear()
        stashobj.data = get_eval_mesh(dg, source, data_block=True)

    else:
        stashobj.data = source.data.copy()

    stashobj.MM.isstashobj = True
    stashobj.use_fake_user = True
    stashobj.name = f"{source.name}_stash_{stashindex}"

    stashobj.display_type = 'TEXTURED'

    stashobj.MM.stashes.clear()

    if stashobj.parent and stashobj.parent != active:
        parent(stashobj, active)

    s = active.MM.stashes.add()

    s.name = stashname
    s.index = stashindex

    s.version = '.'.join([str(v) for v in bl_info['version']])
    s.uuid = str(uuid4())

    s.self_stash = self_stash

    s.obj = stashobj
    stashobj.MM.stashuuid = s.uuid

    active.MM.active_stash_idx = stashindex

    deltamx = active.matrix_world.inverted_safe() @ source.matrix_world
    stashobj.MM.stashdeltamx = flatten_matrix(deltamx)

    stashobj.MM.stashorphanmx = flatten_matrix(active.matrix_world)

    stashobj.matrix_world = active.matrix_world

    s.obj.data.transform(deltamx)

    if debug:
        print("new stash:", stashname)

    return s

def retrieve_stash(active, stashobj, retrieve_original=False):
    if retrieve_original:
        retrieved = stashobj
    else:
        retrieved = stashobj.copy()
        retrieved.data = stashobj.data.copy()

    bpy.context.collection.objects.link(retrieved)

    retrieved.select_set(False)

    deltamx = retrieved.MM.stashdeltamx
    activemx = active.matrix_world if active else retrieved.MM.stashorphanmx

    retrieved.matrix_world = activemx @ deltamx
    retrieved.data.transform(deltamx.inverted_safe())

    retrieved.use_fake_user = False
    retrieved.display_type = 'TEXTURED'

    retrieved.MM.isstashobj = False
    retrieved.MM.stashuuid = ''
    retrieved.MM.stashdeltamx.identity()
    retrieved.MM.stashorphanmx.identity()

    retrieved.MM.stashmx.identity()
    retrieved.MM.stashtargetmx.identity()

    retrieved.name = get_stashobj_basename(retrieved.name)

    update_local_view(bpy.context.space_data, [(retrieved, True)])

    return retrieved

def transfer_stashes(source, target, restash=False):

    target_stash_count = len(target.MM.stashes)
    stashes = [stash for stash in source.MM.stashes if stash.obj]

    active_stash = source.MM.stashes[source.MM.active_stash_idx] if source.MM.stashes[source.MM.active_stash_idx] in stashes else None

    transferred = []

    for idx, stash in enumerate(stashes):
        index = idx + target_stash_count

        if restash:
            r = retrieve_stash(source, stash.obj)
            s = create_stash(target, r)
            bpy.data.objects.remove(r, do_unlink=True)

        else:
            s = target.MM.stashes.add()
            s.index = index
            s.name = stash.obj.MM.stashname if stash.obj.MM.stashname else f"stash_{s.index}"

            s.obj = stash.obj.copy()
            s.obj.data = stash.obj.data.copy()

            s.uuid = stash.uuid
            s.version = stash.version

            s.self_stash = stash.self_stash
            s.flipped = stash.flipped

        if stash == active_stash:
            target.MM.active_stash_idx = index

        transferred.append(index)

    if not active_stash:
        target.MM.active_stash_idx = len(target.MM.stashes) - 1

    return [target.MM.stashes[idx] for idx in transferred]

def clear_stashes(obj, stashes=[]):
    delete = [stash for stash in stashes]
    keep = [{'name': stash.name, 'uuid': stash.uuid, 'version': stash.version, 'obj': stash.obj, 'flipped': stash.flipped} for stash in obj.MM.stashes if stash.obj and stash not in delete]

    obj.MM.stashes.clear()

    if keep:

        for stash in keep:
            stashobj = stash['obj']

            idx = len(obj.MM.stashes)
            stash_name = stashobj.MM.stashname if stashobj.MM.stashname else f"stash_{idx}"

            s = obj.MM.stashes.add()
            s.index = idx
            s.name = stash_name

            s.uuid = stash['uuid']
            s.version = stash['version']

            s.flipped = stash['flipped']

            s.obj = stashobj
            s.obj.name = f"{get_stashobj_basename(stashobj.name)}_stash_{idx}"
            s.obj.MM.uuid = stash['uuid']

    obj.MM.active_stash_idx = min(obj.MM.active_stash_idx, len(obj.MM.stashes) - 1)

def swap_stash(context, active, stashidx, debug=False):

    if active.MM.stashes and stashidx < len(active.MM.stashes):
        global machin3tools, decalmachine

        if machin3tools is None:
            machin3tools = get_addon('MACHIN3tools')[0]

        if decalmachine is None:
            decalmachine = get_addon('DECALmachine')[0]

        mode = context.mode

        if mode == 'EDIT_MESH':
            active.update_from_editmode()

        mods = [mod for obj in context.scene.objects for mod in obj.modifiers if (mod.type == 'MIRROR' and mod.mirror_object == active) or (mod.type == 'BOOLEAN' and mod.object == active)]

        new_active = None
        new_stash_objs = []
        new_idx = 0
        self_stash = False

        for idx, stash in enumerate(active.MM.stashes):
            if stash.obj:

                stash_users = [s for obj in bpy.data.objects if obj.MM.stashes for s in obj.MM.stashes if s.obj == stash.obj]

                r = retrieve_stash(active, stash.obj, retrieve_original=len(stash_users) == 1)

                if idx == stashidx:
                    new_active = r

                    new_stash_objs.append(active)

                    self_stash = stash.self_stash

                else:
                    new_stash_objs.append(r)

        if debug:
            print()
            print("old active:", active.name, active.parent.name if active.parent else None)
            print("new active:", new_active.name, new_active.parent.name if new_active.parent else None)
            print()

        parent_old_to_new = new_active.parent == active
        parent_new_to_old_parent = active.parent
        parent_old_to_new_parent = new_active.parent if new_active.parent and new_active.parent != active else None

        if parent_old_to_new:
            if debug:
                print("parenting the old active to the new active")

            unparent(new_active)
            parent(active, new_active)

        if parent_new_to_old_parent:
            if debug:
                print("parenting the new active to the old active's parent")

            parent(new_active, parent_new_to_old_parent)

        if parent_old_to_new_parent:
            if debug:
                print("parent the old active to the new active's parent")

            parent(active, parent_old_to_new_parent)

        for obj in active.children:
            parent(obj, new_active)

            if decalmachine and obj.DM.isdecal:
                if obj.DM.isprojected:
                    obj.DM.projectedon = new_active

                elif obj.DM.issliced:
                    obj.DM.slicedon = new_active

        if machin3tools:
            if debug and active.M3.is_group_object:
                print("adding new active to active's group")

            new_active.M3.is_group_object = active.M3.is_group_object
            new_active.color = active.color

        if debug:
            print("\nre-stashing:")

        for idx, obj in enumerate(new_stash_objs):
            if debug:
                print(f" {idx} {obj.name} {'(old active)' if idx == stashidx else ''}")

            if obj.parent == active:
                if debug:
                    print("  reparenting obj to new active")

                unparent(obj)
                parent(obj, new_active)

            if obj == active:
                new_idx = len(new_active.MM.stashes)

            create_stash(new_active, obj, self_stash=new_active.matrix_world == obj.matrix_world)

            if obj.data.users > 1:
                bpy.data.objects.remove(obj, do_unlink=True)

            else:
                bpy.data.meshes.remove(obj.data, do_unlink=True)

        new_active.MM.active_stash_idx = new_idx

        if self_stash:
            if debug:
                print("\nmaking new active take old active's place in MIRROR and BOOLEAN mods")

            for mod in mods:
                if debug:
                    print(f" {mod.name} on {mod.id_data.name}")

                if mod.type == 'MIRROR':
                    mod.mirror_object = new_active
                elif mod.type == 'BOOLEAN':
                    mod.object = new_active

        bpy.ops.object.select_all(action='DESELECT')
        new_active.select_set(True)
        context.view_layer.objects.active = new_active

        if mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='EDIT')

        return new_active, new_active.MM.stashes[new_idx]
