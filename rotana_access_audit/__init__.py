# -*- coding: utf-8 -*-
import csv
import io
import logging

from odoo import fields

from . import models

_logger = logging.getLogger(__name__)


def uninstall_hook(env):
    """إلغاء تثبيت المديول يحذف جدول السجل نهائياً.

    قبل ذلك تُحفظ نسخة CSV كاملة كمرفق على سجل المديول (ir.module.module) ويُكتب تحذير
    في سجل الخادم. المرفق يبقى بعد الإلغاء، ويمكن تنزيله من
    الإعدادات ← تقني ← المرفقات.
    """
    Log = env['rotana.access.log'].sudo()
    fnames = ['id', 'log_date', 'actor_id', 'actor_name', 'actor_login', 'target_user_id',
              'target_user_name', 'res_model', 'res_id', 'record_name', 'operation',
              'field_label', 'old_value', 'new_value', 'description']
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(fnames)
    total, last_id = 0, 0
    while True:
        rows = Log.search_read([('id', '>', last_id)], fnames, order='id', limit=5000)
        if not rows:
            break
        for row in rows:
            writer.writerow([
                (value[0] if isinstance(value, (list, tuple)) else value) or ''
                for value in (row[f] for f in fnames)
            ])
        total += len(rows)
        last_id = rows[-1]['id']
    if not total:
        return
    module = env['ir.module.module'].sudo().search([('name', '=', 'rotana_access_audit')], limit=1)
    stamp = fields.Datetime.now().strftime('%Y%m%d_%H%M%S')
    attachment = env['ir.attachment'].sudo().create({
        'name': 'rotana_access_audit_backup_%s.csv' % stamp,
        'raw': buffer.getvalue().encode('utf-8-sig'),
        'mimetype': 'text/csv',
        'res_model': 'ir.module.module' if module else False,
        'res_id': module.id if module else 0,
    })
    _logger.warning(
        'rotana_access_audit is being uninstalled: %s log rows will be deleted. '
        'A full CSV backup was saved as attachment #%s (%s).',
        total, attachment.id, attachment.name)
