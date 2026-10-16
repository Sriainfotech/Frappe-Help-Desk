import os

import frappe
from frappe import _
from frappe.www.login import get_context as frappe_login_context

BRAND = "NXERP"
ASSETS = "/assets/helpdesk/nxerp_login"
LOGO = f"{ASSETS}/images/nxerp-logo.png"
FAVICON = f"{ASSETS}/images/favicon.png"
STOCK_NAMES = {"frappe", "helpdesk", "erpnext"}

no_cache = True


def get_context(context):
    """Build the stock login context (authentication, redirects, social login,
    2FA, sign-up flags - all the framework's own code) and only layer branding
    on top. Nothing is written to the database."""
    context = frappe_login_context(context) or context

    name = (context.get("app_name") or "").strip()
    if not name or name.lower() in STOCK_NAMES:
        context.app_name = BRAND

    logo = context.get("logo") or ""
    if not logo or logo.startswith("/assets/frappe/"):
        context.logo = LOGO
    context.favicon = FAVICON

    if not context.get("login_name_placeholder"):
        label = (context.get("login_label") or _("Email")).strip().lower()
        context.login_name_placeholder = _("Enter your {0}").format(label)

    # Drop the vendor-cloud shortcut button that stock Frappe may add.
    context.login_with_frappe_cloud_url = None

    context.nx_year = frappe.utils.now_datetime().year
    context.nx_css_version = _asset_version("css/nxerp-login.css")
    return context


def _asset_version(relative_path):
    try:
        path = frappe.get_app_path("helpdesk", "public", "nxerp_login", *relative_path.split("/"))
        return int(os.path.getmtime(path))
    except Exception:
        return 1
