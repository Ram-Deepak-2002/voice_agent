from fastapi import APIRouter
import openai
import asyncio
import base64
import re
from ..constants.env import OPENAI_API_KEY
from playwright.async_api import async_playwright


router = APIRouter()


async def capture_screenshot(url: str) -> str:
    """Opens the URL in Playwright, captures a screenshot, and returns it as base64."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(2000)
        screenshot_bytes = await page.screenshot(full_page=True)
        await browser.close()
    return base64.b64encode(screenshot_bytes).decode("utf-8")


async def generate_playwright_script(screenshot_b64: str, task: str) -> str:
    """Sends screenshot + task to OpenAI and gets back Playwright script."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an assistant that generates Playwright automation code in Python. IMPORTANT: Use ONLY the ASYNC API (async_playwright, await keywords). Return ONLY the Python code without any explanations, comments, or markdown formatting. The code should be executable and properly indented. Use 'from playwright.async_api import async_playwright' and 'async with async_playwright() as p:'. DO NOT use asyncio.run() or create new event loops - the code will run in an existing async context."},
            {"role": "user", "content": f"Task: {task}. Use Playwright ASYNC API in Python. Return only the executable Python code with proper indentation and await keywords. Do not use asyncio.run()."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Here is the screenshot of the webpage:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                ],
            }
        ],
    )

    script = response.choices[0].message.content
    return script


def convert_sync_to_async(script: str) -> str:
    """Convert sync Playwright code to async if needed."""
    script = re.sub(r'asyncio\.run\([^)]+\)', '', script)
    script = re.sub(r'await asyncio\.run\([^)]+\)', '', script)
    
    script = script.replace('from playwright.sync_api import sync_playwright', 'from playwright.async_api import async_playwright')
    script = script.replace('sync_playwright()', 'async_playwright()')
    
    playwright_methods = [
        'browser.launch()',
        'browser.new_page()',
        'page.goto(',
        'page.click(',
        'page.fill(',
        'page.type(',
        'page.select_option(',
        'page.check(',
        'page.uncheck(',
        'page.hover(',
        'page.dblclick(',
        'page.right_click(',
        'page.press(',
        'page.keyboard.type(',
        'page.keyboard.press(',
        'page.mouse.click(',
        'page.mouse.down(',
        'page.mouse.up(',
        'page.mouse.move(',
        'page.wait_for_timeout(',
        'page.wait_for_selector(',
        'page.wait_for_load_state(',
        'browser.close()'
    ]
    
    for method in playwright_methods:
        if f'{method}' in script and f'await {method}' not in script:
            script = script.replace(f'{method}', f'await {method}')
    
    lines = script.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('asyncio.run'):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def extract_python_code(text: str) -> str:
    """Extract Python code from AI response, preserving indentation."""
    text = re.sub(r'```python\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    lines = text.split('\n')
    python_lines = []
    in_code_block = False
    
    for line in lines:
        stripped_line = line.strip()
        
        if not stripped_line and not in_code_block:
            continue
            
        if stripped_line.startswith('#') and not in_code_block:
            continue
            
        if (stripped_line.startswith('import ') or 
            stripped_line.startswith('from ') or 
            stripped_line.startswith('async def ') or 
            stripped_line.startswith('def ') or 
            stripped_line.startswith('async with ') or
            stripped_line.startswith('with ') or
            stripped_line.startswith('await ') or
            stripped_line.startswith('page.') or
            stripped_line.startswith('browser.') or
            stripped_line.startswith('p.')):
            in_code_block = True
        
        if in_code_block:
            python_lines.append(line)  # Keep original line with indentation
    
    return '\n'.join(python_lines)


async def execute_script(script: str):
    """Dynamically execute the generated Playwright script."""
    try:
        # Extract only the Python code
        clean_script = extract_python_code(script)
        if not clean_script.strip():
            raise ValueError("No executable Python code found in the response")

        # Convert sync Playwright code to async if needed
        clean_script = convert_sync_to_async(clean_script)

        print(f"Executing script:\n{clean_script}")  # Debug output

        # Properly indent each line for the async function
        indented_lines = []
        for line in clean_script.splitlines():
            if line.strip():  # Only indent non-empty lines
                indented_lines.append("    " + line)
            else:
                indented_lines.append(line)  # Keep empty lines as is
        
        indented_code = "\n".join(indented_lines)

        # Wrap inside async function
        wrapped_script = f"""async def execute_automation():
{indented_code}
"""

        print(f"Wrapped script:\n{wrapped_script}")  # Debug output

        # Globals available inside exec
        exec_globals = {
            "async_playwright": async_playwright,
            "asyncio": asyncio,
        }

        # Local namespace for the script
        local_namespace = {}

        # Compile and exec the wrapped script
        compiled_script = compile(wrapped_script, "<string>", "exec")
        exec(compiled_script, exec_globals, local_namespace)

        # Finally, run the generated async function
        await local_namespace["execute_automation"]()

    except Exception as e:
        print(f"Error executing script: {e}")
        print(f"Script content: {script}")
        raise


@router.post("/automate")
async def automate(url: str, task: str):
    screenshot_b64 = await capture_screenshot(url)
    playwright_code = await generate_playwright_script(screenshot_b64, task)

    await execute_script(playwright_code)

    return {
        "message": "Task executed",
        "generated_code": playwright_code
    }