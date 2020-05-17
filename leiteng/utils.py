from toolz import keyfilter, curry


@curry
def pick(whitelist, d):
    return keyfilter(lambda k: k in whitelist, d)
