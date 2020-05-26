# -*- coding: utf-8 -*-
import frappe


def autoname(doc, method):
    frappe.model.naming.set_name_by_naming_series(doc)
