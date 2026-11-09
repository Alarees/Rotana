import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "rotana.weighbridge.ticket";

export class WeighbridgeDashboard extends Component {
    static template = "rotana_weighbridge.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, days: 30 });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call(MODEL, "get_dashboard_data", [], {
            days: this.state.days,
        });
    }

    async refresh() {
        await this.load();
    }

    async onChangeDays(ev) {
        this.state.days = parseInt(ev.target.value, 10) || 30;
        await this.load();
    }

    /** Daily rows, newest first. */
    get rows() {
        return this.state.data ? [...this.state.data.days].reverse() : [];
    }

    get maxNet() {
        return Math.max(0, ...this.rows.map((row) => row.net));
    }

    tons(kg) {
        return ((kg || 0) / 1000).toLocaleString(undefined, {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
        });
    }

    barWidth(kg) {
        if (!kg || !this.maxNet) {
            return 0;
        }
        return Math.max(2, Math.round((kg / this.maxNet) * 100));
    }

    openTickets(title, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: MODEL,
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
        });
    }

    openToday() {
        const day = this.state.data.today_date;
        this.openTickets(_t("Tickets today"), [
            ["state", "=", "done"],
            ["ticket_date", "=", day],
        ]);
    }

    openMonth() {
        const start = this.state.data.month_start;
        this.openTickets(_t("Tickets this month"), [
            ["state", "=", "done"],
            ["ticket_date", ">=", start],
        ]);
    }

    openPending() {
        const day = this.state.data.today_date;
        this.openTickets(_t("In progress today"), [
            ["state", "=", "pending"],
            ["ticket_date", "=", day],
        ]);
    }

    openReview() {
        this.openTickets(_t("Needs review"), [
            ["needs_review", "=", true],
            ["state", "!=", "cancelled"],
        ]);
    }

    openDay(row) {
        this.openTickets(row.date, [
            ["state", "=", "done"],
            ["ticket_date", "=", row.date],
        ]);
    }
}

registry.category("actions").add("rotana_weighbridge.dashboard", WeighbridgeDashboard);
