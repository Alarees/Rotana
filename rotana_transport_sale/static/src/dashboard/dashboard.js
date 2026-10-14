/** @odoo-module **/
import { Component, onWillStart, useEffect, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { download } from "@web/core/network/download";

const MODEL = "rotana.transport.dashboard";
const PALETTE = {
    primary: "#3949AB",
    teal: "#00897B",
    amber: "#FFB300",
    red: "#E53935",
    green: "#43A047",
    grey: "#78909C",
};
const STATE_COLORS = {
    draft: PALETTE.grey,
    confirmed: PALETTE.primary,
    in_transit: PALETTE.amber,
    done: PALETTE.green,
};
const NF = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const NI = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export class RotanaTransportDashboard extends Component {
    static template = "rotana_transport_sale.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        const params = (this.props.action && this.props.action.params) || {};
        this.page = params.page || "trips";
        this.charts = {};
        this.state = useState({
            loading: true,
            data: null,
            sub: "trips", // قسم الحسابات: trips | sales | vehicles
            open: null, // القائمة المنسدلة المفتوحة
            search: "",
            options: { trips: [], vehicles: [] },
            filters: { date_from: "", date_to: "", trip_ids: [], vehicle_ids: [] },
        });
        this.subTabs = [
            { key: "trips", label: "الرحلات", icon: "fa-road" },
            { key: "sales", label: "المبيعات", icon: "fa-shopping-cart" },
            { key: "vehicles", label: "المركبات", icon: "fa-truck" },
        ];
        this.multiFilters = [
            { key: "trip_ids", optKey: "trips", label: "الرحلات" },
            { key: "vehicle_ids", optKey: "vehicles", label: "المركبات" },
        ];

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            this.state.options = await this.orm.call(MODEL, "get_filter_options", [this.page]);
            await this.load();
        });
        useEffect(
            () => this.drawCharts(),
            () => [this.state.data, this.state.sub, this.state.loading]
        );
    }

    // ---------------- بيانات ----------------
    cleanFilters() {
        const f = this.state.filters;
        return {
            date_from: f.date_from || false,
            date_to: f.date_to || false,
            trip_ids: [...f.trip_ids],
            vehicle_ids: [...f.vehicle_ids],
        };
    }

    async load() {
        this.state.loading = true;
        const method = this.page === "trips" ? "get_trips_data" : "get_accounts_data";
        this.state.data = await this.orm.call(MODEL, method, [this.cleanFilters()]);
        this.state.loading = false;
    }

    onDateChange(key, ev) {
        this.state.filters[key] = ev.target.value;
        this.load();
    }

    resetFilters() {
        Object.assign(this.state.filters, { date_from: "", date_to: "", trip_ids: [], vehicle_ids: [] });
        this.load();
    }

    get hasFilters() {
        const f = this.state.filters;
        return !!(f.date_from || f.date_to || f.trip_ids.length || f.vehicle_ids.length);
    }

    // ---------------- فلاتر متعددة الاختيار ----------------
    toggleDropdown(key) {
        this.state.open = this.state.open === key ? null : key;
        this.state.search = "";
    }

    closeDropdown() {
        this.state.open = null;
    }

    onSearch(ev) {
        this.state.search = ev.target.value;
    }

    optionsFor(mf) {
        const q = this.state.search.trim().toLowerCase();
        const list = this.state.options[mf.optKey];
        return q ? list.filter((o) => o.name.toLowerCase().includes(q)) : list;
    }

    isSelected(mf, id) {
        return this.state.filters[mf.key].includes(id);
    }

    toggleOption(mf, id) {
        const list = this.state.filters[mf.key];
        const idx = list.indexOf(id);
        if (idx >= 0) {
            list.splice(idx, 1);
        } else {
            list.push(id);
        }
        this.load();
    }

    selectedOptions(mf) {
        const ids = this.state.filters[mf.key];
        return this.state.options[mf.optKey].filter((o) => ids.includes(o.id));
    }

    // ---------------- عرض ----------------
    get section() {
        return this.page === "trips" ? this.state.data : this.state.data[this.state.sub];
    }

    get currency() {
        return (this.state.data && this.state.data.currency) || "";
    }

    fmt(value) {
        return NF.format(value || 0);
    }

    fmtInt(value) {
        return NI.format(value || 0);
    }

    cellText(col, row) {
        const v = row[col.key];
        if (["float", "shortage", "profit"].includes(col.type)) {
            return this.fmt(v);
        }
        if (col.type === "int") {
            return this.fmtInt(v);
        }
        return v;
    }

    cellClass(col, row) {
        const v = row[col.key];
        if (col.type === "profit") {
            return "o_rt_num " + (v < 0 ? "o_rt_neg" : v > 0 ? "o_rt_pos" : "");
        }
        if (col.type === "shortage") {
            return "o_rt_num " + (v > 0 ? "o_rt_neg" : "");
        }
        if (["float", "int"].includes(col.type)) {
            return "o_rt_num";
        }
        return "";
    }

    totalText(col) {
        const t = this.section.totals;
        if (t && col.key in t) {
            return this.fmt(t[col.key]);
        }
        return "";
    }

    totalClass(col) {
        const t = this.section.totals;
        if (t && col.key in t) {
            const v = t[col.key];
            if (col.type === "profit") {
                return "o_rt_num " + (v < 0 ? "o_rt_neg" : "o_rt_pos");
            }
            return "o_rt_num";
        }
        return "";
    }

    openRecord(row) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: row.res_model,
            res_id: row.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------- التصدير ----------------
    exportTable(fmt) {
        const section = this.page === "trips" ? "trips" : "acc_" + this.state.sub;
        return download({
            url: `/rotana_transport/dashboard/export/${fmt}`,
            data: { section, filters: JSON.stringify(this.cleanFilters()) },
        });
    }

    // ---------------- الرسوم (Chart.js) ----------------
    destroyCharts() {
        for (const chart of Object.values(this.charts)) {
            chart.destroy();
        }
        this.charts = {};
    }

    makeChart(id, config) {
        const el = document.getElementById(id);
        if (!el || !window.Chart) {
            return;
        }
        config.options = Object.assign(
            {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", rtl: true, labels: { usePointStyle: true } } },
            },
            config.options || {}
        );
        this.charts[id] = new window.Chart(el, config);
    }

    drawCharts() {
        this.destroyCharts();
        if (this.state.loading || !this.state.data) {
            return;
        }
        if (this.page === "trips") {
            const { vehicles, states } = this.state.data.charts;
            this.makeChart("o_rt_chart_1", {
                type: "bar",
                data: {
                    labels: vehicles.labels,
                    datasets: [
                        { label: "المنقول", data: vehicles.transported, backgroundColor: PALETTE.primary, borderRadius: 4 },
                        { label: "المفرغ", data: vehicles.discharged, backgroundColor: PALETTE.teal, borderRadius: 4 },
                        { label: "العجز", data: vehicles.shortage, backgroundColor: PALETTE.red, borderRadius: 4 },
                    ],
                },
            });
            this.makeChart("o_rt_chart_2", {
                type: "doughnut",
                data: {
                    labels: states.labels,
                    datasets: [
                        {
                            data: states.values,
                            backgroundColor: states.states.map((s) => STATE_COLORS[s] || PALETTE.grey),
                        },
                    ],
                },
                options: { cutout: "62%" },
            });
        } else {
            const c = this.section.chart;
            this.makeChart("o_rt_chart_1", {
                data: {
                    labels: c.labels,
                    datasets: [
                        { type: "bar", label: "المدين", data: c.debit, backgroundColor: PALETTE.red, borderRadius: 4 },
                        { type: "bar", label: "الدائن", data: c.credit, backgroundColor: PALETTE.teal, borderRadius: 4 },
                        {
                            type: "line",
                            label: "الربح",
                            data: c.profit,
                            borderColor: PALETTE.primary,
                            backgroundColor: PALETTE.primary,
                            tension: 0.3,
                        },
                    ],
                },
            });
        }
    }
}

registry.category("actions").add("rotana_transport_dashboard", RotanaTransportDashboard);
