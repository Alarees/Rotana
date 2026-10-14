# -*- coding: utf-8 -*-
"""مصدر بيانات داشبورد النقل (الرحلات + الحسابات التحليلية).

- صفحة الرحلات: لمدير النقل.
- صفحة الحسابات: لمجموعة المحاسبة الافتراضية (account.group_account_user).
الفلاتر (التاريخ/الرحلات/المركبات) تُطبَّق على الرحلات (planned_date) ثم تُشتق منها
الحسابات التحليلية، فتتسق الأرقام بين الأقسام الثلاثة.
المدين = مجموع المبالغ السالبة، الدائن = مجموع المبالغ الموجبة، الربح = الدائن - المدين.
"""
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import AccessError

TRIP_GROUP = 'rotana_transport_sale.group_rotana_transport_manager'
ACCOUNT_GROUP = 'account.group_account_user'
FLEET_GROUP = 'fleet.fleet_group_user'


class RotanaTransportDashboard(models.AbstractModel):
    _name = 'rotana.transport.dashboard'
    _description = 'داشبورد النقل'

    # ------------------------------------------------------------------
    # أدوات مساعدة
    # ------------------------------------------------------------------
    def _check_group(self, group):
        if not self.env.user.has_group(group):
            raise AccessError(_('ليست لديك صلاحية الوصول إلى هذه الصفحة.'))

    @api.model
    def _trip_domain(self, filters):
        filters = filters or {}
        domain = [('company_id', 'in', self.env.companies.ids)]
        if filters.get('date_from'):
            domain.append(('planned_date', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('planned_date', '<=', filters['date_to']))
        if filters.get('trip_ids'):
            domain.append(('id', 'in', filters['trip_ids']))
        if filters.get('vehicle_ids'):
            domain.append(('vehicle_id', 'in', filters['vehicle_ids']))
        return domain

    @api.model
    def _shortage(self, trip):
        """العجز = المنقول - المفرغ (يُحتسب فقط بعد وجود كمية مفرغة)."""
        if trip.discharged_quantity > 0:
            return trip.transported_weight - trip.discharged_quantity
        return 0.0

    @api.model
    def _currency_symbol(self):
        return self.env.company.currency_id.symbol or ''

    # ------------------------------------------------------------------
    # خيارات الفلاتر
    # ------------------------------------------------------------------
    @api.model
    def get_filter_options(self, page):
        self._check_group(TRIP_GROUP if page == 'trips' else ACCOUNT_GROUP)
        trips = self.env['rotana.transport.trip'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)], order='id desc', limit=1000)
        vehicles = self.env['fleet.vehicle'].sudo().search([], order='name')
        return {
            'trips': [{'id': t.id, 'name': t.manifest_number} for t in trips],
            'vehicles': [{'id': v.id, 'name': v.display_name} for v in vehicles],
        }

    # ------------------------------------------------------------------
    # صفحة الرحلات
    # ------------------------------------------------------------------
    @api.model
    def _trips_rows(self, filters):
        Trip = self.env['rotana.transport.trip']
        trips = Trip.search(self._trip_domain(filters), order='planned_date desc, id desc')
        states = dict(Trip._fields['state']._description_selection(self.env))
        rows = []
        for t in trips:
            rows.append({
                'res_model': 'rotana.transport.trip',
                'res_id': t.id,
                'manifest': t.manifest_number,
                'date': str(t.planned_date or ''),
                'vehicle': t.vehicle_id.display_name or '',
                'location_from': t.location_from_id.display_name or '',
                'location_to': t.location_to_id.display_name or '',
                'transported': t.transported_weight,
                'discharged': t.discharged_quantity,
                'shortage': self._shortage(t),
                'state': t.state,
                'state_label': states.get(t.state, t.state),
            })
        return rows

    @api.model
    def _trips_columns(self):
        return [
            {'key': 'manifest', 'label': _('المانيفستو'), 'type': 'text'},
            {'key': 'date', 'label': _('التاريخ'), 'type': 'text'},
            {'key': 'vehicle', 'label': _('العربة'), 'type': 'text'},
            {'key': 'location_from', 'label': _('من'), 'type': 'text'},
            {'key': 'location_to', 'label': _('إلى'), 'type': 'text'},
            {'key': 'transported', 'label': _('الوزن المنقول'), 'type': 'float'},
            {'key': 'discharged', 'label': _('الوزن المفرغ'), 'type': 'float'},
            {'key': 'shortage', 'label': _('كمية العجز'), 'type': 'shortage'},
            {'key': 'state_label', 'label': _('الحالة'), 'type': 'state'},
        ]

    @api.model
    def get_trips_data(self, filters=None):
        self._check_group(TRIP_GROUP)
        rows = self._trips_rows(filters)
        transported = sum(r['transported'] for r in rows)
        discharged = sum(r['discharged'] for r in rows)
        shortage = sum(r['shortage'] for r in rows)

        by_vehicle, by_state = {}, {}
        for r in rows:
            v = by_vehicle.setdefault(r['vehicle'], {'transported': 0.0, 'discharged': 0.0, 'shortage': 0.0})
            v['transported'] += r['transported']
            v['discharged'] += r['discharged']
            v['shortage'] += r['shortage']
            s = by_state.setdefault(r['state_label'], {'count': 0, 'state': r['state']})
            s['count'] += 1
        top = sorted(by_vehicle.items(), key=lambda kv: kv[1]['shortage'], reverse=True)[:10]
        return {
            'columns': self._trips_columns(),
            'rows': rows,
            'totals': {'transported': transported, 'discharged': discharged, 'shortage': shortage},
            'kpis': {
                'count': len(rows),
                'transported': transported,
                'discharged': discharged,
                'shortage': shortage,
                'shortage_pct': (shortage / transported * 100.0) if transported else 0.0,
            },
            'charts': {
                'vehicles': {
                    'labels': [k for k, _v in top],
                    'transported': [v['transported'] for _k, v in top],
                    'discharged': [v['discharged'] for _k, v in top],
                    'shortage': [v['shortage'] for _k, v in top],
                },
                'states': {
                    'labels': list(by_state.keys()),
                    'values': [s['count'] for s in by_state.values()],
                    'states': [s['state'] for s in by_state.values()],
                },
            },
        }

    # ------------------------------------------------------------------
    # صفحة الحسابات
    # ------------------------------------------------------------------
    @api.model
    def _accounts_sections(self, filters):
        """يرجع الأقسام الثلاثة (رحلات/مبيعات/مركبات) مبنية على السطور التحليلية."""
        Trip = self.env['rotana.transport.trip'].sudo()
        Line = self.env['account.analytic.line']
        all_trips = Trip.search(self._trip_domain(filters), order='planned_date desc, id desc')
        # الحساب التحليلي يُنشأ عند تأكيد الرحلة، فالمسودات بلا حساب (تظهر بقيم صفرية)
        trips = all_trips.filtered('account_analytic_id')
        accounts = trips.account_analytic_id

        # السطور التحليلية تحفظ الحساب في عمود خاص بالخطة الجذر للحساب (x_plan{id}_id)،
        # وليس دائماً في account_id، لذلك نجمع على أعمدة خطط هذه الحسابات.
        fnames = {plan._column_name() for plan in accounts.plan_id}
        fnames = [f for f in fnames if f in Line._fields]
        debit_map, credit_map = defaultdict(float), defaultdict(float)
        lines_count = 0
        for fname in fnames:
            domain = [(fname, 'in', accounts.ids)]
            lines_count += Line.search_count(domain)
            for acc, amount in Line._read_group(domain + [('amount', '<', 0)], [fname], ['amount:sum']):
                if acc:
                    debit_map[acc.id] += -amount
            for acc, amount in Line._read_group(domain + [('amount', '>', 0)], [fname], ['amount:sum']):
                if acc:
                    credit_map[acc.id] += amount

        def money(account_ids):
            d = sum(debit_map.get(i, 0.0) for i in account_ids)
            c = sum(credit_map.get(i, 0.0) for i in account_ids)
            return d, c, c - d

        # --- حسب الرحلة ---
        trip_rows = []
        for t in all_trips:
            acc_ids = [t.account_analytic_id.id] if t.account_analytic_id else []
            d, c, p = money(acc_ids)
            trip_rows.append({
                'res_model': 'rotana.transport.trip', 'res_id': t.id,
                'name': t.manifest_number,
                'vehicle': t.vehicle_id.display_name or '',
                'sale': t.sale_order_id.name or '',
                'debit': d, 'credit': c, 'profit': p,
            })

        # --- حسب البيع (أمر البيع المربوط بالحساب التحليلي، وإلا أمر بيع الرحلة) ---
        sales = {}
        for t in all_trips:
            so = t.account_analytic_id.sale_order_id or t.sale_order_id
            if not so:
                continue
            rec = sales.setdefault(so.id, {'so': so, 'accounts': [], 'trips': 0})
            if t.account_analytic_id:
                rec['accounts'].append(t.account_analytic_id.id)
            rec['trips'] += 1
        sale_rows = []
        for rec in sales.values():
            d, c, p = money(rec['accounts'])
            sale_rows.append({
                'res_model': 'sale.order', 'res_id': rec['so'].id,
                'name': rec['so'].name,
                'partner': rec['so'].partner_id.display_name or '',
                'trips': rec['trips'],
                'debit': d, 'credit': c, 'profit': p,
            })

        # --- حسب المركبة (خطتها التحليلية؛ حسابات رحلاتها تتبع هذه الخطة) ---
        by_vehicle = {}
        for t in all_trips:
            veh = t.vehicle_id
            if not veh:
                continue
            rec = by_vehicle.setdefault(veh.id, {'veh': veh, 'accounts': [], 'trips': 0})
            if t.account_analytic_id:
                rec['accounts'].append(t.account_analytic_id.id)
            rec['trips'] += 1
        vehicle_rows = []
        for rec in by_vehicle.values():
            d, c, p = money(rec['accounts'])
            vehicle_rows.append({
                'res_model': 'fleet.vehicle', 'res_id': rec['veh'].id,
                'name': rec['veh'].display_name,
                'plan': rec['veh'].analytic_plan_id.display_name or '',
                'trips': rec['trips'],
                'debit': d, 'credit': c, 'profit': p,
            })

        self_diag = {
            'trips': len(all_trips),
            'without_account': len(all_trips) - len(trips),
            'lines': lines_count,
        }

        def pack(rows, columns):
            rows = sorted(rows, key=lambda r: r['profit'])
            top = sorted(rows, key=lambda r: abs(r['profit']), reverse=True)[:10]
            return {
                'columns': columns,
                'rows': rows,
                'totals': {k: sum(r[k] for r in rows) for k in ('debit', 'credit', 'profit')},
                'chart': {
                    'labels': [r['name'] for r in top],
                    'debit': [r['debit'] for r in top],
                    'credit': [r['credit'] for r in top],
                    'profit': [r['profit'] for r in top],
                },
            }

        money_cols = [
            {'key': 'debit', 'label': _('إجمالي المدين'), 'type': 'float'},
            {'key': 'credit', 'label': _('إجمالي الدائن'), 'type': 'float'},
            {'key': 'profit', 'label': _('الربح'), 'type': 'profit'},
        ]
        return {
            'diagnostics': self_diag,
            'trips': pack(trip_rows, [
                {'key': 'name', 'label': _('الرحلة'), 'type': 'text'},
                {'key': 'vehicle', 'label': _('العربة'), 'type': 'text'},
                {'key': 'sale', 'label': _('أمر البيع'), 'type': 'text'},
            ] + money_cols),
            'sales': pack(sale_rows, [
                {'key': 'name', 'label': _('أمر البيع'), 'type': 'text'},
                {'key': 'partner', 'label': _('العميل'), 'type': 'text'},
                {'key': 'trips', 'label': _('عدد الرحلات'), 'type': 'int'},
            ] + money_cols),
            'vehicles': pack(vehicle_rows, [
                {'key': 'name', 'label': _('المركبة'), 'type': 'text'},
                {'key': 'plan', 'label': _('الخطة التحليلية'), 'type': 'text'},
                {'key': 'trips', 'label': _('عدد الرحلات'), 'type': 'int'},
            ] + money_cols),
        }

    @api.model
    def get_accounts_data(self, filters=None):
        self._check_group(ACCOUNT_GROUP)
        data = self._accounts_sections(filters)
        data['currency'] = self._currency_symbol()
        return data

    # ------------------------------------------------------------------
    # صفحة المركبات (حالات المركبات حسب الموقع)
    # ------------------------------------------------------------------
    @api.model
    def get_vehicles_data(self, filters=None):
        self._check_group(FLEET_GROUP)
        Vehicle = self.env['fleet.vehicle']
        # البحث بصلاحيات المستخدم، والقراءة بـ sudo لأن مستخدم الأسطول قد لا يملك قراءة المواقع
        vehicles = Vehicle.search([], order='unit_number, id').sudo()
        states = Vehicle._fields['readyness_state']._description_selection(self.env)
        state_labels = dict(states)

        rows, locations = [], {}
        for v in vehicles:
            loc = v.current_location_id
            loc_id = loc.id or 0
            rows.append({
                'res_model': 'fleet.vehicle',
                'res_id': v.id,
                'unit_number': v.unit_number or '',
                'name': v.display_name,
                'license_plate': v.license_plate or '',
                'driver': v.driver_id.display_name or '',
                'state': v.readyness_state,
                'state_label': state_labels.get(v.readyness_state, v.readyness_state or ''),
                'location_id': loc_id,
            })
            rec = locations.setdefault(loc_id, {
                'id': loc_id,
                'name': loc.name if loc else _('بدون موقع'),
                'total': 0,
                'states': {},
            })
            rec['total'] += 1
            rec['states'][v.readyness_state] = rec['states'].get(v.readyness_state, 0) + 1

        counts = {key: 0 for key, _label in states}
        for r in rows:
            counts[r['state']] = counts.get(r['state'], 0) + 1
        loc_list = sorted(locations.values(), key=lambda x: (x['id'] == 0, -x['total'], x['name']))
        return {
            'total': len(rows),
            'states': [{'key': k, 'label': l, 'count': counts.get(k, 0)} for k, l in states],
            'locations': loc_list,
            'rows': rows,
        }

    # ------------------------------------------------------------------
    # التصدير (Excel / PDF)
    # ------------------------------------------------------------------
    @api.model
    def get_export_table(self, section, filters=None):
        """جدول جاهز للتصدير: عناوين وأنواع وصفوف وصف الإجمالي."""
        filters = filters or {}
        if section == 'trips':
            self._check_group(TRIP_GROUP)
            data = self.get_trips_data(filters)
            title = _('داشبورد النقل - الرحلات')
        elif section in ('acc_trips', 'acc_sales', 'acc_vehicles'):
            self._check_group(ACCOUNT_GROUP)
            key = section.split('_', 1)[1]
            data = self._accounts_sections(filters)[key]
            title = {
                'trips': _('داشبورد النقل - حسابات الرحلات'),
                'sales': _('داشبورد النقل - حسابات المبيعات'),
                'vehicles': _('داشبورد النقل - حسابات المركبات'),
            }[key]
        else:
            raise AccessError(_('قسم غير معروف.'))

        columns = data['columns']
        rows = [[r.get(c['key']) for c in columns] for r in data['rows']]
        totals = data['totals']
        total_row = None
        if totals:
            total_row = [(_('الإجمالي') if i == 0 else totals.get(c['key'], '')) for i, c in enumerate(columns)]
        parts = []
        if filters.get('date_from'):
            parts.append(_('من تاريخ: %s', filters['date_from']))
        if filters.get('date_to'):
            parts.append(_('إلى تاريخ: %s', filters['date_to']))
        return {
            'title': title,
            'columns': [c['label'] for c in columns],
            'types': [c['type'] for c in columns],
            'rows': rows,
            'total_row': total_row,
            'filters_text': ' | '.join(parts),
        }


class ReportRotanaTransportDashboard(models.AbstractModel):
    _name = 'report.rotana_transport_sale.report_dashboard'
    _description = 'تقرير PDF لداشبورد النقل'

    @api.model
    def _get_report_values(self, docids, data=None):
        table = (data or {}).get('table') or {}
        types = table.get('types', [])

        def fmt(value, ctype):
            if isinstance(value, float) or ctype in ('float', 'shortage', 'profit'):
                return '{:,.2f}'.format(value or 0.0)
            return '' if value in (None, False) else str(value)

        rows = [[fmt(v, types[i]) for i, v in enumerate(r)] for r in table.get('rows', [])]
        total_row = table.get('total_row')
        if total_row:
            total_row = [fmt(v, types[i]) if i else v for i, v in enumerate(total_row)]
        return {
            'doc_ids': docids,
            'doc_model': 'rotana.transport.dashboard',
            'docs': [],
            'title': table.get('title', ''),
            'filters_text': table.get('filters_text', ''),
            'columns': table.get('columns', []),
            'rows': rows,
            'total_row': total_row,
        }
