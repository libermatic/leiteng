from __future__ import unicode_literals
import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
    frappe.reload_doc("Selling", "doctype", "Customer")
    frappe.reload_doc("Setup", "doctype", "Sales Partner")

    rename_field("Customer", "le_firebase_uid", "firebase_uid")
    rename_field("Customer", "le_fcm_token", "fcm_token")
    rename_field("Sales Partner", "le_sign_up_code", "sign_up_code")
    rename_field("Sales Partner", "le_firebase_uid", "firebase_uid")
    rename_field("Sales Partner", "le_fcm_token", "fcm_token")
