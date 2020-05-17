# -*- coding: utf-8 -*-
import frappe
import firebase_admin
from firebase_admin import auth

cred = firebase_admin.credentials.Certificate(
    f"{frappe.get_app_path('leiteng')}/../firebase-admin-sdk.json"
)
app = firebase_admin.initialize_app(cred, name="leiteng")


def get_decoded_token(token):
    decoded = auth.verify_id_token(token, app=app)
    if not decoded.get("uid"):
        frappe.throw(frappe._("Invalid token"))
    return decoded


def get_user(uid):
    return auth.get_user(uid, app=app)
