import os
from dotenv import load_dotenv
from datetime import datetime
from playwright.sync_api import Playwright, sync_playwright

# =========================================
# Configuration (edit as needed)
# =========================================

load_dotenv()

BASE_URL = "https://www.realpage.com/login/identity/Account/SignIn"
USERNAME = os.getenv('REALPAGE_USERNAME')
PASSWORD = os.getenv('REALPAGE_PASSWORD')
# change as needed
REPORT_NAME = "STYL Variance Report (Custom/MagTech Monthly Financials)"
DATE_FORMAT = "%m/%d/%Y"  # adjust if the form expects a different format
DEFAULT_TIMEOUT_MS = 30_000

# =========================================
# Helpers
# =========================================


def today_str(fmt: str = DATE_FORMAT) -> str:
    return datetime.now().strftime(fmt)


def click_when_visible(page, selector: str, *, timeout: int = DEFAULT_TIMEOUT_MS):
    loc = page.locator(selector)
    loc.wait_for(state="visible", timeout=timeout)
    loc.click()
    return loc


def fill_when_visible(page, selector: str, value: str, *, timeout: int = DEFAULT_TIMEOUT_MS):
    loc = page.locator(selector)
    loc.wait_for(state="visible", timeout=timeout)
    loc.fill(value)
    return loc


# =========================================
# Generic selectors (NOT tailored to a specific skin/tenant)
# =========================================
# --- Login page ---
SEL_USERNAME_INPUT = (
    "input[type='email'], input[name='username'], input[autocomplete='username'], "
    "input[aria-label='Username'], input[placeholder*='User']"
)
SEL_NEXT_BUTTON = (
    ".login-page-form-button button[type='submit'], button:has-text('Next'), button[type='submit']"
)
SEL_PASSWORD_INPUT = (
    "input[type='password'], input[name='password'], input[autocomplete='current-password'], "
    "input[aria-label='Password']"
)
SEL_LOGIN_BUTTON = (
    ".login-page-form-button button[type='submit'], button:has-text('Login'), button:has-text('Sign in'), input[type='submit']"
)

# --- Landing / navigation ---
SEL_FINANCIAL_SUITE_TILE = (
    "text=Financial Suite, role=link[name*='Financial Suite']"
)
SEL_FAVORITES_MENU = (
    "text=Favorites, role=menuitem[name*='Favorites'], role=link[name*='Favorites']"
)
SEL_FINANCIAL_REPORTS_MENUITEM = (
    "text=Financial reports, role=menuitem[name*='Financial report']"
)

# --- Reports list ---
SEL_REPORT_ROWS = "table tr"
SEL_SCHEDULE_LINK_IN_ROW = "a:has-text('Schedule'), button:has-text('Schedule')"

# --- Schedule form ---
SEL_START_DATE_INPUT = (
    "input[aria-label*='Start Date'], input[placeholder*='Start'], input[name*='start'][type='text'], input#start-date"
)
SEL_EVERY_INPUT = (
    "input[aria-label*='Every'], input[name*='every'], input#every"
)
SEL_SAVE_BUTTON = "button:has-text('Save'), button:has-text('Update'), input[type='submit']"

# =========================================
# Flows
# =========================================


def load_login_page(page):
    page.goto(BASE_URL)
    page.wait_for_load_state("domcontentloaded")


def login_flow(page, username: str, password: str):
    # Username -> Next
    fill_when_visible(page, SEL_USERNAME_INPUT, username)
    click_when_visible(page, SEL_NEXT_BUTTON)
    page.wait_for_load_state("networkidle")

    # Password -> Login
    fill_when_visible(page, SEL_PASSWORD_INPUT, password)
    click_when_visible(page, SEL_LOGIN_BUTTON)
    page.wait_for_load_state("networkidle")


def navigate_to_scheduled_reports(page):
    # Wait for the landing page; open Financial Suite
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_load_state("networkidle")

    click_when_visible(page, SEL_FINANCIAL_SUITE_TILE)
    page.wait_for_load_state("networkidle")

    # Hover Favorites to show dropdown
    favorites = page.locator(SEL_FAVORITES_MENU)
    favorites.wait_for(state="visible")
    favorites.hover()

    # Click Financial reports
    menu_item = page.locator(SEL_FINANCIAL_REPORTS_MENUITEM)
    menu_item.wait_for(state="visible")
    menu_item.click()
    page.wait_for_load_state("networkidle")


def find_report_row_and_open_schedule(page, report_name: str):
    page.wait_for_selector(SEL_REPORT_ROWS)

    # Direct row lookup containing report name
    row = page.locator(f"tr:has(td:has-text('{report_name}'))").first
    if row.count() == 0:
        row = page.locator(f"tr:has(:text('{report_name}'))").first

    if row.count() == 0:
        # Fallback: iterate all rows
        rows = page.locator(SEL_REPORT_ROWS)
        n = rows.count()
        for i in range(n):
            r = rows.nth(i)
            try:
                txt = r.inner_text(timeout=2_000)
            except Exception:
                continue
            if report_name.lower() in txt.lower():
                row = r
                break

    assert row.count() > 0, f"Report row not found for: {report_name}"

    # Click the Schedule action in the same row
    schedule_link = row.locator(SEL_SCHEDULE_LINK_IN_ROW).first
    schedule_link.wait_for(state="visible")
    schedule_link.click()
    page.wait_for_load_state("networkidle")


def reschedule_form(page):
    # Start Date -> today
    start_input = page.locator(SEL_START_DATE_INPUT).first
    start_input.wait_for(state="visible")
    start_input.fill("")
    start_input.type(today_str())

    # Toggle Every 1<->2
    every_input = page.locator(SEL_EVERY_INPUT).first
    every_input.wait_for(state="visible")
    current = ""
    try:
        current = every_input.input_value(timeout=3_000).strip()
    except Exception:
        pass
    new_val = "2" if current == "1" else "1" if current == "2" else "1"
    every_input.fill("")
    every_input.type(new_val)

    # Save/Update
    save = page.locator(SEL_SAVE_BUTTON).first
    if save.count() > 0:
        save.click()
        page.wait_for_load_state("networkidle")

# =========================================
# Entry
# =========================================


def run(playwright: Playwright):
    # IMPORTANT: Headful mode enforced (headless=False)
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT_MS)

    try:
        load_login_page(page)
        login_flow(page, USERNAME, PASSWORD)
        navigate_to_scheduled_reports(page)
        find_report_row_and_open_schedule(page, REPORT_NAME)
        reschedule_form(page)
        # Short wait so you can observe the result before closing
        page.wait_for_timeout(1000)
    finally:
        context.close()
        browser.close()


def main():
    with sync_playwright() as p:
        run(p)


if __name__ == "__main__":
    main()
