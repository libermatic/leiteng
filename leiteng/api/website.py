# -*- coding: utf-8 -*-
import frappe
from toolz.curried import (
    compose,
    merge,
    unique,
    excepts,
    first,
    map,
    filter,
)

from leiteng.utils import handle_error, transform_route, pick


@frappe.whitelist(allow_guest=True)
@handle_error
def get_settings():
    from frappe.website.doctype.website_settings.website_settings import (
        get_website_settings,
    )

    leiteng_settings = frappe.get_single("Leiteng Website Settings")
    allcat_groups = [x.item_group for x in leiteng_settings.allcat_groups]
    slideshow = _get_slideshow_settings(leiteng_settings)

    settings = get_website_settings()

    return merge(
        pick(["copyright", "footer_address"], settings),
        {
            "root_groups": _get_root_groups(),
            "allcat_groups": allcat_groups,
            "slideshow": slideshow,
            "privacy": bool(leiteng_settings.privacy),
            "terms": bool(leiteng_settings.terms),
            "show_about_us": bool(leiteng_settings.show_about_us),
            "hide_build_info": bool(leiteng_settings.hide_build_info),
        },
    )


@frappe.whitelist(allow_guest=True)
@handle_error
def get_all_item_groups():
    groups = frappe.get_all(
        "Item Group",
        filters={"show_in_website": 1},
        fields=[
            "name",
            "is_group",
            "route",
            "parent_item_group",
            "description",
            "image",
        ],
        order_by="lft, rgt",
    )
    return [merge(x, {"route": transform_route(x)},) for x in groups]


@frappe.whitelist(allow_guest=True)
@handle_error
def get_legal_doc(content_type):
    get_content = compose(
        lambda x: frappe.get_cached_value("Terms and Conditions", x, "terms"),
        lambda x: frappe.get_cached_value("Leiteng Website Settings", None, x),
    )

    if content_type in ["privacy", "terms"]:
        return get_content(content_type)

    return None


@frappe.whitelist(allow_guest=True)
@handle_error
def get_about_us():
    about = frappe.get_cached_doc("About Us Settings")
    return pick(["company_introduction"], about.as_dict())


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
        list, unique, map(lambda x: x.get("name")), map(get_root)
    )

    return make_unique_roots(groups)


def _get_slideshow_settings(settings):
    if not settings.slideshow:
        return None

    def get_route(item):
        ref_doctype, ref_name = item.get("le_ref_doctype"), item.get("le_ref_docname")
        if ref_doctype and ref_name:
            route, show_in__website = frappe.get_cached_value(
                ref_doctype, ref_name, ["route", "show_in_website"]
            )
            if route and show_in__website:
                if ref_doctype == "Item Group":
                    return transform_route({"route": route})
                if ref_doctype == "Item":
                    item_group = frappe.get_cached_value("Item", ref_name, "item_group")
                    group_route, show_in__website = frappe.get_cached_value(
                        "Item Group", item_group, ["route", "show_in_website"],
                    )
                    if group_route and show_in__website:
                        return "/".join(
                            [
                                transform_route({"route": group_route}),
                                transform_route({"route": route}),
                            ]
                        )
        return None

    return [
        merge(pick(["image", "heading", "description"], x), {"route": get_route(x)})
        for x in frappe.get_all(
            "Website Slideshow Item",
            filters={"parent": settings.slideshow},
            fields=[
                "image",
                "heading",
                "description",
                "le_ref_doctype",
                "le_ref_docname",
            ],
        )
    ]
