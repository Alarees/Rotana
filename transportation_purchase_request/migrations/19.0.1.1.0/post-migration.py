def migrate(cr, version):
    """Map the removed states to the new approval chain."""
    cr.execute(
        "UPDATE transportation_purchase_request SET state = 'dept_manager' "
        "WHERE state = 'to_approve'"
    )
    cr.execute(
        "UPDATE transportation_purchase_request SET state = 'approved' "
        "WHERE state IN ('in_progress', 'done')"
    )
