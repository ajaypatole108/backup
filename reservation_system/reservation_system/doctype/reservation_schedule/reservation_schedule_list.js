

frappe.listview_settings['Reservation Schedule'] = {
    get_indicator: function(doc) {
        if(doc.status==="Open") {
            return [__("Open"), "orange", "status,=,Open"];
        } else if (doc.status==="Delivered") {
            return [__("Delivered"), "green", "status,=,Delivered"];
        } else if(doc.status==="Close") {
            return [__("Close"), "red", "status,=,Close"];
        }
    }
}
