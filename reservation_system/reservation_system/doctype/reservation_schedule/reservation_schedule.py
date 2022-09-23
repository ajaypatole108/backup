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
		self.restrict_duplicate_item_reservaton()
	
	def before_submit(self):
		self.reserve_qty()
		
	def before_save(self):
		pass

	# Restricting to select past date
	def check_reserve_till(self):
		if self.reserve_till and (getdate(self.reserve_till) < getdate(nowdate())):
			frappe.throw("Reserve till date cannot be past date")
	
	# Checking item qty in warehouse bin
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

	# Restricting duplicate item reservation with same so_number
	def restrict_duplicate_item_reservaton(self):
		if self.so_number:
			for i in self.items:
				item_code = i.item_code
				so_number = self.so_number

				items = frappe.db.sql(f"""
										SELECT item_code, so_details FROM `tabReservation Schedule Item`
										WHERE
										item_code = '{item_code}' AND
										so_details = '{so_number}'
									""",as_dict=1)

				if items[0].item_code == item_code and items[0].so_details == so_number:
					frappe.throw('item canot be reserve twice with same so_number')

	# Reserving item qty 
	def reserve_qty(self):
		if self.so_number:
			# so_number = self.get('so_number')
			# clubed_item1 = reserve1(so_number)
			for i in self.items:
				i.so_details = self.so_number

				actual_qty_in_wh = self.check_item_in_warehouse_bin(self.parent_warehouse,i.item_code)[0].actual_qty

				allocated_reserve_qty = frappe.db.sql(f"""
														SELECT item_code, SUM(reserve_qty) as reserve_qty
														FROM `tabReservation Schedule Item`
														WHERE item_code = '{i.item_code}'
													""",as_dict=1)

				# print('Already allocated_reserve_qty : ',allocated_reserve_qty)

				if allocated_reserve_qty[0].reserve_qty == None:
					allocated_reserve_qty[0].item_code = i.item_code
					allocated_reserve_qty[0].reserve_qty = 0.0

				already_allocated = allocated_reserve_qty[0].reserve_qty

				new_wh_qty = actual_qty_in_wh - already_allocated

				if new_wh_qty > i.qty:
					i.reserve_qty = i.qty
					i.actual_qty = new_wh_qty
				elif new_wh_qty == 0.0:
					i.reserve_qty = new_wh_qty
				else:
					i.reserve_qty = new_wh_qty

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
	# extracted item_code, qty, against_sales_order from delivery Note
	delivery_note_items = frappe.db.sql(f"""
										SELECT item_code, qty, against_sales_order from `tabDelivery Note Item`
										WHERE
										`tabDelivery Note Item`.parent = '{doc.voucher_no}'
									""",as_dict=1)
	print(delivery_note_items)
								
	for i in range(len(delivery_note_items)):
		item_code = delivery_note_items[i].item_code
		qty = delivery_note_items[i].qty
		against_sales_order = delivery_note_items[i].against_sales_order

		# Checking Dilivery Note field against_sales_order is not null means it contain so number
		if against_sales_order != None:
			reservation_schedule_documents = frappe.db.sql(f"""
													SELECT name from `tabReservation Schedule`
													WHERE
													so_number = '{against_sales_order}'
												""",as_dict=1)
			print('Reservation schedule document Number: ',reservation_schedule_documents)

			rs_doc_number = reservation_schedule_documents[0].name

			# Assigining delivered_qty from Delivery Note item in reservation schedule
			frappe.db.set_value('Reservation Schedule Item',
								{'parent':rs_doc_number, 'item_code':item_code},
								'delivered_qty',qty)