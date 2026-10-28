# Unseen Ticket Count

The **Tickets** item in the agent sidebar reads `Tickets (3)` when the logged-in
agent has open tickets assigned to them that they have not opened since being
assigned. It reads plain `Tickets` at 0 and caps at `Tickets (99+)`. With the
sidebar collapsed the label is hidden, so a dot shows on the icon instead.

## Rules

- **Counted:** an open ToDo on an HD Ticket allocated to the agent, where the
  ticket's `status_category` is `Open`, and the agent has no HD Ticket View row
  with `seen_at` at or after the ToDo's `creation`.
- **Seen:** the agent opens the ticket page (`TicketAgent.vue` calls the existing
  `HDTicket.mark_seen` on mount). Only an assignee gets a View row. Anyone else
  opening the ticket changes nothing.
- **Reassigned or unassigned:** core cancels the old ToDo, so it drops out of the
  old agent's count. The new agent's ToDo is newer than any earlier `seen_at`,
  so it counts for them, including when a ticket comes back to an agent who
  had already seen it.
- **Per agent:** every query and realtime event is scoped to one user.

## Why the existing pieces were not used for the count

| Existing | Why not |
|---|---|
| `_seen` on HD Ticket (`track_seen`) | Means "seen the latest activity". An agent who viewed the ticket before a reassignment would already be in it. It is a JSON column and cannot be indexed. Left untouched; the bold unread rows in the list still use it. |
| HD Notification `Assignment` + `read` | Only `HDTicket.assign_agent` creates one. The assign dialog, bulk assign, command palette and assignment rules call `frappe.desk.form.assign_to` directly. Adding notifications for those would change the bell for everyone. |
| Sidebar `item.badge` pill | Used as-is by Notifications. Tickets uses a literal `(n)` in the label instead, as requested. |

ToDo is the one record every assign and unassign path writes, so it is the
source of truth for "assigned to me". Nothing in the existing assignment code
was changed.

## Backend

- **`HD Ticket View`** (`ticket`, `user`, `seen_at`), unique on
  `(ticket, user)`. It is overwritten on each open rather than deleted on
  reassignment; comparing `seen_at` with the ToDo's `creation` gives the reset.
  System Manager read only, written with `ignore_permissions`.
- **Index:** `on_doctype_update` adds `(allocated_to, status, reference_type)`
  on `ToDo`, which core leaves unindexed.
- **`HDTicketView.get_unseen_count(user)`**: one query, ToDo joined to HD Ticket,
  left joined to HD Ticket View.
- **`GET helpdesk.api.ticket.get_unseen_assignment_count`** (agents only): the
  count for the session user.
- **`HDTicket.mark_seen`** now also calls `mark_seen_by_assignee`, and returns
  `True` if that cleared a counted ticket, so the client only lowers its count
  when there was something to lower.
- **Realtime:** `helpdesk:unseen-tickets-update`, sent to one user's room after
  commit, from:
  - `ToDo` `on_update` (status or assignee changed, incl. insert) and
    `on_trash`, via `helpdesk/extends/todo.py`
  - `HDTicket.on_update` when `status_category` changes, to all assignees
  - `mark_seen_by_assignee`, for the agent's other tabs

## Frontend

- **`stores/unseenTickets.ts`**: loads for agents, reloads on the socket event
  and when the browser tab becomes visible again (a sleeping tab can miss
  socket events).
- **`AppSidebar.vue`**: adds the count to the Tickets item label, agent portal
  only.
- **`useTicket.ts`**: after `markSeen` returns `True`, lowers the count by one
  and refetches to confirm.

## Migration

`helpdesk.patches.mark_existing_assignments_seen` (post model sync) creates
the indexes, then a View row for every open HD Ticket assignment, so nobody
starts with a count after the upgrade.

## Tests

- `helpdesk/api/test_unseen_assignments.py`: count per agent, mark seen,
  non-assignee open, reassign, unassign, reassign after seen, non-open status,
  endpoint, patch.
- `e2e/tests/unseen-tickets.spec.ts`: the label shows on assignment without a
  reload and clears when the ticket is opened.
