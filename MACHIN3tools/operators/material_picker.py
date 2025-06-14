import os

import bmesh
import bpy
from bpy.props import BoolProperty
from mathutils import Matrix, Vector

from .. utils.registration import get_prefs

from ..colors import blue, green, red, white, yellow
from ..items import alt, ctrl, shift

from ..utils.asset import get_asset_details_from_space, get_import_method_from_library_path
from ..utils.color import lighten, linear_to_srgb
from ..utils.draw import draw_init, draw_label, draw_line, draw_mesh_wire, draw_region_border
from ..utils.material import get_last_node
from ..utils.mesh import get_coords, get_eval_mesh
from ..utils.object import get_eval_object, hide_render, remove_obj
from ..utils.raycast import cast_scene_ray_from_mouse
from ..utils.ui import  draw_status_item, finish_modal_handlers, finish_status, force_ui_update, get_mouse_pos, get_region_space_co2d, get_scale, ignore_events, init_modal_handlers, init_status

def draw_material_pick_status(op):
    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)

        if op.has_material_editor:
            if op.has_object_selection or op.has_face_selection:

                if op.assign or op.assign_from_assetbrowser:
                    draw_status_item(row, text="Material Assign")
                else:
                    draw_status_item(row, text="Material Pick")
                    draw_status_item(row, active=op.assign, key='ALT', text="Assign")

            else:
                draw_status_item(row, text="Material Pick")

        else:
            draw_status_item(row, text=f"Material {'Assign' if op.assign or op.assign_from_assetbrowser else 'Pick'}")

        if op.has_asset_browser and 'ASSIGN_FROM_ASSETBROWSER' in op.modes:
            draw_status_item(row, active=op.assign_from_assetbrowser, key='CTRL' if len(op.modes) > 1 else [], text="from Assetbrowser")

            if op.assign_from_assetbrowser:
                if op.has_object_selection:
                    text = "to Selection"

                    if op.assign_from_assetbrowser_to_selection:
                        text += " + Finish"

                    draw_status_item(row, active=op.assign_from_assetbrowser_to_selection, key=['SHIFT', 'LMB'] if op.assign_from_assetbrowser_to_selection else 'SHIFT', text=text)

                if not op.assign_from_assetbrowser_to_selection:
                    draw_status_item(row, key='LMB' if op.hit_object_name else 'MOVE', text="to Object Under Mouse")

        if not op.assign_from_assetbrowser:
            text = f"from {'Object' if op.hit_object_name is None else op.hit_object_name}"
            draw_status_item(row, active=bool(op.hit_object_name), key='LMB' if op.hit_object_name else 'MOVE', text=text)

        draw_status_item(row, key='MMB', text="Viewport")
        draw_status_item(row, key='ESC', text="Cancel")

        if op.has_object_selection or op.has_face_selection:
            draw_status_item(row, key='X', text="Clear Materials + Finish", gap=10)

    return draw

class MaterialPicker(bpy.types.Operator):
    bl_idname = "machin3.material_picker"
    bl_label = "MACHIN3: Material Picker"
    bl_description = "Pick and/or assign Material from the 3D View, or batch assign from the Assetbrowser"
    bl_options = {'REGISTER', 'UNDO'}

    is_keymap: BoolProperty(name="is Keymap Invocation", default=False)
    passthrough = None

    @classmethod
    def poll(cls, context):
        if context.mode in ['OBJECT', 'EDIT_MESH']:
            return context.area and context.area.type == 'VIEW_3D'

    def draw_HUD(self, context):
        if (area := context.area) in [area['area'] for area in self.areas['VIEW_3D']]:

            HUD_x, HUD_y = self.get_per_area_HUD_coords(context, area)

            if HUD_x and HUD_y:
                draw_init(self)

                title, color = ("Assign", yellow) if self.assign or self.assign_from_assetbrowser else ("Pick", white)
                dims = draw_label(context, title=title, coords=Vector((HUD_x, HUD_y)), color=color, center=False)

                if self.assign_from_assetbrowser:

                    dims += draw_label(context, title=" from Asset Browser ", coords=Vector((HUD_x + dims.x, HUD_y)), color=green, center=False)

                    if self.asset['error']:
                        self.offset += 18
                        draw_label(context, title=self.asset['error'], coords=Vector((HUD_x, HUD_y)), offset=self.offset, center=False, color=red)

                    else:
                        draw_label(context, title=self.asset['import_type'], coords=Vector((HUD_x + dims.x, HUD_y)), center=False, alpha=0.3)

                        self.offset += 18

                        title = f"{self.asset['library']} • {self.asset['blend_name']} • "
                        dims = draw_label(context, title=title, coords=Vector((HUD_x, HUD_y)), offset=self.offset, center=False, alpha=0.5)

                        title = f"{self.asset['material_name']}"
                        draw_label(context, title=title, coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False)

                        self.offset += 18

                        dims = draw_label(context, title="to: ", coords=Vector((HUD_x, HUD_y)), offset=self.offset, center=False, alpha=0.25)

                        if context.mode == 'OBJECT':

                            if self.assign_from_assetbrowser_to_selection:
                                for idx, obj in enumerate(self.sel):
                                    if idx > 0:
                                        self.offset += 18

                                    draw_label(context, title=obj.name, coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, alpha=0.5)

                            else:
                                color, alpha = (red, 1) if self.hit_object_name is None else (white, 0.5)
                                draw_label(context, title=str(self.hit_object_name), coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, color=color, alpha=alpha)

                        elif context.mode == 'EDIT_MESH':
                            draw_label(context, title="Face Selection", coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, color=blue)

                else:
                    self.offset += 18

                    color = white if self.hit_material_name else red

                    dims = draw_label(context, title='Material: ', coords=Vector((HUD_x, HUD_y)), offset=self.offset, center=False, alpha=0.5)
                    start_dims = dims.copy()

                    dims += draw_label(context, title=str(self.hit_material_name), coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, color=color)
                    end_dims = dims.copy()

                    if self.assign and self.hit_material_name and self.hit_object_name:
                        dims += draw_label(context, title=' from: ', coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, alpha=0.25)
                        draw_label(context, title=self.hit_object_name, coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, alpha=0.5)

                    if self.hit_material_color:
                        scale = get_scale(context)

                        draw_line([Vector((HUD_x + start_dims.x - 1, HUD_y - start_dims.y * 3, 0)), Vector((HUD_x + end_dims.x + 1, HUD_y - start_dims.y * 3, 0))], width=12 * scale, alpha=0.1)
                        draw_line([Vector((HUD_x + start_dims.x, HUD_y - start_dims.y * 3, 0)), Vector((HUD_x + end_dims.x, HUD_y - start_dims.y * 3, 0))], color=self.hit_material_color, width=10 * scale)

                        self.offset += 18

                    if self.assign and self.hit_material_name:
                        self.offset += 18

                        dims = draw_label(context, title="to: ", coords=Vector((HUD_x, HUD_y)), offset=self.offset, center=False, alpha=0.25)

                        if context.mode == 'OBJECT':
                            for idx, obj in enumerate(self.sel):
                                if idx > 0:
                                    self.offset += 18

                                draw_label(context, title=obj.name, coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, alpha=0.5)

                        elif context.mode == 'EDIT_MESH':
                            draw_label(context, title="Face Selection", coords=Vector((HUD_x + dims.x, HUD_y)), offset=self.offset, center=False, color=blue)

    def draw_HUD_AB(self, context):
        if len(self.areas['ASSET_BROWSER']) > 1:
            is_active = context.area in [area['area'] for area in self.areas['ASSET_BROWSER'] if area['is_active']]

            if is_active:
                draw_region_border(context.region, width=2, alpha=0.5)

    def draw_VIEW3D(self, context):
        if context.area in [area['area'] for area in self.areas['VIEW_3D']]:
            if context.mode == 'OBJECT':
                alpha = 0.2

                if self.assign_from_assetbrowser and not self.asset['error']:

                    if self.assign_from_assetbrowser_to_selection:
                        for obj in self.sel:

                            batch = self.batches.get(obj.name, None)

                            if batch:
                                draw_mesh_wire(batch, color=green, alpha=alpha)

                    elif self.hit_object_name:
                        batch = self.batches.get(self.hit_object_name, None)

                        if batch:
                            draw_mesh_wire(batch, color=green, alpha=alpha)

                elif self.assign and self.hit_material_name:

                    for obj in self.sel:

                        if obj.name != self.hit_object_name:
                            batch = self.batches.get(obj.name, None)

                            if batch:
                                draw_mesh_wire(batch, color=blue, alpha=alpha)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        self.tag_redraw_areas()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event, window=True, hud=False)

        area_under_mouse = self.get_area_type_under_mouse(self.mouse_pos_window)

        if self.passthrough and area_under_mouse != 'ASSET_BROWSER':
            self.passthrough = False
            context.window.cursor_set("EYEDROPPER")

            self.update_areas_asset_data(context)

            self.asset = self.get_selected_asset(context, debug=False)

        if area_under_mouse == 'ASSET_BROWSER':
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif area_under_mouse == 'VIEW_3D':

            if 'ASSIGN_FROM_ASSETBROWSER' in self.modes and not (self.assign and 'PICK' in self.modes) and event.type in ctrl and event.value == 'PRESS':
                self.set_mode(context, mode='ASSIGN_FROM_ASSETBROWSER')

            elif 'ASSIGN' in self.modes and not self.assign_from_assetbrowser and event.type in alt and event.value == 'PRESS':
                self.set_mode(context, mode='ASSIGN')

                if self.assign:
                    self.populate_batches(self.sel)

            elif event.value == 'RELEASE' and (event.type in alt and not event.ctrl or event.type in ctrl and not event.alt):
                self.set_mode(context, mode=self.modes[0])

            if self.assign_from_assetbrowser and self.has_object_selection:
                self.assign_from_assetbrowser_to_selection = event.shift

            if event.type in [*alt, *ctrl, *shift]:
                force_ui_update(context)

            if 'PICK' in self.modes and event.type in [*alt, *ctrl]:
                if event.value == 'PRESS' and (self.assign or self.assign_from_assetbrowser):
                    context.window.cursor_set("PAINT_CROSS")

                elif not self.assign and not self.assign_from_assetbrowser:
                    context.window.cursor_set("EYEDROPPER")

            if event.type == 'MOUSEMOVE':
                hitobj, matindex = self.get_material_hit(context, debug=False)

                if hitobj and hitobj.name not in self.batches:
                    self.populate_batches([hitobj])

                mat, self.hit_material_name, self.hit_object_name = self.get_material_from_hit(hitobj, matindex)

                if not self.assign_from_assetbrowser:
                    self.hit_material_color = self.get_material_color_from_material(mat, srgb=True)

                force_ui_update(context)

            elif (self.has_object_selection or self.has_face_selection) and event.type == 'X' and event.value == 'PRESS':

                if context.mode == 'OBJECT':
                    for obj in self.sel:
                        obj.data.materials.clear()

                elif context.mode == 'EDIT_MESH':
                    self.clear_material_in_editmode(context)

                self.finish(context)
                return {'FINISHED'}

            elif (self.is_keymap and event.type in ['RIGHTMOUSE'] and event.value == 'RELEASE') or event.type in ['LEFTMOUSE', 'SPACE'] and event.value == 'PRESS':

                if self.assign_from_assetbrowser:

                    if self.asset['error']:
                        self.finish(context)
                        return {'FINISHED'}

                    else:

                        mat = self.get_material_from_assetbrowser(context)

                        if context.mode == 'OBJECT':

                            if self.assign_from_assetbrowser_to_selection:
                                for obj in self.sel:
                                    if not obj.material_slots:
                                        obj.data.materials.append(mat)

                                    else:
                                        obj.material_slots[obj.active_material_index].material = mat

                                self.finish(context)
                                return {'FINISHED'}

                            elif event.type in ['LEFTMOUSE']:
                                hitobj, matindex = self.get_material_hit(context, debug=False)

                                if hitobj:
                                    if hitobj.material_slots:
                                        hitobj.material_slots[matindex].material = mat
                                    else:
                                        hitobj.data.materials.append(mat)

                                    self.dg.update()
                                    return {'RUNNING_MODAL'}

                            else:
                                self.finish(context)
                                return {'FINISHED'}

                        elif context.mode == 'EDIT_MESH':
                            self.assign_material_in_editmode(context, mat)

                            self.finish(context)
                            return {'FINISHED'}

                elif self.assign:
                    hitobj, matindex = self.get_material_hit(context, debug=False)

                    if hitobj:
                        mat, matname, _ = self.get_material_from_hit(hitobj, matindex)

                        if mat:

                            if context.mode == 'OBJECT':
                                sel = [obj for obj in self.sel if obj != hitobj]

                                for obj in sel:
                                    if not obj.material_slots:
                                        obj.data.materials.append(mat)

                                    else:
                                        obj.material_slots[obj.active_material_index].material = mat

                            elif context.mode == 'EDIT_MESH':
                                self.assign_material_in_editmode(context, mat)

                    self.finish(context)
                    return {'FINISHED'}

                else:
                    hitobj, matindex = self.get_material_hit(context, debug=False)

                    if hitobj and matindex is not None:

                        if hitobj.name not in context.view_layer.objects:
                            self.create_material_dummy_object(context, hitobj, matindex)

                            self.finish(context)
                            return {'FINISHED'}

                        iseditmode = context.mode == 'EDIT_MESH'

                        if (active := context.active_object) != hitobj:
                            if iseditmode:
                                bpy.ops.object.mode_set(mode='OBJECT')

                            if active:
                                active.select_set(False)

                            context.view_layer.objects.active = hitobj

                            if iseditmode:
                                bpy.ops.object.mode_set(mode='EDIT')

                        hitobj.active_material_index = matindex

                    self.finish(context)
                    return {'FINISHED'}

            elif event.type == 'MIDDLEMOUSE':
                return {'PASS_THROUGH'}

            elif event.type in ['RIGHTMOUSE', 'ESC']:
                self.finish(context)
                return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        finish_modal_handlers(self)

        if self.has_asset_browser:
            bpy.types.SpaceFileBrowser.draw_handler_remove(self.HUD_AB, 'WINDOW')

        context.window.cursor_set("DEFAULT")

        if wires := self.hittable_cache['force_excluded_wire_objects']:
            for obj in wires:
                obj.hide_viewport = False

        finish_status(self)

        force_ui_update(context)

    def invoke(self, context, event):
        self.remove_material_dummy_objects()

        shading = context.space_data.shading
        shading_types = ['MATERIAL', 'RENDERED']

        if shading.type == 'SOLID':
            if shading.color_type in ['MATERIAL']:
                shading_types.append('SOLID')

        if context.space_data.shading.type not in shading_types:
            return {'PASS_THROUGH'}

        if not context.visible_objects:
            return {'PASS_THROUGH'}

        self.dg = context.evaluated_depsgraph_get()
        self.sel = [obj for obj in context.selected_objects if obj.type in ['MESH', 'CURVE', 'FONT', 'SURFACE', 'META']]

        self.areas = self.get_areas(context)

        self.has_material_editor = 'MATERIAL_EDITOR' in self.areas
        self.has_asset_browser = 'ASSET_BROWSER' in self.areas

        self.has_object_selection = bool(context.mode == 'OBJECT' and self.sel)
        self.has_face_selection = False

        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            faces = [f for f in bm.faces if f.select]
            self.has_face_selection = bool(faces)

            del bm, faces

        if not self.set_mode(context, init=True):
            return {'PASS_THROUGH'}

        self.batches = {}

        if self.assign:
            self.populate_batches(self.sel)

        get_mouse_pos(self, context, event, window=True, hud=False)
        context.window.cursor_set("EYEDROPPER" if 'PICK' in self.modes else 'PAINT_CROSS')

        self.hittable_cache = {}

        hitobj, matindex = self.get_material_hit(context, debug=False)

        mat, self.hit_material_name, self.hit_object_name = self.get_material_from_hit(hitobj, matindex)

        self.hit_material_color = self.get_material_color_from_material(mat, srgb=True)

        self.asset = self.get_selected_asset(context, debug=False)

        init_status(self, context, func=draw_material_pick_status(self))

        force_ui_update(context)

        init_modal_handlers(self, context, hud=True, view3d=True)

        if self.has_asset_browser:
            self.HUD_AB = bpy.types.SpaceFileBrowser.draw_handler_add(self.draw_HUD_AB, (context, ), 'WINDOW', 'POST_PIXEL')

        self.tag_redraw_areas()
        return {'RUNNING_MODAL'}

    def set_mode(self, context, mode='PICK', init=False):
        if init:
            self.modes = []

            if bpy.data.materials:

                if 'MATERIAL_EDITOR' in self.areas:
                    self.modes.append('PICK')

                if self.has_object_selection or self.has_face_selection:
                    self.modes.append('ASSIGN')

            if self.has_asset_browser and (context.mode == 'OBJECT' or (context.mode == 'EDIT_MESH' and self.has_face_selection)):
                self.modes.append('ASSIGN_FROM_ASSETBROWSER')

            if not self.modes:
                return False

            self.assign_from_assetbrowser_to_selection = False

            mode = self.modes[0]

        if mode == 'PICK':
            self.assign = False
            self.assign_from_assetbrowser = False

        elif mode == 'ASSIGN':
            self.assign = True
            self.assign_from_assetbrowser = False

        elif mode == 'ASSIGN_FROM_ASSETBROWSER':
            self.assign = False
            self.assign_from_assetbrowser = True

        return True

    def populate_batches(self, objects):
        for obj in objects:
            if obj.name not in self.batches:
                mesh_eval = get_eval_mesh(self.dg, obj, data_block=False)
                self.batches[obj.name] = get_coords(mesh_eval, mx=obj.matrix_world, indices=True)

    def get_areas(self, context):
        areas = {}

        for area in context.screen.areas:

            if area.type == 'FILE_BROWSER' and area.ui_type == 'ASSETS':
                area_type = 'ASSET_BROWSER'

            elif area.type == 'NODE_EDITOR':
                area_type = area.type

                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':

                        if space.tree_type == 'ShaderNodeTree' and space.shader_type == 'OBJECT':
                            area_type = 'MATERIAL_EDITOR'
                            break

            else:
                area_type = area.type

            data = {'area': area,
                    'x': (area.x, area.x + area.width),
                    'y': (area.y, area.y + area.height)}

            if area_type == 'ASSET_BROWSER':

                space = area.spaces.active
                data['space'] = space

                asset = self.get_asset_data_from_asset_browser_space(context, space)
                data['asset'] = asset

            if area_type in areas:
                areas[area_type].append(data)

            else:
                areas[area_type] = [data]

        if 'ASSET_BROWSER' in areas:
            for data in (browsers := areas['ASSET_BROWSER']):
                data['is_active'] = len(browsers) == 1

        for data in areas['VIEW_3D']:
            data['is_active'] = data['area'] == context.area

        return areas

    def get_area_type_under_mouse(self, mouse_pos):
        for area_type, areas in self.areas.items():
            for area in areas:
                if area['x'][0] <= mouse_pos.x <= area['x'][1]:

                    if area['y'][0] <= mouse_pos.y <= area['y'][1]:

                        if area_type in ['VIEW_3D', 'ASSET_BROWSER'] and not area['is_active']:
                            for a in areas:
                                a['is_active'] = a['area'] == area['area']

                        return area_type

    def get_window_region_from_area(self, area):
        for region in area.regions:
            if region.type == 'WINDOW':
                return region

    def get_per_area_HUD_coords(self, context, area, hud_offset=(20, 20)):
        region = self.get_window_region_from_area(area)

        if region:
            scale = get_scale(context)

            x, y = get_region_space_co2d(context, self.mouse_pos_window, region=region)

            HUD_x = x + hud_offset[0] * scale
            HUD_y = y + hud_offset[1] * scale

            return HUD_x, HUD_y
        return None, None

    def tag_redraw_areas(self):
        for area_type, areas in self.areas.items():
            if area_type in ['VIEW_3D', 'ASSET_BROWSER']:
                for area in areas:
                    area['area'].tag_redraw()

    def update_areas_asset_data(self, context):
        for area in self.areas['ASSET_BROWSER']:
            area['asset'] = self.get_asset_data_from_asset_browser_space(context, area['space'])

    def get_asset_data_from_asset_browser_space(self, context, space):
        libname, libpath, filename, import_method = get_asset_details_from_space(context, space, asset_type='MATERIAL', debug=False)

        if filename:
            if libpath:

                path = filename.replace('\\', '/')

                blendname, matname = path.split('/Material/')

                if os.path.exists(os.path.join(libpath, blendname)):
                    directory = os.path.join(libpath, blendname, 'Material')

                    if import_method == 'FOLLOW_PREFS':
                        method = get_import_method_from_library_path(context, libpath)

                        if method:
                            import_method = f"{method}_(FOLLOW_PREFS)"

                    asset = {'error': None,
                             'import_type': import_method.title().replace('_', ' ') if import_method else None,
                             'library': libname,
                             'directory': directory,
                             'blend_name': blendname.replace('.blend', ''),
                             'material_name': matname}

                else:
                    msg = f".blend file does not exist: {os.path.join(libpath, blendname)}"
                    asset = {'error': msg}

            else:
                msg = "LOCAL or unsupported library chosen!"
                asset = {'error': msg}

        else:
            msg = "No Material selected in asset browser!"
            asset = {'error': msg}

        return asset

    def get_selected_asset(self, context, debug=False):
        if self.has_asset_browser:
            browsers = self.areas['ASSET_BROWSER']

            if any(ab['is_active'] for ab in browsers):
                selected = [area['asset'] for area in browsers if area['is_active'] and not area['asset']['error']]

                if selected:
                    asset = selected[0]

                else:
                    msg = "There is no selected Material Asset in the active asset browser"
                    asset = {'error': msg}

            else:
                msg = "There is no active asset browser in this workspace, move the mouse over one to make it active"
                asset = {'error': msg}

        else:
            msg = "There is no asset browser in this workspace"
            asset = {'error': msg}

        return asset

    def get_material_hit(self, context, debug=False):
        for area in self.areas['VIEW_3D']:
            if area['is_active']:
                region = self.get_window_region_from_area(area['area'])
                mouse_pos = get_region_space_co2d(context, self.mouse_pos_window, region=region)

                if debug:
                    print("\nmaterial hitting at", mouse_pos, "on view", area['area'])

                _, hitobj, hitindex, _, _, _ = cast_scene_ray_from_mouse(mouse_pos, depsgraph=self.dg, exclude_wire=True, force_exclude_wire=get_prefs().matpick_ignore_wire_objects, cache=self.hittable_cache, region=region, debug=False)

                hitobj_eval = get_eval_object(None, hitobj, self.dg)

                if hitobj_eval:
                    matindex = hitobj_eval.data.polygons[hitindex].material_index if hitobj.type == 'MESH' else 0

                    if debug:
                        print(" hit object:", hitobj.name, "material index:", matindex)

                    matindex = min(matindex, len(hitobj.material_slots) - 1)

                    if matindex < 0:
                        return None, None

                    return hitobj, matindex

        if debug:
            print(" nothing hit")
        return None, None

    def get_material_from_hit(self, obj, index):
        if obj and index is not None:
            if obj.material_slots and obj.material_slots[index].material:
                mat = obj.material_slots[index].material
                return mat, mat.name, obj.name
            return None, None, obj.name
        return None, None, None

    def get_material_from_assetbrowser(self, context):
        import_type = self.asset['import_type']
        directory = self.asset['directory']
        filename = self.asset['material_name']

        mat = bpy.data.materials.get(filename)

        if not mat:

            iseditmode = context.mode == 'EDIT_MESH'

            if iseditmode:
                bpy.ops.object.mode_set(mode='OBJECT')

            if 'Append' in import_type:
                reuse_local_id= 'Reuse' in import_type
                bpy.ops.wm.append(directory=directory, filename=filename, do_reuse_local_id=reuse_local_id)

            else:
                bpy.ops.wm.link(directory=directory, filename=filename)

            if iseditmode:
                bpy.ops.object.mode_set(mode='EDIT')

            mat = bpy.data.materials.get(filename)

            if mat.use_fake_user:
                mat.use_fake_user = False

            if mat.asset_data:
                mat.asset_clear()

            color = self.get_material_color_from_material(mat)

            if color and color != mat.diffuse_color:
                mat.diffuse_color = lighten(color)

            for obj in self.sel:
                obj.select_set(True)

        return mat

    def get_material_color_from_material(self, mat, srgb=False):
        if mat:
            last_node = get_last_node(mat)

            if last_node:
                matcolor = last_node.inputs.get('Base Color', None)

                if not matcolor:
                    for i in last_node.inputs:
                        if i.type == 'RGBA':
                            matcolor = i
                            break

                if matcolor:
                    if srgb:
                        return linear_to_srgb(matcolor.default_value[:3])
                    return matcolor.default_value

    def assign_material_in_editmode(self, context, mat):
        active = context.active_object

        if active.material_slots:
            bm = bmesh.from_edit_mesh(active.data)
            bm.normal_update()

            faces = [f for f in bm.faces if f.select]

            max_index = len(active.material_slots) - 1

            for f in faces:
                if f.material_index > max_index:
                    f.material_index = max_index

            if faces:
                mat_indices = set(f.material_index for f in faces)

                if len(mat_indices) == 1:
                    index = mat_indices.pop()
                    mat_at_index = active.material_slots[index].material

                    if mat_at_index == mat:
                        active.active_material_index = index
                        return

                if mat.name in active.data.materials:
                    index = list(active.data.materials).index(mat)

                else:
                    index = len(active.material_slots)

                for f in faces:
                    f.material_index = index

                bmesh.update_edit_mesh(active.data)

                active.update_from_editmode()

                if mat.name not in active.data.materials:
                    active.data.materials.append(mat)

                active.active_material_index = index

        else:
            active.data.materials.append(mat)

    def create_material_dummy_object(self, context, hitobj, matindex):
        bpy.ops.mesh.primitive_cube_add()

        active = context.active_object
        active.select_set(False)
        active.name = "_MATERIAL_DUMMY_OBJECT"

        active.matrix_world = Matrix()
        mcol = context.scene.collection

        if active.name not in mcol.objects:
            mcol.objects.link(active)

        for col in active.users_collection:
            if col is not mcol:
                col.objects.unlink(active)

        hide_render(active, True)
        active.hide_viewport = True
        active.hide_select = True
        active.hide_set(True)

        mat = hitobj.material_slots[matindex].material
        active.data.materials.append(mat)

        print("INFO: Created material dummy object", active.name)

    def clear_material_in_editmode(self, context):
        active = context.active_object

        if active.material_slots:
            bm = bmesh.from_edit_mesh(active.data)
            bm.normal_update()

            faces = [f for f in bm.faces if f.select]

            if len(faces) == len(bm.faces):
                active.data.materials.clear()
                active.active_material_index = 0

            elif faces:

                empty_index = None

                for idx, slot in enumerate(active.material_slots):
                    if slot.material is None:
                        empty_index = idx
                        break

                if empty_index is None:
                    active.data.materials.append(None)
                    empty_index = len(active.data.materials) - 1

                for f in faces:
                    f.material_index = empty_index

                active.active_material_index = empty_index

            bmesh.update_edit_mesh(active.data)

            active.update_from_editmode()

    def remove_material_dummy_objects(self):
        dummies = [obj for obj in bpy.data.objects if "_MATERIAL_DUMMY_OBJECT" in obj.name]

        for obj in dummies:
            print("INFO: Removing material dummy object", obj.name)
            remove_obj(obj)
