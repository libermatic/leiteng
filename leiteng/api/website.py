# -*- coding: utf-8 -*-
import frappe
from functools import partial
from toolz import compose, keyfilter, merge, unique, excepts, first


@frappe.whitelist(allow_guest=True)
def get_settings():
    from frappe.website.doctype.website_settings.website_settings import (
        get_website_settings,
    )

    get_filters = compose(
        partial(keyfilter, lambda x: x in ["copyright", "address"]),
        lambda x: merge(
            x, {"address": frappe.utils.strip_html_tags(x.get("footer_address"))}
        ),
    )
    allcat_groups = [
        x.get("item_group")
        for x in frappe.get_all(
            "Website Item Group",
            fields=["item_group"],
            filters={"parent": "Leiteng Website Settings"},
        )
    ]

    settings = get_website_settings()

    return merge(
        get_filters(settings),
        {"root_groups": _get_root_groups(), "allcat_groups": allcat_groups},
    )


def _get_root_groups():
    def get_root(x):
        # assuming that parent - child relationship is never circular
        parent = get_parent(x)
        if parent:
            return get_root(parent)
        return x

    groups = frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group"],
        filters={"show_in_website": 1},
    )
    get_parent = compose(
        excepts(StopIteration, first, lambda _: None),
        lambda x: filter(lambda y: y.get("name") == x.get("parent_item_group"), groups),
    )
    make_unique_roots = compose(
        list, unique, partial(map, lambda x: x.get("name")), partial(map, get_root)
    )

    return make_unique_roots(groups)
