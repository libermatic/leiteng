# -*- coding: utf-8 -*-
import frappe


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
