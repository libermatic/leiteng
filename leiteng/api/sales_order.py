# -*- coding: utf-8 -*-
import frappe
import json
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from toolz.curried import keyfilter, merge, groupby, compose


from leiteng.app import get_decoded_token
from leiteng.utils import pick


@frappe.whitelist(allow_guest=True)
def create(token, **kwargs):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    args = pick(["transaction_date", "delivery_date", "customer_address"], kwargs)

    doc = frappe.get_doc(
        merge(
            {
                "doctype": "Sales Order",
                "customer": customer_id,
                "order_type": "Sales",
                "company": frappe.defaults.get_user_default("company"),
                "currency": frappe.defaults.get_user_default("currency"),
                "selling_price_list": frappe.db.get_single_value(
                    "Selling Settings", "selling_price_list"
                ),
            },
            args,
            {"le_delivery_time": kwargs.get("delivery_time")},
        )
    )

    warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    for item_args in json.loads(kwargs.get("items", "[]")):
        doc.append(
            "items",
            merge(
                pick(["item_code", "qty", "rate"], item_args),
                {
                    "warehouse": warehouse,
                    "uom": frappe.db.get_value(
                        "Item", item_args.get("item_code"), "stock_uom"
                    ),
                },
            ),
        )

    doc.set_missing_values()
    doc.insert()
    doc.submit()
    frappe.set_user(session_user)
    return merge(
        pick(
            ["name", "transaction_date", "delivery_date", "rounded_total"],
            doc.as_dict(),
        ),
        {
            "delivery_time": doc.le_delivery_time,
            "items": [
                pick(["item_code", "item_name", "qty", "rate", "amount"], x.as_dict())
                for x in doc.items
            ],
        },
    )


@frappe.whitelist(allow_guest=True)
def list(token, page="1", page_length="10"):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    get_count = compose(
        lambda x: x[0][0],
        lambda x: frappe.db.sql(
            """
                SELECT COUNT(name) FROM `tabSales Order` WHERE customer = %(customer)s
            """,
            values={"customer": x},
        ),
    )

    orders = frappe.db.sql(
        """
            SELECT name, transaction_date, rounded_total, status
            FROM `tabSales Order` WHERE customer = %(customer)s
            ORDER BY transaction_date DESC, creation DESC
            LIMIT %(start)s, %(page_length)s
        """,
        values={
            "customer": customer_id,
            "start": (frappe.utils.cint(page) - 1) * frappe.utils.cint(page_length),
            "page_length": frappe.utils.cint(page_length),
        },
        as_dict=1,
    )
    items = (
        groupby(
            "parent",
            frappe.db.sql(
                """
                    SELECT parent, item_code, item_name, qty, rate, amount
                    FROM `tabSales Order Item`
                    WHERE parent IN %(parents)s
                """,
                values={"parents": [x.get("name") for x in orders]},
                as_dict=1,
            ),
        )
        if orders
        else {}
    )
    return {
        "count": get_count(customer_id),
        "items": [merge(x, {"items": items.get(x.get("name"), [])}) for x in orders],
    }


@frappe.whitelist()
def get_items_to_assign(doc_name):
    existing = [
        x[0]
        for x in frappe.db.sql(
            """
            SELECT dni.so_detail FROM `tabDelivery Note Item` AS dni
            LEFT JOIN `tabDelivery Note` AS dn ON dn.name = dni.parent
            WHERE
                dni.against_sales_order = %(sales_order)s AND
                dn.docstatus < 2 AND
                dn.workflow_state IN ('Pending', 'Completed')
        """,
            values={"sales_order": doc_name},
        )
    ]
    return [
        x[0]
        for x in frappe.get_all(
            "Sales Order Item",
            filters={"parent": doc_name, "name": ("not in", existing)},
            fields=["name"],
            as_list=1,
        )
    ]


@frappe.whitelist()
def assign_technicians(doc_name, items_str):
    group_items_by_sales_partner = compose(
        groupby(lambda x: (x.get("sales_partner"), x.get("scheduled_datetime"))),
        json.loads,
    )

    item_table_mapper = {
        "doctype": "Delivery Note Item",
        "field_map": {
            "rate": "rate",
            "name": "so_detail",
            "parent": "against_sales_order",
        },
        "condition": lambda x: abs(x.delivered_qty) < abs(x.qty)
        and x.delivered_by_supplier != 1,
    }

    items_by_sales_partner = group_items_by_sales_partner(items_str)

    def create_dn(key):
        dn = make_delivery_note(doc_name, skip_item_mapping=True)
        dn.sales_partner = key[0]
        dn.commission_rate = frappe.get_cached_value(
            "Sales Partner", key[0], "commission_rate"
        )
        dn.le_scheduled_datetime = key[1]
        for item in items_by_sales_partner[key]:
            so_item = frappe.get_cached_doc("Sales Order Item", item.get("so_detail"))
            frappe.model.mapper.map_child_doc(so_item, dn, item_table_mapper)
        dn.run_method("set_missing_values")
        dn.run_method("set_po_nos")
        dn.run_method("calculate_taxes_and_totals")
        dn.insert()
        return dn.name

    delivery_notes = [create_dn(x) for x in items_by_sales_partner]
    return delivery_notes
