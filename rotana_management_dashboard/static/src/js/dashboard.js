/** @odoo-module **/

import {
    Component,
    useState,
    useEffect,
    onWillStart,
    onMounted,
    onWillUnmount,
    onWillUpdateProps,
    useExternalListener,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

/* ------------------------------------------------------------------ config */
const AMCHARTS_BUNDLE = "/rotana_management_dashboard/static/lib/amcharts5/amcharts5.bundle.min.js";
const FONT_FAMILY = "IBM Plex Sans Arabic, Tahoma, sans-serif";
const BUS_CHANNEL = "rotana_management_dashboard";
const BUS_EVENT = "rotana_dashboard_sales_updated";
const FALLBACK_REFRESH_MS = 60000;   // تحديث احتياطي إن تعطل bus
const BUS_DEBOUNCE_MS = 1500;
const WEEK_START = 0;                // 0 = الأحد ، 6 = السبت

// الأقسام: لإضافة قسم جديد أضف عنصراً هنا ثم ابنِ محتواه في القالب (dashboard.xml)
const SECTIONS = [
    { id: "sales", label: "المبيعات", icon: "fa-line-chart" },
];

const PALETTE = [
    "#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#fb7185",
    "#60a5fa", "#f472b6", "#2dd4bf", "#fb923c", "#c084fc",
];

const PRESETS = [
    { id: "today", label: "اليوم" },
    { id: "yesterday", label: "أمس" },
    { id: "this_week", label: "هذا الأسبوع" },
    { id: "last_week", label: "الأسبوع الماضي" },
    { id: "last_30", label: "آخر 30 يوماً" },
    { id: "this_month", label: "هذا الشهر" },
    { id: "last_month", label: "الشهر الماضي" },
    { id: "this_year", label: "هذا العام" },
];

/* ----------------------------------------------------------------- helpers */
const pad = (n) => String(n).padStart(2, "0");
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d, n) => {
    const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    r.setDate(r.getDate() + n);
    return r;
};
const startOfWeek = (d) => addDays(d, -((d.getDay() - WEEK_START + 7) % 7));

function presetRange(id) {
    const t = new Date();
    const today = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    switch (id) {
        case "today":
            return [today, today];
        case "yesterday": {
            const y = addDays(today, -1);
            return [y, y];
        }
        case "this_week":
            return [startOfWeek(today), today];
        case "last_week": {
            const s = addDays(startOfWeek(today), -7);
            return [s, addDays(s, 6)];
        }
        case "last_30":
            return [addDays(today, -29), today];
        case "this_month":
            return [new Date(today.getFullYear(), today.getMonth(), 1), today];
        case "last_month":
            return [
                new Date(today.getFullYear(), today.getMonth() - 1, 1),
                new Date(today.getFullYear(), today.getMonth(), 0),
            ];
        case "this_year":
            return [new Date(today.getFullYear(), 0, 1), today];
        default:
            return [today, today];
    }
}

const nf = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
function formatFull(v) {
    return nf.format(Math.round(v || 0));
}
function formatCompact(v) {
    const n = Math.abs(v || 0);
    const sign = v < 0 ? "-" : "";
    if (n >= 1e9) return `${sign}${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `${sign}${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e4) return `${sign}${(n / 1e3).toFixed(1)}K`;
    return `${sign}${nf.format(Math.round(n))}`;
}

async function loadAmCharts() {
    if (window.am5 && window.am5xy && window.am5percent) {
        return;
    }
    await loadJS(AMCHARTS_BUNDLE);
}

/* ---------------------------------------------------------- CountUp widget */
class CountUp extends Component {
    static template = "rotana_management_dashboard.CountUp";
    static props = {
        value: { type: Number },
        format: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({ shown: 0 });
        this._raf = null;
        onMounted(() => this.animate(0, this.props.value || 0));
        onWillUpdateProps((next) => {
            if (next.value !== this.props.value) {
                this.animate(this.state.shown, next.value || 0);
            }
        });
        onWillUnmount(() => cancelAnimationFrame(this._raf));
    }

    animate(from, to) {
        cancelAnimationFrame(this._raf);
        const start = performance.now();
        const duration = 900;
        const step = (now) => {
            const t = Math.min(1, (now - start) / duration);
            const eased = 1 - Math.pow(1 - t, 3);
            this.state.shown = from + (to - from) * eased;
            if (t < 1) {
                this._raf = requestAnimationFrame(step);
            }
        };
        this._raf = requestAnimationFrame(step);
    }

    get text() {
        return (this.props.format || formatFull)(this.state.shown);
    }
}

/* ---------------------------------------------------------- main component */
class RotanaManagementDashboard extends Component {
    static template = "rotana_management_dashboard.Main";
    static components = { CountUp };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.bus = useService("bus_service");
        this.sections = SECTIONS;
        this.presets = PRESETS;
        this.charts = {};
        this._seq = 0;
        this._dead = false;

        const [from, to] = presetRange("this_month");
        this.state = useState({
            section: "sales",
            loading: true,
            refreshing: false,
            error: null,
            preset: "this_month",
            dateFrom: ymd(from),
            dateTo: ymd(to),
            selectedCompanies: [],     // فارغ = كل الشركات
            consolidated: true,        // موحّد: الشركة الأم تشمل فروعها
            companyMenu: false,
            chartMode: "line",
            data: null,
            lastUpdate: null,
            drawer: { open: false, loading: false, company: null, data: null },
        });

        useExternalListener(window, "click", () => {
            if (this.state.companyMenu) {
                this.state.companyMenu = false;
            }
        });

        onWillStart(async () => {
            await loadAmCharts();
        });

        onMounted(() => {
            this.loadData();
            try {
                this.bus.addChannel(BUS_CHANNEL);
                this._unsub = this.bus.subscribe(BUS_EVENT, () => this.scheduleRefresh());
            } catch (e) {
                console.warn("Rotana dashboard: bus unavailable, using polling only", e);
            }
            this._poll = setInterval(() => {
                if (!document.hidden) {
                    this.loadData(true);
                }
            }, FALLBACK_REFRESH_MS);
        });

        onWillUnmount(() => {
            this._dead = true;
            clearInterval(this._poll);
            clearTimeout(this._debounce);
            if (typeof this._unsub === "function") {
                this._unsub();
            }
            try {
                this.bus.deleteChannel(BUS_CHANNEL);
            } catch (e) {
                /* ignore */
            }
            this.disposeCharts();
        });

        useEffect(
            () => {
                this.renderMainCharts();
            },
            () => [this.state.data, this.state.chartMode, this.state.section]
        );
        useEffect(
            () => {
                this.renderDrawerCharts();
            },
            () => [this.state.drawer.data, this.state.drawer.open]
        );
    }

    /* ----------------------------------------------------------- data flow */
    get companyIdsParam() {
        return this.state.selectedCompanies.length ? this.state.selectedCompanies : false;
    }

    scheduleRefresh() {
        if (this._dead) {
            return;
        }
        clearTimeout(this._debounce);
        this._debounce = setTimeout(() => this.loadData(true), BUS_DEBOUNCE_MS);
    }

    async loadData(silent = false) {
        const seq = ++this._seq;
        if (silent) {
            this.state.refreshing = true;
        } else {
            this.state.loading = true;
        }
        try {
            const data = await this.orm.call(
                "rotana.management.dashboard",
                "get_sales_overview",
                [this.state.dateFrom, this.state.dateTo, this.companyIdsParam, this.state.consolidated]
            );
            if (this._dead || seq !== this._seq) {
                return;
            }
            this.state.data = data;
            this.state.error = null;
            this.state.lastUpdate = new Date();
            if (this.state.drawer.open && this.state.drawer.company) {
                this.loadDrawer(this.state.drawer.company, true);
            }
        } catch (e) {
            if (this._dead || seq !== this._seq) {
                return;
            }
            this.state.error =
                (e && e.data && e.data.message) || (e && e.message) || "تعذر جلب البيانات";
        } finally {
            if (!this._dead && seq === this._seq) {
                this.state.loading = false;
                this.state.refreshing = false;
            }
        }
    }

    async loadDrawer(company, silent = false) {
        const drawer = this.state.drawer;
        if (!silent) {
            drawer.loading = true;
            drawer.data = null;
        }
        try {
            const data = await this.orm.call(
                "rotana.management.dashboard",
                "get_company_details",
                [company.id, this.state.dateFrom, this.state.dateTo, this.state.consolidated]
            );
            if (!this._dead && drawer.open && drawer.company && drawer.company.id === company.id) {
                drawer.data = data;
            }
        } catch (e) {
            if (!this._dead) {
                this.state.error = (e && e.data && e.data.message) || "تعذر جلب تفاصيل الشركة";
            }
        } finally {
            drawer.loading = false;
        }
    }

    /* -------------------------------------------------------------- events */
    noop() {}

    selectSection(section) {
        this.state.section = section.id;
    }

    goBack() {
        window.location.href = "/odoo";
    }

    applyPreset(id) {
        const [from, to] = presetRange(id);
        this.state.preset = id;
        this.state.dateFrom = ymd(from);
        this.state.dateTo = ymd(to);
        this.loadData();
    }

    onDateChange(which, ev) {
        const value = ev.target.value;
        if (!value) {
            return;
        }
        if (which === "from") {
            this.state.dateFrom = value;
            if (this.state.dateTo < value) {
                this.state.dateTo = value;
            }
        } else {
            this.state.dateTo = value;
            if (this.state.dateFrom > value) {
                this.state.dateFrom = value;
            }
        }
        this.state.preset = "custom";
        this.loadData();
    }

    toggleCompanyMenu(ev) {
        ev.stopPropagation();
        this.state.companyMenu = !this.state.companyMenu;
    }

    isCompanySelected(id) {
        const sel = this.state.selectedCompanies;
        return !sel.length || sel.includes(id);
    }

    toggleCompany(id) {
        const all = this.allCompanies.map((c) => c.id);
        const effective = this.state.selectedCompanies.length
            ? [...this.state.selectedCompanies]
            : [...all];
        const idx = effective.indexOf(id);
        if (idx >= 0) {
            if (effective.length === 1) {
                return; // لا نسمح بإلغاء كل الشركات
            }
            effective.splice(idx, 1);
        } else {
            effective.push(id);
        }
        this.state.selectedCompanies = effective.length === all.length ? [] : effective;
        this.loadData();
    }

    selectAllCompanies() {
        this.state.selectedCompanies = [];
        this.loadData();
    }

    setConsolidated(value) {
        if (this.state.consolidated === value) {
            return;
        }
        this.state.consolidated = value;
        this.loadData();
    }

    setChartMode(mode) {
        this.state.chartMode = mode;
    }

    openDrawer(company) {
        this.state.drawer.open = true;
        this.state.drawer.company = { id: company.id, name: company.name };
        this.loadDrawer(company);
    }

    closeDrawer() {
        this.state.drawer.open = false;
        this.state.drawer.company = null;
        this.state.drawer.data = null;
        this.disposeKey("drawerLine");
        this.disposeKey("drawerProducts");
    }

    /* ----------------------------------------------------------- view data */
    get allCompanies() {
        return (this.state.data && this.state.data.all_companies) || [];
    }

    get companyFilterLabel() {
        const sel = this.state.selectedCompanies;
        if (!sel.length) {
            return "كل الشركات";
        }
        if (sel.length === 1) {
            const c = this.allCompanies.find((x) => x.id === sel[0]);
            return c ? c.name : "شركة واحدة";
        }
        return `${sel.length} شركات`;
    }

    get rangeLabel() {
        return this.state.dateFrom === this.state.dateTo
            ? this.state.dateFrom
            : `${this.state.dateFrom}  ←  ${this.state.dateTo}`;
    }

    get lastUpdateLabel() {
        const d = this.state.lastUpdate;
        return d ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : "";
    }

    get topCompany() {
        const rows = (this.state.data && this.state.data.companies) || [];
        return rows.reduce((best, c) => (!best || c.own_total > best.own_total ? c : best), null);
    }

    get topShare() {
        const top = this.topCompany;
        const total = this.state.data && this.state.data.totals.total;
        return top && total ? ((top.own_total / total) * 100).toFixed(1) : 0;
    }

    get hasData() {
        const d = this.state.data;
        return !!d && d.companies.length > 0;
    }

    colorOf(id) {
        const idx = this.allCompanies.findIndex((c) => c.id === id);
        return PALETTE[(idx < 0 ? 0 : idx) % PALETTE.length];
    }

    money(v) {
        const cur = this.state.data && this.state.data.currency;
        const num = formatFull(v);
        if (!cur) {
            return num;
        }
        return cur.position === "before" ? `${cur.symbol} ${num}` : `${num} ${cur.symbol}`;
    }

    moneyCompact(v) {
        const cur = this.state.data && this.state.data.currency;
        const num = formatCompact(v);
        if (!cur) {
            return num;
        }
        return cur.position === "before" ? `${cur.symbol} ${num}` : `${num} ${cur.symbol}`;
    }

    growthClass(g) {
        if (g === null || g === undefined) {
            return "flat";
        }
        return g > 0 ? "up" : g < 0 ? "down" : "flat";
    }

    growthText(g) {
        if (g === null || g === undefined) {
            return "—";
        }
        return `${g > 0 ? "▲" : g < 0 ? "▼" : "■"} ${Math.abs(g).toFixed(1)}%`;
    }

    countFormat = (v) => formatFull(v);
    moneyFormat = (v) => this.money(v);

    /* sparkline (SVG بسيط داخل البطاقة) */
    sparkPoints(series) {
        const w = 120;
        const h = 36;
        const n = series.length;
        if (!n) {
            return [];
        }
        const max = Math.max(...series, 1);
        return series.map((v, i) => [
            n === 1 ? w / 2 : (i / (n - 1)) * w,
            h - 3 - (v / max) * (h - 8),
        ]);
    }

    sparkLine(series) {
        const pts = this.sparkPoints(series);
        if (!pts.length) {
            return "";
        }
        return pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    }

    sparkArea(series) {
        const pts = this.sparkPoints(series);
        if (!pts.length) {
            return "";
        }
        const line = this.sparkLine(series);
        return `${line} L${pts[pts.length - 1][0].toFixed(1)},36 L${pts[0][0].toFixed(1)},36 Z`;
    }

    /* -------------------------------------------------------------- charts */
    disposeKey(key) {
        const entry = this.charts[key];
        if (entry) {
            try {
                entry.root.dispose();
            } catch (e) {
                /* ignore */
            }
            delete this.charts[key];
        }
    }

    disposeCharts() {
        Object.keys(this.charts).forEach((k) => this.disposeKey(k));
    }

    _newRoot(el) {
        const am5 = window.am5;
        const root = am5.Root.new(el);
        const fontTheme = window.am5.Theme.new(root);
        fontTheme.rule("Label").setAll({ fontFamily: FONT_FAMILY, fontSize: 13.5 });
        fontTheme.rule("Legend").setAll({ fontFamily: FONT_FAMILY });
        root.setThemes([
            window.am5themes_Animated.new(root),
            window.am5themes_Dark.new(root),
            fontTheme,
        ]);
        root.numberFormatter.set("numberFormat", "#,###");
        return root;
    }

    _points(buckets, values) {
        return buckets.map((b, i) => ({
            date: new Date(b + "T00:00:00").getTime(),
            value: values[i] || 0,
        }));
    }

    renderMainCharts() {
        if (this.state.section !== "sales" || !this.state.data || !this.hasData) {
            this.disposeKey("compare");
            this.disposeKey("share");
            return;
        }
        const cmpEl = document.querySelector(".rmd-chart-compare");
        const shareEl = document.querySelector(".rmd-chart-share");
        if (cmpEl) {
            this.renderCompare(cmpEl);
        }
        if (shareEl) {
            this.renderShare(shareEl);
        }
    }

    renderCompare(el) {
        const am5 = window.am5;
        const am5xy = window.am5xy;
        const data = this.state.data;
        const mode = this.state.chartMode;
        const key = `${mode}|${data.granularity}|${data.companies.map((c) => c.id).join(",")}`;
        const existing = this.charts.compare;

        if (existing && existing.el === el && existing.key === key) {
            // تحديث البيانات فقط (بدون إعادة بناء) لتجنب الوميض أثناء التحديث الحي
            data.companies.forEach((c) => {
                const s = existing.series[c.id];
                if (s) {
                    s.data.setAll(this._points(data.buckets, c.own_series));
                }
            });
            return;
        }
        this.disposeKey("compare");

        const root = this._newRoot(el);
        const chart = root.container.children.push(
            am5xy.XYChart.new(root, {
                panX: true,
                wheelX: "panX",
                wheelY: "zoomX",
                pinchZoomX: true,
                layout: root.verticalLayout,
            })
        );
        chart.set("cursor", am5xy.XYCursor.new(root, { behavior: "none" }));

        const unit = data.granularity === "month" ? "month" : "day";
        const xAxis = chart.xAxes.push(
            am5xy.DateAxis.new(root, {
                baseInterval: { timeUnit: unit, count: 1 },
                renderer: am5xy.AxisRendererX.new(root, { minGridDistance: 70 }),
                tooltip: window.am5.Tooltip.new(root, {}),
            })
        );
        const yAxis = chart.yAxes.push(
            am5xy.ValueAxis.new(root, {
                numberFormat: "#.#a",
                renderer: am5xy.AxisRendererY.new(root, {}),
            })
        );

        const seriesMap = {};
        data.companies.forEach((c) => {
            const color = am5.color(this.colorOf(c.id));
            const settings = {
                name: c.name,
                xAxis,
                yAxis,
                valueYField: "value",
                valueXField: "date",
                fill: color,
                stroke: color,
                tooltip: am5.Tooltip.new(root, { labelText: "{name}: {valueY.formatNumber('#,###')}" }),
            };
            let series;
            if (mode === "column") {
                series = chart.series.push(am5xy.ColumnSeries.new(root, settings));
                series.columns.template.setAll({ cornerRadiusTL: 4, cornerRadiusTR: 4, width: am5.percent(80) });
            } else {
                series = chart.series.push(am5xy.LineSeries.new(root, settings));
                series.strokes.template.setAll({ strokeWidth: 3 });
                series.fills.template.setAll({ visible: true, fillOpacity: 0.12 });
                series.bullets.push(() =>
                    am5.Bullet.new(root, {
                        sprite: am5.Circle.new(root, { radius: 3.5, fill: color, stroke: root.interfaceColors.get("background"), strokeWidth: 1 }),
                    })
                );
            }
            series.data.setAll(this._points(data.buckets, c.own_series));
            seriesMap[c.id] = series;
        });

        const legend = chart.children.push(
            am5.Legend.new(root, { centerX: am5.p50, x: am5.p50, marginTop: 8 })
        );
        legend.data.setAll(chart.series.values);

        this.charts.compare = { root, el, key, series: seriesMap };
    }

    renderShare(el) {
        const am5 = window.am5;
        const am5percent = window.am5percent;
        const data = this.state.data;
        const items = data.companies
            .filter((c) => c.own_total > 0)
            .map((c) => ({
                name: c.name,
                value: c.own_total,
                sliceSettings: { fill: am5.color(this.colorOf(c.id)) },
            }));
        const key = items.map((i) => i.name).join("|");
        const existing = this.charts.share;
        if (existing && existing.el === el && existing.key === key) {
            existing.series.data.setAll(items);
            return;
        }
        this.disposeKey("share");

        const root = this._newRoot(el);
        const chart = root.container.children.push(
            am5percent.PieChart.new(root, { innerRadius: am5.percent(62), layout: root.verticalLayout })
        );
        const series = chart.series.push(
            am5percent.PieSeries.new(root, { valueField: "value", categoryField: "name" })
        );
        series.slices.template.setAll({
            templateField: "sliceSettings",
            strokeOpacity: 0,
            cornerRadius: 6,
            tooltipText: "{category}: {value.formatNumber('#,###')} ({valuePercentTotal.formatNumber('0.0')}%)",
        });
        series.labels.template.set("forceHidden", true);
        series.ticks.template.set("forceHidden", true);
        series.data.setAll(items);
        series.appear(800, 100);

        this.charts.share = { root, el, key, series };
    }

    renderDrawerCharts() {
        const drawer = this.state.drawer;
        if (!drawer.open || !drawer.data) {
            return;
        }
        const lineEl = document.querySelector(".rmd-chart-drawer-line");
        const prodEl = document.querySelector(".rmd-chart-drawer-products");
        const d = drawer.data;
        const color = this.colorOf(d.company.id);
        if (lineEl) {
            this.disposeKey("drawerLine");
            this.renderDrawerLine(lineEl, d, color);
        }
        if (prodEl) {
            this.disposeKey("drawerProducts");
            if (d.products.length) {
                this.renderDrawerProducts(prodEl, d, color);
            }
        }
    }

    renderDrawerLine(el, d, colorHex) {
        const am5 = window.am5;
        const am5xy = window.am5xy;
        const root = this._newRoot(el);
        const chart = root.container.children.push(
            am5xy.XYChart.new(root, { panX: true, wheelX: "panX", wheelY: "zoomX", layout: root.verticalLayout })
        );
        chart.set("cursor", am5xy.XYCursor.new(root, { behavior: "none" }));
        const unit = d.granularity === "month" ? "month" : "day";
        const xAxis = chart.xAxes.push(
            am5xy.DateAxis.new(root, {
                baseInterval: { timeUnit: unit, count: 1 },
                renderer: am5xy.AxisRendererX.new(root, { minGridDistance: 60 }),
            })
        );
        const yAxis = chart.yAxes.push(
            am5xy.ValueAxis.new(root, { numberFormat: "#.#a", renderer: am5xy.AxisRendererY.new(root, {}) })
        );
        const color = am5.color(colorHex);
        const series = chart.series.push(
            am5xy.LineSeries.new(root, {
                xAxis,
                yAxis,
                valueYField: "value",
                valueXField: "date",
                fill: color,
                stroke: color,
                tooltip: am5.Tooltip.new(root, { labelText: "{valueY.formatNumber('#,###')}" }),
            })
        );
        series.strokes.template.setAll({ strokeWidth: 3 });
        series.fills.template.setAll({ visible: true, fillOpacity: 0.18 });
        series.data.setAll(this._points(d.buckets, d.series));
        this.charts.drawerLine = { root };
    }

    renderDrawerProducts(el, d, colorHex) {
        const am5 = window.am5;
        const am5xy = window.am5xy;
        const root = this._newRoot(el);
        const chart = root.container.children.push(
            am5xy.XYChart.new(root, { layout: root.verticalLayout })
        );
        const yAxis = chart.yAxes.push(
            am5xy.CategoryAxis.new(root, {
                categoryField: "name",
                renderer: am5xy.AxisRendererY.new(root, { inversed: true, minGridDistance: 18 }),
            })
        );
        yAxis.get("renderer").labels.template.setAll({ maxWidth: 140, oversizedBehavior: "truncate", fontSize: 11 });
        const xAxis = chart.xAxes.push(
            am5xy.ValueAxis.new(root, { numberFormat: "#.#a", renderer: am5xy.AxisRendererX.new(root, {}) })
        );
        const series = chart.series.push(
            am5xy.ColumnSeries.new(root, {
                xAxis,
                yAxis,
                valueXField: "value",
                categoryYField: "name",
                fill: am5.color(colorHex),
                stroke: am5.color(colorHex),
                tooltip: am5.Tooltip.new(root, { labelText: "{categoryY}: {valueX.formatNumber('#,###')}" }),
            })
        );
        series.columns.template.setAll({ cornerRadiusTR: 4, cornerRadiusBR: 4, height: am5.percent(70) });
        yAxis.data.setAll(d.products);
        series.data.setAll(d.products);
        this.charts.drawerProducts = { root };
    }
}

registry.category("actions").add("rotana_management_dashboard.main", RotanaManagementDashboard);
