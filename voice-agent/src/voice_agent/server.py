from .main import app
from .routes.interaction import router
from fastapi.middleware.cors import CORSMiddleware
import logging 

logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.get("/")(lambda: {"message": "Hello, World!"})
app.include_router(router, prefix="/api", tags=["automate"])

def main():
    import uvicorn
    logger.info("Starting server")
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()