import { expect, test, usePersona } from "../helpers/fixtures";
import { emailOf } from "../helpers/personas";

usePersona("agent");

const COUNT_METHOD = "helpdesk.api.ticket.get_unseen_assignment_count";

// Opens every ticket the agent has not seen, so each test starts at zero
test.beforeEach(async ({ apiAs }) => {
  const agent = await apiAs("agent");
  const todos = await agent.call("frappe.client.get_list", {
    doctype: "ToDo",
    filters: {
      reference_type: "HD Ticket",
      allocated_to: emailOf("agent"),
      status: "Open",
    },
    fields: ["reference_name"],
    limit_page_length: 0,
  });
  for (const { reference_name } of todos) {
    await agent.call("run_doc_method", {
      dt: "HD Ticket",
      dn: reference_name,
      method: "mark_seen",
    });
  }
  expect(await agent.call(COUNT_METHOD)).toBe(0);
});

test("the Tickets count shows on assignment and clears on open", async ({
  page,
  apiAs,
}) => {
  const agent = await apiAs("agent");
  const ticketsItem = page.getByRole("button", { name: /^Tickets/ });

  await page.goto("/helpdesk/tickets");
  await expect(ticketsItem).toHaveText("Tickets");

  const ticket = await agent.call("frappe.client.insert", {
    doc: { doctype: "HD Ticket", subject: "Unseen count e2e" },
  });
  await agent.call("frappe.desk.form.assign_to.add", {
    doctype: "HD Ticket",
    name: ticket.name,
    assign_to: [emailOf("agent")],
  });

  // arrives over the socket, no reload
  await expect(ticketsItem).toHaveText("Tickets (1)");

  await page.goto(`/helpdesk/tickets/${ticket.name}`);
  await expect(ticketsItem).toHaveText("Tickets");
});
