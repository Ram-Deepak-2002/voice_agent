import random
import re
import base64
import asyncio
from pathlib import Path
from playwright.sync_api import Page, expect, sync_playwright, Browser, BrowserContext
from playwright.async_api import async_playwright, Page as AsyncPage, Browser as AsyncBrowser, BrowserContext as AsyncContext
from openai import OpenAI
from ..constants import OPENAI_API_KEY
import re

# Sync globals
_browser = None
_context = None
_page = None
_playwright = None

# Async globals
_async_browser = None
_async_context = None
_async_page = None
_async_playwright = None

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
    async def open_async(url: str, headless: bool = False, slow_mo: int = 0):
        """Open async browser and navigate to a given URL (keeps instance alive)."""
        global _async_browser, _async_context, _async_page, _async_playwright

        if _async_browser is not None:
            print("Async browser already open.")
            return _async_page

        if ALLOWED_DOMAIN not in url:
            raise ValueError(f"Navigation outside allowed domain: {url}")

        _async_playwright = await async_playwright().start()
        _async_browser = await _async_playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        _async_context = await _async_browser.new_context(viewport={"width": 1280, "height": 800})
        _async_page = await _async_context.new_page()
        await _async_page.goto(url)

        print(f"Async browser opened at {url}")
        return _async_page

    @staticmethod
    async def close_async():
        """Close the async browser instance and reset globals."""
        global _async_browser, _async_context, _async_page, _async_playwright

        if _async_context:
            await _async_context.close()
        if _async_browser:
            await _async_browser.close()
        if _async_playwright:
            await _async_playwright.stop()

        _async_browser = None
        _async_context = None
        _async_page = None
        _async_playwright = None
        print("Async browser closed.")

    @staticmethod
    async def get_page_state_async():
        """Get current page state for context."""
        global _async_page
        if _async_page is None:
            return {"error": "Browser not open"}
        
        try:
            url = await _async_page.url
            title = await _async_page.title()
            html = await _async_page.content()
            screenshot = await _async_page.screenshot(full_page=True)
            screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
            
            return {
                "url": url,
                "title": title,
                "html": html[:5000],  # Limit HTML size
                "screenshot_base64": screenshot_b64,
                "timestamp": asyncio.get_event_loop().time()
            }
        except Exception as e:
            return {"error": f"Failed to get page state: {str(e)}"}

    @staticmethod
    async def get_element_context_async(search_terms: list):
        """Get HTML context around specific elements for better selector generation."""
        global _async_page
        if _async_page is None:
            return {"error": "Browser not open"}
        
        try:
            element_contexts = []
            
            for term in search_terms:
                try:
                    # Try to find elements containing the search term
                    elements = await _async_page.locator(f'text*="{term}"').all()
                    
                    for i, element in enumerate(elements[:3]):  # Limit to first 3 matches
                        try:
                            # Get the outer HTML of the element and its parent
                            outer_html = await element.evaluate('el => el.outerHTML')
                            parent_html = await element.evaluate('el => el.parentElement?.outerHTML')
                            
                            # Get element attributes
                            tag_name = await element.evaluate('el => el.tagName')
                            attributes = await element.evaluate('''el => {
                                const attrs = {};
                                for (let attr of el.attributes) {
                                    attrs[attr.name] = attr.value;
                                }
                                return attrs;
                            }''')
                            
                            element_contexts.append({
                                "search_term": term,
                                "element_index": i,
                                "tag_name": tag_name,
                                "attributes": attributes,
                                "outer_html": outer_html[:1000],  # Limit size
                                "parent_html": parent_html[:1000] if parent_html else None
                            })
                        except Exception as e:
                            print(f"Error getting context for element {i}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error finding elements for term '{term}': {e}")
                    continue
            
            return {
                "element_contexts": element_contexts,
                "total_found": len(element_contexts)
            }
        except Exception as e:
            return {"error": f"Failed to get element context: {str(e)}"}

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
    async def save_screenshot_to_file(screenshot_b64: str, filename_prefix: str = "screenshot") -> str:
        """Save base64 screenshot to a local file and return the file path."""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.png"
            filepath = f"screenshots/{filename}"
            
            # Create screenshots directory if it doesn't exist
            Path("screenshots").mkdir(exist_ok=True)
            
            # Decode and save the screenshot
            screenshot_data = base64.b64decode(screenshot_b64)
            with open(filepath, 'wb') as f:
                f.write(screenshot_data)
            
            print(f"Screenshot saved to: {filepath}")
            return filepath
        except Exception as e:
            print(f"Failed to save screenshot: {e}")
            return None
    @staticmethod
    async def execute_instruction_async(instruction: str):
        """
        Convert text instruction into Playwright code with OpenAI and execute
        it safely on the global `_async_page` instance with enhanced context.
        """
        global _async_page
        if _async_page is None:
            raise RuntimeError("Async browser not open. Call `open_async()` first.")

        # Get current page state for better context
        page_state = await PersistentPlaywright.get_page_state_async()
        
        # Extract key terms from instruction for element context
        instruction_lower = instruction.lower()
        search_terms = []
        
        element_context = await PersistentPlaywright.get_element_context_async(search_terms)
        
        # Build element context string
        element_context_str = ""
        if "element_contexts" in element_context:
            for ctx in element_context["element_contexts"][:5]:  # Limit to 5 contexts
                element_context_str += f"""
                Element: {ctx['search_term']} (Index: {ctx['element_index']})
                - Tag: {ctx['tag_name']}
                - Attributes: {ctx['attributes']}
                - HTML: {ctx['outer_html'][:500]}...
                - Parent HTML: {ctx['parent_html'][:500] if ctx['parent_html'] else 'None'}...
                """
        
        # Enhanced system prompt with current page context and element details


        # Enhanced system prompt with current page context and element details
        system_prompt = f"""
        You are an expert Playwright automation code generator. Convert user instructions into robust, executable Playwright Python code.

        CURRENT PAGE CONTEXT:
        - URL: {page_state.get('url', 'Unknown')}
        - Title: {page_state.get('title', 'Unknown')}
        - HTML Preview: {page_state.get('html', '')[:2000]}...

        CRITICAL RULES:
        1. Use ONLY the global `_async_page` variable (already available)
        2. Use ONLY asynchronous Playwright API (`playwright.async_api`)
        3. Do NOT import anything or use eval/exec/file operations
        4. Do NOT navigate (`_async_page.goto`) unless explicitly requested
        5. Generate ONLY the body code (no function defs, no classes)
        6. Use `await` for ALL async operations
        7. Add appropriate waits after actions: `await _async_page.wait_for_load_state('networkidle')`
        8. Use robust selectors in this priority order:
           - `data-testid`, `data-test`, `aria-label`, `aria-labelledby`
           - `role` attributes (button, textbox, link, etc.)
           - `id` attributes
           - `placeholder` text for inputs
           - Text content with `get_by_text()` or `locator('text=...')`
           - CSS selectors as last resort

        MANDATORY LOGGING AND VERIFICATION:
        - ALWAYS add print statements to log what you're doing: `print("Looking for email input field")`
        - ALWAYS verify element exists before clicking: `print(f"  Element found: {{await element.count()}} matches")`
        - ALWAYS log successful actions: `print("  Successfully clicked login button")`
        - ALWAYS check element visibility: `print(f"Element visible: {{await element.is_visible()}}")`
        - ALWAYS log the current URL after navigation: `current_url = await _async_page.url; print(f"  Current URL after action: {{current_url}}")`

        SELECTOR EXAMPLES WITH LOGGING:
        - `email_element = _async_page.get_by_role("textbox", name="Email"); count = await email_element.count(); print(f"Found {{count}} email inputs"); await email_element.fill("test@example.com"); print("  Email filled")`
        - `password_element = _async_page.get_by_role("textbox", name="Enter your password"); count = await password_element.count(); print(f"Found {{count}} password inputs"); await password_element.fill("password123"); print("  Password filled")`
        - `login_button = _async_page.get_by_role("button", name="Login"); count = await login_button.count(); print(f"Found {{count}} login buttons"); await login_button.click(); print("  Login button clicked")`

        ERROR HANDLING:
        - Always wrap critical operations in try/except blocks
        - Use `wait_for()` with timeouts for elements that might not be immediately available
        - Add comments explaining what each step does
        - If an element might not exist, use `.first` or handle the case gracefully
        - Log element counts before interacting: `print(f"Found {{await element.count()}} elements")`

        VERIFICATION PATTERNS:
        - Before clicking: Check if element exists and is visible
        - After clicking: Verify URL changed or page state changed
        - For forms: Verify input values were set correctly
        - For navigation: Check that we're on the expected page

        COMMON PATTERNS WITH LOGGING:
        - For buttons: `submit_button = _async_page.get_by_role("button", name="Submit"); count = await submit_button.count(); print(f"Submit button count: {{count}}"); await submit_button.click(); print("  Submit button clicked")`
        - For links: `dashboard_link = _async_page.get_by_role("link", name="Dashboard"); count = await dashboard_link.count(); print(f"Dashboard link count: {{count}}"); await dashboard_link.click(); print("  Dashboard link clicked")`
        - For text inputs: `email_input = _async_page.get_by_role("textbox", name="Email"); count = await email_input.count(); print(f"Email input count: {{count}}"); await email_input.fill("test@example.com"); print("  Email filled")`

        LOGIN EXAMPLE:
        ```python
        # Login with email and password
        try:
            # Find and fill email field
            email_field = _async_page.get_by_role("textbox", name="Email")
            count = await email_field.count()
            print(f"Found {{count}} email fields")
            await email_field.fill("deepak.ramanujam@oraczen.ai")
            print("  Email filled successfully")
            
            # Find and fill password field
            password_field = _async_page.get_by_role("textbox", name="Enter your password")
            count = await password_field.count()
            print(f"Found {{count}} password fields")
            await password_field.fill("Test@1234567")
            print("  Password filled successfully")
            
            # Find and click login button
            login_button = _async_page.get_by_role("button", name="Login")
            count = await login_button.count()
            print(f"Found {{count}} login buttons")
            await login_button.click()
            print("  Login button clicked successfully")
            
            # Wait for page to load
            await _async_page.wait_for_load_state('networkidle')
            current_url = await _async_page.url
            print(f"  Current URL after login: {{current_url}}")
            
        except Exception as e:
            print(f" Login failed: {{e}}")
        ```

        CRITICAL: If you find 0 elements for any action, you MUST raise an exception to trigger retry:
        - If element count is 0, raise Exception(f"Element not found: {{element_description}}")
        - If element is not visible, raise Exception(f"Element not visible: {{element_description}}")
        - If action fails, raise Exception(f"Action failed: {{action_description}}")

        Generate clean, readable, and robust code that handles edge cases, includes comprehensive logging, and verifies actions were successful.
        """
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Instruction: {instruction}"}
                ],
                temperature=0,
            )
            code = resp.choices[0].message.content.strip()
            print("Generated async code:\n", code)
            
            # Clean code block if needed
            code = PersistentPlaywright.clean_code_block(code)
            print("Cleaned async code:\n", code)
            
            # Security checks
            forbidden = ["import ", "open(", "os.", "subprocess", "exec(", "eval(", "requests.", "http", "socket", "sync_playwright"]
            if any(f in code for f in forbidden):
                raise ValueError("Generated code contained forbidden operations.")
            if "goto(" in code and ALLOWED_DOMAIN not in code:
                raise ValueError("Generated code tried to navigate outside allowed domain.")
            # Execute the code with async context and retry logic
            max_retries = 2
            for attempt in range(max_retries + 1):
                print(f"\n === RETRY ATTEMPT {attempt + 1}/{max_retries + 1} ===")
                print(f" Executing code (attempt {attempt + 1}):\n{code}")
                
                try:
                    safe_globals = {
                        "_async_page": _async_page, 
                        "asyncio": asyncio,
                        "re": re,
                        "base64": base64
                    }
                    # Create async execution context
                    exec(f"async def _temp_exec():\n{chr(10).join('    ' + line for line in code.split(chr(10)))}", safe_globals)
                    await safe_globals["_temp_exec"]()
                    
                    print(f"  Attempt {attempt + 1} executed successfully!")
                    return {
                        "executed_code": code, 
                        "status": "success", 
                        "message": f"Code executed successfully on attempt {attempt + 1}",
                        "page_state": await PersistentPlaywright.get_page_state_async()
                    }
                except Exception as e:
                    print(f" Attempt {attempt + 1} failed with error: {str(e)}")
                    
                    # If this is the first failure, take screenshot and regenerate code with better context
                    if attempt == 0:
                        try:
                            print(f"📸 Taking screenshot for retry attempt {attempt + 1}...")
                            # Take screenshot for better context
                            error_screenshot = await _async_page.screenshot(full_page=True)
                            error_screenshot_b64 = base64.b64encode(error_screenshot).decode('utf-8')
                            
                            # Save screenshot to file
                            screenshot_path = await PersistentPlaywright.save_screenshot_to_file(
                                error_screenshot_b64, 
                                f"retry_attempt_{attempt + 1}_error"
                            )
                            
                            # Get current page state and element context
                            current_state = await PersistentPlaywright.get_page_state_async()
                            print(f"  Current page state: {current_state.get('url', 'Unknown')} - {current_state.get('title', 'Unknown')}")
                            
                            # Get element context for retry
                            retry_search_terms = []
                            retry_element_context = await PersistentPlaywright.get_element_context_async(retry_search_terms)
                            
                            # Build retry element context string
                            retry_element_context_str = ""
                            if "element_contexts" in retry_element_context:
                                for ctx in retry_element_context["element_contexts"][:3]:  # Limit for retry
                                    retry_element_context_str += f"""
                                    Element: {ctx['search_term']} (Index: {ctx['element_index']})
                                    - Tag: {ctx['tag_name']}
                                    - Attributes: {ctx['attributes']}
                                    - HTML: {ctx['outer_html'][:300]}...
                                    """
                                    print(f"Retry element context: {retry_element_context_str}")
                            
                            # Enhanced system prompt with error context and screenshot
                            retry_system_prompt = f"""
                            You are an expert Playwright automation code generator. The previous attempt failed with this error: {str(e)}

                            RETRY CONTEXT:
                            - Attempt: {attempt + 1} of {max_retries + 1}
                            - Error Type: {type(e).__name__}
                            - Screenshot saved to: {screenshot_path if screenshot_path else 'Failed to save'}

                            CURRENT PAGE CONTEXT:
                            - URL: {current_state.get('url', 'Unknown')}
                            - Title: {current_state.get('title', 'Unknown')}
                            - HTML Preview: {current_state.get('html', '')[:2000]}...
                            - Error Screenshot (Base64): {error_screenshot_b64}

                            RELEVANT ELEMENT CONTEXT FOR RETRY:
                            {retry_element_context_str}

                            PREVIOUS FAILED CODE:
                            {code}

                            CRITICAL RULES FOR RETRY:
                            1. Use ONLY the global `_async_page` variable (already available)
                            2. Use ONLY asynchronous Playwright API (`playwright.async_api`)
                            3. Do NOT import anything or use eval/exec/file operations
                            4. Generate ONLY the body code (no function defs, no classes)
                            5. Use `await` for ALL async operations
                            6. Handle multiple elements with same text by using more specific selectors
                            7. For anchor tags, use `get_by_role("link")` or `locator('a[href*="..."]')`
                            8. For buttons, use `get_by_role("button")` with specific names
                            9. Use `.first`, `.nth(0)`, or more specific selectors to avoid strict mode violations
                            10. Add appropriate waits: `await _async_page.wait_for_load_state('networkidle')`

                            SELECTOR PRIORITY FOR RETRY (based on actual HTML):
                            - Use the exact attributes from the element context above
                            - For links: `get_by_role("link", name="...")` or `locator('a[href*="..."]')` or `locator('a:has-text("...")').first`
                            - For buttons: `get_by_role("button", name="...")` or `locator('button:has-text("...")').first`
                            - For divs/containers: use class names, data attributes, or parent-child relationships
                            - If element has specific classes: `locator('.class-name')`
                            - If element has data attributes: `locator('[data-testid="..."]')`
                            - For multiple elements: use `.first` or be more specific with parent selectors

                            ERROR-SPECIFIC FIXES:
                            - If "strict mode violation" error: use `.first` or more specific selectors based on HTML context
                            - If "element not found": use more flexible selectors or wait for visibility
                            - If "timeout": increase timeout or use different wait strategies
                            - If "Locator.click: Timeout": the element might not be clickable, try different approach
                            - If "object str can't be used in 'await' expression": fix f-string syntax errors

                            SMART SELECTOR STRATEGIES:
                            - Look at the actual HTML structure in the element context
                            - Use parent-child relationships: `parent.locator('child-selector')`
                            - Use CSS selectors based on actual classes/attributes
                            - Try multiple fallback selectors in sequence
                            - Use `wait_for()` with appropriate state before clicking

                            CRITICAL: If you find 0 elements for any action, you MUST raise an exception to trigger retry:
                            - If element count is 0, raise Exception(f"Element not found: {{element_description}}")
                            - If element is not visible, raise Exception(f"Element not visible: {{element_description}}")
                            - If action fails, raise Exception(f"Action failed: {{action_description}}")

                            Generate robust code that uses the actual HTML structure from the element context.
                            """
                            
                            # Regenerate code with error context
                            print(f"Regenerating code for attempt {attempt + 2} with error context...")
                            retry_resp = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": retry_system_prompt},
                                    {"role": "user", "content": f"Original instruction: {instruction}\n\nPlease fix the code to handle the error: {str(e)}"}
                                ],
                                temperature=0,
                            )
                            code = retry_resp.choices[0].message.content.strip()
                            code = PersistentPlaywright.clean_code_block(code)
                            print(f" Regenerated code for attempt {attempt + 2}:\n{code}")
                            
                        except Exception as retry_error:
                            print(f" Error during retry code generation: {str(retry_error)}")
                    
                    # If this is the last attempt, return error
                    if attempt == max_retries:
                        print(f" All {max_retries + 1} attempts failed. Taking final debug screenshot...")
                        # Try to get a screenshot for debugging
                        try:
                            debug_screenshot = await _async_page.screenshot(full_page=True)
                            debug_b64 = base64.b64encode(debug_screenshot).decode('utf-8')
                            final_screenshot_path = await PersistentPlaywright.save_screenshot_to_file(
                                debug_b64, 
                                "final_debug_screenshot"
                            )
                            print(f"📸 Final debug screenshot saved to: {final_screenshot_path}")
                        except Exception as screenshot_error:
                            print(f" Failed to save final debug screenshot: {screenshot_error}")
                            debug_b64 = None
                            final_screenshot_path = None
                        
                        return {
                            "executed_code": code, 
                            "status": "error", 
                            "message": f"Execution error after {max_retries + 1} attempts: {str(e)}",
                            "page_state": await PersistentPlaywright.get_page_state_async(),
                            "debug_screenshot": debug_b64,
                            "final_screenshot_path": final_screenshot_path
                        }
                    
                    # Wait a bit before retry
                    print(f"⏳ Waiting 2 seconds before retry attempt {attempt + 2}...")
                    await asyncio.sleep(2)
        except Exception as e:
            print(f" Error generating code: {str(e)}")
            return {
                "executed_code": "", 
                "status": "error", 
                "message": f"Code generation error: {str(e)}",
                "page_state": await PersistentPlaywright.get_page_state_async()
            }
