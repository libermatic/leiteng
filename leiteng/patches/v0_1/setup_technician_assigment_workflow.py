from __future__ import unicode_literals
import frappe

from leiteng.api.workflow import setup_workflow


def execute():
    workflow_name = "Technician Assignment Workflow"
    if not frappe.db.exists("Workflow", workflow_name):
        wf = setup_workflow(workflow_name)
        wf.is_active = 1
        wf.save(ignore_permissions=True)
