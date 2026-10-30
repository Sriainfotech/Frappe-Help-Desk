import { createApp, h } from "vue";
import {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  frappeRequest,
  FrappeUI,
  setConfig,
  TextInput,
  toast,
  Tooltip,
} from "frappe-ui";
import { createPinia } from "pinia";
import App from "./App.vue";
import { spritePlugin } from "frappe-ui/icons";
import { createDialog } from "./components/dialogs";
import "./index.css";
import { router } from "./router";
import { telemetryPlugin } from "frappe-ui/frappe";
import { isCustomerPortal } from "@/utils";
import { translationPlugin } from "./translation";
import CircleAlert from "~icons/lucide/circle-alert";
import { initSocket, socket as sharedSocket } from "./socket";

const globalComponents = {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FeatherIcon,
  FormControl,
  Tooltip,
  TextInput,
};

setConfig("resourceFetcher", frappeRequest);
setConfig("serverMessagesHandler", (msgs) => {
  if (isCustomerPortal.value) {
    return;
  }
  msgs.forEach((msg) => {
    msg = JSON.parse(msg);
    if (msg && msg.message == "Feedback email has been sent to the customer.") {
      toast.success(msg.message);
      return;
    }
    toast.create({
      message: msg.message,
      icon: h(CircleAlert, { class: "text-ink-accent-5" }),
    });
  });
});
setConfig("fallbackErrorHandler", (error) => {
  const msg = error.exc_type
    ? (error.messages || error.message || []).join(", ")
    : error.message;
  toast.error(msg);
});

const pinia = createPinia();
const app = createApp(App);

// HD Task module / docker: frappe-ui's built-in initSocket dials :9000 whenever location.port is set.
// desk creates its own same-origin socket below, so skip the plugin's one.
app.use(FrappeUI, { socketio: false });
app.use(spritePlugin);
app.use(pinia);
app.use(router);
app.use(translationPlugin);
// HD Task module / docker: Frappe 15.122 has no pulse `boot_config` method, so the plugin 417s on boot.
// Off by default; set VITE_ENABLE_PULSE_TELEMETRY=true at build time once Frappe is upgraded.
const ENABLE_PULSE_TELEMETRY = import.meta.env.VITE_ENABLE_PULSE_TELEMETRY === "true";
if (ENABLE_PULSE_TELEMETRY) {
  app.use(telemetryPlugin, { app_name: "helpdesk" });
}

for (const c in globalComponents) {
  app.component(c, globalComponents[c]);
}

app.config.globalProperties.$dialog = createDialog;

let socket;
if (import.meta.env.DEV) {
  frappeRequest({
    url: "/api/method/helpdesk.www.helpdesk.index.get_context_for_dev",
  }).then((values) => {
    for (let key in values) {
      window[key] = values[key];
    }
    if (window.dir) document.documentElement.dir = window.dir;
    if (window.lang) document.documentElement.lang = window.lang;
    socket = initSocket();
    app.config.globalProperties.$socket = socket;
    app.mount("#app");
  });
} else {
  // HD Task module / docker: reuse the socket created on import of ./socket instead of opening a second one.
  socket = sharedSocket;
  app.config.globalProperties.$socket = socket;
  app.mount("#app");
}
