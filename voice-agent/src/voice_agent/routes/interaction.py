from fastapi import APIRouter, WebSocket
from ..playwright.automation_class import PersistentPlaywright
router = APIRouter()

# open browser
@router.get("/playwright/open")
def open_browser():
    PersistentPlaywright.open("https://farmce-dev.oraczen.xyz/", headless=False, slow_mo=200)
    return {"status": "browser opened"}


# close browser
@router.get("/playwright/close")
def close_browser():
    PersistentPlaywright.close()
    return {"status": "browser closed"}


@router.websocket("/playwright/ws")
async def playwright_ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Connected to Playwright WebSocket")
    
    # Open async browser for WebSocket operations
    try:
        await PersistentPlaywright.open_async("https://farmce-dev.oraczen.xyz/", headless=False, slow_mo=200)
        await websocket.send_text("Async browser opened and ready!")
        
        # Send initial page state
        initial_state = await PersistentPlaywright.get_page_state_async()
        if "error" not in initial_state:
            await websocket.send_text(f"Current page: {initial_state.get('title', 'Unknown')} at {initial_state.get('url', 'Unknown')}")
        
    except Exception as e:
        await websocket.send_text(f"Failed to open browser: {str(e)}")
        await websocket.close()
        return
    
    try:
        while True:
            try:
                msg = await websocket.receive_text()
                print(f"Received message: {msg}")
                
                # Handle special commands
                if msg.lower() in {"quit", "exit", "close"}:
                    await websocket.send_text("Closing WebSocket session...")
                    break
                elif msg.lower() in {"status", "state"}:
                    state = await PersistentPlaywright.get_page_state_async()
                    if "error" not in state:
                        await websocket.send_text(f"Current state: {state.get('title', 'Unknown')} at {state.get('url', 'Unknown')}")
                    else:
                        await websocket.send_text(f"State error: {state.get('error')}")
                    continue
                elif msg.lower() in {"screenshot", "snap"}:
                    state = await PersistentPlaywright.get_page_state_async()
                    if "error" not in state and "screenshot_base64" in state:
                        await websocket.send_text(f"Screenshot captured (base64 length: {len(state['screenshot_base64'])})")
                    else:
                        await websocket.send_text("Failed to capture screenshot")
                    continue
                elif msg.lower().startswith("context "):
                    # Extract search terms from "context get started" or "context dairy"
                    search_terms = msg[8:].split()  # Remove "context " prefix
                    element_context = await PersistentPlaywright.get_element_context_async(search_terms)
                    if "error" not in element_context:
                        await websocket.send_text(f" Found {element_context.get('total_found', 0)} elements for: {', '.join(search_terms)}")
                        for ctx in element_context.get("element_contexts", [])[:3]:
                            await websocket.send_text(f"Element: {ctx['search_term']} - Tag: {ctx['tag_name']} - Attrs: {list(ctx['attributes'].keys())}")
                    else:
                        await websocket.send_text(f"Context error: {element_context.get('error')}")
                    continue
                
                # Process automation instruction
                await websocket.send_text(f"Processing instruction: '{msg}'")
                await websocket.send_text(" Generating Playwright code...")
                
                # Execute the instruction using async method
                result = await PersistentPlaywright.execute_instruction_async(msg)
                
                # Check if there was a retry and inform the user
                if "attempt" in str(result.get("message", "")) and "attempts" in str(result.get("message", "")):
                    await websocket.send_text("Code was retried with enhanced context after initial failure")
                
                # Send detailed response with enhanced formatting
                if result["status"] == "success":
                    await websocket.send_text("Code executed successfully!")
                    await websocket.send_text(f"Generated Code:\n```python\n{result['executed_code']}\n```")
                    await websocket.send_text(f" Message: {result['message']}")
                    
                    # Send updated page state
                    if "page_state" in result and "error" not in result["page_state"]:
                        page_state = result["page_state"]
                        await websocket.send_text(f"Updated page: {page_state.get('title', 'Unknown')} at {page_state.get('url', 'Unknown')}")
                        
                        # Send screenshot info if available
                        if "screenshot_base64" in page_state:
                            await websocket.send_text(f"Screenshot captured (base64 length: {len(page_state['screenshot_base64'])})")
                else:
                    await websocket.send_text("Execution failed!")
                    await websocket.send_text(f"Generated Code:\n```python\n{result['executed_code']}\n```")
                    await websocket.send_text(f" Error: {result['message']}")
                    
                    # Still send page state even on error
                    if "page_state" in result and "error" not in result["page_state"]:
                        page_state = result["page_state"]
                        await websocket.send_text(f"Current page: {page_state.get('title', 'Unknown')} at {page_state.get('url', 'Unknown')}")
                        
                        # Send screenshot info if available
                        if "screenshot_base64" in page_state:
                            await websocket.send_text(f"Screenshot captured (base64 length: {len(page_state['screenshot_base64'])})")

            except Exception as e:
                await websocket.send_text(f"Processing Error: {str(e)}")
                print(f"WebSocket processing error: {str(e)}")
                
    except Exception as e:
        await websocket.send_text(f"WebSocket Error: {str(e)}")
        print(f"WebSocket error: {str(e)}")
    finally:
        try:
            await websocket.send_text("🧹 Cleaning up browser session...")
            await PersistentPlaywright.close_async()
            await websocket.send_text("Browser closed successfully")
        except Exception as e:
            await websocket.send_text(f" Error during cleanup: {str(e)}")
        finally:
            await websocket.close()
