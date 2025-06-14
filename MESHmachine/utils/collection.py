import bpy

def unlink_object(obj):
    for col in obj.users_collection:
        col.objects.unlink(obj)

def create_realmirror_collections(scene):
    mcol = scene.collection

    rmcol = bpy.data.collections.get('RealMirror')

    if not rmcol:
        rmcol = bpy.data.collections.new(name='RealMirror')
        mcol.children.link(rmcol)

    rmocol = bpy.data.collections.get('RM.Originals')

    if not rmocol:
        rmocol = bpy.data.collections.new(name='RM.Originals')
        rmcol.children.link(rmocol)

    rmmcol = bpy.data.collections.get('RM.Mirrored')

    if not rmmcol:
        rmmcol = bpy.data.collections.new(name='RM.Mirrored')
        rmcol.children.link(rmmcol)

    return rmcol, rmocol, rmmcol

def sort_into_realmirror_collections(originals, originals_collection, mirrored, mirrored_collection):
    for obj in originals:
        if obj.name not in originals_collection.objects:
            originals_collection.objects.link(obj)

    for obj in mirrored:
        if obj.name not in mirrored_collection.objects:
            mirrored_collection.objects.link(obj)

def create_plug_collections(scene, pluglib):
    mcol = scene.collection

    pcol = bpy.data.collections.get('Plugs')

    if not pcol:
        pcol = bpy.data.collections.new(name='Plugs')
        mcol.children.link(pcol)

    plcol = bpy.data.collections.get(pluglib)

    if not plcol:
        plcol = bpy.data.collections.new(name=pluglib)
        pcol.children.link(plcol)

    return pcol, plcol
