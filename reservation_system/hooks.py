from . import __version__ as app_version

app_name = "reservation_system"
app_title = "Reservation System"
app_publisher = "ajay patole"
app_description = "Reserve Qty"
app_email = "ajaypatole@dhupargroup.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/reservation_system/css/reservation_system.css"
# app_include_js = "/assets/reservation_system/js/reservation_system.js"

# include js, css files in header of web template
# web_include_css = "/assets/reservation_system/css/reservation_system.css"
# web_include_js = "/assets/reservation_system/js/reservation_system.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "reservation_system/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

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
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "reservation_system.utils.jinja_methods",
#	"filters": "reservation_system.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "reservation_system.install.before_install"
# after_install = "reservation_system.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "reservation_system.uninstall.before_uninstall"
# after_uninstall = "reservation_system.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "reservation_system.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Stock Ledger Entry": {
		"on_submit": "reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.update_delivered_qty",
	},

	"Purchase Receipt": {
		"on_cancel": "reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.recalculate_reserve_qty_for_pr",
	},

	"Delivery Note": {
		"on_cancel": "reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.recalculate_reserve_qty_for_dn",
	},
	
	"Stock Entry": {
		"on_cancel": "reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.recalculate_reserve_qty_for_stock_entry",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
#	"all": [
#		"reservation_system.tasks.all"
#	],
#	"daily": [
#		"reservation_system.tasks.daily"
#	],
#	"hourly": [
#		"reservation_system.tasks.hourly"
#	],
#	"weekly": [
#		"reservation_system.tasks.weekly"
#	],
#	"monthly": [
#		"reservation_system.tasks.monthly"
#	],
# }

# Testing
# -------

# before_tests = "reservation_system.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "reservation_system.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "reservation_system.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"reservation_system.auth.validate"
# ]
