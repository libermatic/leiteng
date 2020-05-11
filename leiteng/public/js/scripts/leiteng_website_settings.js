export default function leiteng_website_settings() {
  return {
    setup(frm) {
      frm.set_query('item_group', 'allcat_groups', {
        filters: { show_in_website: 1 },
      });
    },
  };
}
