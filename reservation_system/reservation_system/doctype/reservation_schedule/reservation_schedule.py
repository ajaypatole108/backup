# Copyright (c) 2022, ajay patole and contributors
# For license information, please see license.txt

from pydoc import doc
from turtle import update
from typing_extensions import Self
import frappe
from frappe.model.document import Document
from frappe.utils  import getdate,nowdate

class ReservationSchedule(Document):
	def validate(self):
		self.check_reserve_till()
		# self.reservReservationSchedulee_qty()
		# self.restrict_duplicate_item_reservaton()
		# self.set_status()
		# self.update_status()
		flag = 1
		for i in self.items:
			if i.delivered_qty != i.qty:
				flag = 0
		if flag == 0:
			self.status = 'Open'
				
	def before_submit(self):
		self.reserve_qty()
		

	def before_save(self):
		pass

	def on_update(self):
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

	# Restricting duplicate item reservation against same so_number
	def restrict_duplicate_item_reservaton(self):
		if self.so_number:
			item_list = []
			for i in self.items:
				item_code = i.item_code
				so_number = self.so_number

				items = frappe.db.sql(f"""
										SELECT item_code, so_details FROM `tabReservation Schedule Item`
										WHERE
										item_code = '{item_code}' AND
										so_details = '{so_number}'
									""",as_dict=1)
				# This condition is define to collect all items in a list which are already reserve with same so_number	
				if len(items) != 0:
					if items[0].item_code == item_code and items[0].so_details == so_number:
						item_list.append(items[0].item_code)
				else:
					continue
			
			message = f"{' - '.join(item_list)} items already reserve against the same sales order"
			
			# Again Define to print error message
			if len(items) != 0:
					if items[0].item_code == item_code and items[0].so_details == so_number:
						frappe.throw(message)
			
	def reserve_qty(self):
		if self.so_number:
			# so_number = self.get('so_number')
			# clubed_item1 = reserve1(so_number)
			for i in self.items:
				i.so_details = self.so_number

				actual_qty_in_wh = self.check_item_in_warehouse_bin(self.parent_warehouse,i.item_code)[0].actual_qty
				print('actual_qty_in_wh: ',actual_qty_in_wh)

				allocated_reserve_qty = frappe.db.sql(f"""
														SELECT item_code, SUM(reserve_qty) as reserve_qty
														FROM `tabReservation Schedule Item`
														WHERE item_code = '{i.item_code}'
														AND
														(
															SELECT docstatus from `tabReservation Schedule` 
															WHERE name = `tabReservation Schedule Item`.parent
														) = 1
														
													""",as_dict=1)

				print('allocated_reserve_qty',allocated_reserve_qty)

				if allocated_reserve_qty[0].reserve_qty == None:
					allocated_reserve_qty[0].item_code = i.item_code
					allocated_reserve_qty[0].reserve_qty = 0.0
				
				# If Delivery Note created and items delivered
				delivery_note_items = frappe.db.sql(f"""
													SELECT item_code, SUM(qty) as qty ,against_sales_order from `tabDelivery Note Item`
													WHERE
													against_sales_order = '{self.so_number}' 
													AND
													item_code = '{i.item_code}'
												""",as_dict=1)

				against_sales_order = delivery_note_items[0].against_sales_order

				print('delivery_note_items:',delivery_note_items)
				qty = delivery_note_items[0].qty # qty -> delivery note item qty
				if qty == None:
					qty = 0.0

				already_allocated = allocated_reserve_qty[0].reserve_qty
				print(already_allocated)

				new_wh_qty = actual_qty_in_wh - already_allocated
				print('new_wh_qty : ',new_wh_qty)

				if new_wh_qty > i.qty:
					i.reserve_qty = i.qty - qty
					i.actual_qty = new_wh_qty
				else:
					i.reserve_qty = new_wh_qty
					i.actual_qty = new_wh_qty

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

# Hook -  This function update the delivered qty in reservation schedule items
def update_delivered_qty(doc,event):

	def set_status(doc_no):
		rs = frappe.get_doc('Reservation Schedule',doc_no)
		flag = 1
		
		for i in rs.items:
			print('i.qty: ',i.qty,'i.delivered_qty: ',i.delivered_qty)
			if i.qty != i.delivered_qty:
				flag = 0
			
		if flag == 1:
			rs.db_set('status','Complete')

	if doc.voucher_type == 'Delivery Note':
		delivery_note_items = frappe.db.sql(f"""
										SELECT item_code, qty, against_sales_order from `tabDelivery Note Item`
										WHERE
										parent = '{doc.voucher_no}'
										AND
										item_code = '{doc.item_code}'
									""",as_dict=1)[0]
		print('delivery_note_items:',delivery_note_items)

		item_code = doc.item_code
		dn_qty = delivery_note_items.qty
		against_sales_order = delivery_note_items.against_sales_order

		flag = 1
		if against_sales_order != None:
			reservation_schedule_items = frappe.db.sql(f"""
														SELECT name,parent,item_code, qty, delivered_qty, reserve_qty from `tabReservation Schedule Item`
														WHERE
														so_details = '{against_sales_order}' 
														AND
														item_code = '{item_code}'
														""",as_dict=1)[0]

			print('reservation_schedule_items: ',reservation_schedule_items)

			rs_qty = float(reservation_schedule_items.qty)
			rs_delivered_qty = float(reservation_schedule_items.delivered_qty)
			rs_reserve_qty = float(reservation_schedule_items.reserve_qty)

			print('rs_qty : ',rs_qty)
			print('delivered_qty: ',rs_delivered_qty)
			print('reserve_qty: ',rs_reserve_qty)
			
			if rs_delivered_qty == None:
				rs_delivered_qty = 0
			if rs_reserve_qty == None:
				rs_reserve_qty = 0

			if rs_delivered_qty < rs_qty:
				rs_delivered_qty = rs_delivered_qty + dn_qty
				rs_reserve_qty = rs_qty - rs_delivered_qty
			elif rs_delivered_qty == rs_reserve_qty:
				rs_delivered_qty = rs_qty
				rs_reserve_qty = rs_qty - rs_delivered_qty

			# Updating delivered_qty from Delivery Note item in reservation schedule
			frappe.db.set_value('Reservation Schedule Item',reservation_schedule_items.name,
								{'delivered_qty': rs_delivered_qty,'reserve_qty': rs_reserve_qty},update_modified=True)

			delivered_qty_flag = frappe.db.get_value('Reservation Schedule Item',reservation_schedule_items.name,'delivered_qty')
			print('delivered_qty_flag : ',delivered_qty_flag)

		else:
			reservation_schedule_items = frappe.db.sql(f"""
														SELECT name,item_code, qty, SUM(reserve_qty) AS reserve_qty from `tabReservation Schedule Item`
														WHERE
														item_code = '{item_code}'
														""",as_dict=1)[0]

			print('else reservation_schedule_items: ',reservation_schedule_items)

			rs_qty = float(reservation_schedule_items.qty)
			rs_reserve_qty = float(reservation_schedule_items.reserve_qty)

			item_qty_in_wh = frappe.db.sql(f"""
											SELECT actual_qty
											FROM `tabBin` 
											WHERE
											warehouse = '{doc.warehouse}'
											AND 
											item_code = '{item_code}'
											""",as_dict=1)[0]
			print('item_qty_in_wh: ',item_qty_in_wh)

			item_qty_in_wh = item_qty_in_wh.actual_qty

			if item_qty_in_wh == None:
				item_qty_in_wh = 0
			
			open_qty = item_qty_in_wh - rs_reserve_qty

			print('open_qty: ',open_qty)

			if open_qty < dn_qty:
				msg = f'{item_code} : {open_qty} qty available in warehouse'
				frappe.throw(msg)
			else:
				pass

	set_status(reservation_schedule_items.parent)
	
	# GRN items
	if doc.voucher_type == 'Purchase Receipt':
		print('Purchase Receipt Item')
		purchase_reciept_item = frappe.db.sql(f"""
												SELECT item_code, qty FROM `tabPurchase Receipt Item`
												WHERE
												parent = '{doc.voucher_no}'
												AND
												item_code = '{doc.item_code}'
											""",as_dict=1)[0]
		print('purchase_reciept_item: ',purchase_reciept_item)

		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT name,so_number from `tabReservation Schedule`
													WHERE
													status = 'Open'
												""",as_dict=1)[0]

		# reservation_schedule_doc_num = reservation_schedule_doc[0].name
		print('reservation_schedule_doc: ',reservation_schedule_doc)

		for i in purchase_reciept_item:
			item_code = purchase_reciept_item.item_code
			pr_qty = purchase_reciept_item.qty
			print('item_code : ',item_code)
			print('pr_qty : ',pr_qty)

			for j in reservation_schedule_doc:
				reservation_schedule_doc_num = reservation_schedule_doc.name
				print('reservation_schedule_doc_num: ',reservation_schedule_doc_num)

				reservation_schedule_items = frappe.db.sql(f"""
																SELECT item_code,qty,delivered_qty,reserve_qty FROM `tabReservation Schedule Item`
																WHERE
																parent = '{reservation_schedule_doc_num}' 
																AND
																item_code = '{item_code}'
																AND
																(
																	SELECT docstatus from `tabReservation Schedule` 
																	WHERE name = `tabReservation Schedule Item`.parent
																) = 1
															""",as_dict=1)[0]

				print('reservation_schedule_items:',reservation_schedule_items)

				rs_qty = float(reservation_schedule_items.qty)
				rs_reserve_qty = float(reservation_schedule_items.reserve_qty)
				rs_delivered_qty = float(reservation_schedule_items.delivered_qty)

				new_reserve_qty = rs_qty - rs_reserve_qty
				print('new_reserve_qty: ',new_reserve_qty)

				if pr_qty > new_reserve_qty:
					if new_reserve_qty > 0 :
						frappe.db.set_value('Reservation Schedule Item',
										{'parent':reservation_schedule_doc_num, 'item_code':item_code},
										'reserve_qty',rs_qty,update_modified=True)
					else:
						continue
				elif pr_qty < new_reserve_qty:
					if new_reserve_qty > 0 :
						reserve = rs_reserve_qty + pr_qty
						frappe.db.set_value('Reservation Schedule Item',
										{'parent':reservation_schedule_doc_num, 'item_code':item_code},
										'reserve_qty',reserve,update_modified=True)
					else:
						continue
