import { call, useTheme } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { tokens } from "../generated/tokens";

// frappe-ui 1.0.0-beta.24 exposes `useTheme`; this wrapper keeps the same surface the app uses on
// newer frappe-ui (`colorScheme`, `resolvedColorScheme`, `setColorScheme`, `toggleColorScheme`),
// so components do not care which version they run on.
export type ColorScheme = "light" | "dark" | "system";

const DESK_VALUE: Record<ColorScheme, string> = {
  light: "Light",
  dark: "Dark",
  system: "Automatic",
};

let metaSynced = false;
const systemDark = ref(false);
let systemWatched = false;

function watchSystem() {
  if (systemWatched || typeof window === "undefined") return;
  systemWatched = true;
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  systemDark.value = query.matches;
  query.addEventListener("change", (e) => (systemDark.value = e.matches));
}

function isLoggedIn() {
  const user = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/)?.[1];
  return !!user && user !== "Guest";
}

// Keeps the choice on the user record so Frappe Desk and other devices agree.
function persist(scheme: ColorScheme) {
  if (!isLoggedIn()) return;
  call("helpdesk.api.theme.set_desk_theme", {
    theme: DESK_VALUE[scheme],
  }).catch(() => {});
}

function syncThemeColorMeta(resolved: "light" | "dark") {
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", tokens[resolved]["surface-base"]);
}

export function useAppTheme() {
  const theme = useTheme();
  watchSystem();

  const colorScheme = computed<ColorScheme>(() => theme.currentTheme.value);
  const resolvedColorScheme = computed<"light" | "dark">(() =>
    colorScheme.value === "system"
      ? systemDark.value
        ? "dark"
        : "light"
      : colorScheme.value
  );

  if (!metaSynced) {
    metaSynced = true;
    watch(resolvedColorScheme, syncThemeColorMeta, { immediate: true });
  }

  function setColorScheme(next: ColorScheme) {
    theme.setTheme(next);
    persist(next);
  }

  function toggleColorScheme() {
    theme.toggleTheme();
    persist(colorScheme.value);
  }

  return {
    colorScheme,
    resolvedColorScheme,
    setColorScheme,
    toggleColorScheme,
  };
}
