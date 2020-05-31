# -*- coding: utf-8 -*-
import frappe
from functools import partial
from toolz import compose, excepts, first, merge, concat, unique, groupby, valmap
from erpnext.accounts.doctype.sales_invoice.pos import get_child_nodes

from leiteng.utils import handle_error


@frappe.whitelist(allow_guest=True)
@handle_error
def get_item(route):
    item_code = frappe.db.exists(
        "Item", {"route": route.replace("__", "/"), "show_in_website": 1}
    )
    if not item_code:
        frappe.throw(frappe._("Item does not exist at this route"))

    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")

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
        frappe.db.get_value(
            "Item Price",
            filters={"item_code": item_code, "price_list": price_list},
            fieldname="price_list_rate",
            as_dict=1,
        ),
    )
