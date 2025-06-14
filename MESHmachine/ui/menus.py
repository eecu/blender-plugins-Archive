import bpy
from .. utils.registration import get_prefs, get_addon
from .. utils.ui import get_keymap_item, get_icon
from .. import bl_info

class MenuMeshMachine(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine"
    bl_label = "MESHmachine %s" % ('.'.join([str(v) for v in bl_info['version']]))

    def draw(self, context):
        if context.mode == "EDIT_MESH":
            draw_menu_edit(self, context)

        elif context.mode == "OBJECT":
            draw_menu_object(self, context)

def draw_menu_object(self, context, context_menu=False):
    layout = self.layout

    debug = context.scene.MM.debug
    update_available = get_prefs().update_available

    active = context.active_object
    sel = context.selected_objects

    can_plug = active and len(sel) == 2 and active in sel
    handles = [obj for obj in context.selected_objects if obj.MM.isplughandle]
    show_utils = active and len(sel) >= 1

    can_apply_boolean = [obj for obj in sel if any(mod.type == 'BOOLEAN' and mod.object for mod in obj.modifiers)]
    can_boolean = active and len(sel) >= 2
    can_quickpatch = active and not (active.MM.isplug or active.MM.isplughandle)

    has_orphans = [obj for obj in bpy.data.objects if obj.MM.isstashobj and obj.use_fake_user and obj.users == 1]
    has_mirror = any([mod.type == 'MIRROR' for obj in sel for mod in obj.modifiers])

    is_instance = [obj for obj in sel if obj.data and obj.data.users > 1]

    show_delete = get_keymap_item('Object Mode', 'machin3.call_mesh_machine_menu', 'X') and get_prefs().show_delete

    layout.operator_context = "INVOKE_DEFAULT"

    if update_available:
        layout.label(text="A new version is available!", icon_value=get_icon("refresh_green"))
        layout.separator()

    if debug and not context_menu:
        layout.separator()

    if can_plug:
        layout.operator("machin3.plug", text="Plug")

    layout.menu("MACHIN3_MT_mesh_machine_plug_libraries", text="Plug Libraries")

    if show_utils:
        layout.menu("MACHIN3_MT_mesh_machine_plug_utils", text="Plug Utils")

    if handles:
        layout.operator("machin3.delete_plug", text=f"({'Y' if show_delete else 'X'}) Delete Plug{'s' if len(handles) > 1 else ''}")

    if active and active.select_get():
        layout.separator()
        layout.operator("machin3.create_stash", text=f"Stash {'them' if len(sel) > 2 else 'it'}")

        layout.operator("machin3.view_stashes", text="View Stashes")
        layout.operator("machin3.transfer_stashes", text="Transfer Stashes")

    if has_orphans:
        layout.separator()
        layout.operator("machin3.view_orphan_stashes", text="View Orphan Stashes")

    if active and has_mirror:
        layout.separator()
        layout.operator("machin3.real_mirror", text="Real Mirror")

    if can_boolean or can_apply_boolean or is_instance:
        layout.separator()

        if can_boolean:
            layout.operator("machin3.boolean", text="Add Boolean")

        if can_apply_boolean:
            layout.operator("machin3.boolean_apply", text="Apply Booleans")
            layout.operator("machin3.boolean_duplicate", text="Duplicate Booleans")

        if is_instance:
            layout.operator("machin3.make_unique", text="Make Unique")

    if can_quickpatch:
        layout.separator()
        layout.operator("machin3.quick_patch", text="Quick Patch")

    if not context_menu:
        if show_delete:
            layout.separator()
            layout.operator_context = "EXEC_DEFAULT"
            layout.operator("object.delete", text="(X) Delete")

def draw_menu_edit(self, context, context_menu=False):
    layout = self.layout

    debug = context.scene.MM.debug
    update_available = get_prefs().update_available
    looptools = get_addon('LoopTools')[0]

    show_delete = get_keymap_item('Mesh', 'machin3.call_mesh_machine_menu', 'X') and get_prefs().show_delete
    show_mesh_split = get_keymap_item('Mesh', 'machin3.call_mesh_machine_menu', 'Y') and get_prefs().show_mesh_split
    show_looptools_wrappers = looptools and get_prefs().show_looptools_wrappers
    flick_symmetrize = get_keymap_item('Mesh', 'machin3.symmetrize', key=None, properties=[('flick', True)])

    layout.operator_context = "INVOKE_DEFAULT"

    if update_available:
        layout.label(text="A new version is available!", icon_value=get_icon("refresh_green"))
        layout.separator()

    if debug and not context_menu:
        layout.menu("MACHIN3_MT_mesh_machine_debug", text="Debug")
        layout.separator()

    layout.operator("machin3.fuse", text="Fuse")

    layout.operator("machin3.change_width", text="(W) Change Width")

    layout.operator("machin3.flatten", text="(E) Flatten")

    layout.separator()

    layout.operator("machin3.unfuse", text="(D) Unfuse")

    layout.operator("machin3.refuse", text="(R) Refuse")

    layout.operator("machin3.unchamfer", text="(C) Unchamfer")

    layout.operator("machin3.unbevel", text="(B) Unbevel")

    layout.operator("machin3.unfuck", text=f"({'Y' if show_delete else 'X'}) Unf*ck")

    layout.separator()
    layout.operator("machin3.turn_corner", text="Turn Corner")

    layout.operator("machin3.quad_corner", text="Quad Corner")

    layout.separator()
    layout.menu("MACHIN3_MT_mesh_machine_loops", text="Loops")

    layout.separator()
    layout.operator("machin3.boolean_cleanup", text="Boolean Cleanup")

    layout.operator("machin3.chamfer", text="Chamfer")

    layout.operator("machin3.offset", text="Offset")

    if get_prefs().experimental:
        layout.operator("machin3.offset_cut", text="Offset Cut")

    layout.separator()

    layout.operator("machin3.create_stash", text="Stash it")

    layout.operator("machin3.view_stashes", text="View Stashes")
    layout.separator()

    layout.operator("machin3.conform", text="Conform")

    layout.menu("MACHIN3_MT_mesh_machine_normals", text="Normals")
    layout.separator()

    if flick_symmetrize:
        layout.operator("machin3.symmetrize", text="Symmetrize").flick = True
    else:
        layout.menu("MACHIN3_MT_mesh_machine_symmetrize", text="Symmetrize")

    layout.separator()

    layout.menu("MACHIN3_MT_mesh_machine_select", text="Select")
    layout.separator()

    layout.operator("machin3.wedge", text="Wedge")

    if looptools and show_looptools_wrappers:
        layout.separator()

        layout.operator("machin3.looptools_circle", text="Circle")

        layout.operator("machin3.looptools_relax", text="Relax")

    if not context_menu:
        if show_delete:
            layout.separator()
            layout.operator("wm.call_menu", text="(X) Delete").name = "VIEW3D_MT_edit_mesh_delete"

        elif show_mesh_split:
            layout.separator()
            layout.operator("mesh.split", text="(Y) Split")

def context_menu(self, context):
    layout = self.layout

    p = get_prefs()
    if (context.mode == 'OBJECT' and p.show_in_object_context_menu) or (context.mode == "EDIT_MESH" and p.show_in_mesh_context_menu):
        layout.menu("MACHIN3_MT_mesh_machine_context")
        layout.separator()

class MenuContext(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_context"
    bl_label = "MESHmachine"

    def draw(self, context):
        if context.mode == 'OBJECT':
            draw_menu_object(self, context, context_menu=True)

        elif context.mode == "EDIT_MESH":
            draw_menu_edit(self, context, context_menu=True)

class MenuDebug(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_debug"
    bl_label = "Debug"

    def draw(self, context):
        layout = self.layout

        layout.operator_context = "INVOKE_DEFAULT"

        if getattr(bpy.types, "MACHIN3_OT_debug_whatever", False):
            layout.operator("machin3.debug_whatever", text="Debug Whatever")

        layout.operator("machin3.get_angle", text="Angle")
        layout.operator("machin3.get_length", text="Length")
        layout.operator("machin3.draw_debug", text="Draw Debug")
        layout.operator("machin3.debug_hud", text="debug HUD")

class MenuLoops(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_loops"
    bl_label = "Loops"

    def draw(self, context):
        layout = self.layout

        layout.operator("machin3.mark_loop", text="Mark Loop").clear = False
        layout.operator("machin3.mark_loop", text="Clear Loop").clear = True

class MenuNormals(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_normals"
    bl_label = "Normals"

    def draw(self, context):
        layout = self.layout

        layout.operator_context = 'INVOKE_DEFAULT'

        layout.operator("machin3.normal_flatten", text="Flatten")

        layout.operator("machin3.normal_straighten", text="Straighten")

        layout.operator("machin3.normal_transfer", text="Transfer")

        layout.operator("machin3.normal_clear", text="Clear")

class MenuSymmetrize(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_symmetrize"
    bl_label = "Symmetrize"

    def draw(self, context):
        layout = self.layout

        op = layout.operator("machin3.symmetrize", text="X")
        op.flick = False
        op.axis = "X"

        op = layout.operator("machin3.symmetrize", text="Y")
        op.flick = False
        op.axis = "Y"

        op = layout.operator("machin3.symmetrize", text="Z")
        op.flick = False
        op.axis = "Z"

class MenuPlugLibraries(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_plug_libraries"
    bl_label = "Plug Libraries"

    def draw(self, context):
        libraryscale = get_prefs().libraryscale
        plugsinlibraryscale = get_prefs().plugsinlibraryscale

        plugmode = get_prefs().plugmode

        pluglibsCOL = get_prefs().pluglibsCOL
        show_names = get_prefs().showplugnames
        show_count = get_prefs().showplugcount
        show_button = get_prefs().showplugbutton
        show_button_name = get_prefs().showplugbuttonname

        wm = context.window_manager
        wmt = bpy.types.WindowManager

        pluglibs = [lib.name for lib in pluglibsCOL if lib.isvisible]
        lockedlibs = [lib.name for lib in pluglibsCOL if lib.islocked]

        if pluglibs:
            layout = self.layout

            column = self.layout.column()

            column.prop(get_prefs(), "plugremovemode", text="Remove Plugs")

            column = layout.column_flow(columns=len(pluglibs))

            for library in pluglibs:
                libname = library.center(4, " ") if len(library) < 4 else library

                plugname = getattr(bpy.context.window_manager, "pluglib_" + library)

                column.separator()

                if show_count:
                    plugcount = len(getattr(wmt, "pluglib_" + library).keywords['items'])
                    liblabel = "%s, %d" % (libname, plugcount)
                else:
                    liblabel = libname

                column.label(text=liblabel)

                r = column.row()

                lib = "lockedpluglib" if plugmode == "REMOVE" and library in lockedlibs else "pluglib_" + library
                r.template_icon_view(wm, lib, show_labels=show_names, scale=libraryscale, scale_popup=plugsinlibraryscale)

                if show_button:
                    r = column.row()

                    if plugmode == "REMOVE" and library in lockedlibs:
                        r.label(text="LOCKED")

                    else:
                        if plugmode == "INSERT":
                            button = plugname if show_button_name else "+"
                            op = r.operator("machin3.insert_plug", text=button.center(len(liblabel), " "))  # NOTE: this is not a regular space, it's wider, it's a figure space U+2007, see https://www.brunildo.org/test/space-chars.html

                        elif plugmode == "REMOVE":
                            op = r.operator("machin3.remove_plug", text="X".center(len(liblabel), " "))  # NOTE: this is not a regular space, it's wider, it's a figure space U+2007, see https://www.brunildo.org/test/space-chars.html

                        op.library = library
                        op.plug = plugname

class MenuPlugUtils(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_plug_utils"
    bl_label = "Plug Utils"

    def draw(self, context):
        layout = self.layout

        layout.operator("machin3.create_plug", text="Create Plug")

        layout.operator("machin3.add_plug_to_library", text="Add Plug to Library")
        layout.separator()

        layout.operator("machin3.set_plug_props", text="Set Plug Props")

        layout.operator("machin3.clear_plug_props", text="Clear Plug Props")
        layout.separator()

        layout.operator("machin3.validate_plug", text="Validate Plug")

class MenuSelect(bpy.types.Menu):
    bl_idname = "MACHIN3_MT_mesh_machine_select"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout

        layout.operator("machin3.lselect", text="LSelect")
        layout.operator("machin3.sselect", text="SSelect")
        layout.operator("machin3.vselect", text="VSelect")
