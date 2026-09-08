from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.analysis import router as analysis_router


app = FastAPI(
    title="Denial Navigator AI - Damco Demo",
    version="0.2.0",
    description="Sanitized denied-claim decision API using deterministic validation first.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")


@app.get("/")
def read_root():
    return {"service": "denial-navigator-damco", "status": "ok"}
