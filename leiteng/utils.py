import frappe
from toolz import keyfilter, curry, compose, excepts
import sys, traceback


@curry
def pick(whitelist, d=None):
    return keyfilter(lambda k: k in whitelist, d)


def handle_error(fn):
    def wrapper(*args, **kwargs):
        if "cmd" in kwargs.keys():
            del kwargs["cmd"]
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            frappe.logger("leiteng").error(e)
            traceback.print_exc(file=sys.stdout)

    return wrapper


transform_route = compose(
    excepts(AttributeError, lambda x: x.replace("/", "__"), lambda _: None),
    lambda x: x.get("route"),
)
