import bpy
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
import bmesh
import mathutils
from .. items import side_selection_items, outer_face_method_items
from .. utils.selection import get_sides
from .. utils.math import average_normals
from .. utils.ui import init_cursor, wrap_cursor, draw_init, draw_title, draw_prop, popup_message, get_zoom_factor, update_HUD_location
from .. utils.ui import init_status, finish_status
from .. utils.math import average_locations
from .. utils.property import step_enum
from .. utils.developer import output_traceback

class Offset(bpy.types.Operator):
    bl_idname = "machin3.offset"
    bl_label = "MACHIN3: Offset"
    bl_description = "Offset cyclic edgeloops resulting from Boolean Operations to create a perimeter loop"
    bl_options = {'REGISTER', 'UNDO'}

    sideselection: EnumProperty(name="Side Select", items=side_selection_items, default="A")
    width: FloatProperty("Width", default=0.001, min=0, step=0.1)
    smooth: BoolProperty(name="Smooth", default=True)
    loop_slide: BoolProperty(name="Loop Slide ", default=False)
    face_method: EnumProperty(name="Face Method", items=outer_face_method_items, default="REBUILD")
    merge: BoolProperty(name="Merge", default=False)
    reach: IntProperty(name="Reach", default=0, min=0)
    create_vgroup: BoolProperty(name="Create Vertex Group", default=True)
    allowmodalwidth: BoolProperty(default=True)
    debuginit: BoolProperty(default=True)
    passthrough: BoolProperty(default=False)
    vgroup = None

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.prop(self, "sideselection", expand=True)

        column.separator()
        column.prop(self, "width")

        column.separator()
        row = column.row()
        row.prop(self, "loop_slide", text="Loop Slide")
        row.prop(self, "smooth", text="Smooth")
        column.prop(self, "create_vgroup")

        column.separator()
        row = column.row()
        row.prop(self, "face_method", expand=True)

        if self.face_method == "REBUILD":
            column.prop(self, "merge", text="Merge")
        elif self.face_method == "REPLACE":
            column.prop(self, "reach")

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Offset")

            draw_prop(self, "Width", self.width, decimal=3, active=self.allowmodalwidth, hint="move LEFT/RIGHT, toggle W")
            self.offset += 10

            draw_prop(self, "Side", self.sideselection, offset=18, hint="scroll UP/DOWN")
            draw_prop(self, "Loop Slide", self.loop_slide, offset=18, hint="toggle Q")
            self.offset += 10

            draw_prop(self, "Face Method", self.face_method, offset=18, hint="CTRL scroll UP/DOWN")

            if self.face_method == "REBUILD":
                draw_prop(self, "Merge Perimeter", self.merge, offset=18, hint="toggle M")

            elif self.face_method == "REPLACE":
                draw_prop(self, "Reach", self.reach, offset=18, hint="ALT scroll UP/DOWN")

            self.offset += 10
            draw_prop(self, "Smooth", self.smooth, offset=18, hint="toggle S")
            draw_prop(self, "Vertex Group", self.create_vgroup, offset=18, hint="toggle V")

    @classmethod
    def poll(cls, context):
        if context.mode == 'EDIT_MESH':
            bm = bmesh.from_edit_mesh(context.active_object.data)
            mode = tuple(context.tool_settings.mesh_select_mode)

            if mode == (True, False, False) or mode == (False, True, False):
                return len([e for e in bm.edges if e.select]) >= 1

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'W', 'S', 'Q', 'M', 'V']

        if self.allowmodalwidth:
            events.append('MOUSEMOVE')

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalwidth:
                        divisor = 100 if event.shift else 1 if event.ctrl else 10

                        delta_x = event.mouse_x - self.last_mouse_x
                        delta_width = delta_x / divisor * self.factor

                        self.width += delta_width

            elif event.type in ['WHEELUPMOUSE', 'ONE'] and event.value == "PRESS":
                if event.ctrl:
                    self.face_method = step_enum(self.face_method, outer_face_method_items, 1)
                elif event.alt:
                    if self.face_method == "REPLACE":
                        self.reach += 1
                else:
                    self.sideselection = step_enum(self.sideselection, side_selection_items, 1)

            elif event.type in ['WHEELDOWNMOUSE', 'TWO'] and event.value == "PRESS":
                if event.ctrl:
                    self.face_method = step_enum(self.face_method, outer_face_method_items, -1)
                elif event.alt:
                    if self.face_method == "REPLACE":
                        self.reach -= 1
                else:
                    self.sideselection = step_enum(self.sideselection, side_selection_items, -1)

            elif event.type == 'S' and event.value == "PRESS":
                self.smooth = not self.smooth

            elif event.type == 'Q' and event.value == "PRESS":
                self.loop_slide = not self.loop_slide

            elif event.type == 'W' and event.value == "PRESS":
                self.allowmodalwidth = not self.allowmodalwidth

            elif event.type == 'M' and event.value == "PRESS":
                if self.face_method == "REBUILD":
                    self.merge = not self.merge

            elif event.type == 'V' and event.value == "PRESS":
                    self.create_vgroup = not self.create_vgroup

            try:
                ret = self.main(self.active, modal=True)

                if not ret:
                    self.active.vertex_groups.remove(self.vgroup)

                    bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
                    finish_status(self)

                    return {'FINISHED'}

            except Exception as e:
                self.active.vertex_groups.remove(self.vgroup)

                bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
                finish_status(self)

                output_traceback(self, e)
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish()

            if not self.create_vgroup:
                self.active.vertex_groups.remove(self.vgroup)

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()

            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self):
        self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

        self.active.vertex_groups.remove(self.vgroup)

    def invoke(self, context, event):
        self.active = context.active_object

        self.vgroup = self.active.vertex_groups.new(name="offset")

        self.active.update_from_editmode()

        self.allowmodalwidth = True
        self.width = 0.001
        self.loop_slide = False
        self.face_method = "REBUILD"
        self.merge = False
        self.reach = 0

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        self.factor = get_zoom_factor(context, self.active.matrix_world @ average_locations([v.co for v in self.initbm.verts if v.select]))

        init_cursor(self, event)

        init_status(self, context, 'Offset')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        active = context.active_object

        if self.create_vgroup:
            if not self.vgroup:
                self.vgroup = active.vertex_groups.new(name="offset")

        else:
            if self.vgroup:
                active.vertex_groups.remove(self.vgroup)
                self.vgroup = None

        try:
            self.main(active)
        except Exception as e:
            output_traceback(self, e)

        return {'FINISHED'}

    def main(self, active, modal=False):
        debug = False

        mesh = active.data

        bpy.ops.object.mode_set(mode='OBJECT')

        if modal:
            self.initbm.to_mesh(active.data)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        bm.verts.ensure_lookup_table()

        groups = bm.verts.layers.deform.verify()
        verts = [v for v in bm.verts if v.select]
        edges = [e for e in bm.edges if e.select]

        sideA, sideB, cyclic, err = get_sides(bm, verts, edges, debug=debug)

        if sideA and sideB:
            self.get_normals(bm, sideA, sideB, debug=debug)

            offsetdict = self.create_offset_verts(bm, sideA, sideB, self.width, self.sideselection, self.loop_slide, debug=debug)

            old_faces, new_faces = self.rebuild_outer_faces(bm, sideA, sideB, offsetdict, self.sideselection)

            if cyclic:
                sideA.append(sideA[0])
                sideB.append(sideB[0])

            inner_faces, rail = self.rebuild_inner_faces(bm, sideA, sideB, self.sideselection)

            bm.select_flush(True)

            if self.face_method == "REBUILD":
                if self.merge:
                    mergeverts, dissovleedges = self.move_perimeter(bm, rail, debug=debug)

                bmesh.ops.delete(bm, geom=old_faces, context='FACES')

                if self.merge:
                    bmesh.ops.dissolve_edges(bm, edges=dissovleedges)

                    doubles = [v for v in mergeverts if v.is_valid]

                    bmesh.ops.remove_doubles(bm, verts=doubles, dist=0.00001)

            elif self.face_method == "REPLACE":
                side = sideA if self.sideselection == "A" else sideB

                outer_edges = self.replace_outer_faces(bm, verts, edges, side, rail, new_faces, reach=self.reach)

                repl_faces = []

                if outer_edges:
                    ret = bmesh.ops.bridge_loops(bm, edges=rail + outer_edges)
                    repl_faces += ret["faces"]

            if self.create_vgroup:
                for f in inner_faces:
                    for v in f.verts:
                        v[groups][self.vgroup.index] = 1

            bm.to_mesh(mesh)
            bpy.ops.object.mode_set(mode='EDIT')

            return True

        else:
            popup_message(err[0], title=err[1])
            bpy.ops.object.mode_set(mode='EDIT')

            return False

    def move_perimeter(self, bm, rail, debug=False):
        if debug:
            print("Merging perimeter")

        railverts = []
        mergeverts = []
        dissovleedges =[]
        seen = []

        for e in rail:
            for v in e.verts:
                if v not in seen:
                    seen.append(v)
                else:
                    continue

                ves = [e for e in v.link_edges if e not in rail and not e.select]

                for e in ves:
                    if e.other_vert(v).select:
                        continue
                    else:
                        mv = e.other_vert(v)

                        if mv in mergeverts:
                            dissovleedges.append(e)

                        else:
                            if debug:
                                print(" • vert:", mv.index, "merge to:", v.index)

                            mv.co = v.co

                            mergeverts.append(mv)

                            if v not in railverts:
                                railverts.append(v)

                            for e in mv.link_edges:
                                if e.other_vert(mv) in mergeverts:
                                    dissovleedges.append(e)

        return mergeverts + railverts, dissovleedges

    def replace_outer_faces(self, bm, verts, edges, side, rail, new_faces, reach=0):
        def get_perimeter(outer_faces, inner_verts):
            outer_edges = []
            outer_verts = []
            for f in outer_faces:
                for e in f.edges:
                    if e in edges + rail:
                        e.select = False
                    elif any([v in inner_verts for v in e.verts]):
                        continue
                    else:
                        outer_edges.append(e)
                        for v in e.verts:
                            if v not in outer_verts:
                                outer_verts.append(v)

            return outer_edges, outer_verts

        outer_faces = []
        for s in side:
            for f in s["faces"]:
                if f not in outer_faces:
                    outer_faces.append(f)

        outer_edges, outer_verts = get_perimeter(outer_faces, verts)

        for i in range(reach):
            next_outer_faces = []
            for v in outer_verts:
                for f in v.link_faces:
                    if f not in outer_faces + next_outer_faces + new_faces:
                        next_outer_faces.append(f)

            next_outer_edges, next_outer_verts = get_perimeter(next_outer_faces, outer_verts)

            outer_faces += next_outer_faces
            outer_edges = next_outer_edges
            outer_verts = next_outer_verts

        bmesh.ops.delete(bm, geom=outer_faces + new_faces, context='FACES')

        outer_edges = [e for e in outer_edges if e.is_valid]

        return outer_edges

    def rebuild_inner_faces(self, bm, sideA, sideB, sideselection):
        rail = []
        inner_faces = []

        if sideselection == "A":
            for idx, sA in enumerate(sideA):
                if idx == len(sideA) - 1:
                    break

                vert = sA["vert"]
                offset_vert = sA["offset_vert"]
                vert_next = sideA[idx + 1]["vert"]
                offset_vert_next = sideA[idx + 1]["offset_vert"]

                face = bm.faces.new([vert, vert_next, offset_vert_next, offset_vert])
                face.smooth = self.smooth

                inner_faces.append(face)

                re = bm.edges.get([offset_vert, offset_vert_next])
                rail.append(re)
                re.select = True

            bm.edges.index_update()

            return inner_faces, rail

        elif sideselection == "B":
            for idx, sB in enumerate(sideB):
                if idx == len(sideA) - 1:
                    break

                vert = sB["vert"]
                offset_vert = sB["offset_vert"]
                vert_next = sideB[idx + 1]["vert"]
                offset_vert_next = sideB[idx + 1]["offset_vert"]

                face = bm.faces.new([vert, offset_vert, offset_vert_next, vert_next])
                face.smooth = self.smooth

                inner_faces.append(face)

                re = bm.edges.get([offset_vert, offset_vert_next])
                rail.append(re)

                re.select = True

            bm.edges.index_update()

            return inner_faces, rail

    def rebuild_outer_faces(self, bm, sideA, sideB, offsetdict, sideselection):
        new_face_verts = []
        old_faces = []
        for sA, sB in zip(sideA, sideB):
            if sideselection == "A":
                for face in sA["faces"]:
                    if face not in old_faces:
                        old_faces.append(face)

                        face_verts = []
                        for v in face.verts:
                            if v in offsetdict:
                                face_verts.append(offsetdict[v]["offsetA"])
                            else:
                                face_verts.append(v)

                        new_face_verts.append(face_verts)

            elif sideselection == "B":
                for face in sB["faces"]:
                    if face not in old_faces:
                        old_faces.append(face)

                        face_verts = []
                        for v in face.verts:
                            if v in offsetdict:
                                face_verts.append(offsetdict[v]["offsetB"])
                            else:
                                face_verts.append(v)

                        new_face_verts.append(face_verts)

        new_faces = []

        for f in new_face_verts:
            face = bm.faces.new(f)
            face.smooth = self.smooth
            new_faces.append(face)

        bm.faces.index_update()

        return old_faces, new_faces

    def create_offset_verts(self, bm, sideA, sideB, width, sideselection, loopslide, debug=False):
        for sA, sB in zip(sideA, sideB):
            vert = sA["vert"]
            cuttingnormal = mathutils.geometry.normal([vert.co, vert.co + sA["normal"], vert.co + sB["normal"]])

            if sideselection == "A":
                if loopslide and sA["edges"]:
                    if debug:
                        print(" • Loop Sliding on Side A")

                    edge = sA["edges"][0]

                    vert_end = edge.other_vert(vert)
                    offset_vectorA = (vert_end.co - vert.co).normalized()

                else:
                    ivsA = mathutils.geometry.intersect_plane_plane(vert.co, sA["normal"], vert.co, cuttingnormal)

                    if sA["seledge"].calc_face_angle_signed() >= 0:
                        offset_vectorA = ivsA[1]
                    else:
                        offset_vectorA = ivsA[1].reflect(ivsA[1])

                overtA = bm.verts.new()
                overtA.co = vert.co + offset_vectorA * width

                sA["offset_vert"] = overtA

                if debug:
                    e = bm.edges.new([vert, overtA])
                    e.select = True

            elif sideselection == "B":
                if loopslide and sB["edges"]:
                    if debug:
                        print(" • Loop Sliding on Side B")

                    edge = sB["edges"][0]

                    vert_end = edge.other_vert(vert)
                    offset_vectorB = (vert_end.co - vert.co).normalized()

                else:
                    ivsB = mathutils.geometry.intersect_plane_plane(vert.co, cuttingnormal, vert.co, sB["normal"])

                    if sB["seledge"].calc_face_angle_signed() >= 0:
                        offset_vectorB = ivsB[1]
                    else:
                        offset_vectorB = ivsB[1].reflect(ivsB[1])

                overtB = bm.verts.new()
                overtB.co = vert.co + offset_vectorB * width

                sB["offset_vert"] = overtB

                if debug:
                    e = bm.edges.new([vert, overtB])
                    e.select = True

            bm.verts.index_update()

        offsetdict = {}

        for sA, sB in zip(sideA, sideB):
            if sA["vert"] not in offsetdict:
                offsetdict[sA["vert"]] = {}

            if sideselection == "A":
                offsetdict[sA["vert"]]["offsetA"] = sA["offset_vert"]

            elif sideselection == "B":
                offsetdict[sA["vert"]]["offsetB"] = sB["offset_vert"]

        return offsetdict

    def get_normals(self, bm, sideA, sideB, debug=False):
        for sA, sB in zip(sideA, sideB):
            if debug:
                print()
                print("vertA:", sA["vert"].index, "\tvertB:", sB["vert"].index)
                print(" • edgesA:", [e.index for e in sA["edges"]], "\tedgesB:", [e.index for e in sB["edges"]])
                print(" • facesA:", [f.index for f in sA["faces"]], "\tfacesB:", [f.index for f in sB["faces"]])

            sA["normal"] = average_normals([f.normal for f in sA["faces"]])
            sB["normal"] = average_normals([f.normal for f in sB["faces"]])

            if debug:
                endvert = bm.verts.new()
                endvert.co = sA["vert"].co + sA["normal"] * 0.05
                bm.edges.new([sA["vert"], endvert])

                endvert = bm.verts.new()
                endvert.co = sB["vert"].co + sB["normal"] * 0.05
                bm.edges.new([sB["vert"], endvert])
