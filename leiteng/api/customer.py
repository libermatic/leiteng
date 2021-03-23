# -*- coding: utf-8 -*-
import frappe
import json
from firebase_admin import auth
from toolz.curried import (
    keyfilter,
    merge,
    compose,
    groupby,
    concat,
    first,
    valmap,
    map,
    filter,
)

from leiteng.app import get_decoded_token, app
from leiteng.utils import pick, handle_error


@frappe.whitelist(allow_guest=True)
@handle_error
def get(token):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        return None
    doc = frappe.get_doc("Customer", customer_id)
    orders = frappe.db.exists("Sales Order", {"customer": customer_id})
    return merge(
        pick(["name", "customer_name"], doc.as_dict()),
        {"can_register_messaging": bool(orders)},
    )


@frappe.whitelist(allow_guest=True)
@handle_error
def create(token, **kwargs):
    decoded_token = get_decoded_token(token)
    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    uid = decoded_token["uid"]
    customer_id = frappe.db.exists("Customer", {"le_firebase_uid": uid})
    if customer_id:
        frappe.throw(frappe._("Customer already created"))

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

    doc = frappe.get_doc(
        merge(
            {
                "doctype": "Customer",
                "le_firebase_uid": uid,
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
    auth.set_custom_user_claims(uid, {"customer": True}, app=app)

    frappe.set_user(session_user)
    return pick(["name", "customer_name"], doc.as_dict())


@frappe.whitelist(allow_guest=True)
@handle_error
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
@handle_error
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
@handle_error
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


@frappe.whitelist(allow_guest=True)
@handle_error
def list_orders(token, page="1", page_length="10", status=None):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    get_conditions = compose(lambda x: " AND ".join(x), filter(None))
    conditions = get_conditions(
        [
            "docstatus = 1",
            "customer = %(customer)s",
            "status IN %(statuses)s" if status else None,
        ]
    )

    statuses = json.loads(status) if status else None

    get_count = compose(
        lambda x: x[0][0],
        lambda x: frappe.db.sql(
            """
                SELECT COUNT(name) FROM `tabSales Order`
                WHERE {conditions}
            """.format(
                conditions=conditions
            ),
            values={"customer": x, "statuses": statuses},
        ),
    )

    orders = frappe.db.sql(
        """
            SELECT
                name, transaction_date, status,
                total, total_taxes_and_charges, grand_total, rounding_adjustment, rounded_total
            FROM `tabSales Order`
            WHERE {conditions}
            ORDER BY transaction_date DESC, creation DESC
            LIMIT %(start)s, %(page_length)s
        """.format(
            conditions=conditions
        ),
        values={
            "customer": customer_id,
            "statuses": statuses,
            "start": (frappe.utils.cint(page) - 1) * frappe.utils.cint(page_length),
            "page_length": frappe.utils.cint(page_length),
        },
        as_dict=1,
    )
    items = (
        groupby(
            "parent",
            frappe.db.sql(
                """
                    SELECT parent, name, item_code, item_name, item_group, qty, rate, amount
                    FROM `tabSales Order Item`
                    WHERE parent IN %(parents)s
                """,
                values={"parents": [x.get("name") for x in orders]},
                as_dict=1,
            ),
        )
        if orders
        else {}
    )

    return {
        "count": get_count(customer_id),
        "items": [merge(x, {"items": items.get(x.get("name"), [])}) for x in orders],
    }


@frappe.whitelist(allow_guest=True)
@handle_error
def get_notes(token, so_name):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))

    if customer_id != frappe.db.get_value("Sales Order", so_name, "customer"):
        frappe.throw(frappe._("Not allowed to view this document"))

    get_dn_fields = compose(
        keyfilter(
            lambda x: x
            in [
                "name",
                "partner",
                "partner_name",
                "scheduled_datetime",
                "posting_datetime",
                "total",
                "total_taxes_and_charges",
                "grand_total",
                "rounding_adjustment",
                "rounded_total",
                "status",
            ]
        ),
        first,
    )
    get_item_fields = compose(
        list,
        map(
            keyfilter(
                lambda x: x
                in [
                    "name",
                    "item_code",
                    "item_name",
                    "item_group",
                    "rate",
                    "amount",
                    "so_detail",
                ]
            )
        ),
        map(lambda x: merge(x, {"name": x.get("child_name")})),
    )

    get_deliveries = compose(
        lambda x: x.values(),
        valmap(lambda x: merge(get_dn_fields(x), {"items": get_item_fields(x)})),
        groupby("name"),
        lambda x: frappe.db.sql(
            """
                SELECT
                    dn.name,
                    dn.sales_partner AS partner,
                    sp.partner_name,
                    dn.le_scheduled_datetime AS scheduled_datetime,
                    TIMESTAMP(dn.posting_date, dn.posting_time) AS posting_datetime,
                    dn.total,
                    dn.total_taxes_and_charges,
                    dn.grand_total,
                    dn.rounding_adjustment,
                    dn.rounded_total,
                    dn.workflow_state AS status,
                    dni.name AS child_name,
                    dni.item_code,
                    dni.item_name,
                    dni.item_group,
                    dni.qty,
                    dni.rate,
                    dni.amount,
                    dni.so_detail
                FROM `tabDelivery Note Item` AS dni
                LEFT JOIN `tabDelivery Note` AS dn ON dn.name = dni.parent
                LEFT JOIN `tabSales Partner` AS sp ON sp.name = dn.sales_partner
                WHERE
                    dn.status < 2 AND
                    dn.workflow_state IN ('Pending', 'Completed') AND
                    dni.against_sales_order = %(against_sales_order)s
            """,
            values={"against_sales_order": x},
            as_dict=1,
        ),
    )
    return get_deliveries(so_name)


@frappe.whitelist(allow_guest=True)
@handle_error
def make_order(token, **kwargs):
    customer_id = _get_customer_id(token)

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    doc = _make_sales_order(customer_id, **kwargs)
    doc.calculate_taxes_and_totals()
    frappe.set_user(session_user)
    return _get_formatted_sales_order(doc)


@frappe.whitelist(allow_guest=True)
@handle_error
def create_order(token, **kwargs):
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

    doc = _make_sales_order(customer_id, **kwargs)
    doc.insert()
    doc.submit()
    frappe.set_user(session_user)
    return _get_formatted_sales_order(doc)


@frappe.whitelist(allow_guest=True)
@handle_error
def create_messaging_registration(token, registration_token):
    customer_id = _get_customer_id(token)

    session_user = frappe.session.user
    settings = frappe.get_single("Leiteng Website Settings")
    if not settings.user:
        frappe.throw(frappe._("Site setup not complete"))
    frappe.set_user(settings.user)

    frappe.db.set_value("Customer", customer_id, "le_fcm_token", registration_token)

    frappe.set_user(session_user)


@frappe.whitelist(allow_guest=True)
@handle_error
def remove_messaging_registration(token):
    create_messaging_registration(token, None)


def _make_sales_order(customer_id, **kwargs):
    args = pick(["transaction_date", "delivery_date", "customer_address"], kwargs)

    doc = frappe.get_doc(
        merge(
            {
                "doctype": "Sales Order",
                "customer": customer_id,
                "order_type": "Shopping Cart",
                "company": frappe.defaults.get_user_default("company"),
                "currency": frappe.defaults.get_user_default("currency"),
                "selling_price_list": frappe.db.get_single_value(
                    "Selling Settings", "selling_price_list"
                ),
            },
            args,
            {"le_delivery_time": kwargs.get("delivery_time")},
        )
    )

    warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    for item_args in json.loads(kwargs.get("items", "[]")):
        doc.append(
            "items",
            merge(
                pick(["item_code", "qty", "rate"], item_args),
                {
                    "warehouse": warehouse,
                    "uom": frappe.db.get_value(
                        "Item", item_args.get("item_code"), "stock_uom"
                    ),
                },
            ),
        )

    doc.set_missing_values()
    return doc


def _get_formatted_sales_order(doc):
    return merge(
        pick(
            [
                "name",
                "transaction_date",
                "delivery_date",
                "total",
                "grand_total",
                "rounding_adjustment",
                "rounded_total",
            ],
            doc.as_dict(),
        ),
        {
            "delivery_time": doc.le_delivery_time,
            "items": [
                pick(
                    [
                        "item_code",
                        "item_name",
                        "item_group",
                        "qty",
                        "rate",
                        "amount",
                        "net_amount",
                    ],
                    x.as_dict(),
                )
                for x in doc.items
            ],
            "taxes": [
                pick(["description", "tax_amount"], x.as_dict()) for x in doc.taxes
            ],
        },
    )


def _get_customer_id(token):
    decoded_token = get_decoded_token(token)
    customer_id = frappe.db.exists(
        "Customer", {"le_firebase_uid": decoded_token["uid"]}
    )
    if not customer_id:
        frappe.throw(frappe._("Customer does not exist on backend"))
    return customer_id
