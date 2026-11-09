# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

OPERATIONS = [
    ('create', 'إنشاء'),
    ('write', 'تعديل'),
    ('unlink', 'حذف'),
    ('group_add', 'إضافة إلى مجموعة'),
    ('group_remove', 'إزالة من مجموعة'),
]

LABELS = {
    'login': 'اسم الدخول',
    'active': 'نشط',
    'company_id': 'الشركة الحالية',
    'company_ids': 'الشركات المسموحة',
    'group_ids': 'المجموعات',
    'groups': 'المجموعات',
    'implied_ids': 'المجموعات المضمّنة',
    'name': 'الاسم',
    'model_id': 'الموديل',
    'group_id': 'المجموعة',
    'domain_force': 'النطاق (Domain)',
    'perm_read': 'قراءة',
    'perm_write': 'كتابة',
    'perm_create': 'إنشاء',
    'perm_unlink': 'حذف',
}


class RotanaAccessLog(models.Model):
    _name = 'rotana.access.log'
    _description = 'سجل تغييرات الصلاحيات'
    _order = 'log_date desc, id desc'
    _rec_name = 'description'

    log_date = fields.Datetime('التاريخ', default=fields.Datetime.now, readonly=True, index=True)
    actor_id = fields.Many2one('res.users', 'المنفّذ', readonly=True, index=True)
    actor_name = fields.Char('اسم المنفّذ', readonly=True)
    actor_login = fields.Char('دخول المنفّذ', readonly=True)
    target_user_id = fields.Many2one('res.users', 'المستخدم المتأثر', readonly=True, index=True)
    target_user_name = fields.Char('اسم المستخدم المتأثر', readonly=True)
    res_model = fields.Char('الموديل', readonly=True, index=True)
    res_id = fields.Integer('رقم السجل', readonly=True)
    record_name = fields.Char('السجل', readonly=True)
    operation = fields.Selection(OPERATIONS, 'العملية', readonly=True, index=True)
    field_label = fields.Char('الحقل', readonly=True)
    old_value = fields.Text('القيمة قبل', readonly=True)
    new_value = fields.Text('القيمة بعد', readonly=True)
    description = fields.Char('الوصف', readonly=True)

    # السجل دائم: لا تعديل ولا حذف لأي مستخدم
    def write(self, vals):
        raise UserError('سجل الصلاحيات للقراءة فقط ولا يمكن تعديله.')

    def unlink(self):
        raise UserError('سجل الصلاحيات دائم ولا يمكن حذفه.')

    @api.model
    def _fmt(self, value):
        if isinstance(value, (list, tuple)):
            return ', '.join(value)
        if isinstance(value, bool):
            return 'نعم' if value else 'لا'
        return str(value) if value else ''

    @api.model
    def _label(self, record, fname):
        return LABELS.get(fname) or record._fields[fname].string

    @api.model
    def _snapshot(self, records, fnames):
        """لقطة لقيم الحقول كنصوص، لمقارنتها قبل/بعد التعديل."""
        records = records.sudo()
        fnames = [f for f in fnames if f in records._fields]
        result = {}
        for rec in records:
            vals = {}
            for fname in fnames:
                field = rec._fields[fname]
                value = rec[fname]
                if field.type in ('many2one', 'one2many', 'many2many'):
                    vals[fname] = sorted(r.display_name or str(r.id) for r in value)
                elif field.type == 'boolean':
                    vals[fname] = bool(value)
                else:
                    vals[fname] = value or ''
            result[rec.id] = vals
        return result

    @api.model
    def _summary(self, record, fnames):
        snap = self._snapshot(record, fnames).get(record.id, {})
        parts = []
        for fname in fnames:
            if fname in snap:
                parts.append('%s: %s' % (self._label(record, fname), self._fmt(snap[fname])))
        return ' | '.join(parts)

    @api.model
    def _log(self, record, operation, description, field_label=False,
             old=False, new=False, target_user=None):
        actor = self.env.user.sudo()
        record = record.sudo()
        vals = {
            'actor_id': actor.id,
            'actor_name': actor.name,
            'actor_login': actor.login,
            'res_model': record._name,
            'res_id': record.id,
            'record_name': record.display_name,
            'operation': operation,
            'description': description,
            'field_label': field_label or False,
            'old_value': old or False,
            'new_value': new or False,
        }
        if target_user:
            vals['target_user_id'] = target_user.id
            vals['target_user_name'] = target_user.name
        self.sudo().create(vals)

    @api.model
    def _log_changes(self, records, before, fnames, target_user_of=None):
        """يسجّل الفروقات بين لقطة ما قبل التعديل والحالة الحالية."""
        after = self._snapshot(records, fnames)
        for rec in records.sudo():
            old_vals = before.get(rec.id, {})
            new_vals = after.get(rec.id, {})
            target = target_user_of(rec) if target_user_of else None
            for fname in fnames:
                if fname not in new_vals:
                    continue
                old, new = old_vals.get(fname), new_vals.get(fname)
                if old == new:
                    continue
                label = self._label(rec, fname)
                if rec._name == 'res.users' and fname == 'group_ids':
                    old_set, new_set = set(old or []), set(new or [])
                    for grp in sorted(new_set - old_set):
                        self._log(rec, 'group_add',
                                  'إضافة المستخدم %s إلى المجموعة %s' % (rec.name, grp),
                                  label, new=grp, target_user=target)
                    for grp in sorted(old_set - new_set):
                        self._log(rec, 'group_remove',
                                  'إزالة المستخدم %s من المجموعة %s' % (rec.name, grp),
                                  label, old=grp, target_user=target)
                    continue
                self._log(rec, 'write', '%s: تعديل «%s»' % (rec.display_name, label),
                          label, old=self._fmt(old), new=self._fmt(new), target_user=target)
