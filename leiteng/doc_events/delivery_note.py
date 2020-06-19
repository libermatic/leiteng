# -*- coding: utf-8 -*-
import json
import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from toolz.curried import compose, unique, first, excepts, map, filter

from leiteng.app import send_data


def validate(doc, method):
    get_so_count = compose(len, list, unique, map(lambda x: x.against_sales_order))
    if get_so_count(doc.items) != 1:
        frappe.throw(frappe._("Cannot create document with multiple Sales Orders"))


def after_insert(doc, method):
    _send_customer_confirmation(doc)
    _send_partner_assignment(doc)


def on_submit(doc, method):
    if doc.le_auto_invoice:
        _create_sales_invoice(doc)

    _send_customer_fulfillment(doc)


def _send_customer_confirmation(doc):
    order = _get_so(doc)
    if not order:
        return
    fcm_token = frappe.get_cached_value("Customer", doc.customer, "le_fcm_token")
    if not fcm_token:
        return

    data = {
        "type": "order_confirmation",
        "order_id": order,
        "note_id": doc.name,
        "items": json.dumps([x.item_name for x in doc.items]),
        "scheduled_datetime": frappe.utils.get_datetime_str(doc.le_scheduled_datetime),
        "partner_name": frappe.get_cached_value(
            "Sales Partner", doc.sales_partner, "partner_name"
        )
        if doc.sales_partner
        else None,
    }

    send_data(fcm_token, data)


def _send_customer_fulfillment(doc):
    order = _get_so(doc)
    if not order:
        return
    fcm_token = frappe.get_cached_value("Customer", doc.customer, "le_fcm_token")
    if not fcm_token:
        return

    data = {
        "type": "order_fulfillment",
        "order_id": order,
        "items": json.dumps([x.item_name for x in doc.items]),
        "posting_datetime": "{} {}".format(doc.posting_date, doc.posting_time),
        "partner_name": frappe.get_cached_value(
            "Sales Partner", doc.sales_partner, "partner_name"
        )
        if doc.sales_partner
        else None,
    }

    send_data(fcm_token, data)


def _send_partner_assignment(doc):
    order = _get_so(doc)
    if not order:
        return
    fcm_token = frappe.get_cached_value(
        "Sales Partner", doc.sales_partner, "le_fcm_token"
    )
    if not fcm_token:
        return

    get_address = compose(
        json.dumps,
        list,
        filter(None),
        excepts(
            frappe.DoesNotExistError,
            lambda x: frappe.get_cached_value(
                "Address", x, ["address_line1", "address_line2"],
            ),
            lambda _: [],
        ),
    )

    data = {
        "type": "job_assigment",
        "note_id": doc.name,
        "items": json.dumps([x.item_name for x in doc.items]),
        "scheduled_datetime": frappe.utils.get_datetime_str(doc.le_scheduled_datetime),
        "customer_name": doc.customer_name,
        "address": get_address(doc.shipping_address_name or doc.customer_address),
    }

    send_data(fcm_token, data)


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


_get_so = compose(
    first, filter(None), map(lambda x: x.against_sales_order), lambda x: x.items
)


def _get_item_description(items):
    item_names = [x.item_name for x in items]
    return (
        "{}".format(item_names[0])
        if len(item_names) == 1
        else "{} +{} more item(s)".format(item_names[0], len(item_names) - 1)
    )


def _format_datetime(dt_str):
    return "{0:%a} {0:%b} {0.day}, {0.year} {0:%H}:{0:%M} {0:%p}".format(
        frappe.utils.get_datetime(dt_str)
    )
