# -*- coding: utf-8 -*-
import frappe
import firebase_admin
from firebase_admin import auth, messaging

cred = firebase_admin.credentials.Certificate(
    "{}/../firebase-admin-sdk.json".format(frappe.get_app_path("leiteng"))
)
app = firebase_admin.initialize_app(cred, name="leiteng")


def get_decoded_token(token):
    decoded = auth.verify_id_token(token, app=app)
    if not decoded.get("uid"):
        frappe.throw(frappe._("Invalid token"))
    return decoded


def get_user(uid):
    return auth.get_user(uid, app=app)


def send_notification(token, title, body, link=None):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title, body=body, image="/logo192.png"
        ),
        webpush=messaging.WebpushConfig(
            fcm_options=messaging.WebpushFCMOptions(link=link)
        ),
        token=token,
    )

    return messaging.send(message, app=app)


def send_data(token, data):
    message = messaging.Message(data=data, token=token,)

    return messaging.send(message, app=app)
