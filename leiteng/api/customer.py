# -*- coding: utf-8 -*-
import frappe
from firebase_admin import auth
from toolz import keyfilter, merge

from leiteng.app import get_decoded_token


@frappe.whitelist(allow_guest=True)
def get_customer(token):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        return None
    doc = frappe.get_doc("Customer", customer_id)
    return keyfilter(lambda x: x in ["name", "customer_name"], doc.as_dict())


@frappe.whitelist(allow_guest=True)
def create_customer(token, **kwargs):
    decoded_token = get_decoded_token(token)
    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    args = keyfilter(
        lambda x: x
        in [
            "customer_name",
            "mobile_no",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "country",
            "pincode",
        ],
        kwargs,
    )

    if not customer_id:
        doc = frappe.get_doc(
            merge(
                {
                    "doctype": "Customer",
                    "le_firebase_uid": decoded_token["uid"],
                    "customer_type": "Individual",
                    "customer_group": frappe.db.get_single_value(
                        "Selling Settings", "customer_group"
                    ),
                    "territory": frappe.db.get_single_value(
                        "Selling Settings", "territory"
                    ),
                },
                args,
            )
        ).insert()
        return keyfilter(lambda x: x in ["name", "customer_name"], doc.as_dict())

    doc = frappe.get_doc("Customer", customer_id)
    frappe.set_user(session_user)
    return keyfilter(lambda x: x in ["name", "customer_name"], doc.as_dict())
