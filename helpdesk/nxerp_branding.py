import frappe

BRAND = "NXERP"
ASSETS = "/assets/helpdesk/nxerp_login/images"
LOGO = f"{ASSETS}/nxerp-wordmark.png"  # wide logo: login, desk, website
MARK = f"{ASSETS}/nxerp-mark.png"  # square mark: the app's small sidebar slot
FAVICON = f"{ASSETS}/nxerp-favicon.png"


def apply_branding():
    """Set the NXERP name and logos in site settings, printing the old values.

    Run by hand: bench --site <site> execute helpdesk.nxerp_branding.apply_branding
    """
    changes = {
        "HD Settings": {"brand_name": BRAND, "brand_logo": MARK, "favicon": FAVICON},
        "Website Settings": {
            "app_name": BRAND,
            "app_logo": LOGO,
            "favicon": FAVICON,
            "splash_image": LOGO,
        },
        "Navbar Settings": {"app_logo": LOGO},
    }
    for doctype, values in changes.items():
        for fieldname, value in values.items():
            old = frappe.db.get_single_value(doctype, fieldname)
            frappe.db.set_single_value(doctype, fieldname, value)
            print(f"{doctype}.{fieldname}: {old!r} -> {value!r}")
    frappe.clear_cache()
