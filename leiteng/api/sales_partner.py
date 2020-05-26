# -*- coding: utf-8 -*-
import frappe
from toolz import merge

from leiteng.app import get_decoded_token, auth
from leiteng.utils import pick, handle_error


@frappe.whitelist(allow_guest=True)
@handle_error
def get(token):
    decoded_token = get_decoded_token(token)
    partner_id = frappe.db.exists(
        "Sales Partner", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not partner_id:
        return None
    doc = frappe.get_doc("Sales Partner", partner_id)
    return pick(["name", "sales_partner_name"], doc.as_dict())


@frappe.whitelist(allow_guest=True)
@handle_error
def create(token, partner_name, code, **kwargs):
    decoded_token = get_decoded_token(token)
    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    partner_id = frappe.db.exists("Sales Partner", {"le_sign_up_code": code})
    if not partner_id:
        frappe.throw(frappe._("Invalid Sign Up Code"))

    uid = decoded_token["uid"]
    address_args = pick(
        ["address_line1", "address_line2", "city", "state", "country", "pincode"],
        kwargs,
    )
    if address_args:
        frappe.get_doc(
            merge(
                {
                    "doctype": "Address",
                    "links": [
                        {"link_doctype": "Sales Partner", "link_name": partner_id}
                    ],
                },
                address_args,
            )
        ).insert()

    contact_args = pick(["mobile_no", "email_id"], kwargs)
    if contact_args:
        contact = frappe.get_doc(
            merge(
                {
                    "doctype": "Contact",
                    "first_name": partner_name,
                    "is_primary_contact": 1,
                    "links": [
                        {"link_doctype": "Sales Partner", "link_name": partner_id}
                    ],
                },
            )
        )
        if contact_args.get("email_id"):
            contact.add_email(contact_args.get("email_id"), is_primary=True)
        if contact_args.get("mobile_no"):
            contact.add_phone(contact_args.get("mobile_no"), is_primary_mobile_no=True)
        contact.insert()

    print([contact_args, address_args])

    doc = frappe.get_doc("Sales Partner", partner_id)
    doc.update(
        {
            "partner_name": partner_name,
            "le_sign_up_code": None,
            "le_firebase_uid": uid,
            "le_mobile_no": contact_args.get("mobile_no"),
        }
    )
    doc.save()
    auth.set_custom_user_claims(uid, {"partner": True})

    frappe.set_user(session_user)
    return pick(["name", "partner_name"], doc.as_dict())


@frappe.whitelist(allow_guest=True)
@handle_error
def check_signup_code(code):
    exists = frappe.db.exists("Sales Partner", {"le_sign_up_code": code.upper()})
    if not exists:
        frappe.throw(frappe._("Invalid Sign Up Code"))


@frappe.whitelist()
def generate_signup_code(sales_partner_name):
    firebase_uid = frappe.db.get_value(
        "Sales Partner", sales_partner_name, "le_firebase_uid"
    )
    if firebase_uid:
        frappe.throw(frappe._("Sign-up already completed for this Sales Partner. "))

    sign_up_code = frappe.generate_hash(
        "Sales Partner:{}".format(sales_partner_name), 6
    ).upper()
    frappe.db.set_value(
        "Sales Partner", sales_partner_name, "le_sign_up_code", sign_up_code
    )
    return sign_up_code
