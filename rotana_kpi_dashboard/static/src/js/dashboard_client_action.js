/** @odoo-module **/

import { Component, xml, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Minimal client action: just embeds our existing server-rendered
 * dashboard page (plain HTML/CSS/JS + Chart.js, no framework) inside
 * an iframe, so it renders WITHIN Odoo's backend frame (top menu,
 * breadcrumb, app switcher) instead of replacing the whole page.
 *
 * All dashboard logic (filters, Chart.js, table) lives untouched in
 * /rotana_kpi_dashboard/static/src/js/dashboard.js, served by the
 * existing controller at /rotana_kpi/dashboard?module=<module>.
 */
class RotanaKpiClientAction extends Component {
    static template = xml`
        <div class="o_rotana_kpi_iframe_wrapper" style="height: 100%; width: 100%;">
            <iframe t-ref="iframe"
                    style="width: 100%; height: 100%; border: 0;"
                    t-att-src="src"/>
        </div>
    `;
    static props = ["*"];

    setup() {
        this.iframeRef = useRef("iframe");
        this.actionService = useService("action");

        // The module key is passed via the action's params (see menu_views.xml)
        const params = this.props.action.params || {};
        const moduleKey = params.module || "sales";
        this.src = `/rotana_kpi/dashboard?module=${encodeURIComponent(moduleKey)}`;

        onMounted(() => {
            // Keep the breadcrumb title in sync with the action name
            if (this.props.action.name) {
                this.env.config.setDisplayName(this.props.action.name);
            }
        });
    }
}

registry.category("actions").add("rotana_kpi_dashboard.client_action", RotanaKpiClientAction);
