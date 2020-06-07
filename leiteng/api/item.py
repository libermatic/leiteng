# -*- coding: utf-8 -*-
import frappe
from functools import partial
from toolz.curried import (
    compose,
    excepts,
    first,
    merge,
    concat,
    unique,
    groupby,
    valmap,
)
from erpnext.portal.product_configurator.utils import get_products_for_website
from erpnext.accounts.doctype.sales_invoice.pos import get_child_nodes
from erpnext.utilities.product import get_price

from leiteng.utils import handle_error, transform_route


@frappe.whitelist(allow_guest=True)
@handle_error
def get_item(route):
    item_code = frappe.db.exists(
        "Item", {"route": route.replace("__", "/"), "show_in_website": 1}
    )
    if not item_code:
        frappe.throw(frappe._("Item does not exist at this route"))

    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")

    def get_rates(item_code):
        price_obj = get_price(
            item_code,
            price_list,
            customer_group=frappe.get_cached_value(
                "Selling Settings", None, "customer_group"
            ),
            company=frappe.defaults.get_global_default("company"),
        )
        price_list_rate = frappe.db.get_value(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fieldname="price_list_rate",
        )
        item_price = price_obj.get("price_list_rate") or price_list_rate
        return {
            "price_list_rate": item_price,
            "slashed_rate": price_list_rate if price_list_rate != item_price else None,
        }

    doc = frappe.db.get_value(
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
    )
    return merge(
        {"route": route},
        doc,
        {
            "description": frappe.utils.strip_html_tags(doc.get("description") or ""),
            "web_long_description": frappe.utils.strip_html_tags(
                doc.get("web_long_description") or ""
            ),
        },
        get_rates(doc.get("name")),
    )


@frappe.whitelist(allow_guest=True)
@handle_error
def get_items(page="1", field_filters=None, attribute_filters=None, search=None):
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
