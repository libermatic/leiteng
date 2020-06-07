export default function website_slideshow() {
  return {
    setup: function (frm) {
      frm.set_query('le_ref_doctype', 'slideshow_items', (doc) => ({
        filters: { name: ['in', ['Item Group', 'Item']] },
      }));
      frm.set_query('le_ref_docname', 'slideshow_items', (doc) => ({
        filters: { show_in_website: 1 },
      }));
    },
  };
}
