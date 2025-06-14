import bpy
from bpy.props import FloatProperty, BoolProperty, IntProperty, EnumProperty
import bmesh
import mathutils
from .. utils.selection import get_sides
from .. utils.math import average_normals, average_locations
from .. utils.ui import init_cursor, wrap_cursor, draw_init, draw_title, draw_prop, popup_message, get_zoom_factor, update_HUD_location
from .. utils.ui import init_status, finish_status
from .. utils.draw import draw_lines, draw_line, draw_points
from .. utils.property import step_enum
from .. utils.developer import output_traceback
from .. items import outer_face_method_items, side_selection_items

class Chamfer(bpy.types.Operator):
    bl_idname = "machin3.chamfer"
    bl_label = "MACHIN3: Chamfer"
    bl_description = "Chamfer cyclic selections resulting from Boolean Operations"
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty("Width", default=0, min=0, step=0.1)
    smooth: BoolProperty(name="Smooth", default=True)
    loop_slide_sideA: BoolProperty(name="Side A", default=False)
    loop_slide_sideB: BoolProperty(name="Side B", default=False)
    face_method_sideA: EnumProperty(name="Side A", items=outer_face_method_items, default="REBUILD")
    face_method_sideB: EnumProperty(name="Side B", items=outer_face_method_items, default="REBUILD")
    mergeA: BoolProperty(name="Merge", default=False)
    mergeB: BoolProperty(name="Merge", default=False)
    reachA: IntProperty(name="Reach", default=0, min=0)
    reachB: IntProperty(name="Reach", default=0, min=0)
    create_vgroup: BoolProperty(name="Create Vertex Groups", default=True)
    allowmodalwidth: BoolProperty(default=True)
    modal_side_select: EnumProperty(name="Side Select", items=side_selection_items, default="A")
    passthrough: BoolProperty(default=True)
    coA = None
    coB = None
    vgroupA = None
    vgroupB = None

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.split(factor=0.75)
        row.prop(self, "width")
        row.prop(self, "smooth")
        column.prop(self, "create_vgroup")

        column.separator()

        row = column.row()
        row.label(text="Side A")
        row.label(text="Side B")

        row = column.row()
        row.prop(self, "loop_slide_sideA", text="Loop Slide", toggle=True)
        row.prop(self, "loop_slide_sideB", text="Loop Slide", toggle=True)

        column.separator()

        row = column.row()
        row.prop(self, "face_method_sideA", expand=True)
        row.prop(self, "face_method_sideB", expand=True)

        row = column.split()
        if self.face_method_sideA == "REBUILD":
            row.prop(self, "mergeA")
        elif self.face_method_sideA == "REPLACE":
            row.prop(self, "reachA")

        if self.face_method_sideB == "REBUILD":
            row.prop(self, "mergeB")
        elif self.face_method_sideB == "REPLACE":
            row.prop(self, "reachB")

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Chamfer")

            draw_prop(self, "Width", self.width, decimal=3, active=self.allowmodalwidth, hint="move LEFT/RIGHT, toggle W")
            self.offset += 10

            draw_prop(self, "Side", self.modal_side_select, offset=18, hint="scroll UP/DOWN")
            self.offset += 10

            if self.modal_side_select == "A":
                draw_prop(self, "Loop Slide", self.loop_slide_sideA, offset=18, hint="toggle Q")
                draw_prop(self, "Face Method", self.face_method_sideA, offset=18, hint="CTRL scroll UP/DOWN")

                if self.face_method_sideA == "REBUILD":
                    draw_prop(self, "Merge Perimeter", self.mergeA, offset=18, hint="toggle M")
                elif self.face_method_sideA == "REPLACE":
                    draw_prop(self, "Reach", self.reachA, offset=18, hint="ALT scroll UP/DOWN")
            else:
                draw_prop(self, "Loop Slide", self.loop_slide_sideB, offset=18, hint="toggle Q")
                draw_prop(self, "Face Method", self.face_method_sideB, offset=18, hint="CTRL scroll UP/DOWN")

                if self.face_method_sideB == "REBUILD":
                    draw_prop(self, "Merge Perimeter", self.mergeB, offset=18, hint="toggle M")
                elif self.face_method_sideB == "REPLACE":
                    draw_prop(self, "Reach", self.reachB, offset=18, hint="ALT scroll UP/DOWN")

            self.offset += 10
            draw_prop(self, "Smooth", self.smooth, offset=18, hint="toggle S")
            draw_prop(self, "Vertex Group", self.create_vgroup, offset=18, hint="toggle V")

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            if any([self.coA, self.coB]):
                mx = self.active.matrix_world
                coords = getattr(self, "co" + self.modal_side_select)

                draw_line(coords, mx=mx, width=2)

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
                    divisor = 100 if event.shift else 1 if event.ctrl else 10

                    delta_x = event.mouse_x - self.last_mouse_x
                    delta_width = delta_x / divisor * self.factor

                    self.width += delta_width

            elif event.type == 'S' and event.value == "PRESS":
                self.smooth = not self.smooth

            elif event.type in ['WHEELUPMOUSE', 'ONE'] and event.value == "PRESS":
                if event.ctrl:
                    if self.modal_side_select == "A":
                        self.face_method_sideA = step_enum(self.face_method_sideA, outer_face_method_items, 1)
                    else:
                        self.face_method_sideB = step_enum(self.face_method_sideB, outer_face_method_items, 1)
                elif event.alt:
                    if self.modal_side_select == "A" and self.face_method_sideA == "REPLACE":
                        self.reachA += 1

                    elif self.modal_side_select == "B" and self.face_method_sideB == "REPLACE":
                        self.reachB += 1
                else:
                    self.modal_side_select = step_enum(self.modal_side_select, side_selection_items, 1)

            elif event.type in ['WHEELDOWNMOUSE', 'TWO'] and event.value == "PRESS":
                if event.ctrl:
                    if self.modal_side_select == "A":
                        self.face_method_sideA = step_enum(self.face_method_sideA, outer_face_method_items, -1)
                    else:
                        self.face_method_sideB = step_enum(self.face_method_sideB, outer_face_method_items, -1)
                elif event.alt:
                    if self.modal_side_select == "A" and self.face_method_sideA == "REPLACE":
                        self.reachA -= 1
                    elif self.modal_side_select == "B" and self.face_method_sideB == "REPLACE":
                        self.reachB -= 1
                else:
                    self.modal_side_select = step_enum(self.modal_side_select, side_selection_items, -1)

            elif event.type == 'Q' and event.value == "PRESS":
                if self.modal_side_select == "A":
                    self.loop_slide_sideA = not self.loop_slide_sideA
                else:
                    self.loop_slide_sideB = not self.loop_slide_sideB

            elif event.type == 'M' and event.value == "PRESS":
                if self.modal_side_select == "A" and self.face_method_sideA == "REBUILD":
                    self.mergeA = not self.mergeA

                elif self.modal_side_select == "B" and self.face_method_sideB == "REBUILD":
                    self.mergeB = not self.mergeB

            elif event.type == 'V' and event.value == "PRESS":
                self.create_vgroup = not self.create_vgroup

            elif event.type == 'W' and event.value == "PRESS":
                self.allowmodalwidth = not self.allowmodalwidth

            try:
                ret = self.main(self.active, modal=True)

                if not ret:
                    self.active.vertex_groups.remove(self.vgroupA)
                    self.active.vertex_groups.remove(self.vgroupB)

                    self.finish()
                    return {'FINISHED'}

            except Exception as e:
                self.active.vertex_groups.remove(self.vgroupA)
                self.active.vertex_groups.remove(self.vgroupB)

                self.finish()

                output_traceback(self, e)
                return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish()

            if not self.create_vgroup:
                self.active.vertex_groups.remove(self.vgroupA)
                self.active.vertex_groups.remove(self.vgroupB)

            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.finish()

            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(self.active.data)
            bpy.ops.object.mode_set(mode='EDIT')

            self.active.vertex_groups.remove(self.vgroupA)
            self.active.vertex_groups.remove(self.vgroupB)
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        bpy.types.SpaceView3D.draw_handler_remove(self.VIEW3D, 'WINDOW')

        finish_status(self)

    def invoke(self, context, event):
        self.active = context.active_object

        self.vgroupA = self.active.vertex_groups.new(name="chamfer")
        self.vgroupB = self.active.vertex_groups.new(name="chamfer")

        self.active.update_from_editmode()

        self.allowmodalwidth = True
        self.width = 0
        self.loop_slide_sideA = False
        self.loop_slide_sideB = False
        self.face_method_sideA = "REBUILD"
        self.face_method_sideB = "REBUILD"
        self.mergeA = False
        self.mergeB = False
        self.reachA = 0
        self.reachB = 0

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        self.factor = get_zoom_factor(context, self.active.matrix_world @ average_locations([v.co for v in self.initbm.verts if v.select]))

        init_cursor(self, event)

        init_status(self, context, 'Chamfer')

        self.area = context.area
        self.VIEW3D = bpy.types.SpaceView3D.draw_handler_add(self.draw_VIEW3D, (context, ), 'WINDOW', 'POST_VIEW')
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        active = context.active_object

        if self.create_vgroup:
            if not self.vgroupA:
                self.vgroupA = active.vertex_groups.new(name="chamfer")
            if not self.vgroupB:
                self.vgroupB = active.vertex_groups.new(name="chamfer")

        else:
            if self.vgroupA:
                active.vertex_groups.remove(self.vgroupA)
                self.vgroupA = None
            if self.vgroupB:
                active.vertex_groups.remove(self.vgroupB)
                self.vgroupB = None

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

            offsetdict = self.create_offset_verts(bm, sideA, sideB, debug=debug)

            self.rebuild_outer_faces(bm, sideA, sideB, offsetdict)

            if self.face_method_sideA == "REPLACE":
                outer_edgesA = self.replace_outer_faces(bm, verts, edges, sideA, reach=self.reachA)

            if self.face_method_sideB == "REPLACE":
                outer_edgesB = self.replace_outer_faces(bm, verts, edges, sideB, reach=self.reachB)

            if cyclic:
                sideA.append(sideA[0])
                sideB.append(sideB[0])

            chamfer_faces, railA, railB, self.coA, self.coB = self.build_chamfer_faces(bm, sideA, sideB, self.smooth, debug=debug)

            bm.faces.index_update()
            bm.edges.index_update()

            railA_verts = []
            if self.face_method_sideA == "REBUILD" and self.mergeA:
                    railA_verts = self.merge_perimeter(bm, railA, debug=debug)

            railB_verts = []
            if self.face_method_sideB == "REBUILD" and self.mergeB:
                    railB_verts = self.merge_perimeter(bm, railB, debug=debug)

            railA_faces = []
            if self.face_method_sideA == "REPLACE" and outer_edgesA:
                ret = bmesh.ops.bridge_loops(bm, edges=railA + outer_edgesA)
                railA_faces += ret["faces"]

            railB_faces = []
            if self.face_method_sideB == "REPLACE" and outer_edgesB:
                ret = bmesh.ops.bridge_loops(bm, edges=railB + outer_edgesB)
                railB_faces += ret["faces"]

            if self.create_vgroup:
                self.assign_vgroup(groups, chamfer_faces, self.vgroupA, railA, railA_verts, railA_faces)

                self.assign_vgroup(groups, chamfer_faces, self.vgroupB, railB, railB_verts, railB_faces)

            bm.to_mesh(mesh)
            bpy.ops.object.mode_set(mode='EDIT')

            return True

        else:
            popup_message(err[0], title=err[1])
            bpy.ops.object.mode_set(mode='EDIT')

            return False

    def assign_vgroup(self, deform_layer, chamfer_faces, vgroup, rail, rail_verts, rail_faces):
        if rail_faces:
            for f in rail_faces:
                for v in f.verts:
                    v[deform_layer][vgroup.index] = 1
        elif rail_verts:
            for v in rail_verts:
                for f in [f for f in v.link_faces if f not in chamfer_faces]:
                    for v in f.verts:
                        v[deform_layer][vgroup.index] = 1
        else:
            for e in rail:
                for f in [f for f in e.link_faces if f not in chamfer_faces]:
                    for v in f.verts:
                        v[deform_layer][vgroup.index] = 1
    def merge_perimeter(self, bm, rail, debug=False):
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

        if dissovleedges:
            bmesh.ops.dissolve_edges(bm, edges=dissovleedges)

        doubles = [v for v in mergeverts + railverts if v.is_valid]

        bmesh.ops.remove_doubles(bm, verts=doubles, dist=0.00001)

        return [d for d in doubles if d.is_valid]

    def replace_outer_faces(self, bm, verts, edges, side, reach=0):
        def get_perimeter(outer_faces, inner_verts):
            outer_edges = []
            outer_verts = []
            for f in outer_faces:
                for e in f.edges:
                    if e in edges:
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
                    if f not in outer_faces + next_outer_faces:
                        next_outer_faces.append(f)

            next_outer_edges, next_outer_verts = get_perimeter(next_outer_faces, outer_verts)

            outer_faces += next_outer_faces
            outer_edges = next_outer_edges
            outer_verts = next_outer_verts

        bmesh.ops.delete(bm, geom=outer_faces, context='FACES')

        outer_edges = [e for e in outer_edges if e.is_valid]

        return outer_edges

    def build_chamfer_faces(self, bm, sideA, sideB, smooth, debug=False):
        chamfer_faces = []
        railA = []
        railB = []

        coA = []
        coB = []

        for idx, (sA, sB) in enumerate(zip(sideA, sideB)):
            vA = sA["offset_vert"]
            vB = sB["offset_vert"]

            coA.append(mathutils.Vector(vA.co))
            coB.append(mathutils.Vector(vB.co))

            if idx == len(sideA) - 1:
                break

            vA_next = sideA[idx + 1]["offset_vert"]
            vB_next = sideB[idx + 1]["offset_vert"]

            if debug:
                print(idx)
                print(" • ", vA.index)
                print(" • ", vB.index)
                print(" • ", vB_next.index)
                print(" • ", vA_next.index)

            face = bm.faces.new([vA, vB, vB_next, vA_next])
            face.smooth = smooth
            face.select = True

            chamfer_faces.append(face)

            reA = bm.edges.get([vA, vA_next])
            reB = bm.edges.get([vB, vB_next])

            railA.append(reA)
            railB.append(reB)

            if self.smooth:
                reA.smooth = False
                reB.smooth = False

        return chamfer_faces, railA, railB, coA, coB

    def rebuild_outer_faces(self, bm, sideA, sideB, offsetdict):
        new_face_verts = []
        old_faces = []
        for sA, sB in zip(sideA, sideB):
            if self.face_method_sideA == "REBUILD":
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

            if self.face_method_sideB == "REBUILD":
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

        for f in new_face_verts:
            face = bm.faces.new(f)
            face.smooth = self.smooth

        bmesh.ops.delete(bm, geom=old_faces, context='FACES')

    def create_offset_verts(self, bm, sideA, sideB, debug=False):
        for sA, sB in zip(sideA, sideB):
            vert = sA["vert"]
            cuttingnormal = mathutils.geometry.normal([vert.co, vert.co + sA["normal"], vert.co + sB["normal"]])

            if self.loop_slide_sideA and sA["edges"]:
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
            overtA.co = vert.co + offset_vectorA * self.width

            sA["offset_vert"] = overtA

            if debug:
                e = bm.edges.new([vert, overtA])
                e.select = True

            if self.loop_slide_sideB and sB["edges"]:
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
            overtB.co = vert.co + offset_vectorB * self.width

            sB["offset_vert"] = overtB

            if debug:
                e = bm.edges.new([vert, overtB])
                e.select = True

            bm.verts.index_update()

        offsetdict = {}

        for sA, sB in zip(sideA, sideB):
            if sA["vert"] not in offsetdict:
                offsetdict[sA["vert"]] = {}

            offsetdict[sA["vert"]]["offsetA"] = sA["offset_vert"]
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
