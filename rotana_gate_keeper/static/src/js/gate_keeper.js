import { Component, onMounted, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { deserializeDateTime } from "@web/core/l10n/dates";

const MODEL = "rotana.gate.keeper";

export class GateKeeperDashboard extends Component {
    static template = "rotana_gate_keeper.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.searchRef = useRef("search");
        this.userName = user.name || "";
        this.state = useState({
            query: "",
            loading: false,
            saving: false,
            picking: null,
            notFound: false,
            error: "",
            values: {},
        });
        onMounted(() => this.focusSearch());
    }

    focusSearch() {
        const el = this.searchRef.el;
        if (el) {
            el.focus();
            el.select();
        }
    }

    goHome() {
        browser.location.assign("/odoo");
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.search();
        }
    }

    async search() {
        const code = this.state.query.trim();
        if (!code || this.state.loading) {
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const picking = await this.orm.call(MODEL, "search_picking", [code]);
            if (picking) {
                this.setPicking(picking);
            } else {
                this.state.picking = null;
                this.state.notFound = true;
            }
        } catch (error) {
            this.state.picking = null;
            this.state.notFound = false;
            this.state.error = (error.data && error.data.message) || "تعذر تنفيذ البحث";
        } finally {
            this.state.loading = false;
            this.focusSearch();
        }
    }

    setPicking(picking) {
        this.state.picking = picking;
        this.state.notFound = false;
        this.state.error = "";
        this.resetValues();
    }

    resetValues() {
        const values = {};
        for (const field of this.state.picking ? this.state.picking.fields : []) {
            if (field.editable) {
                values[field.name] = field.value || "";
            }
        }
        this.state.values = values;
    }

    get editableFields() {
        return this.state.picking ? this.state.picking.fields.filter((f) => f.editable) : [];
    }

    get isDirty() {
        return this.editableFields.some(
            (f) => (this.state.values[f.name] || "").trim() !== (f.value || "")
        );
    }

    onInput(name, ev) {
        this.state.values[name] = ev.target.value;
    }

    async save() {
        if (!this.isDirty || this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const picking = await this.orm.call(MODEL, "save_delivery_info", [
                this.state.picking.id,
                { ...this.state.values },
            ]);
            this.setPicking(picking);
            this.notification.add("تم حفظ معلومات التوصيل", { type: "success" });
            this.focusSearch();
        } catch (error) {
            this.notification.add(
                (error.data && error.data.message) || "تعذر حفظ معلومات التوصيل",
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }

    discard() {
        this.resetValues();
    }

    formatDate(value) {
        return value ? deserializeDateTime(value).toFormat("yyyy/MM/dd HH:mm") : "-";
    }

    formatNumber(value) {
        return (value || 0).toLocaleString("en-US", { maximumFractionDigits: 3 });
    }
}

registry.category("actions").add("rotana_gate_keeper.dashboard", GateKeeperDashboard);
