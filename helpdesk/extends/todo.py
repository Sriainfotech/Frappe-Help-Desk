from helpdesk.helpdesk.doctype.hd_ticket_view.hd_ticket_view import HDTicketView


def on_update(doc, method=None):
    """Every assign path (dialog, bulk, palette, assignment rules) and unassign
    ends in a ToDo save, so the assignee's badge is refreshed from here."""
    if doc.reference_type != "HD Ticket":
        return
    # both are True on insert, as there is no doc before save
    if not (doc.has_value_changed("status") or doc.has_value_changed("allocated_to")):
        return

    before = doc.get_doc_before_save()
    for user in {doc.allocated_to, before and before.allocated_to}:
        if user:
            HDTicketView.notify(user)


def on_trash(doc, method=None):
    if doc.reference_type == "HD Ticket" and doc.allocated_to:
        HDTicketView.notify(doc.allocated_to)
