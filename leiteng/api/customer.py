# -*- coding: utf-8 -*-
import frappe
from toolz import keyfilter, merge, compose

from leiteng.app import get_decoded_token
from leiteng.utils import pick


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


@frappe.whitelist(allow_guest=True)
def list_addresses(token, page="1", page_length="10"):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    get_count = compose(
        lambda x: x[0][0],
        lambda x: frappe.db.sql(
            """
                SELECT COUNT(name) FROM `tabDynamic Link` WHERE
                    parenttype = 'Address' AND
                    link_doctype = 'Customer' AND
                    link_name = %(link_name)s
            """,
            values={"link_name": x},
        ),
    )
    addresses = frappe.db.sql(
        """
            SELECT
                a.name AS name,
                a.address_line1 AS address_line1,
                a.address_line2 AS address_line2,
                a.city AS city,
                a.state AS state,
                a.country AS country,
                a.pincode AS pincode
            FROM `tabDynamic Link` AS dl
            LEFT JOIN `tabAddress` AS a ON a.name = dl.parent
            WHERE dl.parenttype = 'Address' AND
                dl.link_doctype = 'Customer' AND
                dl.link_name = %(link_name)s
            GROUP BY a.name
            ORDER BY a.modified DESC
            LIMIT %(start)s, %(page_length)s
        """,
        values={
            "link_name": customer_id,
            "start": (frappe.utils.cint(page) - 1) * frappe.utils.cint(page_length),
            "page_length": frappe.utils.cint(page_length),
        },
        as_dict=1,
    )
    return {
        "count": get_count(customer_id),
        "items": addresses,
    }


@frappe.whitelist(allow_guest=True)
def create_address(token, **kwargs):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    fields = ["address_line1", "address_line2", "city", "state", "country", "pincode"]

    args = pick(fields, kwargs,)
    doc = frappe.get_doc(
        merge({"doctype": "Address", "address_type": "Billing"}, args,)
    )
    doc.append("links", {"link_doctype": "Customer", "link_name": customer_id})
    doc.insert()
    frappe.set_user(session_user)
    return pick(["name"] + fields, doc.as_dict())


@frappe.whitelist(allow_guest=True)
def delete_address(token, name):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    frappe.delete_doc_if_exists("Address", name)

    frappe.set_user(session_user)
    return None
