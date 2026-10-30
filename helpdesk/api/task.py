from typing import Any

import frappe
from bs4 import BeautifulSoup
from frappe import _
from frappe.utils import get_last_day_of_week, today
from frappe.utils.html_utils import sanitize_html

from helpdesk.utils import agent_only

DOCTYPE = "HD Task"
CLOSED_STATUSES = ["Completed", "Cancelled"]
VIEWS = ("my", "all", "overdue", "due_this_week", "unassigned")
LIST_FIELDS = [
    "name",
    "subject",
    "status",
    "priority",
    "assigned_to",
    "reviewer",
    "project",
    "milestone",
    "assignee_type",
    "freelancer",
    "start_date",
    "due_date",
    "progress",
    "owner",
    "creation",
]
MAX_PAGE_SIZE = 100


def parse_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    return frappe.parse_json(value) if isinstance(value, str) else value


def view_filters(view: str) -> list[list]:
    """Filters that define each view. Record-level access is applied by get_list itself."""
    if view not in VIEWS:
        frappe.throw(_("Unknown view {0}").format(view))

    if view == "my":
        return [[DOCTYPE, "assigned_to", "=", frappe.session.user]]
    if view == "overdue":
        # get_list treats a NULL date as the earliest date, so "<" alone would match it
        return [
            [DOCTYPE, "due_date", "is", "set"],
            [DOCTYPE, "due_date", "<", today()],
            [DOCTYPE, "status", "not in", CLOSED_STATUSES],
        ]
    if view == "due_this_week":
        return [
            [DOCTYPE, "due_date", "between", [today(), get_last_day_of_week(today())]],
            [DOCTYPE, "status", "not in", CLOSED_STATUSES],
        ]
    if view == "unassigned":
        return [[DOCTYPE, "assigned_to", "is", "not set"]]
    return []


def count_tasks(filters: list[list]) -> int:
    rows = frappe.get_list(
        DOCTYPE, filters=filters, fields=["count(name) as count"], limit_page_length=0
    )
    return rows[0].count if rows else 0


def user_details(users: set[str]) -> dict[str, dict]:
    users.discard(None)
    if not users:
        return {}
    rows = frappe.get_all(
        "User",
        filters={"name": ["in", list(users)]},
        fields=["name", "full_name", "user_image"],
    )
    return {row.name: row for row in rows}


def attach_user_details(rows: list[dict]) -> list[dict]:
    users = {r[key] for r in rows for key in ("assigned_to", "reviewer", "owner")}
    details = user_details(users)
    for row in rows:
        row["assignee"] = details.get(row.assigned_to)
        row["reviewer_details"] = details.get(row.reviewer)
        row["creator"] = details.get(row.owner)
    return rows


def load_for_update(name: str):
    """Lock the row before reading it, so two simultaneous edits queue up instead of the
    second failing with a TimestampMismatchError (e.g. a double-clicked checklist box)."""
    frappe.db.get_value(DOCTYPE, name, "name", for_update=True)
    return frappe.get_doc(DOCTYPE, name)


@frappe.whitelist(methods=["GET", "POST"])
@agent_only
def get_tasks(
    filters: dict | str | None = None,
    view: str = "my",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    filters = parse_json(filters, {})
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
    page = max(1, int(page))

    conditions = view_filters(view)
    for fieldname in ("status", "priority", "assigned_to", "project"):
        if filters.get(fieldname):
            conditions.append([DOCTYPE, fieldname, "=", filters[fieldname]])

    or_filters = []
    if search := (filters.get("search") or "").strip():
        or_filters = [
            [DOCTYPE, "subject", "like", f"%{search}%"],
            [DOCTYPE, "name", "like", f"%{search}%"],
        ]

    rows = frappe.get_list(
        DOCTYPE,
        filters=conditions,
        or_filters=or_filters,
        fields=LIST_FIELDS,
        order_by="creation desc",
        limit_start=(page - 1) * page_size,
        limit_page_length=page_size,
    )
    total = frappe.get_list(
        DOCTYPE,
        filters=conditions,
        or_filters=or_filters,
        fields=["count(name) as count"],
        limit_page_length=0,
    )[0].count

    return {
        "data": attach_user_details(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@frappe.whitelist(methods=["GET", "POST"])
@agent_only
def get_task_form_options(project: str | None = None, department: str | None = None) -> dict:
    """Choices for the Add Task form. Milestones follow `project`; employees (active agents)
    are narrowed to the members of the `department` (an HD Team) when one is given."""
    milestones = []
    if project:
        milestones = frappe.get_all(
            "HD Task Milestone",
            filters={"project": project},
            fields=["name", "milestone_name"],
            order_by="creation asc",
        )

    agent_filters = {"is_active": 1}
    if department:
        members = frappe.get_all(
            "HD Team Member", filters={"parent": department}, pluck="user"
        )
        agent_filters["user"] = ["in", members or [""]]

    return {
        "milestones": milestones,
        "departments": frappe.get_all("HD Team", filters={"disabled": 0}, pluck="name"),
        "designations": frappe.get_all("HD Task Designation", pluck="name"),
        "freelancers": frappe.get_all(
            "HD Task Freelancer", fields=["name", "freelancer_name"]
        ),
        "employees": frappe.get_all(
            "HD Agent", filters=agent_filters, fields=["user", "agent_name"]
        ),
    }


@frappe.whitelist(methods=["GET", "POST"])
@agent_only
def get_task_counts() -> dict:
    counts = {view: count_tasks(view_filters(view)) for view in VIEWS}
    counts["open"] = count_tasks([[DOCTYPE, "status", "not in", CLOSED_STATUSES]])
    return counts


@frappe.whitelist(methods=["GET", "POST"])
@agent_only
def get_task(name: str) -> dict:
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("read")

    task = doc.as_dict()
    task["description"] = sanitize_html(doc.description or "")
    task.update(
        {
            "assignee": None,
            "reviewer_details": None,
            "creator": None,
            "attachments": get_attachments(name),
            "comments": get_comments(name),
            "activity": get_activity(name),
            "permissions": {
                "write": doc.has_permission("write"),
                "delete": doc.has_permission("delete"),
            },
        }
    )
    attach_user_details([task])
    return task


def get_attachments(name: str) -> list[dict]:
    return frappe.get_all(
        "File",
        filters={"attached_to_doctype": DOCTYPE, "attached_to_name": name},
        fields=["name", "file_name", "file_url", "file_size", "is_private", "creation"],
        order_by="creation asc",
    )


def get_comments(name: str) -> list[dict]:
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": DOCTYPE,
            "reference_name": name,
            "comment_type": "Comment",
        },
        fields=["name", "content", "owner", "comment_email", "creation"],
        order_by="creation asc",
    )
    details = user_details({c.owner for c in comments})
    for comment in comments:
        comment["content"] = sanitize_html(comment.content or "")
        comment["user"] = details.get(comment.owner)
    return comments


def get_activity(name: str) -> list[dict]:
    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": DOCTYPE, "docname": name},
        fields=["name", "data", "owner", "creation"],
        order_by="creation desc",
    )
    details = user_details({v.owner for v in versions})
    activity = []
    for version in versions:
        data = frappe.parse_json(version.data or "{}")
        changes = [
            {"field": field, "old": old, "new": new}
            for field, old, new in data.get("changed", [])
        ]
        if data.get("added") or data.get("removed") or data.get("row_changed"):
            changes.append({"field": "checklist", "old": None, "new": None})
        if changes:
            activity.append(
                {
                    "creation": version.creation,
                    "user": details.get(version.owner),
                    "changes": changes,
                }
            )
    return activity


@frappe.whitelist(methods=["POST"])
@agent_only
def update_status(name: str, status: str, reason: str | None = None) -> dict:
    doc = load_for_update(name)
    apply_status(doc, status, reason)
    return get_task(name)


def apply_status(doc, status: str, reason: str | None = None) -> None:
    doc.check_permission("write")
    doc.flags.status_reason = reason
    if status == "Blocked":
        doc.blocked_reason = reason
    doc.status = status
    doc.save()


@frappe.whitelist(methods=["POST"])
@agent_only
def update_checklist(name: str, checklist: list | str) -> dict:
    items = parse_json(checklist, [])
    doc = load_for_update(name)
    doc.check_permission("write")
    doc.set("checklist", [])
    for item in items:
        text = (item.get("item") or "").strip()
        if text:
            doc.append("checklist", {"item": text, "done": 1 if item.get("done") else 0})
    doc.save()
    return get_task(name)


@frappe.whitelist(methods=["POST"])
@agent_only
def add_comment(name: str, content: str) -> dict:
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("read")
    if not (content or "").strip():
        frappe.throw(_("Comment cannot be empty"))
    doc.add_comment("Comment", restrict_mentions(doc, sanitize_html(content)))
    return get_task(name)


def restrict_mentions(doc, content: str) -> str:
    """Core notifies every @mentioned user with the comment text, without checking that
    they can open the document. Turn mentions of users who cannot read this task (and
    group mentions, which expand to unchecked members) into plain text."""
    soup = BeautifulSoup(content, "html.parser")
    for node in soup.find_all(class_="mention"):
        user = node.get("data-id")
        allowed = (
            node.get("data-is-group") != "true"
            and user
            and frappe.db.get_value("User", {"name": user, "enabled": 1})
            and frappe.has_permission(DOCTYPE, "read", doc=doc, user=user)
        )
        if not allowed:
            node.replace_with("@" + node.get_text().lstrip("@"))
    return str(soup)


@frappe.whitelist(methods=["GET", "POST"])
@agent_only
def get_mentionable_users(name: str) -> list[dict]:
    """Active agents who can read this task, as `{id, label}` for the editor's @ list."""
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("read")
    agents = frappe.get_all(
        "HD Agent", filters={"is_active": 1}, fields=["user", "agent_name"]
    )
    return [
        {"id": a.user, "label": a.agent_name or a.user}
        for a in agents
        if frappe.has_permission(DOCTYPE, "read", doc=doc, user=a.user)
    ]


@frappe.whitelist(methods=["POST"])
@agent_only
def bulk_assign(names: list | str, assigned_to: str) -> dict:
    def assign(doc):
        doc.check_permission("write")
        doc.assigned_to = assigned_to
        doc.save()

    return run_bulk(names, assign)


@frappe.whitelist(methods=["POST"])
@agent_only
def bulk_update_status(
    names: list | str, status: str, reason: str | None = None
) -> dict:
    return run_bulk(names, lambda doc: apply_status(doc, status, reason))


def run_bulk(names: list | str, action) -> dict:
    """Run `action` per task so one rejected task never blocks the rest."""
    result = {"updated": [], "failed": []}
    for name in parse_json(names, []):
        frappe.db.savepoint("hd_task_bulk")
        try:
            action(load_for_update(name))
            result["updated"].append(name)
        except Exception as e:
            frappe.db.rollback(save_point="hd_task_bulk")
            result["failed"].append({"name": name, "error": str(e)})
    return result
