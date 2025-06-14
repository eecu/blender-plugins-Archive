import bpy
from typing import Union

def get_active_object(context) -> Union[bpy.types.Object, None]:
    objects = getattr(context.view_layer, 'objects', None)

    if objects:
        return getattr(objects, 'active', None)
