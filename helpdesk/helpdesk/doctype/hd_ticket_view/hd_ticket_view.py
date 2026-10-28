import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Count
from frappe.utils import now_datetime

UNSEEN_TICKETS_EVENT = "helpdesk:unseen-tickets-update"


class HDTicketView(Document):
    """When an assignee last opened a ticket. One row per (ticket, user).

    An assignment is unseen while its ToDo was created after `seen_at`, so a
    new or repeated assignment counts again without deleting this row.
    """

    @staticmethod
    def mark(ticket: str, user: str):
        name = frappe.db.get_value("HD Ticket View", {"ticket": ticket, "user": user})
        if name:
            frappe.db.set_value(
                "HD Ticket View", name, "seen_at", now_datetime(), update_modified=False
            )
            return
        try:
            frappe.get_doc(
                {
                    "doctype": "HD Ticket View",
                    "ticket": ticket,
                    "user": user,
                    "seen_at": now_datetime(),
                }
            ).insert(ignore_permissions=True)
        except frappe.UniqueValidationError:
            # another tab opened the same ticket at the same moment, already recorded
            pass

    @staticmethod
    def get_unseen_count(user: str) -> int:
        ToDo = frappe.qb.DocType("ToDo")
        Ticket = frappe.qb.DocType("HD Ticket")
        View = frappe.qb.DocType("HD Ticket View")
        result = (
            frappe.qb.from_(ToDo)
            .join(Ticket)
            .on(Ticket.name == ToDo.reference_name)
            .left_join(View)
            .on(
                (View.ticket == ToDo.reference_name)
                & (View.user == ToDo.allocated_to)
                & (View.seen_at >= ToDo.creation)
            )
            .select(Count(ToDo.reference_name).distinct())
            .where(ToDo.allocated_to == user)
            .where(ToDo.status == "Open")
            .where(ToDo.reference_type == "HD Ticket")
            .where(Ticket.status_category == "Open")
            .where(View.name.isnull())
        ).run()
        return result[0][0] if result else 0

    @staticmethod
    def notify(user: str):
        """Tell `user`'s open tabs to refetch their unseen count."""
        frappe.publish_realtime(UNSEEN_TICKETS_EVENT, user=user, after_commit=True)


def on_doctype_update():
    frappe.db.add_unique(
        "HD Ticket View", ["ticket", "user"], constraint_name="unique_ticket_user"
    )
    # the unseen count filters ToDo by assignee, which core leaves unindexed
    frappe.db.add_index(
        "ToDo",
        ["allocated_to", "status", "reference_type"],
        index_name="allocated_to_status_reference_type_index",
    )
