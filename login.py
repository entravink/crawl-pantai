from playwright.sync_api import sync_playwright
import sys
import random

# Desktop User Agents for Fasih-SM (Avoid mobile emulation for this site)
user_agan = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
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
    """Login logic tailored for fasih-sm.bps.go.id/oauth_login.html"""
    pw = _get_playwright()
    # Set headless=False to debug if the SSO redirects differently in your region
    browser = pw.chromium.launch(headless=False) 
    
    context = browser.new_context(
        user_agent=user_agents,
        viewport={"width": 1280, "height": 800}
    )
    page = context.new_page()
    
    try:
        print("Navigating to Fasih-SM Login Page...")
        page.goto("https://fasih-sm.bps.go.id/oauth_login.html", timeout=60000)
        page.wait_for_load_state('networkidle')

        # 1. Click the SSO / Login Button
        # Based on typical BPS oauth_login pages, we look for a button or link
        print("Clicking Login/SSO button...")
        sso_button = page.locator('a:has-text("Login"), button:has-text("Login"), .btn-login').first
        sso_button.click()

        # 2. Wait for redirect to SSO Keycloak
        print("Waiting for SSO Provider (Keycloak)...")
        page.wait_for_selector('input[name="username"]', timeout=60000)

        # 3. Fill Credentials
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        
        # Click Sign In / Submit
        # Keycloak usually uses id="kc-login" or name="login"
        submit_btn = page.locator('#kc-login, input[type="submit"], button[type="submit"]').first
        submit_btn.click()

        page.wait_for_load_state('networkidle')

        # 4. Handle OTP if triggered
        if page.locator('input[name="otp"], #otp').is_visible(timeout=5000):
            print("OTP Required detected.")
            if not otp_code:
                otp_code = input("Enter OTP Code: ")
            page.fill('input[name="otp"], #otp', otp_code)
            page.keyboard.press("Enter")
            page.wait_for_load_state('networkidle')

        # 5. Final Verification
        # Wait until we are redirected back to the main app dashboard
        print("Verifying redirection back to App...")
        page.wait_for_url("https://fasih-sm.bps.go.id/**", timeout=60000)
        
        if "fasih-sm.bps.go.id" in page.url and "login" not in page.url.lower():
            print("Login SUCCESSFUL!")
            return page, browser
        else:
            print(f"Login FAILED. Current URL: {page.url}")
            browser.close()
            return None, None

    except Exception as e:
        print(f"Detailed Error during login: {e}")
        try:
            browser.close()
        except:
            pass
        return None, None

if __name__ == "__main__":
    # Test script standalone
    u = input("SSO Username: ")
    p = input("SSO Password: ")
    pg, br = login_with_sso(u, p)
    if pg:
        print("Page object acquired. Session is active.")
        br.close()
    _stop_playwright()