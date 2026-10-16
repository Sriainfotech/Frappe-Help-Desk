import os
import re

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
    context.nx_lang_code = frappe.local.lang or "en"
    context.nx_lang_name = _language_name(context.nx_lang_code)
    context.nx_support_url = _support_url()
    return context


def _asset_version(relative_path):
    try:
        path = frappe.get_app_path("helpdesk", "public", "nxerp_login", *relative_path.split("/"))
        return int(os.path.getmtime(path))
    except Exception:
        return 1


def _language_name(code):
    try:
        name = frappe.db.get_value("Language", code, "language_name") or "English"
        return re.sub(r"\s*\(.*\)\s*$", "", name)  # "English (United States)" -> "English"
    except Exception:
        return "English"


def _support_url():
    """Target of "Contact IT Support". Nothing is invented: it comes from site
    config (`nxerp_support_url`, e.g. a mailto: or https: link) or, failing that,
    the address in Contact Us Settings. If neither is set the line is not shown."""
    try:
        url = (frappe.conf.get("nxerp_support_url") or "").strip()
        if not url:
            email = frappe.db.get_single_value("Contact Us Settings", "forward_to_email")
            url = f"mailto:{email.strip()}" if email else ""
        # only links a browser can open safely
        return url if url.lower().startswith(("mailto:", "https://", "http://", "/")) else ""
    except Exception:
        return ""
