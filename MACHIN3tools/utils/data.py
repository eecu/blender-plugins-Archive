import re

from . object import is_instance_collection

def get_id_data_type(id):

    datatypeRegex = re.compile(r"<bpy_struct, +(\w+)\(.*?\) +at")

    mo = datatypeRegex.match(str(id))

    if mo:
        type = mo.group(1).upper()

        if type == 'OBJECT' and not id.data:
            return 'EMPTY'

        return type

def get_icon_from_data_type(type):
    if type == 'COLLECTION':
        icon = 'OUTLINER_COLLECTION'

    elif type in ['OBJECT', 'ARMATURE', 'CAMERA', 'CURVE', 'CURVES', 'EMPTY', 'TEXTCURVE', 'LATTICE', 'MESH', 'META', 'SURFACE']:
        icon = f"{type}_DATA"

    else:
        icon = 'MONKEY'

    return icon

def get_pretty_linked_data(linked, obj=None, debug=False):
    linked = linked.copy()

    main = {'object': None, 'data': None, 'icol': None}

    if obj:
        object = obj if obj in linked else None
        data = data  if (data := obj.data) and data in linked else None
        icol = icol if (icol := is_instance_collection(obj)) and icol in linked else None

        main = {
            'object': object,
            'data': data,
            'icol': icol,
        }

        if object:
            linked.remove(object)

        if data:
            linked.remove(data)

        if icol:
            linked.remove(icol)

    other = {}

    for data in linked:

        if (type := get_id_data_type(data)) in other:
            if data in other[type]:
                other[type][data] += 1
            else:
                other[type][data] = 1

        else:
            other[type] = {data: 1}

    sorted_linked = []

    if object := main['object']:
        sorted_linked.append(('MAIN_OBJECT', get_icon_from_data_type(get_id_data_type(object)), object, 1))

    if data := main['data']:
        sorted_linked.append((f"MAIN_{get_id_data_type(data)}", get_icon_from_data_type(get_id_data_type(data)), data, 1))

    if icol := main['icol']:
        sorted_linked.append(("MAIN_INSTANCE_COLLECTION",  get_icon_from_data_type('COLLECTION'), icol, 1))

    for type in ['COLLECTION', 'OBJECT', 'MESH']:
        if type in other:
            items = other.pop(type)

            sorted_items = [(item, items[item]) for item in sorted(items, key=lambda i: (-items[i], i.name))]

            for item, count in sorted_items:
                sorted_linked.append((type, get_icon_from_data_type(type), item, count))

    for type in sorted(other):
        items = other[type]

        sorted_items = [(item, items[item]) for item in sorted(items, key=lambda i: (-items[i], i.name))]

        for item, count in sorted_items:
            sorted_linked.append((type, get_icon_from_data_type(type), item, count))

    if debug:
        print()

        for type, icon, item, count in sorted_linked:
            print(type, icon, item.name, count)

    return sorted_linked
