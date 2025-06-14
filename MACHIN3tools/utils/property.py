def step_list(current, list, step, loop=True):
    item_idx = list.index(current)

    step_idx = item_idx + step

    if step_idx >= len(list):
        if loop:
            step_idx = 0
        else:
            step_idx = len(list) - 1

    elif step_idx < 0:
        if loop:
            step_idx = len(list) - 1
        else:
            step_idx = 0

    return list[step_idx]

def step_enum(current, items, step, loop=True):
    item_list = [item[0] for item in items]
    item_idx = item_list.index(current)

    step_idx = item_idx + step

    if step_idx >= len(item_list):
        if loop:
            step_idx = 0
        else:
            step_idx = len(item_list) - 1
    elif step_idx < 0:
        if loop:
            step_idx = len(item_list) - 1
        else:
            step_idx = 0

    return item_list[step_idx]

def rotate_list(list, amount):
    for i in range(abs(amount)):
        if amount > 0:
            list.append(list.pop(0))
        else:
            list.insert(0, list.pop(-1))

    return list
