// Copyright (c) 2022, ajay patole and contributors
// For license information, please see license.txt

frappe.ui.form.on('Reservation Schedule', {
	setup: function(frm) {
		frm.set_query("so_number", function() {
			return {
				filters: [
					['Sales Order','docstatus','=',1],
					['Sales Order','customer','=',cur_frm.doc.customer]
				]
			}
		});

		frm.set_query("quotation", function() {
			return {
				filters: [
					['Quotation', 'docstatus','=',1],
					['Quotation','party_name','=',cur_frm.doc.party_name],
					['Quotation','status','=','Open']
				]
			}
		});

		frm.set_query('parent_warehouse', function() {
			return {
				filters: [
					['Warehouse','is_group','=',1],
				]
			}
		});
	}
});
