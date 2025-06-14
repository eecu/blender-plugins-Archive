import bpy
from mathutils import Vector
import rna_keymap_ui
from bl_ui.space_statusbar import STATUSBAR_HT_header as statusbar
from bpy_extras.view3d_utils import region_2d_to_location_3d 
from time import time
from . registration import get_prefs

icons = None

def get_icon(name):
    global icons

    if not icons:
        from .. import icons

    return icons[name].icon_id

def get_mouse_pos(self, context, event, window=False, hud=True, hud_offset=(20, 20)):
    self.mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))

    if window:
        self.mouse_pos_window = Vector((event.mouse_x, event.mouse_y))

    if hud:
        scale = get_scale(context)

        self.HUD_x = self.mouse_pos.x + hud_offset[0] * scale
        self.HUD_y = self.mouse_pos.y + hud_offset[1] * scale

def wrap_mouse(self, context, x=False, y=False, wrap_hud=True):
    width = context.region.width
    height = context.region.height

    mouse = self.mouse_pos.copy()

    if x:
        if mouse.x <= 0:
            mouse.x = width - 10

        elif mouse.x >= width - 1:  # the -1 is required for full screen, where the max region width is never passed
            mouse.x = 10

    if y and mouse == self.mouse_pos:
        if mouse.y <= 0:
            mouse.y = height - 10

        elif mouse.y >= height - 1:
            mouse.y = 10

    if mouse != self.mouse_pos:
        warp_mouse(self, context, mouse, warp_hud=wrap_hud)

def warp_mouse(self, context, co2d=Vector(), region=True, warp_hud=True, hud_offset=(20, 20)):
    coords = get_window_space_co2d(context, co2d) if region else co2d

    context.window.cursor_warp(int(coords.x), int(coords.y))

    self.mouse_pos = co2d if region else get_region_space_co2d(context, co2d)

    if getattr(self, 'last_mouse', None):
        self.last_mouse = self.mouse_pos

    if warp_hud and getattr(self, 'HUD_x', None):
        scale = get_scale(context)

        self.HUD_x = self.mouse_pos.x + hud_offset[0] * scale
        self.HUD_y = self.mouse_pos.y + hud_offset[1] * scale

def get_window_space_co2d(context, co2d=Vector()):
    return co2d + Vector((context.region.x, context.region.y))

def get_region_space_co2d(context, co2d=Vector()):
    return Vector((context.region.x, context.region.y)) - co2d

def get_zoom_factor(context, depth_location, scale=10, ignore_obj_scale=False, debug=False):
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

def draw_keymap_items(kc, name, keylist, layout, skip_box_label=False):
    drawn = []

    idx = 0

    for item in keylist:
        keymap = item.get("keymap")
        isdrawn = False

        if keymap:
            km = kc.keymaps.get(keymap)

            kmi = None
            if km:
                idname = item.get("idname")

                for kmitem in km.keymap_items:
                    if kmitem.idname == idname:
                        properties = item.get("properties")

                        if properties:
                            if all([getattr(kmitem.properties, name, None) == value for name, value in properties]):
                                kmi = kmitem
                                break

                        else:
                            kmi = kmitem
                            break

            if kmi:
                if idx == 0:
                    box = layout.box()

                label = item.get("label", None)

                if not label:
                    label = name.title().replace("_", " ")

                if len(keylist) > 1:
                    if idx == 0 and not skip_box_label:
                        box.label(text=name.title().replace("_", " "))

                row = box.split(factor=0.15)
                row.label(text=label)

                rna_keymap_ui.draw_kmi(["ADDON", "USER", "DEFAULT"], kc, km, kmi, row, 0)

                infos = item.get("info", [])
                for text in infos:
                    row = box.split(factor=0.15)
                    row.separator()
                    row.label(text=text, icon="INFO")

                isdrawn = True
                idx += 1

        drawn.append(isdrawn)
    return drawn

def get_event_icon(event_type):
    if 'MOUSE' in event_type:
        return 'MOUSE_LMB' if 'LEFT' in event_type else 'MOUSE_RMB' if 'RIGHT' in event_type else 'MOUSE_MMB'

    elif 'EVT_TWEAK' in event_type:
        return f"MOUSE_{'LMB' if event_type.endswith('_L') else 'RMB' if event_type.endswith('_R') else 'MMB'}_DRAG"

    else:
        return f'EVENT_{event_type}'

def get_keymap_item(name, idname, key=None, alt=False, ctrl=False, shift=False, properties=[], iterate=False):
    def return_found_item():
        found = True if key is None else all([kmi.type == key and kmi.alt is alt and kmi.ctrl is ctrl and kmi.shift is shift])

        if found:
            if properties:
                if all([getattr(kmi.properties, name, False) == prop for name, prop in properties]):
                    return kmi
            else:
                return kmi

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user

    km = kc.keymaps.get(name)

    if bpy.app.version >= (3, 0, 0):
        alt = int(alt)
        ctrl = int(ctrl)
        shift = int(shift)

    if km:

        if iterate:
            kmis = [kmi for kmi in km.keymap_items if kmi.idname == idname]

            for kmi in kmis:
                r = return_found_item()

                if r:
                    return r

        else:
            kmi = km.keymap_items.get(idname)

            if kmi:
                return return_found_item()

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

def finish_status(self):
    statusbar.draw = self.bar_orig

def navigation_passthrough(event, alt=True, wheel=False):
    if alt and wheel:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and event.value == 'PRESS') or event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
    elif alt:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'} and event.value == 'PRESS')
    elif wheel:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF') or event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}
    else:
        return event.type in {'MIDDLEMOUSE'} or event.type.startswith('NDOF')

def scroll_up(event, wheel=True, key=False):
    up_key = 'ONE'

    if event.value == 'PRESS':
        if wheel and key:
            return event.type in {'WHEELUPMOUSE', up_key}
        elif wheel:
            return event.type in {'WHEELUPMOUSE'}
        else:
            return event.type in {up_key}

def scroll_down(event, wheel=True, key=False):
    down_key = 'TWO'

    if event.value == 'PRESS':
        if wheel and key:
            return event.type in {'WHEELDOWNMOUSE', down_key}
        elif wheel:
            return event.type in {'WHEELDOWNMOUSE'}
        else:
            return event.type in {down_key} and event.value == 'PRESS'

def get_mousemove_divisor(event, normal=10, shift=100, ctrl=10, sensitivity=1):
    divisor = shift if event.shift else ctrl if event.ctrl else normal
    ui_scale = bpy.context.preferences.system.ui_scale

    return divisor * ui_scale * sensitivity

def ignore_events(event, none=True, timer=True, timer_report=True):
    ignore = ['INBETWEEN_MOUSEMOVE', 'WINDOW_DEACTIVATE']

    if none:
        ignore.append('NONE')

    if timer:
        ignore.extend(['TIMER', 'TIMER1', 'TIMER2', 'TIMER3'])

    if timer_report:
        ignore.append('TIMER_REPORT')

    return event.type in ignore

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

def is_key(self, event, key, onpress=None, onrelease=None, debug=False):
    keystr = f'is_{key.lower()}'

    if getattr(self, keystr, None) is None:
        setattr(self, keystr, False)

    if event.type == key:
        if event.value == 'PRESS':
            if not getattr(self, keystr):
                setattr(self, keystr, True)

                if onpress:
                    onpress()

        elif event.value == 'RELEASE':
            if getattr(self, keystr):
                setattr(self, keystr, False)

                if onrelease:
                    onrelease()

    if debug:
        print()
        print(f"is {key.capitalize()}:", getattr(self, keystr))

    return getattr(self, keystr)

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

    elif context.mode == 'EDIT_CURVE':
        curve = context.active_object.data

        for spline in curve.splines:
            for point in spline.points:
                if not point.hide:
                    point.co = point.co
                    return

def get_scale(context):
    return context.preferences.system.ui_scale * get_prefs().modal_hud_scale

def is_on_screen(context, co2d):
    if 0 <= co2d.x <= context.region.width:
        if 0 <= co2d.y <= context.region.height:
            return True
    return False
