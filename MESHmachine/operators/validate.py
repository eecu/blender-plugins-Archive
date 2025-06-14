import bpy
from bpy.props import BoolProperty, IntProperty, FloatProperty, EnumProperty, StringProperty
import bmesh
from uuid import uuid4
from mathutils import Vector
from .. utils.ui import popup_message, get_icon

class Validate(bpy.types.Operator):
    bl_idname = "machin3.validate_plug"
    bl_label = "MACHIN3: Validate Plug"
    bl_description = "Validate and Debug a Plug Asset"

    hidesupportobjs: BoolProperty(name="Hide Deformer and Occluder and Others", default=True)
    generateuuid: BoolProperty(name="Generate new UUID", default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object

    def draw(self, context):
        layout = self.layout

        box = layout.box()

        column = box.column()
        column.label(text="Basic")

        checkmark = get_icon('save')
        error = get_icon('error')
        info = get_icon('info')

        if len(self.handles) == 1:
            column.label(text="Handle: %s" % self.handles[0].name, icon_value=checkmark)
            if self.ngon:
                column.label(text="Handle contains N-Gons!", icon_value=error)
            if self.flipped:
                column.label(text="Handle polygons are flipped!", icon_value=error)

        elif len(self.handles) == 0:
            column.label(text="No Handle found!", icon_value=error)
        else:
            column.label(text="Multiple Handles found!", icon_value=error)
            for handle in self.handles:
                column.label(text="  • %s" % handle.name)

        if len(self.plugs) == 1:
            column.label(text="Plug: %s" % self.plugs[0].name, icon_value=checkmark)
            filletoredge = "FILLET" if self.plugs[0].MM.hasfillet else "EDGE"
            column.label(text="  • Type: %s" % filletoredge)
        elif len(self.plugs) == 0:
            column.label(text="No Plug Mesh found!", icon_value=error)
        else:
            column.label(text="Multiple Plug Meshes found!", icon_value=error)
            for plug in self.plugs:
                column.label(text="  • %s" % plug.name)

        if self.subsets:
            if len(self.subsets) == 1:
                column.label(text="Subset: %s" % self.subsets[0].name, icon_value=checkmark)
                column.label(text="  • Force Deform: %s " % str(self.subsets[0].MM.forcesubsetdeform))
            else:
                icon = checkmark if "ARRAY" not in self.modifiers else info
                if icon == info:
                    column.label(text="Multiple Subsets:", icon_value=icon)
                else:
                    column.label(text="Multiple Subsets", icon_value=icon)
                    column.label(text="Make sure they aren't just ARRAY caps, that need to have their props cleared!")

                for sub in self.subsets:
                    column.label(text="  • %s" % sub.name)
                    column.label(text="    • Force Deform: %s " % str(sub.MM.forcesubsetdeform))

        if self.deformers:
            if len(self.deformers) == 1:
                column.label(text="Deformer: %s" % self.deformers[0].name, icon_value=checkmark)
                column.label(text="  • Use Deformer: %s" % str(self.deformers[0].MM.usedeformer))
            else:
                column.label(text="Multiple Deformers found!", icon_value=error)
                for deformer in self.deformers:
                    column.label(text="  • %s" % deformer.name)

        if self.occluders:
            if len(self.occluders) == 1:
                column.label(text="Occluder: %s" % self.occluders[0].name, icon_value=checkmark)
            else:
                column.label(text="Multiple Occluders found!", icon_value=error)
                for occluder in self.occluders:
                    column.label(text="  • %s" % occluder.name)

        if self.modifiers or self.empties or self.others:
            column.separator()
            column.label(text="Advanced")

            if self.modifiers:
                if len(self.modifiers) == 1:
                    column.label(text="Modifier: %s" % self.modifiers[0], icon="MODIFIER")
                else:
                    column.label(text="Multiple Modifiers:", icon="MODIFIER")
                    for mod in self.modifiers:
                        column.label(text="  • %s" % mod)

            if self.empties:
                if any([mod in self.modifiers for mod in ["ARRAY", "HOOK"]]):
                    if len(self.empties) == 1:
                        column.label(text="Empty: %s" % self.empties[0].name, icon_value=checkmark)
                    else:
                        column.label(text="Multiple Empties:", icon_value=checkmark)
                        for empty in self.empties:
                            column.label(text="  • %s" % empty.name)
                else:
                    if len(self.empties) == 1:
                        column.label(text="Empty: %s" % self.empties[0].name, icon_value=info)
                        column.label(text="Empty found, but no ARRAY or HOOK modifiers present!")
                    else:
                        column.label(text="Multiple Empties", icon_value=info)
                        column.label(text="Empties found, but no ARRAY or HOOK modifiers present!")
                        for empty in self.empties:
                            column.label(text="  • %s" % empty.name)

            if self.others:
                if any([mod in self.modifiers for mod in ["ARRAY"]]):
                    if len(self.others) == 1:
                        column.label(text="Other: %s" % self.others[0].name, icon_value=checkmark)
                    else:
                        column.label(text="Multiple Others:", icon_value=checkmark)
                        for other in self.others:
                            column.label(text="  • %s" % other.name)
                else:
                    if len(self.others) == 1:
                        column.label(text="Other: %s" % self.others[0].name, icon_value=info)
                        column.label(text="Other object found, but no ARRAY modifiers present! What is it?")
                    else:
                        column.label(text="Multiple Others:", icon_value=info)
                        column.label(text="Other objects found, but no ARRAY modifiers present! What are they?")
                        for other in self.others:
                            column.label(text="  • %s" % other.name)

        if self.uuids or self.creators:
            column.separator()

            column.label(text="Extra")

            if self.uuids:
                if len(self.uuids) == 1:
                    column.label(text="UUID: %s" % self.uuids[0], icon_value=checkmark)
                else:
                    column.label(text="Multiple UUIDs", icon_value=info)
                    for uuid in self.uuids:
                        column.label(text="  • %s" % uuid)

            if self.creators:
                if len(self.creators) == 1:
                    column.label(text="Creator: %s" % self.creators[0], icon="SOLO_OFF")
                else:
                    column.label(text="Multiple Creators", icon_value=info)
                    for creator in self.creators:
                        column.label(text="  • %s" % creator)

        if self.active.MM.isplughandle:
            box = layout.box()

            column = box.column()
            column.label(text="Actions")

            if self.deformers or self.occluders or self.others:
                column.prop(self, "hidesupportobjs")

            column.prop(self, "generateuuid")

    def invoke(self, context, event):
        self.generateuuid = False

        self.active = context.active_object

        self.uuids = []
        self.handles = []
        self.plugs = []
        self.subsets = []
        self.deformers = []
        self.occluders = []
        self.empties = []
        self.others = []
        self.modifiers = []
        self.creators = []

        print(20 * "-")
        print("PLUG OBJECTS")

        if self.active:
            self.get_props(self.active)

            self.uuids, self.handles, self.plugs, self.subsets, self.deformers, self.occluders, self.others, self.empties, self.modifiers, self.creators = self.append(self.active, self.uuids, self.handles, self.plugs, self.subsets, self.deformers, self.occluders, self.others, self.empties, self.modifiers, self.creators)
            if self.active.children:
                children = list(self.active.children)

                while children:
                    child = children[0]
                    self.get_props(child)
                    self.uuids, self.handles, self.plugs, self.subsets, self.deformers, self.occluders, self.others, self.empties, self.modifiers, self.creators = self.append(child, self.uuids, self.handles, self.plugs, self.subsets, self.deformers, self.occluders, self.others, self.empties, self.modifiers, self.creators)
                    children.extend(list(child.children))
                    children.pop(0)

            self.uuids = list(set(self.uuids))
            self.modifiers = list(set(self.modifiers))
            self.creators = list(set(self.creators))

            print(5 * "-")
            print("SUMMARY\n")

            print("uuids:", self.uuids)
            print("handles:", self.handles)

            if len(self.handles) == 1:
                handle = self.handles[0]
                self.ngon, self.flipped, deselect = self.check_handle(handle)

                if self.ngon:
                    print(" ! Handle contains N-Gons!")

                if self.flipped:
                    print(" ! Handle polygons are flipped!")

                if deselect:
                    print(" ! Handle faces have been deselected!")

            print("plugs:", self.plugs)
            print("subsets:", self.subsets)
            print("deformers:", self.deformers)
            print("occluders:", self.occluders)
            print("others:", self.others)
            print("empties:", self.empties)

            for obj in self.empties:
                if not obj.MM.uuid:
                    uuid = str(uuid4())
                    obj.MM.uuid = uuid
                    print(" ! Empty ID has been set for %s!" % (obj.name))

            print("modifiers:", self.modifiers)
            print("creators:", self.creators)

            wide = True if len(self.subsets) > 1 and "ARRAY" in self.modifiers else False

            if not wide:  # prevent a previous True from being overwritten
                wide = True if self.empties and not any([mod in self.modifiers for mod in ["ARRAY", "HOOK"]]) else False

            if not wide:  # prevent a previous True from being overwritten
                wide = True if self.others and not any([mod in self.modifiers for mod in ["ARRAY"]]) else False

            width = 400 if wide else 300

            wm = context.window_manager
            return wm.invoke_props_dialog(self, width=width)

        else:
            popup_message("No active object!")
            return {'CANCELLED'}

    def execute(self, context):
        if self.active.MM.isplughandle and (self.plugs or self.deformers or self.occluders or self.others or self.empties):
            for obj in self.deformers + self.occluders + self.others:
                obj.hide_set(self.hidesupportobjs)
                obj.hide_render = self.hidesupportobjs

            if len(self.handles) == 1:
                self.handles[0].hide_set(False)
                self.handles[0].hide_render = True

            if len(self.deformers) == 1:
                self.deformers[0].hide_render = True
            if len(self.occluders) == 1:
                self.occluders[0].hide_render = False

            if len(self.plugs) == 1:
                self.plugs[0].hide_set(False)
                self.plugs[0].hide_render = False

        if self.active.MM.isplughandle:
            if len(self.handles) == 1:
                for obj in self.handles + self.empties:
                    obj.show_in_front = True

        if self.generateuuid:
            if self.active.MM.isplughandle:
                if len(self.handles) == 1:
                    uuid = str(uuid4())

                    for obj in self.handles + self.plugs + self.subsets + self.deformers + self.occluders + self.others:
                        obj.MM.uuid = uuid

        return {'FINISHED'}

    def check_handle(self, handle):
        ngon = False
        flipped = False
        deselect = False

        bm = bmesh.new()
        bm.from_mesh(handle.data)

        for f in bm.faces:
            if len(f.verts) > 4:
                ngon = True

            dot = f.normal.dot(Vector((0, 0, 1)))

            if dot < 0:
                flipped = True

            if f.select:
                deselect = True

            f.select = False

        bm.select_flush(False)

        bm.to_mesh(handle.data)
        bm.clear()

        return ngon, flipped, deselect

    def append(self, obj, uuids, handles, plugs, subsets, deformers, occluders, others, empties, modifiers, creators):
        if obj.type == "MESH":  # only collect MESH uuds, not empty uuids, which are used differently
            if obj.MM.uuid:
                uuids.append(obj.MM.uuid)

        if obj.MM.isplughandle:
            handles.append(obj)

        if obj.MM.isplug:
            plugs.append(obj)

        if obj.MM.isplugsubset:
            subsets.append(obj)

        if obj.MM.isplugdeformer:
            deformers.append(obj)
        if obj.MM.isplugoccluder:
            occluders.append(obj)

        if not any([obj.MM.isplughandle, obj.MM.isplug, obj.MM.isplugsubset, obj.MM.isplugdeformer, obj.MM.isplugoccluder]):
            if obj.type == "EMPTY":
                empties.append(obj)
            else:
                others.append(obj)

        modifiers.extend([mod.type for mod in obj.modifiers])

        if obj.MM.plugcreator:
            creators.append(obj.MM.plugcreator)

        return uuids, handles, plugs, subsets, deformers, occluders, others, empties, modifiers, creators
    def get_props(self, obj):
        print()
        print("Object Properties of '%s'" % (obj.name))
        print(" • uuid:", obj.MM.uuid)
        print(" • isplughandle:", obj.MM.isplughandle)
        print(" • isplug:", obj.MM.isplug)
        print("  • hasfillet:", obj.MM.hasfillet)
        print(" • isplugdeformer:", obj.MM.isplugdeformer)
        print("  • usedeformer:", obj.MM.usedeformer)
        print(" • isplugsubset:", obj.MM.isplugsubset)
        print("  • forcesubsetdeform:", obj.MM.forcesubsetdeform)
        print(" • isplugoccluder:", obj.MM.isplugoccluder)
        print(" • deformerprecision:", obj.MM.deformerprecision)
        print(" • plugcreaetor:", obj.MM.plugcreator)
