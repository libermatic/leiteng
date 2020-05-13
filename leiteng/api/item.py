# -*- coding: utf-8 -*-
import frappe
from functools import partial
from toolz import compose, excepts, first, merge, concat, unique, groupby, valmap
from erpnext.accounts.doctype.sales_invoice.pos import get_child_nodes


_transform_route = compose(lambda x: x.replace("/", "__"), lambda x: x.get("route"))
_clean_description = compose(
    frappe.utils.strip_html_tags, lambda x, field="description": x.get(field) or ""
)


@frappe.whitelist(allow_guest=True)
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
        merge(x, {"route": _transform_route(x), "description": _clean_description(x)})
        for x in groups
    ]


@frappe.whitelist(allow_guest=True)
def get_items(page=1, field_filters=None, attribute_filters=None, search=None):
    from erpnext.portal.product_configurator.utils import get_products_for_website

    other_fieldnames = ["item_group", "thumbnail"]
    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")
    products_per_page = frappe.db.get_single_value(
        "Products Settings", "products_per_page"
    )
    get_item_groups = compose(
        list,
        unique,
        partial(map, lambda x: x.get("name")),
        concat,
        partial(map, lambda x: get_child_nodes("Item Group", x)),
    )
    get_other_fields = compose(
        partial(valmap, excepts(StopIteration, first, lambda _: {})),
        partial(groupby, "name"),
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
            partial(valmap, excepts(StopIteration, first, lambda _: {})),
            partial(groupby, "item_code"),
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

    return {
        "page_count": get_page_count(item_groups),
        "items": [
            merge(
                x,
                {
                    "route": _transform_route(x),
                    "description": _clean_description(x),
                    "web_long_description": _clean_description(
                        x, "web_long_description"
                    ),
                    "price_list_rate": item_prices.get(x.get("name"), {}).get(
                        "price_list_rate"
                    ),
                },
                {
                    k: other_fields.get(x.get("name"), {}).get(k)
                    for k in other_fieldnames
                },
            )
            for x in items
        ],
    }


@frappe.whitelist(allow_guest=True)
def get_item(route):
    item_code = frappe.db.exists(
        "Item", {"route": route.replace("__", "/"), "show_in_website": 1}
    )
    if not item_code:
        frappe.throw(frappe._("Item does not exist at this route"))

    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")

    return merge(
        {"route": route},
        frappe.db.get_value(
            "Item",
            item_code,
            fieldname=[
                "name",
                "item_name",
                "description",
                "web_long_description",
                "image",
                "website_image",
                "item_group",
            ],
            as_dict=1,
        ),
        frappe.db.get_value(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fieldname="price_list_rate",
            as_dict=1,
        ),
    )
