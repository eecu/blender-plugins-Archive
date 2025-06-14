from . registration import get_prefs

def get_lib():
    idx = get_prefs().pluglibsIDX
    libs = get_prefs().pluglibsCOL
    active = libs[idx] if libs else None

    return idx, libs, active
