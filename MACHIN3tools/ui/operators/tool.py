import bpy
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, StringProperty

from mathutils import Matrix, Vector

import os

from ... utils.collection import get_active_collection
from ... utils.draw import draw_fading_label, draw_init, draw_label, draw_vector
from ... utils.math import create_rotation_matrix_from_vectors, get_loc_matrix, get_sca_matrix
from ... utils.object import is_instance_collection, parent
from ... utils.raycast import cast_scene_ray_from_mouse, get_closest
from ... utils.registration import get_addon_prefs, get_path, get_prefs
from ... utils.system import load_json, printd, save_json
from ... utils.tools import get_active_tool, get_tool_options, get_tools_from_context, prettify_tool_name
from ... utils.ui import draw_status_item, finish_modal_handlers, finish_status, force_ui_update, get_mouse_pos, get_scale, get_zoom_factor, ignore_events, init_modal_handlers, init_status, popup_message, scroll, scroll_up
from ... utils.view import update_local_view

from ... colors import blue, green, orange, white, yellow
from ... items import  annotate_inputs, letters, numbers, numbers_map, special, specials_map

from ... import MACHIN3toolsManager as M3

class SetToolByName(bpy.types.Operator):
    bl_idname = "machin3.set_tool_by_name"
    bl_label = "MACHIN3: Set Tool by Name"
    bl_description = "Set Tool by Name"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name="Tool name/ID")
    alpha: FloatProperty(name="Alpha", default=0.5, min=0.1, max=1)
    def draw(self, context):
        layout = self.layout
        column = layout.column()

        column.label(text=f"Tool: {self.name}")

    def execute(self, context):
        global first_annotate, first_erase

        active_tool = get_active_tool(context).idname

        if active_tool == 'machin3.tool_hyper_cursor_simple':
            context.space_data.overlay.show_cursor = True

        bpy.ops.wm.tool_set_by_id(name=self.name)

        if 'machin3.tool_hyper_cursor' in self.name:
            size, color = 20, green
        else:
            size, color = 12, white

        draw_fading_label(context, text=prettify_tool_name(self.name), time=get_prefs().HUD_fade_tools_pie, size=size, color=color, move_y=10)

        return {'FINISHED'}

class SetBCPreset(bpy.types.Operator):
    bl_idname = "machin3.set_boxcutter_preset"
    bl_label = "MACHIN3: Set BoxCutter Preset"
    bl_description = "Quickly enable/switch BC tool in/to various modes"
    bl_options = {'REGISTER', 'UNDO'}

    mode: StringProperty()
    shape_type: StringProperty()
    set_origin: StringProperty(default='MOUSE')
    @classmethod
    def poll(cls, context):
        if M3.get_addon("BoxCutter"):
            return M3.addons['boxcutter']['foldername'] in get_tools_from_context(context)

    def execute(self, context):
        tools = get_tools_from_context(context)
        bcprefs = get_addon_prefs('BoxCutter')

        bc = M3.addons['boxcutter']['foldername']

        if not tools[bc]['active']:
            bpy.ops.wm.tool_set_by_id(name=bc)

        options = get_tool_options(context, bc, 'bc.shape_draw')

        if options:
            options.mode = self.mode
            options.shape_type = self.shape_type

            bcprefs.behavior.set_origin = self.set_origin
            bcprefs.snap.enable = True
        return {'FINISHED'}

class ToggleAnnotation(bpy.types.Operator):
    bl_idname = "machin3.toggle_annotation"
    bl_label = "MACHIN3: Toggle Annotation"
    bl_description = "Toggle Annotation Visibility"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if bpy.app.version < (4, 3, 0):
            return context.annotation_data
        else:
            note_gps = [obj for obj in context.visible_objects if obj.type == 'GREASEPENCIL' and 'Annotation' in obj.name]
            return context.annotation_data or note_gps

    def execute(self, context):

        if bpy.app.version < (4, 3, 0):
            is_visible = any(not layer.hide for layer in context.annotation_data.layers)

            if is_visible:
                self.hide_legacy_annotations(context)

            else:
                self.show_legacy_annotations(context)

        else:
            is_annotation_visible = any(not layer.annotation_hide for layer in context.annotation_data.layers) if context.annotation_data else False

            note_gps = [obj for obj in context.visible_objects if obj.type == 'GREASEPENCIL' and 'Annotation' in obj.name]
            is_gp_visible = any([not layer.hide for obj in note_gps for layer in obj.data.layers])

            is_either_visible = is_annotation_visible or is_gp_visible

            if is_either_visible:
                self.hide_annotations(context)

            else:
                self.show_annotations(context)

        return {'FINISHED'}

    def hide_annotations(self, context):
        data = context.annotation_data

        is_annotation_visible = any(not layer.annotation_hide for layer in context.annotation_data.layers) if context.annotation_data else False

        note_gps = [obj for obj in context.visible_objects if obj.type == 'GREASEPENCIL' and 'Annotation' in obj.name]
        is_gp_visible = any([not layer.hide for obj in note_gps for layer in obj.data.layers])

        if is_annotation_visible:
            vis = {}

            for layer in data.layers:
                if len(data.layers) > 1:
                    vis[layer.info] = not layer.annotation_hide

                layer.annotation_hide = True

            context.scene.M3['annotation_visibility'] = vis

        if is_gp_visible:
            for obj in note_gps:
                gpd = obj.data

                vis = {}

                for layer in gpd.layers:

                    if len(gpd.layers) > 1:
                        vis[layer.name] = not layer.hide

                    layer.hide = True

                obj.M3['annotation_visibility'] = vis

    def show_annotations(self, context, force_active=False):
        data = context.annotation_data
        note_gps = [obj for obj in context.visible_objects if obj.type == 'GREASEPENCIL' and 'Annotation' in obj.name]

        if data:
            vis = context.scene.M3.get('annotation_visibility', None)

            for layer in data.layers:
                layer.annotation_hide = not vis[layer.info] if vis and layer.info in vis else False

        if note_gps:
            for obj in note_gps:
                gpd = obj.data
                vis = obj.M3.get('annotation_visibility', None)

                for layer in gpd.layers:
                    layer.hide = not vis[layer.name] if vis and layer.name in vis else False

                if force_active and gpd.layers.active and gpd.layers.active.hide:
                    gpd.layers.active.hide = False

        if not context.space_data.overlay.show_overlays:
            context.space_data.overlay.show_overlays = True

    def hide_legacy_annotations(self, context):
        data = context.annotation_data

        vis = {}

        for layer in data.layers:
            if len(data.layers) > 1:
                vis[layer.info] = not layer.hide

            layer.hide = True

        context.scene.M3['annotation_visibility'] = vis

    def show_legacy_annotations(self, context, force_active=False):
        data = context.annotation_data

        vis = context.scene.M3.get('annotation_visibility', None)

        for layer in data.layers:
            layer.hide = not vis[layer.info] if vis and layer.info in vis else False

        if force_active and context.active_annotation_layer and context.active_annotation_layer.hide:
            context.active_annotation_layer.hide = False

        if not context.space_data.overlay.show_overlays:
            context.space_data.overlay.show_overlays = True

def draw_annotate_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)

        row.label(text="Annotate")

        draw_status_item(row, key='LMB', text="Finish")
        draw_status_item(row, key='RMB', text="Cancel")

        row.separator(factor=10)

        draw_status_item(row, text="Type...", gap=10)

        draw_status_item(row, text="Note", prop=op.text.replace('~', ' | '), gap=2)

        draw_status_item(row, key='MMB_SCROLL', text="Size", prop=round(op.size, 1), gap=2)

        draw_status_item(row, key='BACKSPACE', text="Clear All" if op.is_ctrl else "Backspace", gap=2)

        if not op.is_ctrl:
            draw_status_item(row, key=['SHIFT', 'RETURN'], text="New Line", gap=1)

        draw_status_item(row, active=op.is_ctrl, key='CTRL', text="Special", gap=2)

        if op.is_ctrl:
            draw_status_item(row, active=not op.screen_align, key='C', text="Cursor Align", gap=2)

            draw_status_item(row, key='W', text="Remove Last Word", gap=1)

            if bpy.app.version >= (4, 3, 0):
                draw_status_item(row, key='B', text="Blend Mode", prop=op.frame.id_data.layers.active.blend_mode.title(), gap=1)

            draw_status_item(row, key='RETURN', text="Finish", gap=1)

    return draw

class Annotate(bpy.types.Operator):
    bl_idname = "machin3.annotate"
    bl_label = "MACHIN3: Annotate"
    bl_description = "Annotate"
    bl_options = {'REGISTER', 'UNDO'}

    screen_align: BoolProperty(name="Screen Align Note", default=True)
    multiply: BoolProperty(name="Multiply", default=False)
    size: FloatProperty(name="Size", default=1, min=0.1, max=10)
    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == 'VIEW_3D'

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def draw_HUD(self, context):
        if self.area == context.area:
            draw_init(self)

            dims = draw_label(context, title="Add Note...", coords=Vector((self.HUD_x, self.HUD_y)), center=False)

            self.offset += 18

            dims = draw_label(context, title="Size: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)
            draw_label(context, title=str(round(self.size, 1)), coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, color=yellow)

            if bpy.app.version >= (4, 3, 0):
                self.offset += 18

                layer = self.frame.id_data.layers.active

                dims = draw_label(context, title="Blend Mode: ", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

                color, alpha = (yellow, 1) if layer.blend_mode == 'MULTIPLY' else (white, 0.5)
                draw_label(context, title=layer.blend_mode.title(), coords=Vector((self.HUD_x + dims.x, self.HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)

            self.offset += 18

            if self.screen_align:
                draw_label(context, title="Screen Aligned", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=blue)

            else:
                draw_label(context, title="Cursor Aligned", coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, color=green)

            self.offset += 18

            text = self.text.split('~')

            for t in text:
                self.offset += 15

                draw_label(context, title=t, coords=Vector((self.HUD_x, self.HUD_y)), offset=self.offset, center=False, alpha=0.5)

    def draw_VIEW3D(self, context):
        if context.area == self.area:

            if self.is_prompt_show:
                mx = self.get_annotation_matrix(prompt=True)

                draw_vector(Vector((0.2, 1, 0)), mx=mx, width=3, color=orange if self.is_ctrl else white, alpha=0.5)

    def modal(self, context, event):
        if ignore_events(event, timer=False):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        self.is_ctrl = event.ctrl

        if event.type == 'TIMER':
            self.is_prompt_show = not self.is_prompt_show

        elif event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

        elif scroll(event, key=False):
            if scroll_up(event, key=True):
                self.size += 0.1

            else:
                self.size -= 0.1

            self.refresh_annotation(context)

        elif event.ctrl and event.type in ['S', 'C'] and event.value == 'PRESS':
            self.screen_align = not self.screen_align

            self.refresh_annotation(context)

            force_ui_update(context)

        elif bpy.app.version >= (4, 3, 0) and event.ctrl and event.type in ['B', 'M'] and event.value == 'PRESS':
            if self.frame.id_data.layers.active.blend_mode == 'MULTIPLY':
                self.frame.id_data.layers.active.blend_mode = 'REGULAR'
                self.multiply = False
            else:
                self.frame.id_data.layers.active.blend_mode = 'MULTIPLY'
                self.multiply = True

            force_ui_update(context)

        elif event.type == "LEFTMOUSE" or (event.ctrl and event.type == 'RET'):
            self.finish(context)

            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC']:
            self.finish(context)

            self.remove_entire_note()
            return {'CANCELLED'}

        elif event.type in annotate_inputs and event.value == 'PRESS':

            char = self.get_char_from_event(event)

            if not char:

                if event.type == "RET":
                    self.add_line_break()

                elif event.type == 'BACK_SPACE':
                    if self.text:

                        if event.ctrl:
                            self.remove_entire_note()

                        else:
                            self.remove_last_annotation_character()

                elif event.ctrl and event.type == 'U':
                    self.remove_entire_note()

                elif event.ctrl and event.type == 'W':
                    if self.text:
                        self.remove_last_annotation_word()

            elif char in self.font:
                self.add_annotation_char(context, char)

            force_ui_update(context)

        return {'RUNNING_MODAL'}

    def finish(self, context):
        finish_modal_handlers(self)

        context.window.cursor_set('DEFAULT')

        finish_status(self)

    def invoke(self, context, event):
        fontpath = os.path.join(get_path(), "resources", "annotate", "square_italic.json")

        self.font = self.load_annotate_font(fontpath)

        if self.font:
            self.text = ""

            self.tracking = 0.06
            self.character_offset = Vector((0, 0))

            self.is_prompt_show = True

            self.is_ctrl = False

            self.loc, self.locobj = self.get_depth_location(context)

            self.factor = get_zoom_factor(context, depth_location=self.loc, scale=20 * get_scale(context), ignore_obj_scale=True)

            get_mouse_pos(self, context, event)
            context.window.cursor_set('TEXT')

            self.cmx, self.smx = self.get_alignment_matrices(context)

            self.size = 1

            self.frame = self.get_frame(context)

            init_status(self, context, func=draw_annotate_status(self))

            init_modal_handlers(self, context, hud=True, view3d=True, timer=True, time_step=0.4)
            return {'RUNNING_MODAL'}

        else:
            popup_message("Couldn't find Annotate font", title="Font not found")

        return {'CANCELLED'}

    def load_annotate_font(self, fontpath):
        if os.path.exists(fontpath):
            fontdata = load_json(fontpath)

            for letter, data in fontdata.items():
                data['strokes'] = [[Vector(co) for co in stroke] for stroke in data['strokes']]
                data['dimensions'] = Vector(data['dimensions'])

            return fontdata

    def get_depth_location(self, context):#
        pie_pos = getattr(bpy.types.MACHIN3_MT_tools_pie, "mouse_pos_region", None)
        hitlocation = None
        cache = {}

        if pie_pos:
            _, hitobj, _, hitlocation, _, _ = cast_scene_ray_from_mouse(pie_pos, depsgraph=context.evaluated_depsgraph_get(), exclude_wire=True, cache=cache, debug=False)

            if hitobj and not hitobj.users_scene:

                empty_candidates = []

                for obj in context.visible_objects:
                    if col := is_instance_collection(obj):

                        if col in hitobj.users_collection:
                            empty_candidates.append((obj, col))

                if empty_candidates:

                    if len(empty_candidates) == 1:
                        hitobj = empty_candidates[0][0]

                    else:
                        distances = []

                        for obj, col in empty_candidates:
                            loc = obj.matrix_world @ get_loc_matrix(col.instance_offset) @ hitobj.matrix_world.decompose()[0]

                            distances.append(((loc - hitlocation).length, obj))

                        hitobj = min(distances)[1]

                else:
                    print("WARNING: Could not associate hitlocation with instance collection empty")
                    print("         Nested collection instances? Get in touch with support@machin3.io if you ever see this.")
                    return context.scene.cursor.location, None

        if hitlocation:
            return hitlocation, hitobj

        else:
            return context.scene.cursor.location, None

    def get_alignment_matrices(self, context):
        viewmx = context.space_data.region_3d.view_matrix

        x_dir = Vector((1, 0, 0)) @ viewmx
        y_dir = Vector((0, 1, 0)) @ viewmx
        z_dir = Vector((0, 0, 1)) @ viewmx

        cursor_mx = get_loc_matrix(self.loc) @ context.scene.cursor.rotation_quaternion.to_matrix().to_4x4()
        screen_mx = get_loc_matrix(self.loc) @ create_rotation_matrix_from_vectors(x_dir, y_dir, z_dir)

        return cursor_mx, screen_mx

    def get_annotation_matrix(self, prompt=False):
        extra_offset = self.tracking if prompt else 0

        offsetmx = get_loc_matrix(Vector((self.character_offset.x + extra_offset, self.character_offset.y, 0)))

        if self.screen_align:

            if bpy.app.version < (4, 3, 0) or prompt:
                return self.smx @ get_sca_matrix(Vector.Fill(3, self.factor * self.size)) @ offsetmx
            else:
                return self.gpmx.inverted_safe() @ self.smx @ get_sca_matrix(Vector.Fill(3, self.factor * self.size)) @ offsetmx

        else:
            if bpy.app.version < (4, 3, 0) or prompt:
                return self.cmx @ get_sca_matrix(Vector.Fill(3, self.factor * self.size)) @ offsetmx
            else:
                return self.gpmx.inverted_safe() @ self.cmx @ get_sca_matrix(Vector.Fill(3, self.factor * self.size)) @ offsetmx

    def get_char_from_event(self, event):
        char = None

        if event.ctrl:
            return

        if event.type in letters:
            if event.shift:
                char = event.type

            else:
                char = event.type.lower()

        elif event.type in numbers:

            if event.shift and event.type == "ONE":
                char = "!"

            elif event.shift and event.type == "TWO":
                char = '"'

            elif event.shift and event.type == "THREE":
                char = "?"

            elif event.shift and event.type == "ZERO":
                char = "="

            elif event.shift and event.type == "QUOTE":
                char = "'"

            else:
                char = str(numbers_map[event.type])

        elif event.type in special:

            if event.shift and event.type == "SLASH":
                char = "?"

            elif event.shift and event.type == "PERIOD":
                char = ":"

            elif event.shift and event.type == "PLUS":
                char = "*"

            elif event.type == "LEFT_BRACKET":
                char = "("

            elif event.type == "RIGHT_BRACKET":
                char = ")"

            else:
                char = specials_map[event.type]

        return char

    def get_frame(self, context):
        if bpy.app.version < (4, 3, 0):

            if not context.active_annotation_layer:
                bpy.ops.gpencil.annotation_add()

            layer = context.active_annotation_layer

            ToggleAnnotation.show_legacy_annotations(self, context, force_active=True)

            if not layer.frames or not layer.active_frame:
                return layer.frames.new(context.scene.frame_current)

            else:
                return layer.active_frame

        else:
            active = context.active_object if context.active_object and context.active_object.select_get() else None
            mcol = context.scene.collection
            view = context.space_data

            gp = self.get_annotation_object(context, active, mcol, view)
            gpd = gp.data

            self.gpmx = gp.matrix_world

            if gp.data.layers:
                layer = gpd.layers.active
                self.multiply = layer.blend_mode == 'MULTIPLY'

            else:
                layer = gpd.layers.new(name="Note")

                layer.tint_color = Vector(gp.color).resized(3)
                layer.tint_factor = 1

                if self.multiply:
                    layer.blend_mode = 'MULTIPLY'

            ToggleAnnotation.show_annotations(self, context, force_active=True)

            if layer.current_frame():
                return layer.current_frame()

            else:
                return layer.frames.new(0)

    def add_annotation_char(self, context, char):
        mx = self.get_annotation_matrix()

        for coords in self.font[char]['strokes']:

            if bpy.app.version < (4, 3, 0):
                stroke = self.frame.strokes.new()
                stroke.points.add(len(coords))

                for point, co in zip(stroke.points, coords):
                    point.co = mx @ co.resized(3)

            else:
                drawing = self.frame.drawing
                drawing.add_strokes([len(coords)])

                stroke = drawing.strokes[-1]
                stroke.cyclic = False     # note sure if it helps, but sometimes strokes get cyclic when going into edit mode and selecting all? hard to reproruce, so setting it to False explicitely for now

                radius = 0.05 * self.factor * self.size

                for point, co in zip(stroke.points, coords):
                    point.position = mx @ co.resized(3)

                    point.radius = radius

        self.character_offset.x += self.font[char]['dimensions'].x + self.tracking

        self.text += char

    def add_line_break(self):
        self.text += "~"

        self.character_offset.x = 0
        self.character_offset.y -= 1.3

    def remove_last_annotation_character(self):
        last_char = self.text[-1]

        if last_char == '~':
            prev_line = self.text[:-1].split('~')[-1]

            self.character_offset.x = sum([self.font[char]['dimensions'].x + self.tracking for char in prev_line])
            self.character_offset.y += 1.3

        else:

            for i in range(len(self.font[last_char]['strokes'])):
                if bpy.app.version < (4, 3, 0):
                    self.frame.strokes.remove(self.frame.strokes[-1])

                else:
                    drawing = self.frame.drawing
                    idx = len(drawing.strokes) - 1          # NOTE: -1 does not work here for some reason
                    drawing.remove_strokes(indices=[idx])

            self.character_offset.x -= self.font[last_char]['dimensions'].x + self.tracking

        self.text = self.text[:-1]

    def remove_last_annotation_word(self):
        last_word = ""

        for char in reversed(self.text):
            if char == " ":

                if last_word.strip():
                    break

                else:
                    last_word += char

            elif char == '~':

                if last_word:
                    break

                else:
                    self.remove_last_annotation_character()

            else:
                last_word += char

        for char in last_word:
            self.remove_last_annotation_character()

    def remove_entire_note(self):
        strokecount = 0

        for char in self.text:

            if char == '~':
                continue

            strokecount += len(self.font[char]['strokes'])

        for i in range(strokecount):
            if bpy.app.version < (4, 3, 0):
                self.frame.strokes.remove(self.frame.strokes[-1])
            else:
                drawing = self.frame.drawing
                idx = len(drawing.strokes) - 1            # NOTE: -1 does not work here for some reason
                drawing.remove_strokes(indices=[idx])

        self.character_offset = Vector((0, 0))

        self.text = ""

    def refresh_annotation(self, context):
        text = self.text

        self.remove_entire_note()

        for char in text:

            if char == '~':
                self.add_line_break()

            else:
                self.add_annotation_char(context, char)

    def add_grease_pencil_annotation_object(self, active, col, view):
        name = f"{active.name}_Annotation" if active else "Scene_Annotation"

        gpd = bpy.data.grease_pencils_v3.new(name)
        gp = bpy.data.objects.new(name, gpd)

        gp.show_in_front = True

        gp.color = (0.12, 0.33, 0.57, 1)

        blues = [mat for mat in bpy.data.materials if mat.name == 'NoteMaterial' and mat.is_grease_pencil]
        mat = blues[0] if blues else bpy.data.materials.new(name='NoteMaterial')

        bpy.data.materials.create_gpencil_data(mat)
        gp.data.materials.append(mat)

        mat.grease_pencil.color = gp.color

        col.objects.link(gp)

        if active:

            loc, rot, _ = active.matrix_world.decompose()
            gp.matrix_world = Matrix.LocRotScale(loc, rot, Vector((1, 1, 1)))

            parent(gp, active)

        update_local_view(view, [(gp, True)])

        return gp

    def get_annotation_object(self, context, active, mcol, view):
        if self.locobj:
            active = self.locobj

        if active:

            if active.type == "GREASEPENCIL" and "_Annotation" in active.name:
                gp = active

            else:
                annotations = [obj for obj in active.children if obj.type == "GREASEPENCIL" and "_Annotation" in obj.name]

                if annotations:
                    gp = annotations[0]

                else:
                    gp = self.add_grease_pencil_annotation_object(active, mcol, view)

        else:
            annotations = [obj for obj in context.scene.objects if obj.type == "GREASEPENCIL" and "_Annotation" in obj.name and not obj.parent]

            if annotations:
                gp = annotations[0]

            else:
                gp = self.add_grease_pencil_annotation_object(None, mcol, view)

        return gp

class PrepareAnnotateFont(bpy.types.Operator):
    bl_idname = "machin3.prepare_annotate_font"
    bl_label = "MACHIN3: Prepare Annotate Font"
    bl_description = "Prepare Annotate Font from imported svg letter set"
    bl_options = {'REGISTER', 'UNDO'}

    origin_offset: FloatVectorProperty(name="Origin Offset", default=Vector((-0.137, -1.318, 0)), step=0.1)
    scale_offset: FloatProperty(name="Scale Offset", default=47, step=0.1)
    tracking: FloatProperty(name="Tracking", default=0.06, step=0.1)
    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        row = column.row()
        row.prop(self, "origin_offset", text="")

        row = column.row()
        row.prop(self, "scale_offset")

        row = column.row()
        row.prop(self, "tracking")

    def execute(self, context):
        dg = context.evaluated_depsgraph_get()
        col = get_active_collection(context)

        if col:

            bpy.ops.object.select_all(action='DESELECT')

            for idx, obj in enumerate(col.objects):
                if obj.type != 'MESH':
                    obj.select_set(True)

                if idx:
                    obj.matrix_world = col.objects[0].matrix_world

            if context.selected_objects:
                bpy.ops.object.convert(target='MESH')
                bpy.ops.object.convert(target='CURVE')

            for obj in col.objects:
                obj.data.transform(get_loc_matrix(self.origin_offset) @ get_sca_matrix(Vector((self.scale_offset, self.scale_offset, self.scale_offset))))

            dg.update()

            offset_x = 0

            for obj in col.objects:
                obj.location.x += offset_x
                offset_x += obj.dimensions.x + self.tracking

        else:
            popup_message("Ensure there is an active collection containing a set of importeded svg letter objects", title="Select a Collection")

        return {'FINISHED'}

class CreateAnnotateFont(bpy.types.Operator):
    bl_idname = "machin3.create_annotate_font"
    bl_label = "MACHIN3: Create Annotate Font"
    bl_description = "Create Annotate Font from prepared mesh letter set"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return False

    def draw(self, context):
        layout = self.layout
        _column = layout.column(align=True)

    def execute(self, context):
        col = get_active_collection(context)

        letter_dict = {}

        if col:

            bpy.ops.object.select_all(action='DESELECT')

            for idx, obj in enumerate(col.objects):
                if obj.type == 'CURVE' and all(spline.type == 'POLY' for spline in obj.data.splines):
                    print("found letter:", obj.name)

                    obj.select_set(True)

                    letter_dict[obj.name] = {'strokes': [[(point.co.x, point.co.y) for point in spline.points] for spline in obj.data.splines],
                                             'dimensions': (obj.dimensions.x, obj.dimensions.y)}

            printd(letter_dict)

            path = bpy.data.filepath.replace('.blend', '.json')
            save_json(letter_dict, path)

            print("saved to:", path)
        else:
            popup_message("Ensure there is an active collection containing a set of importeded svg letter objects", title="Select a Collection")

        return {'FINISHED'}

class SurfaceDraw(bpy.types.Operator):
    bl_idname = "machin3.surface_draw"
    bl_label = "MACHIN3: Surface Draw"
    bl_description = "Surface Draw, create parented, empty GreasePencil object and enter DRAW mode.\nSHIFT: Select the Line tool."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.active_object

    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode='OBJECT')

        scene = context.scene
        ts = scene.tool_settings
        mcol = context.scene.collection
        view = context.space_data
        active = context.active_object

        existing_gps = [obj for obj in active.children if obj.type == ("GPENCIL" if bpy.app.version < (4, 3, 0) else "GREASEPENCIL") and "_SurfaceDrawing" in obj.name]

        if existing_gps:
            gp = existing_gps[0]

        else:
            name = f"{active.name}_SurfaceDrawing"
            gpd = bpy.data.grease_pencils.new(name) if bpy.app.version < (4, 3, 0) else bpy.data.grease_pencils_v3.new(name)
            gp = bpy.data.objects.new(name, gpd)

            mcol.objects.link(gp)

            gp.matrix_world = active.matrix_world
            parent(gp, active)

        update_local_view(view, [(gp, True)])

        layer = gp.data.layers.new(name="SurfaceLayer")
        layer.blend_mode = 'MULTIPLY'

        if not layer.frames:
            layer.frames.new(0)

        context.view_layer.objects.active = gp
        active.select_set(False)
        gp.select_set(True)

        gp.color = (0, 0, 0, 1)

        blacks = [mat for mat in bpy.data.materials if mat.name == 'Black' and mat.is_grease_pencil]
        mat = blacks[0] if blacks else bpy.data.materials.new(name='Black')

        bpy.data.materials.create_gpencil_data(mat)
        gp.data.materials.append(mat)

        ts.gpencil_stroke_placement_view3d = 'SURFACE'

        if not view.show_region_toolbar:
            view.show_region_toolbar = True

        if bpy.app.version < (4, 3, 0):

            bpy.ops.object.mode_set(mode='PAINT_GPENCIL')

            gp.data.zdepth_offset = 0.01

            ts.gpencil_paint.brush.gpencil_settings.pen_strength = 1

            opacity = gp.grease_pencil_modifiers.new(name="Opacity", type="GP_OPACITY")
            opacity.show_expanded = False
            thickness = gp.grease_pencil_modifiers.new(name="Thickness", type="GP_THICK")
            thickness.show_expanded = False

            if event.shift:
                bpy.ops.wm.tool_set_by_id(name="builtin.line")

                props = get_tool_options(context, 'builtin.line', "GPENCIL_OT_primitive_line")

                if props.subdivision <= 10:
                    props.subdivision = 50

            else:
                bpy.ops.wm.tool_set_by_id(name="builtin_brush.Draw")

        else:

            bpy.ops.object.mode_set(mode='PAINT_GREASE_PENCIL')

            ts.gpencil_surface_offset = 0.01

            ts.gpencil_paint.brush.strength = 1

            opacity = gp.modifiers.new(name="Opacity", type="GREASE_PENCIL_OPACITY")
            opacity.show_expanded = False
            thickness = gp.modifiers.new(name="Thickness", type="GREASE_PENCIL_THICKNESS")
            thickness.show_expanded = False

            if event.shift:
                bpy.ops.wm.tool_set_by_id(name="builtin.line")

                props = get_tool_options(context, 'builtin.line', "GREASE_PENCIL_OT_primitive_line")

                if props.subdivision <= 10:
                    props.subdivision = 50

            else:
                bpy.ops.wm.tool_set_by_id(name="builtin.brush")

        return {'FINISHED'}

class ShrinkwrapGreasePencil(bpy.types.Operator):
    bl_idname = "machin3.shrinkwrap_grease_pencil"
    bl_label = "MACHIN3: ShrinkWrap Grease Pencil"
    bl_description = "Shrinkwrap current Grease Pencil Layer to closest mesh surface based on Surface Offset value"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active = context.active_object
        if active and active.type in ['GPENCIL', 'GREASEPENCIL']:
            return active.data.layers.active

    def execute(self, context):
        dg = context.evaluated_depsgraph_get()

        ts = context.scene.tool_settings
        gp = context.active_object
        mx = gp.matrix_world

        layer = gp.data.layers.active

        if bpy.app.version < (4, 3, 0):
            offset = gp.data.zdepth_offset
            frame = layer.active_frame

            for stroke in frame.strokes:
                for idx, point in enumerate(stroke.points):
                    closest, _, co, no, _, _ = get_closest(mx @ point.co, depsgraph=dg, debug=False)

                    if closest:
                        point.co = mx.inverted_safe() @ (co + no * offset)

        else:
            offset = ts.gpencil_surface_offset
            drawing = layer.current_frame().drawing

            if False:
                for att in drawing.attributes:
                    if att.domain == 'POINT' and att.name == 'position':

                        for a in att.data:
                            closest, _, co, no, _, _ = get_closest(mx @ a.vector, depsgraph=dg, debug=False)

                            if closest:
                                a.vector = mx.inverted_safe() @ (co + no * offset)

                        break

            else:
                for stroke in drawing.strokes:
                    for point in stroke.points:
                        closest, _, co, no, _, _ = get_closest(mx @ point.position, depsgraph=dg, debug=False)

                        if closest:
                            point.position = mx.inverted_safe() @ (co + no * offset)

        return {'FINISHED'}
