# -*- coding: utf-8 -*-
import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from toolz.curried import compose, unique, map, filter


def validate(doc, methods):
    get_so_count = compose(len, list, unique, map(lambda x: x.against_sales_order))
    if get_so_count(doc.items) != 1:
        frappe.throw(frappe._("Cannot create document with multiple Sales Orders"))


def on_submit(doc, method):
    if _get_order_type(doc) == "Shopping Cart":
        _create_sales_invoice(doc)


def _get_order_type(doc):
    order_name = doc.items[0].against_sales_order
    return (
        frappe.db.get_value("Sales Order", order_name, "order_type")
        if order_name
        else None
    )


def _create_sales_invoice(doc):
    invoice = frappe.new_doc("Sales Invoice")
    invoice.flags.ignore_permissions = True
    make_sales_invoice(doc.name, target_doc=invoice)
    invoice.is_pos = 1
    invoice.payments = []
    invoice.append(
        "payments", {"mode_of_payment": "Cash", "amount": invoice.rounded_total}
    )
    invoice.save()
    invoice.submit()
