from __future__ import unicode_literals
import frappe

from leiteng.api.workflow import setup_workflow


def execute():
    if not frappe.db.exists("Custom Field", "Sales Partner-naming_series"):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Sales Partner",
                "label": "Naming series",
                "fieldname": "naming_series",
                "fieldtype": "Select",
                "options": "SP.YY.",
                "insert_after": "partner_name",
                "depends_on": "eval:doc.__islocal",
            }
        ).insert(ignore_permissions=True)
