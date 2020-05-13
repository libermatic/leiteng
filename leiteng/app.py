# -*- coding: utf-8 -*-
import frappe
import firebase_admin
from firebase_admin import auth

app = firebase_admin.initialize_app(name="leiteng")


def get_decoded_token(token):
    decoded = auth.verify_id_token(token, app=app)
    if not decoded.get("uid"):
        frappe.throw(frappe._("Invalid token"))
    return decoded


def get_user(uid):
    return auth.get_user(uid, app=app)
