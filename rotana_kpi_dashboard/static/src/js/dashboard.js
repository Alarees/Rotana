/* ==========================================================================
   Rotana KPI Dashboard — Vanilla JS (no framework), Chart.js for charts.
   Loaded as a plain <script> (not an ES module) so it works with zero
   build step and zero external framework dependency besides Chart.js.
   ========================================================================== */

(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Config: KPI metric definitions per module.
  // ------------------------------------------------------------------
  var MODULE_CONFIG = {
    sales: {
      title: "مؤشرات أداء المبيعات",
      endpoint: "/rotana_kpi/data/sales",
      metrics: [
        { key: "quotations_count", label: "عدد عروض الأسعار الشهرية", kind: "number" },
        { key: "avg_response_time_hours", label: "زمن الاستجابة (ساعات) حتى التأكيد", kind: "hours" },
        { key: "new_customers", label: "عدد العملاء الجدد", kind: "number" },
        { key: "pct_sales_without_invoice", label: "% المبيعات بدون فواتير", kind: "percent" },
      ],
    },
    purchase: {
      title: "مؤشرات أداء المشتريات",
      endpoint: "/rotana_kpi/data/purchase",
      metrics: [
        { key: "po_count", label: "عدد أوامر الشراء", kind: "number" },
        { key: "avg_lead_time_hours", label: "زمن المعالجة حتى الاعتماد (ساعات)", kind: "hours" },
      ],
    },
    accounting: {
      title: "مؤشرات أداء الحسابات",
      endpoint: "/rotana_kpi/data/accounting",
      metrics: [
        { key: "total_invoices", label: "إجمالي الفواتير الصادرة", kind: "number" },
        { key: "pct_unposted_invoices", label: "% الفواتير غير المؤكدة", kind: "percent" },
        { key: "avg_confirm_time_hours", label: "زمن التأكيد (ساعات)", kind: "hours" },
      ],
    },
    inventory: {
      title: "مؤشرات أداء المخازن",
      endpoint: "/rotana_kpi/data/inventory",
      metrics: [
        { key: "pct_on_time_fulfillment", label: "% التجهيز في الوقت المحدد", kind: "percent" },
        { key: "moves_per_day", label: "حركات المخزون / يوم", kind: "number" },
        { key: "avg_validation_time_hours", label: "زمن الاستجابة حتى التصديق (ساعات)", kind: "hours" },
      ],
    },
    manufacturing: {
      title: "مؤشرات أداء التصنيع",
      endpoint: "/rotana_kpi/data/manufacturing",
      metrics: [
        { key: "pct_completed_mo", label: "% أوامر التصنيع المكتملة", kind: "percent" },
        { key: "avg_processing_time_hours", label: "زمن الاستجابة حتى المعالجة (ساعات)", kind: "hours" },
      ],
    },
  };

  var CHART_COLORS = ["#1565c0", "#2e7d32", "#ef6c00", "#6a1b9a", "#00838f", "#ad1457"];

  // ------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------
  var moduleKey = window.ROTANA_KPI_MODULE || "sales";
  var config = MODULE_CONFIG[moduleKey] || MODULE_CONFIG.sales;
  var state = {
    companies: [],
    selectedCompanies: [],
    dateFrom: null,
    dateTo: null,
    employees: [],
    chartInstances: {},
  };

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function fmt(value, kind) {
    if (value === undefined || value === null) return "-";
    if (kind === "percent") return value + "%";
    if (kind === "hours") return value + " س";
    return value;
  }

  function isoDate(d) { return d.toISOString().slice(0, 10); }

  function defaultDates() {
    var to = new Date();
    var from = new Date();
    from.setDate(from.getDate() - 30);
    return { from: isoDate(from), to: isoDate(to) };
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k.indexOf("on") === 0 && typeof attrs[k] === "function") {
        node.addEventListener(k.slice(2).toLowerCase(), attrs[k]);
      } else {
        node.setAttribute(k, attrs[k]);
      }
    });
    (children || []).forEach(function (c) {
      if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  // ------------------------------------------------------------------
  // Data fetching
  // ------------------------------------------------------------------
  function fetchCompanies() {
    return fetch("/rotana_kpi/companies")
      .then(function (r) { return r.json(); })
      .then(function (rows) { state.companies = rows || []; })
      .catch(function () { state.companies = []; });
  }

  function fetchData() {
    var params = new URLSearchParams();
    if (state.dateFrom) params.append("date_from", state.dateFrom);
    if (state.dateTo) params.append("date_to", state.dateTo);
    if (state.selectedCompanies.length) params.append("company_ids", state.selectedCompanies.join(","));

    return fetch(config.endpoint + "?" + params.toString())
      .then(function (r) { return r.json(); })
      .then(function (json) { state.employees = (json && json.employees) || []; })
      .catch(function () { state.employees = []; });
  }

  // ------------------------------------------------------------------
  // Rendering
  // ------------------------------------------------------------------
  function renderAppBar(root) {
    root.appendChild(
      el("div", { class: "md-appbar" }, [
        el("h1", {}, ["Rotana Development - HQ | " + config.title]),
        el("div", { class: "subtitle" }, ["لوحة مؤشرات أداء الموظفين"]),
      ])
    );
  }

  function renderFilters(container) {
    var card = el("div", { class: "md-card" });
    card.appendChild(el("h2", {}, ["الفلاتر"]));

    var filters = el("div", { class: "md-filters" });

    // Branch/company multi-select
    var branchField = el("div", { class: "md-field" }, [
      el("label", {}, ["الفرع / الشركة"]),
    ]);
    var select = el("select", { class: "md-select", multiple: "multiple" });
    state.companies.forEach(function (c) {
      var opt = el("option", { value: c.id }, [c.name]);
      select.appendChild(opt);
    });
    select.addEventListener("change", function () {
      state.selectedCompanies = Array.prototype.slice
        .call(select.selectedOptions)
        .map(function (o) { return parseInt(o.value, 10); });
    });
    branchField.appendChild(select);
    filters.appendChild(branchField);

    // Date from
    var fromField = el("div", { class: "md-field" }, [el("label", {}, ["من تاريخ"])]);
    var fromInput = el("input", { class: "md-input", type: "date", value: state.dateFrom });
    fromInput.addEventListener("change", function (e) { state.dateFrom = e.target.value; });
    fromField.appendChild(fromInput);
    filters.appendChild(fromField);

    // Date to
    var toField = el("div", { class: "md-field" }, [el("label", {}, ["إلى تاريخ"])]);
    var toInput = el("input", { class: "md-input", type: "date", value: state.dateTo });
    toInput.addEventListener("change", function (e) { state.dateTo = e.target.value; });
    toField.appendChild(toInput);
    filters.appendChild(toField);

    // Apply button
    var applyBtn = el("button", { class: "md-btn", onclick: applyFilters }, ["تطبيق الفلاتر"]);
    filters.appendChild(applyBtn);

    card.appendChild(filters);
    container.appendChild(card);
  }

  function renderStats(container) {
    var grid = el("div", { class: "md-stats-grid" });

    grid.appendChild(
      el("div", { class: "md-stat-card" }, [
        el("div", { class: "stat-label" }, ["عدد الموظفين"]),
        el("div", { class: "stat-value" }, [String(state.employees.length)]),
      ])
    );

    config.metrics.slice(0, 3).forEach(function (m) {
      var total = state.employees.reduce(function (s, e) { return s + (e[m.key] || 0); }, 0);
      var avg = state.employees.length ? (total / state.employees.length).toFixed(2) : 0;
      grid.appendChild(
        el("div", { class: "md-stat-card" }, [
          el("div", { class: "stat-label" }, [m.label + " (متوسط)"]),
          el("div", { class: "stat-value" }, [String(fmt(avg, m.kind))]),
        ])
      );
    });

    container.appendChild(grid);
  }

  function renderCharts(container) {
    var grid = el("div", { class: "md-charts-grid" });

    config.metrics.forEach(function (m, idx) {
      var card = el("div", { class: "md-chart-card" });
      card.appendChild(el("div", { class: "md-chart-title" }, [m.label]));
      var canvas = el("canvas", { id: "chart_" + m.key });
      card.appendChild(canvas);
      grid.appendChild(card);

      // Defer Chart.js instantiation until canvas is in the DOM
      setTimeout(function () {
        var ctx = canvas.getContext("2d");
        var labels = state.employees.map(function (e) { return e.employee; });
        var values = state.employees.map(function (e) { return e[m.key] || 0; });
        var color = CHART_COLORS[idx % CHART_COLORS.length];

        if (state.chartInstances[m.key]) {
          state.chartInstances[m.key].destroy();
        }
        state.chartInstances[m.key] = new Chart(ctx, {
          type: "bar",
          data: {
            labels: labels,
            datasets: [{
              label: m.label,
              data: values,
              backgroundColor: color,
              borderRadius: 6,
              maxBarThickness: 48,
            }],
          },
          options: {
            responsive: true,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (ctx) { return fmt(ctx.parsed.y, m.kind); },
                },
              },
            },
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  callback: function (value) { return fmt(value, m.kind); },
                },
              },
            },
          },
        });
      }, 0);
    });

    container.appendChild(grid);
  }

  function renderTable(container) {
    var card = el("div", { class: "md-card md-table-wrapper" });
    card.appendChild(el("h2", {}, ["تفاصيل حسب الموظف"]));

    var table = el("table", { class: "md-table" });
    var thead = el("thead");
    var headRow = el("tr", {}, [el("th", {}, ["الموظف"])]);
    config.metrics.forEach(function (m) { headRow.appendChild(el("th", {}, [m.label])); });
    thead.appendChild(headRow);
    table.appendChild(thead);

    var tbody = el("tbody");
    if (!state.employees.length) {
      var emptyRow = el("tr", { class: "empty-row" }, [
        el("td", { colspan: String(config.metrics.length + 1) }, ["لا توجد بيانات ضمن الفترة/الفلاتر المحددة"]),
      ]);
      tbody.appendChild(emptyRow);
    } else {
      state.employees.forEach(function (e) {
        var row = el("tr", {}, [el("td", {}, [e.employee])]);
        config.metrics.forEach(function (m) {
          row.appendChild(el("td", {}, [String(fmt(e[m.key], m.kind))]));
        });
        tbody.appendChild(row);
      });
    }
    table.appendChild(tbody);
    card.appendChild(table);
    container.appendChild(card);
  }

  function renderLoader(container) {
    container.appendChild(
      el("div", { class: "md-loader-wrap" }, [el("div", { class: "md-spinner" })])
    );
  }

  function renderBody() {
    var root = document.getElementById("root");
    clear(root);
    renderAppBar(root);

    var main = el("div", { class: "md-container" });
    renderFilters(main);
    renderLoader(main);
    root.appendChild(main);

    fetchData().then(function () {
      clear(main);
      renderFilters(main);
      renderStats(main);
      renderCharts(main);
      renderTable(main);
    });
  }

  function applyFilters() {
    renderBody();
  }

  // ------------------------------------------------------------------
  // Init
  // ------------------------------------------------------------------
  function init() {
    var d = defaultDates();
    state.dateFrom = d.from;
    state.dateTo = d.to;

    fetchCompanies().then(renderBody);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
