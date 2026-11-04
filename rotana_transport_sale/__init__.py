# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import wizard


def post_init_hook(env):
    """Create analytic plans for vehicles that existed before the module was installed."""
    vehicles = env['fleet.vehicle'].with_context(active_test=False).search(
        [('analytic_plan_id', '=', False)]
    )
    vehicles._create_missing_analytic_plans()
