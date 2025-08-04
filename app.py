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
REPORT_NAME = "1. STYL Variance Report (Custom/MagTech Monthly Financials)"
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
    "a:has(raul-icon[title='Financial Suite'])"
)
SEL_FAVORITES_MENU = (
    "#favorites-menu"
)
SEL_FINANCIAL_REPORTS_MENUITEM = (
    "#siaappsmenu > div.qx-siamenu-favorites.qx-siamenu-cnt.active > div.qx-siamenu-fav-content > div.qx-fav-content.qx-menu-hover-scroll.sortable > div:nth-child(1) > div > a.qx-nav-name"
)

# --- Reports list ---
SEL_REPORT_ROWS = "#listcontent tbody tr"
SEL_SCHEDULE_LINK_IN_ROW = "td a[href*='editor.phtml']:has-text('Schedule')"

# --- Schedule form ---
SEL_START_DATE_INPUT = (
    "#_obj__STARTDATE, #obj__STARTDATE, input[id*='obj__STARTDATE'], input[name*='STARTDATE'], "
    "input[aria-label*='Start Date'], input[placeholder*='Start'], input[name*='start'][type='text'], input#start-date"
)
SEL_EVERY_INPUT = (
    "#_obj__INTERVAL, #obj__INTERVAL, input[id*='obj__INTERVAL'], input[id*='INTERVAL'], input[name*='INTERVAL'], "
    "input[aria-label*='Every'], input[name*='every'], input#every"
)
SEL_SAVE_BUTTON = "button:has-text('Save'), button:has-text('Update'), input[type='submit'], button[type='submit']"

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

    # Listen for new page/tab before clicking
    with page.context.expect_page() as new_page_info:
        click_when_visible(page, SEL_FINANCIAL_SUITE_TILE)

    # Switch to the new tab
    new_page = new_page_info.value
    new_page.wait_for_load_state("domcontentloaded")
    new_page.wait_for_load_state("load")

    # Continue with the new page instead of original
    # Wait much longer for Financial Suite page to fully load all dynamic content
    print("Waiting for Financial Suite page to fully load...")
    new_page.wait_for_timeout(10000)

    # Click Favorites to show dropdown (instead of hover)
    favorites = new_page.locator(SEL_FAVORITES_MENU)
    favorites.wait_for(state="visible")
    print(f"Found favorites menu: {favorites.count()}")
    favorites.click()
    print("Clicked favorites menu")

    # Wait for the favorites dropdown to be visible
    new_page.wait_for_selector(".qx-siamenu-favorites.active", timeout=10000)
    print("Favorites dropdown is now visible")

    # Wait additional time for dropdown content to fully load
    new_page.wait_for_timeout(5000)

    # Click Financial reports link in the favorites dropdown
    financial_reports_link = new_page.locator(SEL_FINANCIAL_REPORTS_MENUITEM)
    financial_reports_link.click(force=True)
    print("Clicked Financial reports link in favorites dropdown")

    # Wait for page to load and then wait additional time for dynamic content
    new_page.wait_for_load_state("domcontentloaded")
    new_page.wait_for_load_state("load")
    print("Waiting for Financial reports page to fully load...")
    new_page.wait_for_timeout(8000)  # Wait 8 seconds for dynamic content
    print("Financial reports page should be fully loaded")

    return new_page


def find_report_row_and_open_schedule(page, report_name: str):
    print(f"Looking for report: {report_name}")

    # Find the iframe containing the reports table
    iframe_page = None
    iframes = page.locator("iframe")
    for i in range(iframes.count()):
        try:
            iframe = iframes.nth(i)
            iframe_name = iframe.get_attribute("name") or ""

            if iframe_name:  # Only try iframes with names
                iframe.wait_for(state="attached", timeout=5000)
                page.wait_for_timeout(1000)

                iframe_page = page.frame(name=iframe_name)
                if iframe_page:
                    iframe_page.wait_for_load_state(
                        "domcontentloaded", timeout=10000)
                    iframe_page.wait_for_timeout(2000)

                    # Check if this iframe contains the reports table
                    if iframe_page.locator("#listcontent tbody tr").count() > 0:
                        print(f"Using iframe '{
                              iframe_name}' for reports table")
                        break
        except:
            continue

    if not iframe_page:
        iframe_page = page

    # Wait for table content to load
    iframe_page.wait_for_timeout(3000)

    # Find the report row - try different selectors
    row = iframe_page.locator(
        f"#listcontent tbody tr:has(td font:has-text('{report_name}'))").first

    if row.count() == 0:
        row = iframe_page.locator(
            f"#listcontent tbody tr:has(td:has-text('{report_name}'))").first

    if row.count() == 0:
        # Fallback: search through all rows
        rows = iframe_page.locator("#listcontent tbody tr")
        for i in range(rows.count()):
            try:
                r = rows.nth(i)
                txt = " ".join(r.all_text_contents())
                if report_name.lower() in txt.lower():
                    row = r
                    break
            except:
                continue

    assert row.count() > 0, f"Report row not found for: {report_name}"

    # Click the Schedule link
    schedule_link = row.locator(SEL_SCHEDULE_LINK_IN_ROW).first
    schedule_link.wait_for(state="visible")
    schedule_link.click()
    iframe_page.wait_for_load_state("networkidle")

    return iframe_page


def reschedule_form(initial_iframe_page):
    print("=== RESCHEDULE FORM DEBUG ===")
    print(f"Initial iframe page: {initial_iframe_page}")

    # After clicking Schedule, we need to find the new iframe with the form
    # This might be a new page or a new iframe within the current context

    # Wait for new page/iframe to load
    print("Waiting for new page/iframe to load...")
    initial_iframe_page.wait_for_timeout(3000)

    # Try to find the schedule form iframe - it might be in the parent page
    parent_page = initial_iframe_page.page
    print(f"Parent page: {parent_page}")
    form_iframe_page = None

    # Look for iframes in the parent page that might contain the form
    iframes = parent_page.locator("iframe")
    iframe_count = iframes.count()
    print(f"Found {iframe_count} iframes in parent page")

    for i in range(iframe_count):
        try:
            iframe = iframes.nth(i)
            iframe_name = iframe.get_attribute("name") or ""
            iframe_src = iframe.get_attribute("src") or ""
            iframe_id = iframe.get_attribute("id") or ""
            print(f"  Iframe {i}: name='{iframe_name}' src='{
                  iframe_src[:50]}...' id='{iframe_id}'")

            if iframe_name:
                iframe_page = parent_page.frame(name=iframe_name)
                if iframe_page:
                    print(f"    Successfully accessed iframe '{iframe_name}'")
                    iframe_page.wait_for_load_state(
                        "domcontentloaded", timeout=5000)
                    iframe_page.wait_for_timeout(1000)

                    # Check for various input types and elements
                    text_inputs = iframe_page.locator(
                        "input[type='text']").count()
                    all_inputs = iframe_page.locator("input").count()
                    forms = iframe_page.locator("form").count()
                    print(f"    Found: {text_inputs} text inputs, {
                          all_inputs} total inputs, {forms} forms")

                    # Also check for the specific selectors we're looking for
                    start_date_matches = iframe_page.locator(
                        SEL_START_DATE_INPUT).count()
                    every_matches = iframe_page.locator(
                        SEL_EVERY_INPUT).count()
                    save_matches = iframe_page.locator(SEL_SAVE_BUTTON).count()
                    print(f"    Selector matches: start_date={start_date_matches}, every={
                          every_matches}, save={save_matches}")

                    # Check if this iframe contains form inputs
                    if (text_inputs > 0 or all_inputs > 0 or start_date_matches > 0):
                        print(f"    ✓ Using iframe '{
                              iframe_name}' for schedule form")
                        form_iframe_page = iframe_page
                        break
                    else:
                        print(f"    ✗ No form elements found in iframe '{
                              iframe_name}'")
        except Exception as e:
            print(f"  Error accessing iframe {i}: {e}")
            continue

    # If no form iframe found, try the original iframe
    if not form_iframe_page:
        print("No form iframe found, using original iframe")
        form_iframe_page = initial_iframe_page

        # Debug the original iframe too
        text_inputs = form_iframe_page.locator("input[type='text']").count()
        all_inputs = form_iframe_page.locator("input").count()
        start_date_matches = form_iframe_page.locator(
            SEL_START_DATE_INPUT).count()
        every_matches = form_iframe_page.locator(SEL_EVERY_INPUT).count()
        save_matches = form_iframe_page.locator(SEL_SAVE_BUTTON).count()
        print(
            f"Original iframe - inputs: {text_inputs} text, {all_inputs} total")
        print(f"Original iframe - selectors: start_date={
              start_date_matches}, every={every_matches}, save={save_matches}")

    # Wait a bit more for form elements to load
    print("Waiting for form elements to load...")
    form_iframe_page.wait_for_timeout(2000)

    # Debug: Show what selectors we're using
    print(f"Start Date selector: {SEL_START_DATE_INPUT}")
    print(f"Every selector: {SEL_EVERY_INPUT}")
    print(f"Save selector: {SEL_SAVE_BUTTON}")

    # Start Date -> today
    print("Looking for Start Date input...")
    start_input = form_iframe_page.locator(SEL_START_DATE_INPUT).first
    start_count = start_input.count()
    print(f"Found {start_count} start date inputs")

    if start_count > 0:
        print("Filling start date input...")
        start_input.wait_for(state="visible")
        start_input.fill("")
        start_input.type(today_str())
        print(f"Start date set to: {today_str()}")
    else:
        print("ERROR: No start date input found!")
        # Try to find any inputs that might be the start date
        all_inputs = form_iframe_page.locator("input")
        print(f"All inputs found: {all_inputs.count()}")
        for i in range(min(5, all_inputs.count())):  # Show first 5 inputs
            try:
                inp = all_inputs.nth(i)
                inp_type = inp.get_attribute("type") or ""
                inp_name = inp.get_attribute("name") or ""
                inp_id = inp.get_attribute("id") or ""
                inp_placeholder = inp.get_attribute("placeholder") or ""
                print(f"  Input {i}: type='{inp_type}' name='{inp_name}' id='{
                      inp_id}' placeholder='{inp_placeholder}'")
            except Exception as e:
                print(f"  Input {i}: Error - {e}")

    # Toggle Every 1<->2
    print("Looking for Every input...")
    every_input = form_iframe_page.locator(SEL_EVERY_INPUT).first
    every_count = every_input.count()
    print(f"Found {every_count} every inputs")

    if every_count > 0:
        every_input.wait_for(state="visible")
        current = ""
        try:
            current = every_input.input_value(timeout=3_000).strip()
            print(f"Current 'every' value: '{current}'")
        except Exception as e:
            print(f"Error getting current value: {e}")
        new_val = "2" if current == "1" else "1" if current == "2" else "1"
        print(f"Setting 'every' to: '{new_val}'")
        every_input.fill("")
        every_input.type(new_val)
    else:
        print("ERROR: No every input found!")

    # Save/Update
    print("Looking for Save button...")
    save = form_iframe_page.locator(SEL_SAVE_BUTTON).first
    save_count = save.count()
    print(f"Found {save_count} save buttons")

    if save_count > 0:
        print("Clicking save button...")
        save.click()
        form_iframe_page.wait_for_load_state("networkidle")
        print("Save completed")
    else:
        print("ERROR: No save button found!")

    print("=== RESCHEDULE FORM DEBUG END ===")

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
        financial_page = navigate_to_scheduled_reports(page)
        iframe_page = find_report_row_and_open_schedule(
            financial_page, REPORT_NAME)
        reschedule_form(iframe_page)
        # Short wait so you can observe the result before closing
        iframe_page.wait_for_timeout(1000)
    finally:
        context.close()
        browser.close()


def main():
    with sync_playwright() as p:
        run(p)


if __name__ == "__main__":
    main()
