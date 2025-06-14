import bpy
from bpy.props import  BoolProperty, FloatProperty, IntProperty, StringProperty
import os
from time import time
from . import bl_info
from . utils.registration import get_path, get_name, get_addon
from . utils.draw import draw_split_row, draw_fading_label
from . utils.ui import get_keymap_item, draw_keymap_items, get_icon
from . utils.system import get_bl_info_from_file, remove_folder, get_update_files
from . registration import keys as keysdict
from . colors import green, yellow

decalmachine = None
curvemachine = None
machin3tools = None
punchit = None
hypercursor = None

thankyou_time = None

class CURVEmachinePreferences(bpy.types.AddonPreferences):
    path = get_path()
    bl_idname = get_name()

    def update_update_path(self, context):
        if self.avoid_update:
            self.avoid_update = False
            return

        if self.update_path:
            if os.path.exists(self.update_path):
                filename = os.path.basename(self.update_path)

                if filename.endswith('.zip'):
                    split = filename.split('_')

                    if len(split) == 2:
                        addon_name, tail = split

                        if addon_name == bl_info['name']:
                            split = tail.split('.')

                            if len(split) >= 3:
                                dst = os.path.join(self.path, '_update')

                                from zipfile import ZipFile

                                with ZipFile(self.update_path, mode="r") as z:
                                    print(f"INFO: extracting {addon_name} update to {dst}")
                                    z.extractall(path=dst)

                                blinfo = get_bl_info_from_file(os.path.join(dst, addon_name, '__init__.py'))

                                if blinfo:
                                    self.update_msg = f"{blinfo['name']} {'.'.join(str(v) for v in blinfo['version'])} is ready to be installed."

                                else:
                                    remove_folder(dst)

            self.avoid_update = True
            self.update_path = ''

    update_path: StringProperty(name="Update File Path", subtype="FILE_PATH", update=update_update_path)
    update_msg: StringProperty(name="Update Message")

    registration_debug: BoolProperty(name="Addon Terminal Registration Output", default=True)

    blendulate_segment_count: IntProperty(name="Blendulate default Segment Count", description="Use this many Segments, when invoking Blendulate with a single Point selection", default=6, min=0)

    show_sidebar_panel: BoolProperty(name="Show Sidebar Panel", default=True)

    show_curve_split: BoolProperty(name="Show Curve Split tool", default=True)
    show_delete: BoolProperty(name="Show Delete Menu", default=True)
    show_in_curve_context_menu: BoolProperty(name="Show in Edit Curve Context Menu", default=False)

    modal_hud_scale: FloatProperty(name="HUD Scale", default=1, min=0.5, max=10)
    modal_hud_timeout: FloatProperty(name="HUD Timeout", description="Modulate duration of fading HUD elements", default=1, min=0.1, max=10)
    symmetrize_flick_distance: IntProperty(name="Flick Distance", default=75, min=20, max=1000)

    def update_show_update(self, context):
        if self.show_update:
            get_update_files(force=True)

    update_available: BoolProperty()
    show_update: BoolProperty(default=False, update=update_show_update)
    avoid_update: BoolProperty()

    def draw(self, context):
        layout = self.layout

        self.draw_thank_you(layout)

        self.draw_update(layout)

        self.draw_support(layout)

        global decalmachine, curvemachine, machin3tools, punchit, hypercursor

        if decalmachine is None:
            decalmachine = get_addon('DECALmachine')[0]

        if curvemachine is None:
            curvemachine = get_addon('curvemachine')[0]

        if machin3tools is None:
            machin3tools = get_addon('MACHIN3tools')[0]

        if punchit is None:
            punchit = get_addon('PUNCHit')[0]

        if hypercursor is None:
            hypercursor = get_addon('HyperCursor')[0]

        menu_keymap = get_keymap_item('Curve', 'wm.call_menu', properties=[('name', 'MACHIN3_MT_curve_machine')], iterate=True)

        column = layout.column(align=True)
        box = column.box()

        split = box.split()

        b = split.box()

        bb = b.box()
        bb.label(text="Addon")

        column = bb.column()
        draw_split_row(self, column, prop='registration_debug', label='Print Addon Registration Output in System Console')

        bb = b.box()
        bb.label(text="General")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='blendulate_segment_count', label='Blendulate Default Segment Count')

        bb = b.box()
        bb.label(text="Menu")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='show_in_curve_context_menu', label="Show CURVEmachine in Blender's Edit Curve Context Menu")

        if menu_keymap.type in ['Y', 'X']:
            if menu_keymap.type == 'Y':
                draw_split_row(self, column, prop='show_curve_split', label='Show Curve Split Tool', info='Because the Y key is used for the Menu', factor=0.202)

            else:
                draw_split_row(self, column, prop='show_delete', label='Show Delete Tool', info='Because the X key is used for the Menu', factor=0.202)

        bb = b.box()
        bb.label(text="HUD")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='modal_hud_scale', label='Modal HUD Scale')
        draw_split_row(self, column, prop='modal_hud_timeout', label='Timeout', info='Modulate Duration of Fading HUDs', factor=0.202)
        draw_split_row(self, column, prop='symmetrize_flick_distance', label='Flick Distance')

        bb = b.box()
        bb.label(text="3D View")

        column = bb.column(align=True)

        draw_split_row(self, column, prop='show_sidebar_panel', label='Show Sidebar Panel')

        b = split.box()

        b.label(text="Keymaps")
        col = b.column(align=True)

        wm = bpy.context.window_manager
        kc = wm.keyconfigs.user

        draw_keymap_items(kc, 'Curve', keysdict['MENU'], col)
        draw_keymap_items(kc, 'Curve', keysdict['BLEND'], col)
        draw_keymap_items(kc, 'Curve', keysdict['MERGE'], col, skip_box_label=True)
        draw_keymap_items(kc, 'Curve', keysdict['KNIFE'], col)
        draw_keymap_items(kc, 'Curve', keysdict['SYMMETRIZE'], col)

        self.draw_about(layout)

    def draw_thank_you(self, layout):
        global thankyou_time

        message = [f"Thank you for purchasing {bl_info['name']}!",
                   "",
                   "Your support allows me to keep developing this addon and future ones, keeps updates free for everyone, and most importantly enables me to provide for my family.",
                   f"If you haven't purchased {bl_info['name']}, please consider doing so."]

        if thankyou_time is None:
            thankypou_path = os.path.join(get_path(), 'thank_you')

            if not os.path.exists(thankypou_path):
                thankyou_time = time()
                msg = message + ['', str(thankyou_time)]

                with open(thankypou_path, mode='w') as f:
                    f.write('\n'.join(m for m in msg))

            else:
                with open(thankypou_path) as f:
                    lines = [l[:-1] for l in f.readlines()]

                try:
                    thankyou_time = float(lines[-1])

                except:
                    os.unlink(thankypou_path)

        if thankyou_time:
            draw_message = False
            message_lifetime = 5

            if isinstance(thankyou_time, float):
                deltatime = (time() - thankyou_time) / 60
                draw_message = deltatime < message_lifetime

            else:
                draw_message = True
                deltatime = 'X'

            if draw_message:

                b = layout.box()
                b.label(text="Thank You!", icon='INFO')

                col = b.column()

                for i in range(2):
                    col.separator()

                for line in message:
                    if line:
                        col.label(text=line)
                    else:
                        col.separator()

                for i in range(3):
                    col.separator()

                col.label(text=f"This message will self-destruct in {message_lifetime - deltatime:.1f} minutes.", icon='SORTTIME')

                for i in range(3):
                    col.separator()

                col.label(text=f"If you have purchased {bl_info['name']} and find this nag-screen annoying, I appologize.")
                col.label(text=f"If you haven't purchased {bl_info['name']} and find this nag-screen annoying, go fuck yourself.")

    def draw_update(self, layout):
        column = layout.column(align=True)

        row = column.row()
        row.scale_y = 1.25
        row.prop(self, 'show_update', text="Install CURVEmachine Update", icon='TRIA_DOWN' if self.show_update else 'TRIA_RIGHT')

        if self.show_update:
            update_files = get_update_files()

            box = layout.box()
            box.separator()

            if self.update_msg:
                row = box.row()
                row.scale_y = 1.5

                split = row.split(factor=0.4, align=True)
                split.label(text=self.update_msg, icon_value=get_icon('refresh_green'))

                s = split.split(factor=0.3, align=True)
                s.operator('machin3.remove_curvemachine_update', text='Remove Update', icon='CANCEL')
                s.operator('wm.quit_blender', text='Quit Blender + Install Update', icon='FILE_REFRESH')

            else:
                b = box.box()
                col = b.column(align=True)

                row = col.row()
                row.alignment = 'LEFT'

                if update_files:
                    row.label(text="Found the following Updates in your home and/or Downloads folder: ")
                    row.operator('machin3.rescan_curvemachine_updates', text="Re-Scan", icon='FILE_REFRESH')

                    col.separator()

                    for path, tail, _ in update_files:
                        row = col.row()
                        row.alignment = 'LEFT'

                        r = row.row()
                        r.active = False

                        r.alignment = 'LEFT'
                        r.label(text="found")

                        op = row.operator('machin3.use_curvemachine_update', text=f"CURVEmachine {tail}")
                        op.path = path
                        op.tail = tail

                        r = row.row()
                        r.active = False
                        r.alignment = 'LEFT'
                        r.label(text=path)

                else:
                    row.label(text="No Update was found. Neither in your Home directory, nor in your Downloads folder.")
                    row.operator('machin3.rescan_curvemachine_updates', text="Re-Scan", icon='FILE_REFRESH')

                row = box.row()

                split = row.split(factor=0.4, align=True)
                split.prop(self, 'update_path', text='')

                text = "Select CURVEmachine_x.x.x.zip file"

                if update_files:
                    if len(update_files) > 1:
                        text += " or pick one from above"

                    else:
                        text += " or pick the one above"

                split.label(text=text)

            box.separator()

    def draw_support(self, layout):
        column = layout.column(align=True)
        box = column.box()
        box.label(text="Support")

        column = box.column()
        row = column.row()
        row.scale_y = 1.5
        row.operator('machin3.get_curvemachine_support', text='Get Support', icon='GREASEPENCIL')

    def draw_about(self, layout):
        column = layout.column(align=True)
        box = column.box()
        box.label(text="About")

        column = box.column(align=True)
        row = column.row(align=True)

        row.scale_y = 1.5
        row.operator("wm.url_open", text='CURVEmachine', icon='CURVE_DATA').url = 'https://machin3.io/CURVEmachine/'
        row.operator("wm.url_open", text='Documentation', icon='INFO').url = 'https://machin3.io/CURVEmachine/docs'
        row.operator("wm.url_open", text='MACHINƎ.io', icon='WORLD').url = 'https://machin3.io'
        row.operator("wm.url_open", text='blenderartists', icon_value=get_icon('blenderartists')).url = 'https://blenderartists.org/t/curvemachine/1467375'

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='Patreon', icon_value=get_icon('patreon')).url = 'https://patreon.com/machin3'
        row.operator("wm.url_open", text='Twitter', icon_value=get_icon('twitter')).url = 'https://twitter.com/machin3io'
        row.operator("wm.url_open", text='Youtube', icon_value=get_icon('youtube')).url = 'https://www.youtube.com/c/MACHIN3/'
        row.operator("wm.url_open", text='Artstation', icon_value=get_icon('artstation')).url = 'https://www.artstation.com/machin3'

        column.separator()

        row = column.row(align=True)
        row.scale_y = 1.5
        row.operator("wm.url_open", text='DECALmachine', icon_value=get_icon('save' if decalmachine else 'cancel_grey')).url = 'https://decal.machin3.io'
        row.operator("wm.url_open", text='curvemachine', icon_value=get_icon('save' if curvemachine else 'cancel_grey')).url = 'https://mesh.machin3.io'
        row.operator("wm.url_open", text='MACHIN3tools', icon_value=get_icon('save' if machin3tools else 'cancel_grey')).url = 'https://machin3.io/MACHIN3tools'
        row.operator("wm.url_open", text='PUNCHit', icon_value=get_icon('save' if punchit else 'cancel_grey')).url = 'https://machin3.io/PUNCHit'
        row.operator("wm.url_open", text='HyperCursor', icon_value=get_icon('save' if hypercursor else 'cancel_grey')).url = 'https://www.youtube.com/playlist?list=PLcEiZ9GDvSdWs1w4ZrkbMvCT2R4F3O9yD'
