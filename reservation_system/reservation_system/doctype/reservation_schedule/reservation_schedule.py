# Copyright (c) 2022, ajay patole and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils  import getdate,nowdate

class ReservationSchedule(Document):
	def validate(self):
		self.check_reserve_till()
		self.restrict_duplicate_item_reservaton()

		flag = 1
		for i in self.items:
			if i.delivered_qty != i.qty:
				flag = 0
		if flag == 0:
			self.status = 'Open'

		self.db_set('status',self.status)

	def on_cancel(self):
		self.status = 'Cancelled'
		self.db_set('status',self.status)


	def before_submit(self):
		self.reserve_qty()

	def before_save(self):
		pass

	def on_update(self):
		pass

	# Restricting to select past date
	def check_reserve_till(self):
		if self.reserve_till and (getdate(self.reserve_till) < getdate(nowdate())):
			frappe.throw("Reserve date cannot be past date")
	
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
										so_details = '{so_number}' AND
										(
											SELECT docstatus from `tabReservation Schedule` 
											WHERE name = `tabReservation Schedule Item`.parent
										) = 1
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
			
			#Pulled so_date for priority at the time of GRN
			pulled_so_date = frappe.db.sql(f"""
											SELECT creation from `tabSales Order`
											WHERE
											name = '{self.so_number}'
										""",as_dict=1)[0]
			self.so_date = pulled_so_date.creation

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
															SELECT parent_warehouse from `tabReservation Schedule` 
															WHERE name = `tabReservation Schedule Item`.parent
														) = '{self.parent_warehouse}'
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
													SELECT parent, item_code, SUM(qty) as qty ,against_sales_order from `tabDelivery Note Item`
													WHERE
													against_sales_order = '{self.so_number}'
													AND
													item_code = '{i.item_code}'
												""",as_dict=1)
				print('delivery_note_items: ',delivery_note_items)
				qty = delivery_note_items[0].qty # qty -> delivery note item qty
				if qty == None:
					qty = 0.0

				already_allocated = allocated_reserve_qty[0].reserve_qty
				print('already_allocated: ',already_allocated)

				new_wh_qty = actual_qty_in_wh - already_allocated
				print('new_wh_qty : ',new_wh_qty)

				if new_wh_qty > i.qty:
					i.reserve_qty = i.qty - qty
					print('i.qty: ',i.qty,'qty: ',qty,'i.reserve_qty: ',i.reserve_qty)
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
			if i.qty != i.delivered_qty:
				flag = 0
		if flag == 1:
			rs.db_set('status','Complete')

	if doc.voucher_type == 'Delivery Note':
		print('--------------------------------------------- voucher_type : Delivery Note --------------------------------------------------')
		delivery_note_items = frappe.db.sql(f"""
										SELECT item_code, qty, against_sales_order,warehouse from `tabDelivery Note Item`
										WHERE
										parent = '{doc.voucher_no}'
										AND
										item_code = '{doc.item_code}'
									""",as_dict=1)[0]
		# (select status from `Delivery Note` as dn WHERE dn.name = parent) != 'Cancelled'
		print('delivery_note_items:',delivery_note_items)

		item_code = doc.item_code
		dn_qty = delivery_note_items.qty
		against_sales_order = delivery_note_items.against_sales_order
		dn_warehouse = delivery_note_items.warehouse

		def set_delivered_and_reserve_qty(delivered,reserve):
				frappe.db.set_value('Reservation Schedule Item',reservation_schedule_items[0].name,
									{'delivered_qty': delivered,'reserve_qty': reserve})

		if against_sales_order != None:
			reservation_schedule_items = frappe.db.sql(f"""
														SELECT name, parent, item_code, qty, delivered_qty, reserve_qty from `tabReservation Schedule Item`
														WHERE
														so_details = '{against_sales_order}'
														AND
														item_code = '{item_code}'
														AND
														(select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open'
														""",as_dict=1)
			print('reservation_schedule_items: ',reservation_schedule_items)

			if len(reservation_schedule_items) != 0:
				rs_qty = reservation_schedule_items[0].qty
				rs_delivered_qty = reservation_schedule_items[0].delivered_qty
				rs_reserve_qty = reservation_schedule_items[0].reserve_qty

				bin_qty = frappe.db.sql(f"""
											SELECT item_code,actual_qty FROM `tabBin` WHERE
											item_code = '{item_code}'
											AND warehouse = '{dn_warehouse}'
										""",as_dict=1)
				print('Bin Qty : ', bin_qty)
				bin_qty1 = bin_qty[0].actual_qty
				bin_qty = bin_qty1

				# if rs_delivered_qty == None:
				# 	rs_delivered_qty = 0
				# if rs_reserve_qty == None:
				# 	rs_reserve_qty = 0
				# if bin_qty == None:
				# 	bin_qty = 0

				if rs_delivered_qty < rs_qty:
					rs_delivered_qty = rs_delivered_qty + dn_qty
					rs_reserve_qty = rs_qty - rs_delivered_qty

					if bin_qty >= dn_qty:
						new_reserve_qty = bin_qty - rs_delivered_qty
						bin_qty = bin_qty - rs_reserve_qty
						
						if rs_qty == rs_delivered_qty:
							new_reserve_qty = 0
							set_delivered_and_reserve_qty(rs_delivered_qty,new_reserve_qty)
						else:
							set_delivered_and_reserve_qty(rs_delivered_qty,new_reserve_qty)
					elif bin_qty == 0:
						new_reserve_qty = 0
						bin_qty = new_reserve_qty
						set_delivered_and_reserve_qty(rs_delivered_qty,new_reserve_qty)
					else:
						new_reserve_qty = rs_reserve_qty - bin_qty
						bin_qty = bin_qty - new_reserve_qty
						set_delivered_and_reserve_qty(rs_delivered_qty,new_reserve_qty)

				elif rs_delivered_qty == rs_reserve_qty:
					new_reserve_qty = rs_qty - rs_delivered_qty
					set_delivered_and_reserve_qty(rs_delivered_qty,new_reserve_qty)

				set_status(reservation_schedule_items[0].parent) # Here we updating the status
			else:
				reservation_schedule_items = frappe.db.sql(f"""
															SELECT name,item_code, qty, SUM(reserve_qty) AS reserve_qty from `tabReservation Schedule Item`
															WHERE
															item_code = '{item_code}'
															""",as_dict=1)
				print('else reservation_schedule_items: ',reservation_schedule_items)

				if reservation_schedule_items[0].item_code != None:
					rs_qty = reservation_schedule_items[0].qty
					rs_reserve_qty = reservation_schedule_items[0].reserve_qty

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

					# if item_qty_in_wh == None:
					# 	item_qty_in_wh = 0
 	
					open_qty = item_qty_in_wh - rs_reserve_qty

					if open_qty < dn_qty:
						msg = f'{item_code} : {open_qty} qty available in warehouse'
						frappe.throw(msg)
					else:
						pass
		
	#--------------------------------------------------- Purchase Receipt Items (GRN) ------------------------------------------------------
	
	if doc.voucher_type == 'Purchase Receipt':
		print('----------------------------- voucher_type : Purchase Reciept ------------------------------')
		sl_item_code = doc.item_code
		sl_qty1 = doc.actual_qty
		sl_warehouse = doc.warehouse
		sl_qty = sl_qty1

		print('sl_item_code: ',sl_item_code,'sl_qty: ',sl_qty, 'sl_warehouse: ',sl_warehouse)

		parent_warehouse_name = frappe.db.sql(f"""
												SELECT parent_warehouse FROM `tabWarehouse`
												WHERE
												name = '{sl_warehouse}'
											""",as_dict=1)[0]

		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT rsi.name, rsi.item_code, rsi.qty, rsi.reserve_qty, rsi.delivered_qty, rsi.so_details, rs.so_date, rs.parent_warehouse
													FROM `tabReservation Schedule Item` AS rsi
													JOIN `tabReservation Schedule` As rs
													ON rsi.parent = rs.name
													WHERE (select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open' 
													AND item_code = '{sl_item_code}'
													AND parent_warehouse = '{parent_warehouse_name.parent_warehouse}'
													ORDER BY rs.so_date
												""",as_dict=1)
		print('reservation_schedule_doc : ',reservation_schedule_doc)

		if len(reservation_schedule_doc) != 0:
			for i in reservation_schedule_doc:
				rs_qty = i.qty
				rs_reserve_qty = float(i.reserve_qty)
				rs_delivered_qty = i.delivered_qty

				new_reserve_qty = rs_qty - rs_reserve_qty
				print('new_reserve_qty: ',new_reserve_qty)

				if sl_qty >= new_reserve_qty :
					if new_reserve_qty > 0 :
						new_reserve = rs_reserve_qty + new_reserve_qty
						frappe.db.set_value('Reservation Schedule Item',i.name,
											'reserve_qty',new_reserve)
						sl_qty = sl_qty - new_reserve_qty
				else:
					sl_qty2 = rs_reserve_qty + sl_qty
					frappe.db.set_value('Reservation Schedule Item',i.name,
											'reserve_qty',sl_qty2)
					sl_qty = 0.0
    
	# ------------------------------------------------------ Stock Entry ------------------------------------------------------
	
	if doc.voucher_type == 'Stock Entry':
		print('---------------------------------- voucher_type : Stock Transfer Entry ---------------------------------')
		
		sle_item_code = doc.item_code
		sle_qty = doc.actual_qty
		sle_warehouse = doc.warehouse
		sle_voucher_no = doc.voucher_no

		print('se_voucher_no: ',sle_voucher_no,'se_item_code: ',sle_item_code,'se_qty: ',sle_qty,'se_warehouse:',sle_warehouse)
 
		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT rsi.name, rsi.item_code, rsi.qty, rsi.reserve_qty, SUM(rsi.reserve_qty) AS sum_reserve_qty, rsi.delivered_qty, rsi.so_details, rs.so_date
													FROM `tabReservation Schedule Item` AS rsi
													JOIN `tabReservation Schedule` As rs
													ON rsi.parent = rs.name
													WHERE
													(select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open' 
													AND item_code = '{sle_item_code}'
													ORDER BY rs.so_date
												""",as_dict=1)
		print('reservation_schedule_doc : ',reservation_schedule_doc)

		stock_entry_detail = frappe.db.sql(f"""
											SELECT name, item_code, qty, actual_qty, s_warehouse,t_warehouse FROM `tabStock Entry Detail`
											WHERE
											parent = '{sle_voucher_no}'
										""",as_dict=1)[0]
		print('stock_entry_detail: ',stock_entry_detail)

		s_parent_warehouse_name = frappe.db.sql(f"""
													SELECT parent_warehouse FROM `tabWarehouse`
													WHERE
													name = '{stock_entry_detail.s_warehouse}'
												""",as_dict=1)[0]
		
		t_parent_warehouse_name = frappe.db.sql(f"""
													SELECT parent_warehouse FROM `tabWarehouse`
													WHERE
													name = '{stock_entry_detail.t_warehouse}'
												""",as_dict=1)[0]

		# reservation_schedule_doc = pull_reservation_detail(sle_item_code)
		if sle_qty > 0:
			if len(reservation_schedule_doc) != 0: # Means There is no open reservation whose status is open
				if reservation_schedule_doc[0].item_code != None:
					if s_parent_warehouse_name == t_parent_warehouse_name:
						frappe.msgprint('Stock Transfer Within Parent')
						print('Stock Transfer Within Parent')
					else:
						rs_qty = float(reservation_schedule_doc[0].qty)
						rs_reserve_qty = float(reservation_schedule_doc[0].reserve_qty)
						rs_delivered_qty = float(reservation_schedule_doc[0].delivered_qty)

						new_reserve_qty = rs_qty - rs_reserve_qty
						print('new_reserve_qty: ',new_reserve_qty)

						if sle_qty >= new_reserve_qty:
							if new_reserve_qty > 0 :
								new_reserve = rs_reserve_qty + new_reserve_qty
								frappe.db.set_value('Reservation Schedule Item',reservation_schedule_doc[0].name,
													'reserve_qty',new_reserve)
								sle_qty = sle_qty - new_reserve_qty
						else:
							sle_qty2 = rs_reserve_qty + sle_qty
							frappe.db.set_value('Reservation Schedule Item',reservation_schedule_doc[0].name,
													'reserve_qty',sle_qty2)
							sle_qty = 0.0
		else:
			if len(reservation_schedule_doc) != 0: # Means There is no reservation whose status = open
				if reservation_schedule_doc[0].item_code != None: # if transfer item not present in reservation schedule document
					rs_qty = float(reservation_schedule_doc[0].qty)
					rs_sum_reserve_qty = float(reservation_schedule_doc[0].sum_reserve_qty)

					actual_qty_in_wh = stock_entry_detail.actual_qty					
					open_qty = actual_qty_in_wh - rs_sum_reserve_qty

					if open_qty < 0 :
						open_qty = 0
						msg = f'{open_qty} qty are allowed for Transfer'
						frappe.throw(msg)
					else:
						if open_qty < -(sle_qty):
							msg = f'Only {open_qty} qty are allowed for Transfer'
							frappe.throw(msg)