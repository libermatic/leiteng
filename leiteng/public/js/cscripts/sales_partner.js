async function get_signup_code(frm) {
  const { message: code } = await frappe.call({
    method: 'leiteng.api.sales_partner.generate_signup_code',
    args: { sales_partner_name: frm.doc.name },
  });
  frm.reload_doc();
  frappe.msgprint({
    message: `
        <p class="text-center">
            <code style="font-size: 2em;">${code}</code>
        </p>
        <p>
            Note: This code will be valid for one sign up only.
            Regenerating a new code will invalidate the previous one.
        </P
        `,
    indicator: 'green',
  });
}

export default function sales_partner() {
  return {
    refresh: function (frm) {
      if (!frm.doc.__islocal) {
        frm.add_custom_button('Generate Sign-Up Code', () =>
          get_signup_code(frm)
        );
      }
    },
  };
}
