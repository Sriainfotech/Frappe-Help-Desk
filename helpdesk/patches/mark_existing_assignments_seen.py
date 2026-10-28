import frappe
from frappe.utils import now_datetime

from helpdesk.helpdesk.doctype.hd_ticket_view.hd_ticket_view import on_doctype_update


def execute():
    """Mark every current ticket assignment as seen, so agents do not open the
    app after the upgrade to a count of all their existing tickets."""
    on_doctype_update()

    ToDo = frappe.qb.DocType("ToDo")
    View = frappe.qb.DocType("HD Ticket View")
    unseen = (
        frappe.qb.from_(ToDo)
        .left_join(View)
        .on((View.ticket == ToDo.reference_name) & (View.user == ToDo.allocated_to))
        .select(ToDo.reference_name, ToDo.allocated_to)
        .distinct()
        .where(ToDo.reference_type == "HD Ticket")
        .where(ToDo.status == "Open")
        .where(ToDo.allocated_to.isnotnull())
        .where(View.name.isnull())
    ).run()

    now = now_datetime()
    rows = [
        (frappe.generate_hash(), ticket, user, now, now, now, "Administrator", "Administrator")
        for ticket, user in unseen
    ]
    frappe.db.bulk_insert(
        "HD Ticket View",
        fields=["name", "ticket", "user", "seen_at", "creation", "modified", "owner", "modified_by"],
        values=rows,
    )
