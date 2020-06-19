# -*- coding: utf-8 -*-
import frappe
from toolz.curried import merge, groupby, valmap, compose, concat, map, filter

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
    return merge(
        pick(["name", "sales_partner_name"], doc.as_dict()),
        {"can_register_messaging": True},
    )


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

    if frappe.db.exists("Sales Partner", {"le_firebase_uid": uid}):
        frappe.throw(frappe._("Partner already registered"))

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


@frappe.whitelist(allow_guest=True)
@handle_error
def get_job_list(token, page="1", page_length="10", status=None):
    decoded_token = get_decoded_token(token)
    partner_id = frappe.db.exists(
        "Sales Partner", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not partner_id:
        frappe.throw(frappe._("Sales Partner does not exist on backend"))

    get_conditions = compose(lambda x: " AND ".join(x), filter(None))
    conditions = get_conditions(
        [
            "dn.docstatus < 2",
            "dn.sales_partner = %(sales_partner)s",
            "dn.workflow_state = %(workflow_state)s" if status else None,
        ]
    )

    get_count = compose(
        lambda x: x[0][0],
        lambda x: frappe.db.sql(
            """
                SELECT COUNT(dn.name) FROM `tabDelivery Note` AS dn
                WHERE {conditions}
            """.format(
                conditions=conditions
            ),
            values={"sales_partner": x, "workflow_state": status},
        ),
    )

    delivery_notes = frappe.db.sql(
        """
            SELECT
                dn.name,
                dn.le_scheduled_datetime AS scheduled_datetime,
                TIMESTAMP(dn.posting_date, dn.posting_time) AS posting_datetime,
                dn.customer,
                dn.customer_name,
                dn.shipping_address_name,
                dn.customer_address,
                dni.against_sales_order AS order_name,
                dn.rounded_total AS total,
                dn.workflow_state AS status
            FROM `tabDelivery Note` AS dn
            LEFT JOIN `tabDelivery Note Item` AS dni ON
                dni.parent = dn.name
            WHERE {conditions}
            GROUP BY dn.name
            ORDER BY dn.le_scheduled_datetime DESC, dn.creation DESC
            LIMIT %(start)s, %(page_length)s
        """.format(
            conditions=conditions
        ),
        values={
            "sales_partner": partner_id,
            "workflow_state": status,
            "start": (frappe.utils.cint(page) - 1) * frappe.utils.cint(page_length),
            "page_length": frappe.utils.cint(page_length),
        },
        as_dict=1,
    )
    items = (
        compose(
            groupby("parent"),
            lambda names: frappe.db.sql(
                """
                    SELECT
                        dni.parent AS parent,
                        dni.item_code AS item_code,
                        dni.item_name AS item_name,
                        dni.item_group AS item_group,
                        i.thumbnail AS image,
                        dni.amount AS amount
                    FROM `tabDelivery Note Item` AS dni
                    LEFT JOIN `tabItem` AS i ON i.name = dni.item_code
                    WHERE dni.parent IN %(parents)s
                """,
                values={"parents": names},
                as_dict=1,
            ),
            list,
            map(lambda x: x.get("name")),
        )(delivery_notes)
        if delivery_notes
        else {}
    )
    addresses = compose(
        valmap(lambda x: x[0]),
        groupby("name"),
        lambda names: frappe.db.sql(
            """
                    SELECT name, address_line1, address_line2, city, state, country, pincode
                    FROM `tabAddress`
                    WHERE name IN %(names)s
                """,
            values={"names": names},
            as_dict=1,
        )
        if names
        else [],
        list,
        filter(None),
        concat,
        map(lambda x: [x.get("shipping_address_name"), x.get("customer_address")]),
    )(delivery_notes)
    return {
        "count": get_count(partner_id),
        "items": [
            merge(
                pick(
                    [
                        "name",
                        "customer",
                        "customer_name",
                        "order_name",
                        "posting_datetime",
                        "scheduled_datetime",
                        "total",
                        "status",
                    ],
                    x,
                ),
                {
                    "items": items.get(x.get("name"), []),
                    "address": addresses.get(
                        x.get("shipping_address_name") or x.get("customer_address")
                    ),
                },
            )
            for x in delivery_notes
        ],
    }


@frappe.whitelist(allow_guest=True)
@handle_error
def act_on_job(token, note_name, action, posting_datetime=None):
    decoded_token = get_decoded_token(token)
    partner_id = frappe.db.exists(
        "Sales Partner", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not partner_id:
        frappe.throw(frappe._("Partner does not exist on backend"))

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))

    frappe.set_user(settings.user)
    doc = frappe.get_doc("Delivery Note", note_name)
    if not doc:
        frappe.throw(frappe._("Document #{} does not exists".format(note_name)))
    if doc.workflow_state != "Pending":
        frappe.throw(
            frappe._("Action cannot be performed on document #{}".format(note_name))
        )

    frappe.model.workflow.apply_workflow(doc, action)
    frappe.set_user(session_user)
    return merge(
        pick(["name", "posting_date", "posting_time"], doc.as_dict()),
        {"status": doc.workflow_state},
    )
