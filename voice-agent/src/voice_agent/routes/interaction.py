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
    await websocket.send_text("✅ Connected to Playwright WebSocket")

    while True:
        try:
            msg = await websocket.receive_text()
            if msg.lower() in {"quit", "exit"}:
                await websocket.send_text("Closing WebSocket session")
                await websocket.close()
                break
            
            # Send acknowledgment that instruction was received
            await websocket.send_text(f"🔄 Processing: {msg}")
            
            # Execute the instruction
            result = PersistentPlaywright.execute_instruction(msg)
            
            # Send detailed response
            if result["status"] == "success":
                await websocket.send_text(f"✅ Success!\nGenerated Code:\n{result['executed_code']}\n\nMessage: {result['message']}")
            else:
                await websocket.send_text(f"❌ Error!\nGenerated Code:\n{result['executed_code']}\n\nError: {result['message']}")

        except Exception as e:
            await websocket.send_text(f"❌ WebSocket Error: {str(e)}")
            # break
