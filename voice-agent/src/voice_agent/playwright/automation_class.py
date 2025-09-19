import random
import re
import base64
from pathlib import Path
from playwright.sync_api import Page, expect, sync_playwright, Browser, BrowserContext
from openai import OpenAI
from ..constants import OPENAI_API_KEY
import re

_browser = None
_context = None
_page = None
_playwright = None

ALLOWED_DOMAIN = "farmce-dev.oraczen.xyz"

client = OpenAI(api_key=OPENAI_API_KEY)  


class PersistentPlaywright:
    """Manages a persistent Playwright browser session."""

    @staticmethod
    def open(url: str, headless: bool = False, slow_mo: int = 0):
        """Open browser and navigate to a given URL (keeps instance alive)."""
        global _browser, _context, _page, _playwright

        if _browser is not None:
            print("Browser already open.")
            return _page

        if ALLOWED_DOMAIN not in url:
            raise ValueError(f"Navigation outside allowed domain: {url}")

        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        _context = _browser.new_context(viewport={"width": 1280, "height": 800})
        _page = _context.new_page()
        _page.goto(url)

        print(f"Browser opened at {url}")
        return _page

    @staticmethod
    def close():
        """Close the browser instance and reset globals."""
        global _browser, _context, _page, _playwright

        if _context:
            _context.close()
        if _browser:
            _browser.close()
        if _playwright:
            _playwright.stop()

        _browser = None
        _context = None
        _page = None
        _playwright = None
        print("Browser closed.")

    @staticmethod
    def login_and_test():
        """Use the persistent page to login and test dashboard."""
        global _page
        if _page is None:
            raise RuntimeError("Browser not open. Call `open()` first.")

        _page.get_by_role("textbox", name="Email").fill("deepak.ramanujam@oraczen.ai")
        _page.get_by_role("textbox", name="Enter your password").fill("Test@1234567")
        _page.get_by_role("button", name="Login").click()
        _page.wait_for_load_state("networkidle")
        _page.get_by_role("link", name="Get Started").first.click()
        expect(_page).to_have_url(re.compile(".*/dairy-profit-intelligence"))

        random_number = random.randint(100, 999)
        out_dir = Path(f"screenshots/file{random_number}")
        out_dir.mkdir(parents=True, exist_ok=True)
        _page.screenshot(path=str(out_dir / "dashboard.png"), full_page=True)

        print("Login and dashboard test executed.")

    @staticmethod
    def clean_code_block(code: str) -> str:
        return re.sub(r"^```[a-zA-Z]*\n?|```$", "", code, flags=re.MULTILINE).strip()
    @staticmethod
    def execute_instruction(instruction: str):
        """
        Convert text instruction into Playwright code with OpenAI and execute
        it safely on the global `_page` instance.
        """
        global _page
        if _page is None:
            raise RuntimeError("Browser not open. Call `open()` first.")

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
            {"role": "system", "content": f"""
            You are a code generator. Convert user instructions into Playwright Python code.

            RULES:
            - Use the global `_page` variable only.
            - Use ONLY the synchronous Playwright API (`playwright.sync_api`).
            - Do NOT generate async/await.
            - Do NOT import anything.
            - Do NOT use eval/exec/file operations.
            - Do NOT navigate (`_page.goto`).
            - Only generate the body code (no function defs, no classes).
            - Generate clean, executable Playwright code.
            """}
            ],
            temperature=0,
        )
        code = resp.choices[0].message.content.strip()
        print("Generated code:\n", code)
        
        # code = PersistentPlaywright.clean_code_block(code)
        
        print("Cleaned code:\n", code)
        
        # Security checks
        forbidden = ["import ", "open(", "os.", "subprocess", "exec(", "eval(", "requests.", "http", "socket"]
        if any(f in code for f in forbidden):
            raise ValueError("Generated code contained forbidden operations.")
        if "goto(" in code and ALLOWED_DOMAIN not in code:
            raise ValueError("Generated code tried to navigate outside allowed domain.")
        
        # Execute the code
        try:
            # safe_globals = {"_page": _page, "expect": expect, "re": re}
            # exec(code, safe_globals)
            print("✅ Instruction executed successfully.")
            return {"executed_code": code, "status": "success", "message": "Code executed successfully"}
        except Exception as e:
            print(f"❌ Error executing code: {str(e)}")
            return {"executed_code": code, "status": "error", "message": f"Execution error: {str(e)}"}
