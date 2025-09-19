import random
import re
from playwright.sync_api import Page, expect, sync_playwright, Browser, BrowserContext
import base64
from pathlib import Path
import time
from contextlib import contextmanager
from typing import Generator, Optional

def save_screenshot_and_base64(page: Page, out_dir: str, name_prefix: str = "image"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    png_path = out / f"{name_prefix}.png"
    b64_path = out / f"{name_prefix}.b64"

    # Capture full page screenshot (also writes PNG file)
    png_bytes = page.screenshot(path=str(png_path), full_page=True)

    # Write base64 alongside
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    b64_path.write_text(b64, encoding="utf-8")

    return str(png_path), str(b64_path)
def add_cursor_overlay(page: Page):
    page.add_init_script("""
        (() => {
            const cursor = document.createElement('div');
            cursor.id = 'playwright-cursor';
            Object.assign(cursor.style, {
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: 'red',
                position: 'absolute',
                top: '0px',
                left: '0px',
                zIndex: '999999',
                pointerEvents: 'none',
                transition: 'top 0.05s linear, left 0.05s linear'
            });
            document.body.appendChild(cursor);

            document.addEventListener('mousemove', e => {
                cursor.style.left = e.pageX - 10 + 'px';
                cursor.style.top = e.pageY - 10 + 'px';
            });
        })();
    """)

class PlaywrightManager:
    """A reusable Playwright browser manager for automation tasks."""
    
    def __init__(self, headless: bool = False, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright = None
        self._browser = None
        self._context = None
    
    @contextmanager
    def browser_context(self, 
                       browser_type: str = "chromium",
                       viewport: Optional[dict] = None,
                       user_agent: Optional[str] = None) -> Generator[tuple[Browser, BrowserContext, Page], None, None]:
        """
        Context manager for browser automation.
        
        Args:
            browser_type: Type of browser to launch ("chromium", "firefox", "webkit")
            viewport: Browser viewport settings {"width": 1920, "height": 1080}
            user_agent: Custom user agent string
            
        Yields:
            Tuple of (browser, context, page) for automation tasks
        """
        try:
            self._playwright = sync_playwright().start()
            
            # Launch browser based on type
            if browser_type == "chromium":
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless, 
                    slow_mo=self.slow_mo
                )
            elif browser_type == "firefox":
                self._browser = self._playwright.firefox.launch(
                    headless=self.headless, 
                    slow_mo=self.slow_mo
                )
            elif browser_type == "webkit":
                self._browser = self._playwright.webkit.launch(
                    headless=self.headless, 
                    slow_mo=self.slow_mo
                )
            else:
                raise ValueError(f"Unsupported browser type: {browser_type}")
            
            # Create context with optional settings
            context_options = {}
            if viewport:
                context_options["viewport"] = viewport
            if user_agent:
                context_options["user_agent"] = user_agent
                
            self._context = self._browser.new_context(**context_options)
            page = self._context.new_page()
            
            yield self._browser, self._context, page
            
        finally:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()

def test_login_and_dashboard(page: Page):
    """Test function for login and dashboard automation."""
    add_cursor_overlay(page)
    page.goto("https://farmce-dev.oraczen.xyz/auth")
    email_box = page.get_by_role("textbox", name="Email")
    email_box_bounds = email_box.bounding_box()
    page.mouse.move(
        email_box_bounds["x"] + email_box_bounds["width"] / 2,
        email_box_bounds["y"] + email_box_bounds["height"] / 2
    )
    page.mouse.click(
        email_box_bounds["x"] + email_box_bounds["width"] / 2,
        email_box_bounds["y"] + email_box_bounds["height"] / 2
    )
    page.keyboard.type("deepak.ramanujam@oraczen.ai", delay=100)  # delay makes it human-like
    password_box = page.get_by_role("textbox", name="Enter your password")
    pw_bounds = password_box.bounding_box()
    page.mouse.move(
        pw_bounds["x"] + pw_bounds["width"] / 2,
        pw_bounds["y"] + pw_bounds["height"] / 2
    )
    page.mouse.click(
        pw_bounds["x"] + pw_bounds["width"] / 2,
        pw_bounds["y"] + pw_bounds["height"] / 2
    )
    page.keyboard.type("Test@1234567", delay=100)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")
    page.get_by_role("link", name="Get Started").first.click()
    expect(page).to_have_url(re.compile(".*/dairy-profit-intelligence"))
    random_number = random.randint(100, 999)
    save_screenshot_and_base64(page, out_dir=f"screenshots/file{random_number}", name_prefix="dashboard")




# Example usage functions
def run_login_test():
    """Example function showing how to use the PlaywrightManager."""
    manager = PlaywrightManager(headless=False, slow_mo=2000)
    
    with manager.browser_context() as (browser, context, page):
        test_login_and_dashboard(page)

def run_custom_automation():
    """Example function showing custom automation with different settings."""
    manager = PlaywrightManager(headless=True, slow_mo=0)
    
    with manager.browser_context(
        browser_type="chromium",
        viewport={"width": 1920, "height": 1080}
    ) as (browser, context, page):
        page.goto("https://example.com")
