# Copyright (c) 2022, ajay patole and contributors
# For license information, please see license.txt

from ast import And
import frappe
from frappe.model.document import Document
from frappe.utils  import getdate,nowdate
from frappe.model.mapper import get_mapped_doc

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
		
	# Restricting duplicate item reservation against same so_number
	def restrict_duplicate_item_reservaton(self):
		print('------------------------------ restrict_duplicate_item_reservaton ---------------------------------------------------')
		if self.so_number:
			item_list = []
			for i in self.items:
				item_code = i.item_code
				so_number = self.so_number

				items = frappe.db.sql(f"""
										SELECT item_code, so_detail FROM `tabReservation Schedule Item`
										WHERE
										item_code = '{item_code}' AND
										so_detail = '{so_number}' AND
										(
											SELECT docstatus from `tabReservation Schedule` 
											WHERE name = `tabReservation Schedule Item`.parent
										) = 1
									""",as_dict=1)

				# This condition is define to collect all items in a list which are already reserve with same so_number	
				if len(items) != 0:
					if items[0].item_code == item_code and items[0].so_detail == so_number:
						item_list.append(items[0].item_code)
				else:
					continue

			message = f"{' - '.join(item_list)} items already reserve against the same sales order"
			
			# Again Define to print error message
			if len(items) != 0:
					if items[0].item_code == item_code and items[0].so_detail == so_number:
						frappe.throw(message)

	def reserve_qty(self):
		print('---------------------------------------------------reserve_qty------------------------------------------------------------')
		if self.so_number:
			#Pulled so_date for priority at the time of GRN
			pulled_so_date = frappe.db.sql(f"""
											SELECT creation from `tabSales Order`
											WHERE
											name = '{self.so_number}'
										""",as_dict=1)[0]
			self.so_date = pulled_so_date.creation

			for i in self.items:
				i.so_detail = self.so_number
				reserve_item(i, self.parent_warehouse)

def check_item_in_warehouse(parent_warehouse,item_code):
	data = frappe.db.sql(f"""
								SELECT item_code, SUM(actual_qty) as actual_qty
								FROM `tabBin` 
								WHERE `tabBin`.warehouse 
								IN (
									SELECT name FROM `tabWarehouse` WHERE 
									`tabWarehouse`.parent_warehouse = '{parent_warehouse}'
									)
								AND `tabBin`.item_code = '{item_code}'
							""",as_dict=1)
	print('data: ',data)
	return data

def reserve_item(item, parent_warehouse):
	print('------------------------------------------------- reserve_item ----------------------------------------------------------')
	print('item: ',item)
	actual_qty_in_wh = check_item_in_warehouse(parent_warehouse,item.item_code)[0].actual_qty
	print('actual_qty_in_wh: ',actual_qty_in_wh)

	allocated_reserve_qty = frappe.db.sql(f"""
											SELECT rsi.item_code, SUM(rsi.reserve_qty) AS reserve_qty
											FROM `tabReservation Schedule Item` AS rsi
											JOIN `tabReservation Schedule` AS rs
											ON rsi.parent = rs.name
											WHERE rsi.item_code = '{item.item_code}'
											AND
											rs.parent_warehouse = '{parent_warehouse}'
											AND
											(select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open'
										""",as_dict=1)
	print('allocated_reserve_qty : ',allocated_reserve_qty)

	if allocated_reserve_qty[0].reserve_qty == None:
		allocated_reserve_qty[0].item_code = item.item_code
		allocated_reserve_qty[0].reserve_qty = 0.0
	
	# If Delivery Note created and items delivered
	delivery_note_items = frappe.db.sql(f"""
										SELECT parent, item_code, SUM(qty) as qty ,against_sales_order from `tabDelivery Note Item`
										WHERE
										item_code = '{item.item_code}'
										AND
										against_sales_order = '{item.so_detail}'
										AND
										(
											SELECT docstatus from `tabDelivery Note`
											WHERE name = `tabDelivery Note Item`.parent
										) = 1
									""",as_dict=1)
	print('delivery_note_items: ',delivery_note_items)
	qty = delivery_note_items[0].qty # qty -> delivery note item qty
	if qty == None:
		qty = 0.0

	already_allocated = allocated_reserve_qty[0].reserve_qty
	print('already_allocated: ',already_allocated)

	new_wh_qty = actual_qty_in_wh - already_allocated
	print('new_wh_qty : ',new_wh_qty)

	if new_wh_qty > 0 :
		if new_wh_qty > item.qty:
			reserve_qty = item.qty - qty
			item.db_set('reserve_qty',reserve_qty)
		else:
			reserve_qty = new_wh_qty
			item.db_set('reserve_qty',reserve_qty)
	else:
		reserve_qty = 0
		item.db_set('reserve_qty',reserve_qty)

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

#--------------------------------------------------- Delivery Note ------------------------------------------------------
	if doc.voucher_type == 'Delivery Note':
		print('--------------------------------------------- voucher_type : Delivery Note ----------------------------------------------')
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
														so_detail = '{against_sales_order}'
														AND
														item_code = '{item_code}'
														AND
														(select status from `tabReservation Schedule` as rs WHERE rs.name = parent) = 'Open'
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
															AND
															(select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open'
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
						msg = f'{item_code} : {open_qty} qty available in warehouse to deliver'
						frappe.throw(msg)
					else:
						pass
		
#------------------------------------------------------- Purchase Receipt Items (GRN) -----------------------------------------
	if doc.voucher_type == 'Purchase Receipt':
		print('------------------------------------- voucher_type : Purchase Reciept ------------------------------------------')
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
													SELECT rsi.name, rsi.item_code, rsi.qty, rsi.reserve_qty, rsi.delivered_qty, rsi.so_detail, rs.so_date, rs.parent_warehouse
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

				new_reserve_qty = rs_qty - rs_delivered_qty
				print('new_reserve_qty: ',new_reserve_qty)

				if rs_qty != rs_reserve_qty:
					if sl_qty >= new_reserve_qty:
						if new_reserve_qty > 0:
							new_reserve = rs_reserve_qty + new_reserve_qty
							frappe.db.set_value('Reservation Schedule Item',i.name,
												'reserve_qty',new_reserve)
							sl_qty = sl_qty - new_reserve_qty
					else:
						sl_qty2 = rs_reserve_qty + sl_qty
						frappe.db.set_value('Reservation Schedule Item',i.name,
												'reserve_qty',sl_qty2)
						sl_qty = 0.0

# ------------------------------------------------------ Stock Transfer Entry ------------------------------------------------------
	if doc.voucher_type == 'Stock Entry':
		print('---------------------------------- voucher_type : Stock Transfer Entry -----------------------------------------')
		
		sle_item_code = doc.item_code
		sle_qty = doc.actual_qty
		sle_warehouse = doc.warehouse
		sle_voucher_no = doc.voucher_no

		print('se_voucher_no: ',sle_voucher_no,'se_item_code: ',sle_item_code,'se_qty: ',sle_qty,'sle_warehouse:',sle_warehouse)

		parent_warehouse_name = frappe.db.sql(f"""
												SELECT parent_warehouse FROM `tabWarehouse`
												WHERE
												name = '{sle_warehouse}'
											""",as_dict=1)[0]
		print('parent_warehouse_name: ',parent_warehouse_name)
 
		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT rsi.name, rsi.item_code, rsi.qty, rsi.reserve_qty, SUM(rsi.reserve_qty) AS sum_reserve_qty, rsi.delivered_qty, rsi.so_detail, rs.so_date
													FROM `tabReservation Schedule Item` AS rsi
													JOIN `tabReservation Schedule` As rs
													ON rsi.parent = rs.name
													WHERE
													(select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open' 
													AND item_code = '{sle_item_code}'
													AND parent_warehouse = '{parent_warehouse_name.parent_warehouse}'
													ORDER BY rs.so_date
												""",as_dict=1)
		print('reservation_schedule_doc : ',reservation_schedule_doc)

		stock_entry_detail = frappe.db.sql(f"""
											SELECT name, item_code, qty, actual_qty, s_warehouse,t_warehouse FROM `tabStock Entry Detail`
											WHERE
											parent = '{sle_voucher_no}'
										""",as_dict=1)[0]

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
					if s_parent_warehouse_name.parent_warehouse == t_parent_warehouse_name.parent_warehouse:
						frappe.msgprint('Stock Transfer Within Parent')
						print('Stock Transfer Within Parent')
					else:
						rs_qty = float(reservation_schedule_doc[0].qty)
						rs_reserve_qty = float(reservation_schedule_doc[0].reserve_qty)
						rs_delivered_qty = float(reservation_schedule_doc[0].delivered_qty)

						new_reserve_qty = rs_qty - rs_reserve_qty
						print('new_reserve_qty: ',new_reserve_qty)
						
						if rs_qty != rs_reserve_qty:
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
					print('actual_qty_in_wh: ',actual_qty_in_wh)
					print('rs_sum_reserve_qty: ',rs_sum_reserve_qty)
					print('open_qty: ',open_qty)

					if open_qty < 0 :
						open_qty = 0
						msg = f'{open_qty} qty are allowed for Transfer'
						frappe.throw(msg)
					else:
						if open_qty < -(sle_qty):
							msg = f'Only {open_qty} qty are allowed for Transfer'
							frappe.throw(msg)

# Here we Initialising the reserve_qty and delivered_qty when we cancel purchase receipt, delivery note and stock transfer entry
def initialise_reserve_and_delivered_qty(k):
	frappe.db.set_value('Reservation Schedule Item',k.name,'reserve_qty',0)
	frappe.db.set_value('Reservation Schedule Item',k.name,'delivered_qty',0)

#----------------------------------------------------------Hook on_cancel: Purchase Receipt------------------------------------------------
def recalculate_reserve_qty_for_pr(doc,event):
	print('---------------------------------- recalculate_reserve_qty_for_pr ------------------------------------------------------------')
	print('purchase receipt doc: ',doc)
	purchase_receipt_item = frappe.db.sql(f"""
											SELECT item_code, qty, 
											(
												SELECT parent_warehouse FROM `tabWarehouse`
												WHERE
												name = '{doc.set_warehouse}'
											) AS parent_warehouse
											FROM `tabPurchase Receipt Item`
											WHERE parent = '{doc.name}'
										""",as_dict=1)
	print('Purchase Reciept Item -->',purchase_receipt_item)

	for i in purchase_receipt_item:
		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT rsi.name, rsi.item_code, rsi.qty, rsi.reserve_qty, rsi.delivered_qty, rsi.so_detail, rs.so_date, rs.parent_warehouse
													FROM `tabReservation Schedule Item` AS rsi
													JOIN `tabReservation Schedule` As rs
													ON rsi.parent = rs.name
													WHERE (select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open' 
													AND item_code = '{i.item_code}'
													AND parent_warehouse = '{i.parent_warehouse}'
													ORDER BY rs.so_date
												""",as_dict=1)
		print('reservation_schedule_doc: ',reservation_schedule_doc)

		for k in reservation_schedule_doc:
			initialise_reserve_and_delivered_qty(k)

		for j in reservation_schedule_doc:
			rsi_doc = frappe.get_doc('Reservation Schedule Item',j.name)
			reserve_item(rsi_doc, j.parent_warehouse)

#---------------------------------------------------------- Hook on_cancel: Delivery Note ------------------------------------------------
def recalculate_reserve_qty_for_dn(doc,event):
	print('-------------------------------------------- recalculate_reserve_qty_for_dn_cancel ---------------------------------------------')
	def update_status(doc):
		rs = frappe.get_doc('Reservation Schedule',doc)
		flag = 1
		for i in rs.items:
			if i.delivered_qty != i.qty:
				flag = 0
		if flag == 0:
			rs.status = 'Open'

		rs.db_set('status',rs.status)

	delivery_note_all_item = frappe.db.sql(f"""
											SELECT item_code, qty, warehouse, against_sales_order,
											(
												SELECT parent_warehouse FROM `tabWarehouse`
												WHERE
												name = '{doc.set_warehouse}'
											) AS parent_warehouse
											FROM `tabDelivery Note Item`
											WHERE parent = '{doc.name}'
										""",as_dict=1)
	print('delivery_note_all_item -->',delivery_note_all_item)
		
	for i in delivery_note_all_item:
		reservation_schedule_doc = frappe.db.sql(f"""
													SELECT rsi.name, rsi.parent, rsi.item_code, rsi.qty, rsi.reserve_qty, rsi.delivered_qty, rsi.so_detail, rs.so_date, rs.parent_warehouse
													FROM `tabReservation Schedule Item` AS rsi
													JOIN `tabReservation Schedule` As rs
													ON rsi.parent = rs.name
													WHERE 
													so_detail = '{i.against_sales_order}'
													AND item_code = '{i.item_code}'
													AND parent_warehouse = '{i.parent_warehouse}'
													AND rs.status != 'cancelled'
													ORDER BY rs.so_date
												""",as_dict=1)
		print('reservation_schedule_doc: ',reservation_schedule_doc)

		for k in reservation_schedule_doc:
			initialise_reserve_and_delivered_qty(k)

		for j in reservation_schedule_doc:
			rsi_doc = frappe.get_doc('Reservation Schedule Item',j.name)
			reserve_item(rsi_doc, j.parent_warehouse)

	if len(reservation_schedule_doc) != 0:
		update_status(reservation_schedule_doc[0].parent)

#---------------------------------------------------------- Hook on_cancel: Stock Transfer Entry (STE) ------------------------------------------------
def recalculate_reserve_qty_for_stock_entry(doc,event):
	print('--------------------------------------------- recalculate_reserve_qty_for_stock_entry ---------------------------------------------------')
	stock_entry_detail = frappe.db.sql(f"""
										SELECT name, item_code, qty, actual_qty, s_warehouse,t_warehouse,
										(
											SELECT parent_warehouse FROM `tabWarehouse`
											WHERE
											name = '{doc.from_warehouse}'
										) AS parent_warehouse
										FROM `tabStock Entry Detail`
										WHERE
										parent = '{doc.name}'
									""",as_dict=1)[0]
	print('stock_entry_detail: ',stock_entry_detail)

	reservation_schedule_doc = frappe.db.sql(f"""
												SELECT rsi.name, rsi.name , rsi.item_code, rsi.qty, rsi.reserve_qty, rsi.delivered_qty, rsi.so_detail, rs.so_date, rs.parent_warehouse
												FROM `tabReservation Schedule Item` AS rsi
												JOIN `tabReservation Schedule` As rs
												ON rsi.parent = rs.name
												WHERE (select status from `tabReservation Schedule` As rs WHERE rs.name = parent) = 'Open'
												AND item_code = '{stock_entry_detail.item_code}'
												AND parent_warehouse = '{stock_entry_detail.parent_warehouse}'
												ORDER BY rs.so_date
											""",as_dict=1)
	print('reservation_schedule_doc: ',reservation_schedule_doc)

	for k in reservation_schedule_doc:
		initialise_reserve_and_delivered_qty(k)

	for j in reservation_schedule_doc:
		rsi_doc = frappe.get_doc('Reservation Schedule Item',j.name)
		reserve_item(rsi_doc, j.parent_warehouse)



# --------------------------------------- Make Reservation Schedule from Sales Order ---------------------------------------------------------
@frappe.whitelist()
def make_reservation_schedule(source_name, target_doc=None, skip_item_mapping=False):
	print('source_name: ',source_name)

	def set_missing_values(source, target):
		target.select = 'SO Number'
		target.so_posting_date = source.transaction_date
		
		target.flags.ignore_permissions = True
		target.run_method("set_missing_values")

	mapper = {
		"Sales Order": {"doctype": "Reservation Schedule", "validation": {"docstatus": ["=", 1]}},
	}
	
	mapper["Sales Order Item"] = {
			"doctype": "Reservation Schedule Item",
			"field_map": {
				"name": "so_detail",
				"parent": "against_sales_order",
			},
		}

	target_doc = get_mapped_doc("Sales Order", source_name, mapper, target_doc, set_missing_values)
	
	target_doc.set_onload("ignore_price_list", True)

	return target_doc

# ------------------------------------------- Make Delivery Note from Reservation Schedule -------------------------------------------------
@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, skip_item_mapping=False):
	print('source_name: ',source_name)

	mapper = {
		"Reservation Schedule": {"doctype": "Delivery Note", "validation": {"docstatus": ["=", 1]}},
	}

	mapper["Reservation Schedule Item"] = {
			"doctype": "Delivery Note Item",
			"field_map": {
				"name": "Reservation Schedule Item",
				"reserve_qty" : "qty",
				"so_detail": "against_sales_order",
			},
		}

	target_doc = get_mapped_doc("Reservation Schedule", source_name, mapper, target_doc)
	
	target_doc.set_onload("ignore_price_list", True)

	return target_doc
