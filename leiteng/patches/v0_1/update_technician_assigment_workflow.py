from __future__ import unicode_literals
import frappe

from leiteng.api.workflow import setup_workflow


def execute():
    wf = setup_workflow("Technician Assignment Workflow")
    wf.save(ignore_permissions=True)
