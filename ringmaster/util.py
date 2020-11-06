

def walk(data, parent_name=None):
    seq_iter = data if isinstance(data, dict) else range(len(data))
    for i in seq_iter:
        if parent_name:
            me = f"{parent_name}_{i}"
        else:
            me = i

    if isinstance(data[i], dict):
        for k, v in walk(data[i], parent_name=me):
            yield k, v
    elif isinstance(data[i], list) or isinstance(data[i], tuple):
        for k, v in walk(data[i], parent_name=me):
            yield k, v
    else:
        yield me, data[i]

def flatten_nested_dict(data):
    flattened = {}
    for k, v in walk(data):
        flattened[k.lower()] = v

    return flattened
