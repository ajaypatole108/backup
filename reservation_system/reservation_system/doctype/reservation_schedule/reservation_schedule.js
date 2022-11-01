// Copyright (c) 2022, ajay patole and contributors
// For license information, please see license.txt

frappe.ui.form.on('Reservation Schedule', {
	setup: function(frm) {
		frm.set_query("so_number", function() {
			return {
				filters: [
					['Sales Order','docstatus','=',1],
					['Sales Order','customer','=',cur_frm.doc.customer],
					['Sales Order','status','=','To Deliver and Bill'],
				]
			}
		});

		frm.set_query("quotation", function() {
			return {
				filters: [
					['Quotation', 'docstatus','=',1],
					['Quotation','party_name','=',cur_frm.doc.customer],
					['Quotation','status','=','Open'],
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

// Script to populate the items when we select so_number or quotation
frappe.ui.form.on('Reservation Schedule', {
    so_number: function(frm) {
	    let so_number = frm.doc.so_number;
	    
	    if (so_number){
	        frappe.call({
	            method:'reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.get_items',
	            args:{
					so_number:so_number,
				}
	        }).done((r) => {

	           frm.doc.items = []
	           
	           $.each(r.message, function(_i, e){
				console.log(e)
				let entry = frm.add_child('items');
	               entry.item_code = e.item_code;
	               entry.item_name = e.item_name;
	               entry.qty = e.qty;
                   entry.actual_qty = e.actual_qty;
				   entry.description = e.description;
				   entry.uom = e.uom;
				   entry.rate = e.rate;
				   entry.conversion_factor = e.conversion_factor;
	           })
	           refresh_field('items')
	        })
	    }
    },

	quotation: function(frm) {
	    let quotation = frm.doc.quotation;
	    
	    if (quotation){
	        frappe.call({
	            method:'reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.get_items',
	            args:{
					quotation:quotation,
				}
	        }).done((r) => {

	           frm.doc.items = []
           
	           $.each(r.message, function(_i, e){
	               let entry = frm.add_child('items');
	               entry.item_code = e.item_code;
	               entry.item_name = e.item_name;
	               entry.qty = e.qty;
                   entry.actual_qty = e.actual_qty;
				   entry.description = e.description;
				   entry.uom = e.uom;
				   entry.rate = e.rate;
				   entry.conversion_factor = e.conversion_factor;
	           })
	           refresh_field('items')
	        })
	    }
    },
});


frappe.ui.form.on('Reservation Schedule', {
	refresh: function(frm) {
		if (frm.doc.docstatus == 1 && frm.doc.status != 'Complete' && frm.doc.status != 'Draft') {
			frm.add_custom_button(__('Delivery Note'), () => make_delivery_note(), __('Create'));
			frm.page.set_inner_btn_group_as_primary(__('Create'));
		}
	},
});

function make_delivery_note() {
	frappe.model.open_mapped_doc({
		method: "reservation_system.reservation_system.doctype.reservation_schedule.reservation_schedule.make_delivery_note",
		frm: cur_frm
	})
}



