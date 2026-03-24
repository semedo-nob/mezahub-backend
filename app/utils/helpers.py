def ok(data=None, status: int = 200):
    if data is None:
        data = {}
    return data, status

