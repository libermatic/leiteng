import * as scripts from './scripts';
import * as cscripts from './cscripts';

import { get_doctype } from './cscripts/utils';

const __version__ = '0.2.1';

frappe.provide('leiteng');

leiteng = { __version__, scripts };

Object.keys(cscripts).forEach((import_name) => {
  const get_handler = cscripts[import_name];
  frappe.ui.form.on(get_doctype(import_name), get_handler());
});
