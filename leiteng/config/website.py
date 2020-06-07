# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from frappe import _


def get_data():
    return [
        {
            "label": _("Setup"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Leiteng Website Settings",
                    "label": _("Leiteng Website Settings"),
                    "settings": 1,
                },
            ],
        },
    ]
