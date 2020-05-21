async function assign_technician(frm) {
  frappe.dom.freeze();
  const { message: items_to_assign = [] } = await frappe.call({
    method: 'leiteng.api.sales_order.get_items_to_assign',
    args: {
      doc_name: frm.doc.name,
    },
  });
  const items = frm.doc.items
    .filter(({ name }) => items_to_assign.includes(name))
    .map(({ name, item_code, item_name }) => ({
      item_code,
      item_name,
      scheduled_date: frm.doc.delivery_date,
      scheduled_time: frm.doc.le_delivery_time,
      so_detail: name,
    }));
  frappe.dom.unfreeze();

  if (items.length === 0) {
    frappe.msgprint(__('No more items to assign'));
    return;
  }

  const dialog = new frappe.ui.Dialog({
    title: 'Assign Technicians',
    fields: [
      {
        label: 'Service Items',
        fieldname: 'items',
        fieldtype: 'Table',
        fields: [
          {
            label: 'Item Code',
            fieldname: 'item_code',
            fieldtype: 'Link',
            options: 'Item',
            read_only: 1,
            reqd: 1,
          },
          {
            label: 'Item Name',
            fieldname: 'item_name',
            fieldtype: 'Data',
            read_only: 1,
            in_list_view: 1,
          },
          {
            label: 'Service Date',
            fieldname: 'scheduled_date',
            fieldtype: 'Date',
            in_list_view: 1,
            reqd: 1,
          },
          {
            label: 'Service Time',
            fieldname: 'scheduled_time',
            fieldtype: 'Time',
            in_list_view: 1,
            reqd: 1,
          },
          {
            label: 'Technician',
            fieldname: 'sales_partner',
            fieldtype: 'Link',
            options: 'Sales Partner',
            in_list_view: 1,
            reqd: 1,
          },
          { fieldname: 'so_detail', fieldtype: 'Data', hidden: 1 },
        ],
        in_place_edit: true,
        cannot_add_rows: true,
        data: items,
        get_data: () => items,
      },
    ],
  });

  dialog.onhide = () => {
    dialog.$wrapper.remove();
    frappe.dom.unfreeze();
  };

  dialog.set_primary_action('OK', async function () {
    const { items } = dialog.get_values();
    if (
      items.filter(
        (x) => !x.scheduled_date || !x.scheduled_time || !x.sales_partner
      ).length > 0
    ) {
      frappe.throw(
        __(
          'Please fill all required fields. Remove rows if not assigning technicians.'
        )
      );
    }
    const { message: delivery_notes = [] } = await frappe.call({
      method: 'leiteng.api.sales_order.assign_technicians',
      args: {
        doc_name: frm.doc.name,
        items_str: JSON.stringify(
          items.map((x) => ({
            so_detail: x.so_detail,
            sales_partner: x.sales_partner,
            scheduled_datetime: frappe.datetime.get_datetime_as_string(
              new Date(`${x.scheduled_date} ${x.scheduled_time}`)
            ),
          }))
        ),
      },
    });
    delivery_notes.forEach((x) => {
      frappe.show_alert(
        { message: `Created Delivery Note: ${x}`, indicator: 'green' },
        5
      );
    });
    dialog.hide();
    frm.dashboard.refresh();
  });

  dialog.show();
}

export default function sales_order() {
  return {
    refresh: function (frm) {
      frm.add_custom_button('Assign Technicians', () => assign_technician(frm));
    },
  };
}
