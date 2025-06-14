import bpy
from bpy.app.handlers import persistent
from mathutils import Vector
from . utils.application import delay_execution
from . utils.curve import get_curve_as_dict, get_curve_selection
from . utils.object import get_active_object
from . utils.system import printd

global_debug = False

selection_history = []
previous_selection = set()

def manage_curve_selection_history():
    global global_debug, selection_history, previous_selection

    debug = global_debug
    debug = False

    if debug:
        print("  curve selection history")

    C = bpy.context
    active = get_active_object(C)

    if active and active.type == 'CURVE' and C.mode == 'EDIT_CURVE':
        data = get_curve_as_dict(active.data)
        selection = get_curve_selection(data, debug=False)

        symdiff = selection.symmetric_difference(previous_selection)

        if debug:
            print("   symdiff:", symdiff)

        if symdiff:
            if len(symdiff) == 1:
                if debug:
                    print("   a change of 1")

                change = symdiff.pop()

                if change in selection:
                    if debug:
                        print("    it was added")

                    selection_history.append(change)
                else:
                    if debug:
                        print("    it was removed")

                    if change in selection_history:
                        selection_history.remove(change)
                    else:
                        selection_history = []
            else:
                if debug:
                    print("   a change of multiple")

                selection_history = []

        if not selection_history and len(selection) == 1:
            if debug:
                print("   initiating history from single point selection")

            selection_history = list(selection)

        previous_selection = selection

        if debug:
            print("  history:", selection_history)

@persistent
def depsgraph_update_post(scene):
    global global_debug

    if global_debug:
        print()
        print("CURVEmachine depsgraph update post handler:")

    if global_debug:
        print(" managing curve selection history")

    delay_execution(manage_curve_selection_history)
