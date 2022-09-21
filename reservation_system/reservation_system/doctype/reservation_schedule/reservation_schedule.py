# Copyright (c) 2022, ajay patole and contributors
# For license information, please see license.txt

from pydoc import doc
from turtle import update
import frappe
from frappe.model.document import Document
from frappe.utils  import getdate,nowdate

class ReservationSchedule(Document):
	
	def validate(self):
		self.check_reserve_till()
		self.reserve_qty()
		# self.set_status()

	# def set_status(self):
	# 	if self.docstatus == 1:
	# 		self.status = 'Open'

	def check_reserve_till(self):
		if self.reserve_till and (getdate(self.reserve_till) < getdate(nowdate())):
			frappe.throw("Reserve till date cannot be past date")
	
	def check_item_in_warehouse_bin(self,parent_warehouse,item_code):
		data = frappe.db.sql(f"""
								SELECT SUM(actual_qty) as actual_qty
								FROM `tabBin` 
								WHERE `tabBin`.warehouse 
								IN (
									SELECT name FROM `tabWarehouse` WHERE 
									`tabWarehouse`.parent_warehouse = '{parent_warehouse}'
									)
								AND `tabBin`.item_code = '{item_code}'
							""",as_dict=1)
		return data

	def reserve_qty(self):
		if self.so_number:
			# so_number = self.get('so_number')
			# clubed_item1 = reserve1(so_number)

			for i in self.items:
				data = self.check_item_in_warehouse_bin(self.parent_warehouse,i.item_code)[0].actual_qty
				
				if data > i.qty:
					i.reserve_qty = i.qty
				else:
					i.reserve_qty = data


# to extract items from database using so_number or quotation
@frappe.whitelist()
def get_items(**args):
	so_number = args.get('so_number')
	quotation = args.get('quotation')

	if so_number:
		items = frappe.db.sql(f"""
								SELECT * FROM `tabSales Order Item` WHERE `tabSales Order Item`.parent='{so_number}'
							""",as_dict=1)
		return items
	
	if quotation:
		items = frappe.db.sql(f"""
								SELECT * FROM `tabQuotation Item` WHERE `tabQuotation Item`.parent='{quotation}'
							""",as_dict=1)
		return items
		
def update_deliverd_qty(doc,event):
	frappe.throw('Hook Connected')