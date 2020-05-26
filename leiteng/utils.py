import frappe
from toolz import keyfilter, curry


@curry
def pick(whitelist, d):
    return keyfilter(lambda k: k in whitelist, d)


def handle_error(fn):
    def wrapper(*args, **kwargs):
        del kwargs["cmd"]
        try:
            return fn(*args, **kwargs)
        except:
            pass

    return wrapper
