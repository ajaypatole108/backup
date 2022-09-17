# Copyright (c) 2022, ajay patole and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils  import getdate,nowdate

class ReservationSchedule(Document):
	
	def validate(self):
		self.check_reserve_till()

	def check_reserve_till(self):
		if self.reserve_till and (getdate(self.reserve_till) < getdate(nowdate())):
			frappe.throw("Reserve till date cannot be past date")
