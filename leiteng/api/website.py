# -*- coding: utf-8 -*-
import frappe
from toolz.curried import (
    compose,
    keyfilter,
    merge,
    unique,
    excepts,
    first,
    concat,
    valmap,
    groupby,
    map,
)

from leiteng.utils import handle_error, transform_route, pick


@frappe.whitelist(allow_guest=True)
@handle_error
def get_settings():
    from frappe.website.doctype.website_settings.website_settings import (
        get_website_settings,
    )

    get_filters = compose(
        keyfilter(lambda x: x in ["copyright", "address"]),
        lambda x: merge(
            x, {"address": frappe.utils.strip_html_tags(x.get("footer_address"))}
        ),
    )

    leiteng_settings = frappe.get_single("Leiteng Website Settings")
    allcat_groups = [x.item_group for x in leiteng_settings.allcat_groups]
    slideshow = _get_slideshow_settings(leiteng_settings)

    settings = get_website_settings()

    return merge(
        get_filters(settings),
        {
            "root_groups": _get_root_groups(),
            "allcat_groups": allcat_groups,
            "slideshow": slideshow,
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
    return [
        merge(
            x,
            {
                "route": transform_route(x),
                "description": frappe.utils.strip_html_tags(x.get("description") or ""),
            },
        )
        for x in groups
    ]


@frappe.whitelist(allow_guest=True)
@handle_error
def get_items(page="1", field_filters=None, attribute_filters=None, search=None):
    from erpnext.portal.product_configurator.utils import get_products_for_website
    from erpnext.accounts.doctype.sales_invoice.pos import get_child_nodes
    from erpnext.utilities.product import get_price

    other_fieldnames = ["item_group", "thumbnail"]
    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")
    products_per_page = frappe.db.get_single_value(
        "Products Settings", "products_per_page"
    )
    get_item_groups = compose(
        list,
        unique,
        map(lambda x: x.get("name")),
        concat,
        map(lambda x: get_child_nodes("Item Group", x)),
    )
    get_other_fields = compose(
        valmap(excepts(StopIteration, first, lambda _: {})),
        groupby("name"),
        lambda item_codes: frappe.db.sql(
            """
                SELECT name, {other_fieldnames}
                FROM `tabItem`
                WHERE name IN %(item_codes)s
            """.format(
                other_fieldnames=", ".join(other_fieldnames)
            ),
            values={"item_codes": item_codes},
            as_dict=1,
        ),
        lambda items: [x.get("name") for x in items],
    )
    get_item_prices = (
        compose(
            valmap(excepts(StopIteration, first, lambda _: {})),
            groupby("item_code"),
            lambda item_codes: frappe.db.sql(
                """
                    SELECT item_code, price_list_rate
                    FROM `tabItem Price`
                    WHERE price_list = %(price_list)s AND item_code IN %(item_codes)s
                """.format(
                    other_fieldnames=", ".join(other_fieldnames)
                ),
                values={"price_list": price_list, "item_codes": item_codes},
                as_dict=1,
            ),
            lambda items: [x.get("name") for x in items],
        )
        if price_list
        else lambda _: {}
    )

    get_page_count = compose(
        lambda x: frappe.utils.ceil(x[0][0] / products_per_page),
        lambda x: frappe.db.sql(
            """
                SELECT COUNT(name) FROM `tabItem` WHERE
                    show_in_website = 1 AND
                    item_group IN %(item_groups)s
            """,
            values={"item_groups": x},
        ),
    )

    field_dict = frappe.parse_json(field_filters)
    item_groups = (
        get_item_groups(field_dict.get("item_group"))
        if field_dict.get("item_group")
        else None
    )

    frappe.form_dict.start = (frappe.utils.cint(page) - 1) * products_per_page + 1
    items = get_products_for_website(
        field_filters=merge(
            field_dict, {"item_group": item_groups} if item_groups else {}
        ),
        attribute_filters=frappe.parse_json(attribute_filters),
        search=search,
    )
    other_fields = get_other_fields(items) if items else {}
    item_prices = get_item_prices(items) if items else {}

    def get_rates(item_code):
        price_obj = get_price(
            item_code,
            price_list,
            customer_group=frappe.get_cached_value(
                "Selling Settings", None, "customer_group"
            ),
            company=frappe.defaults.get_global_default("company"),
        )
        price_list_rate = item_prices.get(item_code, {}).get("price_list_rate")
        item_price = price_obj.get("price_list_rate") or price_list_rate
        return {
            "price_list_rate": item_price,
            "slashed_rate": price_list_rate if price_list_rate != item_price else None,
        }

    return {
        "page_count": get_page_count(item_groups),
        "items": [
            merge(
                x,
                {
                    "route": transform_route(x),
                    "description": frappe.utils.strip_html_tags(
                        x.get("description") or ""
                    ),
                    "web_long_description": frappe.utils.strip_html_tags(
                        x.get("web_long_description") or ""
                    ),
                },
                get_rates(x.get("name")),
                {
                    k: other_fields.get(x.get("name"), {}).get(k)
                    for k in other_fieldnames
                },
            )
            for x in items
        ],
    }


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
