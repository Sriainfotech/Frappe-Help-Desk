# Task Management

Standalone internal work items for agents. Tasks share authentication, users, permissions, attachments, comments and
version history with the rest of Helpdesk, but have **no relationship to Tickets or Customers**: no link field, no
shared notifications, no hooks on ticket events.

## DocTypes

| DocType                  | Notes                                                                           |
| ------------------------ | ------------------------------------------------------------------------------- |
| `HD Task`                | Autoname `TASK-.####`, title field `subject`, track changes on.                 |
| `HD Task Project`        | Autoname from `project_name`. Optional grouping for tasks.                      |
| `HD Task Checklist Item` | Child table (`istable`): `item` (required), `done` (default 0).                 |
| `HD Task Milestone`      | Autoname `MS-####`. `milestone_name` and `project` (both required).             |
| `HD Task Designation`    | Autoname from `designation_name`. Master for the Add Task form's Designation.   |
| `HD Task Freelancer`     | Autoname from `freelancer_name`; optional `email`. Master for freelancer assignees. |

`HD Task` fields: `subject` (required), `description`, `status` (default Planned), `priority` (default Medium),
`assigned_to` (defaults to the creator), `reviewer`, `project`, `milestone`, `assignee_type` (Employee or Freelancer,
default Employee), `department` (an HD Team), `designation`, `freelancer`, `start_date`, `due_date`, `progress` (read-only,
server-calculated), `checklist`, `blocked_reason`, `completed_on` / `completed_by` (read-only).

## Workflow

Statuses: Planned, In Progress, In Review, Completed, Blocked, Cancelled. A new task may be created in any status (default
Planned); the transition table below applies to changes after creation. A task created as Blocked needs a Blocked Reason, and one
created as Completed gets `completed_on` / `completed_by` and 100% progress like any other completion.

| From        | To                        |
| ----------- | ------------------------- |
| Planned     | In Progress               |
| In Progress | In Review, Blocked        |
| Blocked     | In Progress               |
| In Review   | Completed, In Progress    |
| any         | Cancelled                 |

Every other move is rejected. All rules live in `HDTask.validate`, so they apply to the UI, the whitelisted APIs,
bulk operations and any other save (`frappe.client.*`, desk form, scripts).

- **Blocked** requires `blocked_reason`; the field is cleared on any other status.
- **In Review → In Progress** (return) requires a comment, stored as a core Comment and sent to the assignee.
- **In Review → Completed / In Progress** is limited to the task's reviewer or an Agent Manager / System Manager.
  The assignee can never approve their own task.
- **Completion** sets `completed_on` / `completed_by` from the server clock and session user and forces progress to
  100. Client-sent values are discarded. Reopening clears them.
- **Progress** = done checklist items / total, rounded half-up; 0 with no checklist.
- **Assignee type**: a Freelancer task requires `freelancer` and clears `assigned_to`, `department` and `designation`
  (and is not defaulted to the creator); an Employee task clears `freelancer`.
- **Milestone** must belong to the task's project.
- `due_date` may not precede `start_date`; `assigned_to` and `reviewer` must be enabled users.

## Permissions

| Role           | Access                                                                    |
| -------------- | ------------------------------------------------------------------------- |
| Agent          | Create, read and write tasks they own, are assigned to or review. No delete. |
| Agent Manager  | Full access to every task, including delete.                              |
| System Manager | Full access to every task, including delete.                              |

Enforced by DocType permissions plus `permission_query` (list filtering) and `has_permission` (document check) in
`hd_task.py`, registered in `hooks.py`. The API never trusts a user id from the client; the actor is always
`frappe.session.user`.

## API (`helpdesk.api.task`)

All endpoints require an Agent, Agent Manager or System Manager.

| Endpoint                | Purpose                                                                                 |
| ----------------------- | --------------------------------------------------------------------------------------- |
| `get_tasks`             | Paginated list. `view`: my, all, overdue, due_this_week, unassigned. `filters`: status, priority, assigned_to, project, search. `page_size` is capped at 100. |
| `get_task_form_options` | Choices for the Add Task form: milestones of `project`, departments (HD Teams), designations, freelancers, and active agents (narrowed to the `department` team's members). |
| `get_task_counts`       | Counts for each view plus open tasks.                                                   |
| `get_task`              | One task with checklist, attachments, comments and activity.                            |
| `update_status`         | Move a task through the workflow; `reason` is the blocked reason or return comment.     |
| `update_checklist`      | Replace the checklist; progress is recalculated server-side.                            |
| `add_comment`           | Add a comment (mentions are restricted to users who can access the task).               |
| `get_mentionable_users` | Users who may be mentioned on a task.                                                   |
| `bulk_assign`           | Assign many tasks. Each task is processed in its own savepoint; failures are reported per task. |
| `bulk_update_status`    | Same, for status changes.                                                               |

## Notifications

In-app only, through Frappe's `Notification Log` (not the Ticket `HD Notification`), best effort and never failing the
task operation. Nobody is notified of their own action.

- Assigned (on create and on reassignment) to the assignee.
- Returned from review, with the reviewer's comment, to the assignee.
- Overdue, to the assignee.

### Scheduler

`helpdesk.helpdesk.doctype.hd_task.hd_task.notify_overdue_tasks` runs daily (`scheduler_events["daily"]`). It finds
open tasks past their due date and sends one overdue notification per task per due date (the subject carries the due
date, so a moved due date can notify again).

## Frontend

The Tasks list uses the same generic list as Tickets (`ListViewBuilder` with `useView("HD Task")`), so it has the
Refresh / Filter / Sort / Columns controls, the 20 / 50 / 100 page-size footer and saved, private and public views.
The quick-filter inputs (ID, Subject, Status, Priority, Assigned To) are hidden (`hideQuickFilters`); filtering is
through the Filter button.

- Routes: `/helpdesk/tasks` (list) and `/helpdesk/tasks/:taskId` (detail page, `TaskPage.vue` reusing `TaskDetail.vue`).
  Sidebar entry **Tasks** directly after Contacts (`layoutSettings.ts`).
- Opening a task: clicking a row opens `TaskDetail` in a side panel next to the list (`?task=<name>` on the URL, so Back,
  refresh and shared links keep it open). Below `lg` the panel covers the list. The row link is replaced through the
  `onRowClick` option of `ListViewBuilder`, which also stops a cell click from applying a filter. The open row's subject
  is bold. Status changes in the panel reload the list. `/helpdesk/tasks/:taskId` still works as a full page.
- No default filter: the Tasks list always starts unfiltered. `skipDefaultViewFilters` ignores filters saved on the user's
  default `HD View` and stops saving new ones there, because a one-off Status filter would otherwise become the landing
  state. Sort and columns are still saved.
- Columns: `default_list_data` widths are proportional (`minmax(0, Nfr)`) so the list fits its width with no horizontal
  scrollbar.
- Header: breadcrumb `Tasks / List` with the view dropdown, and a **Create** button that opens `NewTaskDialog` (titled Add Task). Field order: Task Title (required), Project, Milestone
  (follows the project), an Employee/Freelancer switch, then for Employee the Department / Designation filters and
  Select Employee (Department narrows the employee list to that team), or for Freelancer a Select Freelancer dropdown,
  then Status (all six, default Planned; Blocked shows a required Blocked reason), Start Date and End Date (stored as
  `due_date`; may not precede the start). It saves with `frappe.client.insert`. There is no Allocated Hours field.
  **Decision:** HRMS is not connected in this phase, so Employee means an active HD Agent and Department means an HD Team.
  Designation has no employee data behind it yet: it is stored on the task but does not narrow the employee list.
- Default views (frontend only, no saved records): All tasks, My tasks, Overdue, Due this week, Unassigned. Each puts its
  filters on the URL (`?tview=...&filters=[...]`), see `viewFilters` in `taskMeta.ts`. `@me` is resolved server-side.
- Select banner: **Assign** and **Status** (`TaskBulkDialog.vue`, calling `bulk_assign` / `bulk_update_status`), plus the
  list's standard Delete for managers.
- Files: `desk/src/pages/tasks/`: `Tasks.vue`, `TaskPage.vue`, `TaskDetail.vue`, `NewTaskDialog.vue`,
  `TaskBulkDialog.vue`, `TaskReasonDialog.vue`, `TaskUser.vue`, `taskMeta.ts`.
- `useView` returns to the list the user is on after creating or deleting a view (it used to assume Tickets).

### List configuration

- Default columns come from `HDTask.default_list_data` (ID, Subject, Status, Priority, Assigned To, Due Date, Project);
  the generic list does not read `in_list_view`. Users change columns with the Columns button.
- Quick filters come from `in_standard_filter` on `subject`, `status`, `priority`, `assigned_to` and `project`, plus ID
  (`api/doc.py`, marked `# HD Task module`).
- `get_task_counts` is kept in the API but the list page no longer calls it.

## Migration note

The status `Open` was renamed `Planned`; patch `rename_task_open_status_to_planned` updates existing tasks so they stay
saveable.

## Running the tests

Tests need a throwaway site, never the live one:

```bash
bench --site <test-site> run-tests --module helpdesk.api.test_task
```

The module also asserts ticket independence: no `ticket`, `customer` or `reference_ticket` field exists, a task
lifecycle leaves tickets unchanged, and creating a ticket creates no tasks.

## Build and deploy

The local frontend cannot resolve `@framework/ui` outside a bench, so build in Docker:

```bash
docker/nxerp/build-local-image.sh <image-tag>   # base image + working-tree changes, frontend rebuilt
```

Then point `IMAGE` in `docker/nxerp/.env` at the tag, `docker compose -p nxerp-helpdesk --env-file .env up -d`, and run
`bench --site <site> migrate` (only needed when the DocTypes are not yet on the site) followed by `clear-cache`.
