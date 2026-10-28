import type { TicketAnalytics } from "@/components/ticket-agent/analytics/types";
import { __ } from "@/translation";
import type {
  DocumentResource,
  RecentSimilarTicket,
  Resource,
  TicketActivities,
  TicketAssignee,
  TicketContact,
} from "@/types";
import type { HDTicket } from "@/types/doctypes";
import { call, createDocumentResource, createResource, toast } from "frappe-ui";
import { reactive } from "vue";

interface MapValue {
  ticket: DocumentResource<HDTicket>;
  assignees: Resource<TicketAssignee[]>;
  contact: Resource<TicketContact>;
  recentSimilarTickets: Resource<RecentSimilarTicket>;
  activities: Resource<TicketActivities>;
  analytics: Resource<TicketAnalytics>;
}

const ticketMap: Record<string, MapValue> = reactive({});

export const useTicket = (ticketId: string | number): MapValue => {
  if (!ticketMap[ticketId]) {
    ticketMap[ticketId] = {
      ticket: createDocumentResource<HDTicket>({
        doctype: "HD Ticket",
        name: ticketId,
        whitelistedMethods: {
          markSeen: "mark_seen",
        },
        setValue: {
          onSuccess: () => {
            toast.success(__("Ticket updated successfully."));
          },
          onError: (error) => {
            const msg = error.exc_type
              ? (error.messages || error.message || []).join(", ")
              : error.message;
            toast.error(msg);
          },
        },
      }),
      assignees: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_assignees",
        params: { ticket: ticketId },
        auto: true,
      }),
      contact: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_contact",
        params: { ticket: ticketId },
        auto: true,
      }),
      recentSimilarTickets: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_recent_similar_tickets",
        params: { ticket: ticketId },
        auto: true,
      }),
      activities: createResource({
        url: "helpdesk.helpdesk.doctype.hd_ticket.api.get_ticket_activities",
        params: { ticket: ticketId },
        auto: true,
      }),
      // fetched by the analytics tab, not on ticket open
      analytics: createResource({
        url: "helpdesk.api.ticket_analytics.get_ticket_analytics",
        params: { ticket: ticketId },
        cache: ["Ticket", ticketId, "analytics"],
      }),
    };
  }

  return ticketMap[ticketId];
};

// After a Team change, unassign anyone who is not on the new Team, then refresh.
// A cleared Team keeps the assignees, as there is nothing left to restrict by.
export async function dropAssigneesOutsideTeam(
  ticketId: string | number,
  team?: string | null
) {
  const ticketData = ticketMap[ticketId];
  if (!ticketData) return;
  try {
    const assigned = (ticketData.assignees.data || []).map((a) => a.name);
    if (!team || !assigned.length) return;
    const members: string[] = await call(
      "helpdesk.helpdesk.doctype.hd_team.hd_team.get_team_members",
      { team }
    );
    const outside = assigned.filter((name) => !members.includes(name));
    if (!outside.length) return;
    await call("helpdesk.api.doc.remove_assignments", {
      doctype: "HD Ticket",
      name: ticketId,
      assignees: outside,
    });
  } finally {
    ticketData.assignees.reload();
  }
}

export function reloadTicket(ticketId: string) {
  const ticketData = ticketMap[ticketId];
  if (!ticketData) return;
  ticketData.ticket.reload();
  ticketData.assignees.reload();
  ticketData.activities.reload();
}

// Refresh a ticket that may have gone stale
export function revalidateTicket(ticketId: string | number) {
  const ticketData = ticketMap[ticketId];
  if (ticketData?.ticket.get.fetched && !ticketData.ticket.get.loading) {
    reloadTicket(ticketId as string);
  }
}
