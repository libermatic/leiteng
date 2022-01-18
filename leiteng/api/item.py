# -*- coding: utf-8 -*-
import frappe
from erpnext.utilities.product import get_price


@frappe.whitelist()
def list_item_price_list_rates(item_codes):
    _item_codes = frappe.parse_json(item_codes)
    if not _item_codes:
        return []

    return frappe.db.get_list(
        "Item Price",
        fields=["item_code", "price_list_rate"],
        filters={
            "item_code": ("in", _item_codes),
            "selling": 1,
            "price_list": frappe.db.get_single_value(
                "Shopping Cart Settings", "price_list"
            ),
            "ifnull(valid_from, '2000-01-01')": ("<", frappe.utils.today()),
            "ifnull(valid_upto, '2100-01-01')": (">", frappe.utils.today()),
        },
        order_by="valid_from desc",
    )


@frappe.whitelist()
def list_item_rates(item_codes):
    _item_codes = frappe.parse_json(item_codes)
    if not _item_codes:
        return []

    price_list = frappe.db.get_single_value("Shopping Cart Settings", "price_list")
    customer_group = frappe.db.get_single_value("Selling Settings", "customer_group")
    company = frappe.db.get_single_value("Shopping Cart Settings", "company")

    def get_rate(item_code):
        price = (
            get_price(
                item_code,
                price_list,
                customer_group=customer_group,
                company=company,
            )
            or {}
        )
        return price.get("price_list_rate")

    return [
        {"item_code": item_code, "rate": get_rate(item_code)}
        for item_code in _item_codes
    ]


@frappe.whitelist()
def list_item_stock_qtys(item_codes):
    _item_codes = frappe.parse_json(item_codes)
    if not _item_codes:
        return []

    tree = frappe.db.get_value(
        "Warehouse",
        frappe.db.get_single_value("Ahong eCommerce Settings", "warehouse"),
        fieldname=["lft", "rgt"],
    )

    if not tree:
        return []

    warehouses = [
        x
        for (x,) in frappe.get_all(
            "Warehouse",
            filters={
                "lft": (">=", tree[0]),
                "rgt": ("<=", tree[1]),
            },
            as_list=1,
        )
    ]
    if not warehouses:
        return []

    return frappe.db.sql(
        """
            SELECT
                b.item_code AS item_code,
                GREATEST(
                    SUM(
                        b.actual_qty - b.reserved_qty - b.reserved_qty_for_production - b.reserved_qty_for_sub_contract
                    ),
                    0
                ) / IFNULL(C.conversion_factor, 1) AS stock_qty
            FROM `tabBin` AS b
            INNER JOIN `tabItem` AS i
                ON b.item_code = i.item_code
            LEFT JOIN `tabUOM Conversion Detail` C
                ON i.sales_uom = C.uom AND C.parent = i.item_code
            WHERE b.item_code IN %(item_codes)s AND b.warehouse in %(warehouses)s
            GROUP BY b.item_code
        """,
        values={
            "item_codes": _item_codes,
            "warehouses": warehouses,
        },
        as_dict=1,
    )
