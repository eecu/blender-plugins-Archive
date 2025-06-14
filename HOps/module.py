
def module_name():
    '''Return module name assgined by blender'''
    name = __name__
    name = __name__[:len(name) - len(".module")]

    return name