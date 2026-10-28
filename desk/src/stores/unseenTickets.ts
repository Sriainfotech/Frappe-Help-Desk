import { useAuthStore } from "@/stores/auth";
import { useDocumentVisibility } from "@vueuse/core";
import { createResource } from "frappe-ui";
import { defineStore } from "pinia";
import { computed, watch } from "vue";
import { globalStore } from "./globalStore";

const MAX_DISPLAY = 99;

/** Open tickets assigned to the current agent that they have not opened yet. */
export const useUnseenTicketsStore = defineStore("unseen-tickets", () => {
  const authStore = useAuthStore();
  const { $socket } = globalStore();
  const visibility = useDocumentVisibility();

  const resource = createResource({
    url: "helpdesk.api.ticket.get_unseen_assignment_count",
    method: "GET",
    auto: false,
  });

  const count = computed<number>(() => resource.data || 0);
  const label = computed(() =>
    count.value > MAX_DISPLAY ? `${MAX_DISPLAY}+` : String(count.value)
  );

  function reload() {
    if (!authStore.isAgent) return;
    resource.reload();
  }

  // Shown before the refetch confirms, so the count drops as the ticket opens
  function decrement() {
    if (count.value > 0) resource.setData(count.value - 1);
  }

  watch(() => authStore.isAgent, reload, { immediate: true });

  // A socket event can be missed while the tab sleeps, so refetch on return
  watch(visibility, (state) => state === "visible" && reload());

  $socket.on("helpdesk:unseen-tickets-update", reload);

  return { count, label, reload, decrement };
});
