# -*- coding: utf-8 -*-
import frappe
import json
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from toolz.curried import keyfilter, merge, groupby, compose


from leiteng.app import get_decoded_token
from leiteng.utils import pick


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
        dn.le_auto_invoice = 1
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
