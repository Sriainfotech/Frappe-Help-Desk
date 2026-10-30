<template>
  <Dialog
    v-model:open="open"
    :title="__('Add Task')"
    size="lg"
    @after-leave="reset"
  >
    <template #default>
      <!-- novalidate: field errors below are translated and consistent, unlike the browser bubble.
           Ctrl/Cmd+Enter saves from anywhere; plain Enter in the title must not submit. -->
      <form
        class="flex max-h-[calc(100vh-8rem)] flex-col gap-4"
        novalidate
        @submit.prevent="save"
        @keydown.ctrl.enter.prevent="save"
        @keydown.meta.enter.prevent="save"
      >
        <ErrorMessage
          v-if="loadError"
          :message="__('Could not load the form options: {0}', [loadError])"
        />
        <p v-if="projectLabel" class="-mt-3 text-p-sm text-ink-gray-5">
          {{ __("New task in {0}", [projectLabel]) }}
        </p>
        <!-- Only this body scrolls, and only on short screens; the footer stays put. -->
        <div
          class="-mx-1 grid min-h-0 flex-1 grid-cols-2 content-start gap-4 overflow-y-auto px-1 pb-1"
        >
          <FormControl
            v-model="form.subject"
            class="col-span-2"
            autofocus
            :label="__('Task Title')"
            :required="true"
            :placeholder="__('Enter task title')"
            :error="errors.subject"
            @keydown.enter.exact.prevent
          />
          <FormControl
            v-model="form.project"
            class="col-span-2"
            type="select"
            :label="__('Project')"
            :placeholder="__('Select project')"
            :options="projectOptions"
            :disabled="projects.loading"
            :description="hint(projects.loading, projectOptions, __('No projects exist yet'))"
          />
          <FormControl
            v-model="form.milestone"
            class="col-span-2"
            type="select"
            :label="__('Milestone')"
            :options="milestoneOptions"
            :disabled="options.loading"
            :description="
              form.project &&
              !options.loading &&
              !options.data?.milestones?.length
                ? __('This project has no milestones yet')
                : ''
            "
          />

          <div class="col-span-2 flex items-center justify-between gap-3">
            <span class="text-base text-ink-gray-5">{{ __("Assign to") }}</span>
            <TabButtons v-model="form.assignee_type" :buttons="assigneeTypes" />
          </div>
          <template v-if="form.assignee_type === 'Employee'">
            <FormControl
              v-model="form.department"
              type="select"
              :label="__('Department')"
              :options="departmentOptions"
              :disabled="options.loading"
            />
            <FormControl
              v-model="form.designation"
              type="select"
              :label="__('Designation')"
              :options="designationOptions"
              :disabled="options.loading"
              :description="
                !options.loading && !options.data?.designations?.length
                  ? __('No designations exist yet')
                  : ''
              "
            />
            <FormControl
              v-model="form.assigned_to"
              class="col-span-2"
              type="select"
              :label="__('Select Employee')"
              :placeholder="__('Select employee')"
              :options="employeeOptions"
              :disabled="options.loading"
              :description="
                !options.loading && !options.data?.employees?.length
                  ? __('No employees match the selected department')
                  : ''
              "
            />
          </template>
          <FormControl
            v-else
            v-model="form.freelancer"
            class="col-span-2"
            type="select"
            :label="__('Select Freelancer')"
            :placeholder="__('Select freelancer')"
            :options="freelancerOptions"
            :disabled="options.loading"
            :error="errors.freelancer"
            :description="
              !options.loading && !options.data?.freelancers?.length
                ? __('No freelancers exist yet')
                : ''
            "
          />

          <FormControl
            v-model="form.status"
            class="col-span-2"
            type="select"
            :label="__('Status')"
            :options="STATUSES.map((s) => ({ label: __(s), value: s }))"
          />
          <FormControl
            v-if="form.status === 'Blocked'"
            v-model="form.blocked_reason"
            class="col-span-2"
            type="textarea"
            :label="__('Blocked reason')"
            :placeholder="__('Why is this task blocked?')"
            :error="errors.blocked_reason"
          />
          <FormControl
            v-model="form.start_date"
            type="date"
            :label="__('Start Date (Optional)')"
            placeholder="dd-mm-yyyy"
          />
          <FormControl
            v-model="form.due_date"
            type="date"
            :label="__('End Date (Optional)')"
            placeholder="dd-mm-yyyy"
            :error="errors.due_date"
          />
        </div>

        <ErrorMessage v-if="errors.form" :message="errors.form" />
        <div class="flex shrink-0 justify-end gap-2">
          <Button
            type="button"
            :label="__('Cancel')"
            variant="subtle"
            @click="open = false"
          />
          <Button
            type="submit"
            :label="__('Add Task')"
            theme="gray"
            variant="solid"
            :loading="saving"
          />
        </div>
      </form>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { __ } from "@/translation";
import {
  Button,
  call,
  createListResource,
  createResource,
  Dialog,
  ErrorMessage,
  FormControl,
  TabButtons,
  toast,
} from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import { STATUSES } from "./taskMeta";

const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ created: [name: string] }>();

const authStore = useAuthStore();

const projects = createListResource({
  doctype: "HD Task Project",
  fields: ["name", "project_name"],
  pageLength: 999,
  auto: false,
});

// Milestones follow the project and employees follow the department, so both are refetched on change.
const options = createResource({
  url: "helpdesk.api.task.get_task_form_options",
  auto: false,
});

const assigneeTypes = [
  { label: __("Employee"), value: "Employee" },
  { label: __("Freelancer"), value: "Freelancer" },
];

const blank = () => ({
  subject: "",
  project: "",
  milestone: "",
  assignee_type: "Employee",
  department: "",
  designation: "",
  assigned_to: authStore.userId,
  freelancer: "",
  status: "Planned",
  blocked_reason: "",
  start_date: "",
  due_date: "",
});
const form = reactive(blank());
const errors = reactive<Record<string, string>>({});
const saving = ref(false);

const withBlank = (label: string, rows: { label: string; value: string }[]) => [
  { label, value: "" },
  ...rows,
];
const projectOptions = computed(() =>
  (projects.data || []).map((p) => ({ label: p.project_name, value: p.name }))
);
const projectLabel = computed(
  () => projectOptions.value.find((p) => p.value === form.project)?.label
);
const milestoneOptions = computed(() =>
  withBlank(
    __("No milestone"),
    (options.data?.milestones || []).map((m) => ({
      label: m.milestone_name,
      value: m.name,
    }))
  )
);
const departmentOptions = computed(() =>
  withBlank(
    __("All departments"),
    (options.data?.departments || []).map((d) => ({ label: d, value: d }))
  )
);
const designationOptions = computed(() =>
  withBlank(
    __("All designations"),
    (options.data?.designations || []).map((d) => ({ label: d, value: d }))
  )
);
// Two agents can share a display name, so add the user id when a name repeats.
const employeeOptions = computed(() => {
  const employees = options.data?.employees || [];
  const names = employees.map((e) => e.agent_name || e.user);
  return withBlank(
    "",
    employees.map((e, i) => ({
      label:
        names.filter((n) => n === names[i]).length > 1
          ? `${names[i]} (${e.user})`
          : names[i],
      value: e.user,
    }))
  );
});
const freelancerOptions = computed(() =>
  withBlank(
    "",
    (options.data?.freelancers || []).map((f) => ({
      label: f.freelancer_name,
      value: f.name,
    }))
  )
);

const loadError = computed(
  () => options.error?.messages?.[0] || options.error?.message || ""
);

function hint(loading: boolean, rows: unknown[], emptyText: string) {
  return !loading && !rows.length ? emptyText : "";
}

function loadOptions() {
  return options.fetch({
    project: form.project || null,
    department: form.department || null,
  });
}

watch(open, (isOpen) => {
  if (!isOpen) return;
  projects.fetch();
  loadOptions();
  form.assigned_to = authStore.userId;
});

watch(
  () => form.project,
  () => {
    form.milestone = "";
    loadOptions();
  }
);
watch(
  () => form.department,
  async () => {
    await loadOptions();
    // The chosen employee may not be in the new department.
    if (
      form.assigned_to &&
      !(options.data?.employees || []).some((e) => e.user === form.assigned_to)
    )
      form.assigned_to = "";
  }
);

function reset() {
  Object.assign(form, blank());
  Object.keys(errors).forEach((key) => delete errors[key]);
}

function validate() {
  Object.keys(errors).forEach((key) => delete errors[key]);
  if (!form.subject.trim()) errors.subject = __("Task title is required");
  if (form.assignee_type === "Freelancer" && !form.freelancer)
    errors.freelancer = __("Select a freelancer");
  if (form.status === "Blocked" && !form.blocked_reason.trim())
    errors.blocked_reason = __("Blocked reason is required");
  if (form.start_date && form.due_date && form.due_date < form.start_date)
    errors.due_date = __("End date cannot be earlier than the start date");
  return !Object.keys(errors).length;
}

async function save() {
  if (saving.value || !validate()) return;
  const isEmployee = form.assignee_type === "Employee";
  saving.value = true;
  try {
    const doc = await call("frappe.client.insert", {
      doc: {
        doctype: "HD Task",
        subject: form.subject.trim(),
        status: form.status,
        blocked_reason: form.status === "Blocked" ? form.blocked_reason : null,
        project: form.project || null,
        milestone: form.milestone || null,
        assignee_type: form.assignee_type,
        department: isEmployee ? form.department || null : null,
        designation: isEmployee ? form.designation || null : null,
        assigned_to: isEmployee ? form.assigned_to || null : null,
        freelancer: isEmployee ? null : form.freelancer || null,
        start_date: form.start_date || null,
        due_date: form.due_date || null,
      },
    });
    toast.success(__("Task {0} created", [doc.name]));
    open.value = false;
    emit("created", doc.name);
  } catch (e: any) {
    errors.form =
      e?.messages?.[0] || e?.message || __("Could not create the task");
  } finally {
    saving.value = false;
  }
}
</script>
