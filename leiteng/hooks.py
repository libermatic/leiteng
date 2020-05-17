# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "leiteng"
app_title = "Leiteng"
app_publisher = "Libermatic"
app_description = "Leiteng Backend"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@libermatic.com"
app_license = "MIT"

fixture_owner = "leiteng@libermatic.com"
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": {"fieldname": ("like", "le_%"), "owner": fixture_owner},
    },
    {"doctype": "Property Setter", "filters": {"owner": fixture_owner}},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/leiteng/css/leiteng.css"
app_include_js = "/assets/js/leiteng.min.js"

# include js, css files in header of web template
# web_include_css = "/assets/leiteng/css/leiteng.css"
# web_include_js = "/assets/leiteng/js/leiteng.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "leiteng.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "leiteng.install.before_install"
# after_install = "leiteng.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "leiteng.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"leiteng.tasks.all"
# 	],
# 	"daily": [
# 		"leiteng.tasks.daily"
# 	],
# 	"hourly": [
# 		"leiteng.tasks.hourly"
# 	],
# 	"weekly": [
# 		"leiteng.tasks.weekly"
# 	]
# 	"monthly": [
# 		"leiteng.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "leiteng.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "leiteng.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "leiteng.task.get_dashboard_data"
# }
