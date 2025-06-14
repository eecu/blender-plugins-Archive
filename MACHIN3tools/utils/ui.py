from typing import Union
import bpy
import rna_keymap_ui
from mathutils import Vector

from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d
from bl_ui.space_statusbar import STATUSBAR_HT_header as statusbar

from time import time

from . registration import get_prefs
from .. registration import keys

from .. items import accelerator_replacement_map, numbers_map

icons = None

def get_icon(name):
    global icons

    if not icons:
        from .. import icons

    return icons[name].icon_id

def get_icon_from_key(key):
    if key in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
        numbers = {v:k for k, v in numbers_map.items()}
        return f"EVENT_{numbers[key]}KEY"

    elif key in ['LMB', 'MMB', 'RMB', 'LMB_DRAG', 'LMB_2X', 'MMB_DRAG', 'MMB_SCROLL', 'RMB_DRAG', 'MOVE']:

        if bpy.app.version < (4, 3, 0):
            if key == 'MMB_SCROLL':
                key = 'MMB'

        return f"MOUSE_{key}"

    elif key in ['COMMAND', 'CONTROL', 'EMPTY1', 'EMPTY2', 'EMPTY3', 'MENU', 'RING', 'OPTION', 'WINDOWS']:
        return f"KEY_{key}"

    elif key in ['SPACE']:
        return f"EVENT_{key}KEY"

    else:
        return f"EVENT_{key}"

def draw_key_icons(layout, key: Union[list, str]):
    keys = [key] if isinstance(key, str) else key

    for icon in keys:

        layout.label(text='', icon=icon)

        if bpy.app.version >= (4, 3, 0):
            if icon in ['KEY_EMPTY2', 'EVENT_CTRL', 'EVENT_ALT', 'EVENT_OS', 'EVENT_F10', 'EVENT_F11', 'EVENT_F12', 'EVENT_ESC', 'EVENT_PAUSE', 'EVENT_INSERT', 'EVENT_HOME', 'EVENT_END', 'EVENT_APP', 'EVENT_BACKSPACE', 'EVENT_DEL']:
                layout.separator(factor=1.5)

            elif icon in ['KEY_EMPTY3', 'EVENT_SPACEKEY']:
                layout.separator(factor=3)

def get_mouse_pos(self, context, event, window=False, hud=True, hud_offset=(20, 20)):
    self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))

    if window:
        self.mouse_pos_window = Vector((event.mouse_x, event.mouse_y))

    if hud:
        scale = get_scale(context)

        self.HUD_x = self.mouse_pos.x + hud_offset[0] * scale
        self.HUD_y = self.mouse_pos.y + hud_offset[1] * scale

def wrap_mouse(self, context, x=False, y=False):
    width = context.region.width
    height = context.region.height

    mouse_pos = self.mouse_pos.copy()

    if x:
        if mouse_pos.x <= 0:
            mouse_pos.x = width - 10

        elif mouse_pos.x >= width - 1:  # the -1 is required for full screen, where the max region width is never passed
            mouse_pos.x = 10

    if y and mouse_pos == self.mouse_pos:
        if mouse_pos.y <= 0:
            mouse_pos.y = height - 10

        elif mouse_pos.y >= height - 1:
            mouse_pos.y = 10

    if mouse_pos != self.mouse_pos:
        warp_mouse(self, context, mouse_pos)

def warp_mouse(self, context, co2d=Vector(), region=True, hud_offset=(20, 20)):
    coords = get_window_space_co2d(context, co2d) if region else co2d

    context.window.cursor_warp(int(coords.x), int(coords.y))

    self.mouse_pos = co2d if region else get_region_space_co2d(context, co2d)

    if getattr(self, 'last_mouse', None):
        self.last_mouse = self.mouse_pos

    if getattr(self, 'HUD_x', None):
        scale = get_scale(context)

        self.HUD_x = self.mouse_pos.x + hud_offset[0] * scale
        self.HUD_y = self.mouse_pos.y + hud_offset[1] * scale

def get_window_space_co2d(context, co2d=Vector(), region=None):
    region = region if region else context.region
    return co2d + Vector((region.x, region.y))

def get_region_space_co2d(context, co2d=Vector(), region=None):
    region = region if region else context.region
    return co2d - Vector((region.x, region.y))

def wrap_cursor(self, context, event, x=False, y=False):
    if x:

        if event.mouse_region_x <= 0:
            context.window.cursor_warp(context.region.width + self.region_offset_x - 10, event.mouse_y)

        if event.mouse_region_x >= context.region.width - 1:  # the -1 is required for full screen, where the max region width is never passed
            context.window.cursor_warp(self.region_offset_x + 10, event.mouse_y)

    if y:
        if event.mouse_region_y <= 0:
            context.window.cursor_warp(event.mouse_x, context.region.height + self.region_offset_y - 10)

        if event.mouse_region_y >= context.region.height - 1:
            context.window.cursor_warp(event.mouse_x, self.region_offset_y + 100)

def popup_message(message, title="Info", icon="INFO", terminal=True):
    def draw_message(self, context):
        if isinstance(message, list):
            for m in message:
                self.layout.label(text=m)
        else:
            self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw_message, title=title, icon=icon)

    if terminal:
        if icon == "FILE_TICK":
            icon = "ENABLE"
        elif icon == "CANCEL":
            icon = "DISABLE"
        print(icon, title)

        if isinstance(message, list):
            print(" »", ", ".join(message))
        else:
            print(" »", message)

def get_zoom_factor(context, depth_location, scale:float=10, ignore_obj_scale=False, debug=False):
    center = Vector((context.region.width / 2, context.region.height / 2))
    offset = center + Vector((10, 0))

    try:
        center_3d = region_2d_to_location_3d(context.region, context.region_data, center, depth_location)
        offset_3d = region_2d_to_location_3d(context.region, context.region_data, offset, depth_location)

    except:
        return 1

    zoom_factor = (center_3d - offset_3d).length * (scale / 10)

    if context.active_object and not ignore_obj_scale:
        mx = context.active_object.matrix_world.to_3x3()

        zoom_vector = mx.inverted_safe() @ Vector((zoom_factor, 0, 0))
        zoom_factor = zoom_vector.length * (scale / 10)

    if debug:
        from . draw import draw_point

        draw_point(depth_location, color=yellow, modal=False)
        draw_point(center_3d, color=green, modal=False)
        draw_point(offset_3d, color=red, modal=False)

        print("zoom factor:", zoom_factor)
    return zoom_factor

def get_flick_direction(context, mouse_loc_3d, flick_vector, axes):
    origin_2d = location_3d_to_region_2d(context.region, context.region_data, mouse_loc_3d, default=Vector((context.region.width / 2, context.region.height / 2)))
    axes_2d = {}

    for direction, axis in axes.items():

        axis_2d = location_3d_to_region_2d(context.region, context.region_data, mouse_loc_3d + axis, default=origin_2d)
        if (axis_2d - origin_2d).length:
            axes_2d[direction] = (axis_2d - origin_2d).normalized()

    return min([(d, abs(flick_vector.xy.angle_signed(a))) for d, a in axes_2d.items()], key=lambda x: x[1])[0]

def kmi_to_string(kmi, compact=False, docs_mode=False):
    if compact:
        if bool(props := dict(kmi.properties)):
            if kmi.idname == 'machin3.assetbrowser_bookmark':
                props_str = str(props).replace("'", '').replace('{', '').replace('}', '')
            else:
                props_str = str(props).replace("'", '').replace('{', '').replace('}', '').replace('0', 'False').replace('1', 'True')

            kmi_str = f"{kmi.idname}, {kmi.to_string()}, properties: {props_str}"
        else:
            kmi_str = f"{kmi.idname}, {kmi.to_string()}"

    else:
        kmi_str = f"{kmi.idname}, name: {kmi.name}, active: {kmi.active}, map type: {kmi.map_type}, type: {kmi.type}, value: {kmi.value}, alt: {kmi.alt}, ctrl: {kmi.ctrl}, shift: {kmi.shift}, properties: {str(dict(kmi.properties))}"

    if docs_mode:
        return f"`{kmi_str}`"
    else:
        return kmi_str

def draw_keymap_item(layout, kc, km, kmi, label=''):
    box = layout.box()

    if label:
        row = box.split(align=True, factor=0.25)
        row.label(text=label)

    else:
        row = box.row(align=True)

    rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, row, 0)

def draw_keymap_items(kc, name, keylist, layout):
    drawn = []

    idx = 0

    for item in keylist:
        keymap = item.get("keymap")
        isdrawn = False

        if keymap:
            km = kc.keymaps.get(keymap)

            if km:
                idname = item.get("idname")
                properties = item.get("properties", None)
                kmi = find_kmi_from_idname(km, idname, properties)

                if kmi:
                    if idx == 0:
                        box = layout.box()
                        column = box.column(align=True)

                    if len(keylist) == 1:
                        label = name.title().replace("_", " ")

                    else:
                        if idx == 0:
                            column.label(text=name.title().replace("_", " "))

                        label = f"   {item.get('label')}"

                    row = column.split(align=True, factor=0.25)

                    r = row.row(align=True)
                    r.active = len(keylist) == 1
                    r.label(text=label)

                    rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, row, 0)

                    info = item.get("info", '')

                    if info:
                        row = column.row(align=True)
                        row.alignment = 'LEFT'
                        row.alert = True
                        row.label(text=f"  ℹ {info}", icon="NONE")

                    isdrawn = True
                    idx += 1

        drawn.append(isdrawn)

    return any(d for d in drawn)

def get_keymap_item(name, idname, key=None, alt=False, ctrl=False, shift=False, properties=[]):
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    km = kc.keymaps.get(name)

    alt = int(alt)
    ctrl = int(ctrl)
    shift = int(shift)

    if km:
        kmi = km.keymap_items.get(idname)

        if kmi:
            found = True if key is None else all([kmi.type == key and kmi.alt is alt and kmi.ctrl is ctrl and kmi.shift is shift])

            if found:
                if properties:
                    if all([getattr(kmi.properties, name, None) == prop for name, prop in properties]):
                        return kmi
                else:
                    return kmi

def find_kmi_from_idname(km, idname, properties=None, debug=False):
    for kmi in km.keymap_items:
        if kmi.idname == idname:

            if properties:
                if all(getattr(kmi.properties, name, None) == value for name, value in properties):
                    if debug:
                        print(f"  keymap: {km.name} kmi:", kmi_to_string(kmi, compact=True))
                    return kmi

            else:
                if debug:
                    print(f"  keymap: {km.name} kmi:", kmi_to_string(kmi, compact=True))
                return kmi

    if debug:
        print(f"  keymap: {km.name} kmi: NONE")

def get_user_keymap_items(context, debug=False):
    prefs = get_prefs()
    wm = context.window_manager
    kc = wm.keyconfigs.user

    original = set()
    modified_kmis = []
    missing_kmis = []

    for group, keymappings in keys.items():

        is_active = getattr(prefs, f"activate_{group.lower().replace('browser', 'browser_tools')}", None)

        if is_active:

            if debug:
                print()
                print(group)

            for keymapping in keymappings:
                kmname = keymapping['keymap']
                idname = keymapping['idname']

                km = kc.keymaps.get(kmname, None)

                if km:
                    properties = keymapping.get('properties', None)
                    kmi = find_kmi_from_idname(km, idname, properties, debug=False)

                    if kmi:
                        if kmi.is_user_modified:
                            if debug:
                                print(" NOTE: kmi has been user modified!", kmi_to_string(kmi, compact=True))

                            modified_kmis.append((km, kmi))

                        else:
                            original.add(kmi)

                    else:
                        if debug:
                            print(" WARNING: kmi not found for", idname, "with properties:", properties)

                        missing_kmis.append(keymapping)

                else:
                    if debug:
                        print("  keymap: !! NOT FOUND !!")

    return modified_kmis, missing_kmis

def get_layout_type(layout):
    data = layout.introspect()

    type = data[0]['type']

    return type.replace('LAYOUT_', '').replace('RADIAL', 'PIE')

def get_panel_fold(layout, idname, text='', icon='NONE', custom_icon=None, align=True, default_closed=True):
    header, panel = layout.panel(idname=idname, default_closed=default_closed)
    header.active = bool(panel)

    if custom_icon:
        header.label(text=text, icon_value=get_icon(custom_icon))
    else:
        header.label(text=text, icon=icon)

    return panel.column(align=align) if panel else None

def build_pie_button_stack(stack, type='OPERATOR', operator=None, props=None, data=None, property=None, text="", icon='NONE', icon_value=0,  emboss=True, depress=False, scale=1.4, active=True, enabled=True, alert=False):
    button = {
        'type': type,
        'scale': scale,

        'style_kwargs': {
            'active': active,
            'enabled': enabled,
            'alert': alert
        }
    }

    button['common_kwargs'] = {
        'text': text,
        'icon': icon,
        'icon_value': icon_value,

        'emboss': emboss,
    }

    if type == 'OPERATOR':
        button['operator'] = operator
        button['depress'] = depress

        if props:
            button['props'] = props

    elif type == 'PROPERTY':
        button['data'] = data
        button['property'] = property

    stack.append(button)

def get_stacked_pie_layout(layout, scale=1.4, alignment='CENTER', active=True, enabled=True, alert=False):
    if (type := get_layout_type(layout)) == 'PIE':
        box = layout.split()
        column = box.column()
        ret_layout = column

    elif type == 'COLUMN':
        ret_layout = layout

    else:
        return None, layout

    row = ret_layout.row()
    row.alignment = alignment

    row.scale_y = scale

    row.active = active
    row.enabled = enabled
    row.alert = alert

    return row, ret_layout

def draw_pie_button_stack(stack, layout, alignment='CENTER', debug=False):
    if debug:
        print()
        print("button stack:", len(stack), "buttons")

        for button in stack:
            print("", button)

    if stack:

        if len(stack) == 1 and get_layout_type(layout) == 'PIE' and not stack[0]['style_kwargs']['alert'] and not stack[0]['type'] == 'PROPERTY':
            button = stack[0]

            if button['type'] == 'OPERATOR':
                op = layout.operator(button['operator'], **button['common_kwargs'])

                if props := button.get('props', None):
                    for name, prop in props.items():
                        setattr(op, name, prop)

            else:
                print(button)
                layout.separator()

        else:
            for button in stack:

                if button['type'] == 'OPERATOR':
                    lay, layout = get_stacked_pie_layout(layout, scale=button['scale'], alignment=alignment, **button['style_kwargs'])

                    if lay:
                        op = lay.operator(button['operator'], depress=button['depress'], **button['common_kwargs'])

                        if props := button.get('props', None):
                            for name, prop in props.items():
                                setattr(op, name, prop)

                elif button['type'] == 'PROPERTY':
                    lay, layout = get_stacked_pie_layout(layout, scale=button['scale'], alignment=alignment, **button['style_kwargs'])

                    if lay:
                        lay.prop(button['data'], button['property'], **button['common_kwargs'])

                else:
                    print(button)
                    layout.separator()

    else:
        layout.separator()

def init_status(self, context, title='', func=None):
    self.bar_orig = statusbar.draw

    if func:
        statusbar.draw = func
    else:
        statusbar.draw = draw_basic_status(self, context, title)

def draw_basic_status(self, context, title):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text=title)

        row.label(text="", icon='MOUSE_LMB')
        row.label(text="Finish")

        if context.window_manager.keyconfigs.active.name.startswith('blender'):
            row.label(text="", icon='MOUSE_MMB')
            row.label(text="Viewport")

        row.label(text="", icon='MOUSE_RMB')
        row.label(text="Cancel")

    return draw

def draw_status_item(layout, active=True, alert=False, key: Union[list, str] = [], text="", prop=None, gap=None):
    row = layout.row(align=True)
    row.active = active
    row.alert = alert

    keys = [key] if isinstance(key, str) or isinstance(key, int) else key

    if gap:
        row.separator(factor=gap)

    draw_key_icons(row, [get_icon_from_key(key) for key in keys])

    if prop is not None:
        if text:
            row.label(text=f"{text}: {prop}")
        else:
            row.label(text=f"{prop}")
    elif text:
        row.label(text=text)

def draw_status_item_precision(layout, fine=None, coarse=None, fine_key='SHIFT', coarse_key='CTRL', gap=10):
    if fine is not None:
        draw_status_item(layout, active=fine, key=fine_key, gap=gap)

    if coarse is not None:
        draw_status_item(layout, active=coarse, key=coarse_key, gap=gap if fine is None else None)

    if fine is not None and coarse is not None:
        draw_status_item(layout, active=fine or coarse, text="Precision", prop="fine" if fine else "coarse" if coarse else None)

    elif fine is not None:
        draw_status_item(layout, active=fine, text="Precision", prop="fine" if fine else None)

    elif coarse is not None:
        draw_status_item(layout, active=coarse, text="Precision", prop="coarse" if coarse else None)

def finish_status(self):
    statusbar.draw = self.bar_orig

def init_modal_handlers(self, context, area=True, hud=False, view3d=False, timer=False, time_step=0.05, modal=True):
    if area:
        self.area = context.area

    if hud:
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

    if view3d:
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')

    if timer:

        if getattr(self, 'time', None):
            init_timer_modal(self)

        self.TIMER = context.window_manager.event_timer_add(time_step, window=context.window)

    if modal:
        context.window_manager.modal_handler_add(self)

def finish_modal_handlers(self):
    if getattr(self, 'HUD', None):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

    if getattr(self, 'VIEW3D', None):
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

    if getattr(self, 'TIMER', None):
        bpy.context.window_manager.event_timer_remove(self.TIMER)

def navigation_passthrough(event, alt=True, wheel=False) -> bool:
    if alt and wheel:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and event.value == 'PRESS') or event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
    elif alt:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and event.value == 'PRESS')
    elif wheel:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
    else:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF')

def scroll(event, wheel=True, pad=True, key=False):
    return scroll_up(event, wheel=wheel, pad=pad, key=key) or scroll_down(event, wheel=wheel, pad=pad, key=key)

def scroll_up(event, wheel=True, pad=True, key=False):

    if pad and event.type == 'TRACKPADPAN' and event.mouse_y > event.mouse_prev_y and event.mouse_y - event.mouse_prev_y >= 5:
        return True

    elif event.value == 'PRESS':

        if wheel and event.type == 'WHEELUPMOUSE':
            return True

        if key and event.type in ['ONE', 'UP_ARROW', 'PLUS', 'NUMPAD_PLUS']:
            return True

    return False

def scroll_down(event, wheel=True, pad=True, key=False):

    if pad and event.type == 'TRACKPADPAN' and event.mouse_y < event.mouse_prev_y and event.mouse_prev_y - event.mouse_y >= 5:
        return True

    elif event.value == 'PRESS':

        if wheel and event.type == 'WHEELDOWNMOUSE':
            return True

        if key and event.type in ['TWO', 'DOWN_ARROW', 'MINUS', 'NUMPAD_MINUS']:
            return True

    return False

def init_timer_modal(self, debug=False):
    self.start = time()

    self.countdown = self.time * get_prefs().modal_hud_timeout

    if debug:
        print(f"initiating timer with a countdown of {self.time}s ({self.time * get_prefs().modal_hud_timeout}s)")

def set_countdown(self, debug=False):
    self.countdown = self.time * get_prefs().modal_hud_timeout - (time() - self.start)

    if debug:
        print("countdown:", self.countdown)

def get_timer_progress(self, debug=False):
    progress =  self.countdown / (self.time * get_prefs().modal_hud_timeout)

    if debug:
        print("progress:", progress)

    return progress

def ignore_events(event, none=True, timer=True, timer_report=True):
    ignore = ['INBETWEEN_MOUSEMOVE', 'WINDOW_DEACTIVATE']

    if none:
        ignore.append('NONE')

    if timer:
        ignore.extend(['TIMER', 'TIMER1', 'TIMER2', 'TIMER3'])

    if timer_report:
        ignore.append('TIMER_REPORT')

    return event.type in ignore

def force_ui_update(context, active=None):
    if context.mode == 'OBJECT':
        if active:
            active.select_set(True)

        else:
            if active := context.active_object:
                active.select_set(active.select_get())

            if visible := context.visible_objects:
                visible[0].select_set(visible[0].select_get())

    elif context.mode == 'EDIT_MESH':
        context.active_object.select_set(True)

def get_scale(context):
    return context.preferences.system.ui_scale * get_prefs().modal_hud_scale

def suppress_accelerator(text, limit=1, debug=False):
    if debug:
        print()
        print("replacing:", text)

    replaced = ''

    for idx, char in enumerate(text):
        if limit == 0 or idx + 1 <= limit:
            rep = accelerator_replacement_map.get(char, None)
        else:
            rep = None

        if rep:
            replaced += rep

        else:
            if debug:
                print("WARNING:", char, " has not been replaced")
                replaced += char
            else:
                replaced += char

    if debug:
        print("     with:", replaced)

    return replaced
