import frappe
from frappe.tests.utils import FrappeTestCase

from helpdesk.api.ticket import get_unseen_assignment_count
from helpdesk.helpdesk.doctype.hd_ticket_view.hd_ticket_view import HDTicketView
from helpdesk.patches.mark_existing_assignments_seen import execute as run_patch
from helpdesk.test_utils import (
    assign_ticket,
    clear_user_assignments,
    create_agent,
    make_ticket,
    mark_ticket_seen_as,
    unassign_ticket,
)

AGENT_A = "helpdesk-unseen-a@example.com"
AGENT_B = "helpdesk-unseen-b@example.com"


class TestUnseenAssignments(FrappeTestCase):
    """The Tickets sidebar count: open tickets assigned to an agent that the
    agent has not opened since they were assigned."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_agent(AGENT_A)
        create_agent(AGENT_B)

    def setUp(self):
        clear_user_assignments(AGENT_A)
        clear_user_assignments(AGENT_B)
        self.ticket = make_ticket(subject="Unseen assignment test")
        # assignment rules may have picked someone on insert
        frappe.db.set_value(
            "ToDo",
            {"reference_type": "HD Ticket", "reference_name": self.ticket.name},
            "status",
            "Cancelled",
        )

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_assignment_counts_for_assignee_only(self):
        assign_ticket(self.ticket.name, AGENT_A)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 1)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_B), 0)

    def test_opening_ticket_clears_it(self):
        assign_ticket(self.ticket.name, AGENT_A)
        self.assertTrue(mark_ticket_seen_as(self.ticket.name, AGENT_A))
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 0)
        # opening it again is not a second drop in the count
        self.assertFalse(mark_ticket_seen_as(self.ticket.name, AGENT_A))

    def test_non_assignee_opening_ticket_changes_nothing(self):
        assign_ticket(self.ticket.name, AGENT_A)
        self.assertFalse(mark_ticket_seen_as(self.ticket.name, AGENT_B))
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 1)
        self.assertFalse(
            frappe.db.exists(
                "HD Ticket View", {"ticket": self.ticket.name, "user": AGENT_B}
            )
        )

    def test_reassignment_moves_count(self):
        assign_ticket(self.ticket.name, AGENT_A)
        unassign_ticket(self.ticket.name, AGENT_A)
        assign_ticket(self.ticket.name, AGENT_B)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 0)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_B), 1)

    def test_unassignment_removes_count(self):
        assign_ticket(self.ticket.name, AGENT_A)
        unassign_ticket(self.ticket.name, AGENT_A)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 0)

    def test_reassignment_after_seen_counts_again(self):
        assign_ticket(self.ticket.name, AGENT_A)
        mark_ticket_seen_as(self.ticket.name, AGENT_A)
        unassign_ticket(self.ticket.name, AGENT_A)
        assign_ticket(self.ticket.name, AGENT_A)
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 1)

    def test_only_open_tickets_count(self):
        assign_ticket(self.ticket.name, AGENT_A)
        frappe.db.set_value("HD Ticket", self.ticket.name, "status_category", "Resolved")
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 0)

    def test_endpoint_returns_session_user_count(self):
        assign_ticket(self.ticket.name, AGENT_A)
        frappe.set_user(AGENT_A)
        self.assertEqual(get_unseen_assignment_count(), 1)
        frappe.set_user(AGENT_B)
        self.assertEqual(get_unseen_assignment_count(), 0)

    def test_patch_marks_existing_assignments_seen(self):
        assign_ticket(self.ticket.name, AGENT_A)
        run_patch()
        self.assertEqual(HDTicketView.get_unseen_count(AGENT_A), 0)
