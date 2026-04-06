from playwright.sync_api import sync_playwright
import random

# Desktop User Agents
user_agan = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
]

user_agents = random.choice(user_agan)

_PW = None


def _get_playwright():
    global _PW
    if _PW is None:
        _PW = sync_playwright().start()
    return _PW


def _stop_playwright():
    global _PW
    try:
        if _PW is not None:
            _PW.stop()
            _PW = None
    except Exception:
        pass


def login_with_sso(username, password, otp_code=None):

    pw = _get_playwright()

    browser = pw.chromium.launch(headless=False)

    context = browser.new_context(
        user_agent=user_agents,
        viewport={"width": 1280, "height": 800}
    )

    page = context.new_page()

    try:

        print("Navigating to Fasih-SM Login Page...")

        page.goto(
            "https://fasih-sm.bps.go.id/oauth_login.html",
            wait_until="domcontentloaded",
            timeout=60000
        )

        # ==============================
        # Click Login Button
        # ==============================

        print("Clicking Login/SSO button...")

        sso_button = page.locator(
            'a:has-text("Login"), button:has-text("Login"), .btn-login'
        ).first

        sso_button.wait_for(timeout=30000)

        with page.expect_navigation(timeout=60000):
            sso_button.click()

        # ==============================
        # Wait for Keycloak Login Page
        # ==============================

        print("Waiting for SSO Provider (Keycloak)...")

        page.wait_for_selector('input[name="username"]', timeout=60000)

        # ==============================
        # Fill Credentials
        # ==============================

        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)

        submit_btn = page.locator(
            '#kc-login, input[type="submit"], button[type="submit"]'
        ).first

        with page.expect_navigation(timeout=60000):
            submit_btn.click()

        # ==============================
        # Handle OTP (more flexible)
        # ==============================

        try:
            page.wait_for_timeout(2000)

            otp_candidates = page.locator('input')

            if otp_candidates.count() > 0:
                for i in range(otp_candidates.count()):
                    field = otp_candidates.nth(i)
                    name_attr = field.get_attribute("name") or ""

                    if any(k in name_attr.lower() for k in ["otp", "totp", "code"]):
                        print("OTP Required detected.")

                        if not otp_code:
                            otp_code = input("Enter OTP Code: ")

                        field.fill(otp_code)
                        page.keyboard.press("Enter")

                        page.wait_for_load_state("networkidle")
                        break

        except:
            pass

        # ==============================
        # Wait Redirect Back
        # ==============================

        print("Verifying redirection back to App...")

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        current_url = page.url
        cookies = context.cookies()

        print("Final URL:", current_url)
        print("Cookies:", [c["name"] for c in cookies])

        # ==============================
        # RELAXED SUCCESS CHECK
        # ==============================

        is_on_domain = "fasih-sm.bps.go.id" in current_url
        has_cookies = len(cookies) > 0

        # Optional: detect if still on login form
        login_form_visible = False
        try:
            login_form_visible = page.locator('input[name="username"]').is_visible(timeout=3000)
        except:
            pass

        if is_on_domain and (has_cookies or not login_form_visible):

            print("Login SUCCESSFUL!")

            return page, browser

        else:

            print("Login FAILED. Current URL:", current_url)

            browser.close()

            return None, None

    except Exception as e:

        print("Detailed Error during login:", e)

        try:
            browser.close()
        except:
            pass

        return None, None


if __name__ == "__main__":

    u = input("SSO Username: ")
    p = input("SSO Password: ")

    pg, br = login_with_sso(u, p)

    if pg:
        print("Page object acquired. Session is active.")
        br.close()

    _stop_playwright()