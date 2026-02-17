from fastapi import FastAPI

from app.kernel.router import router as kernel_router
from app.kernel.data_router import router as data_router

app = FastAPI(title="ContextKernel", version="0.1.0")
app.include_router(kernel_router)
app.include_router(data_router)


@app.get("/")
async def root() -> dict:
    return {
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "kernel": {
            "presets": "/kernel/presets",
            "presets_detail": "/kernel/presets/{id}",
            "presets_run": "/kernel/presets/{id}/run",
            "cards": "/kernel/cards/{type}",
            "goals": "/kernel/goals",
            "goals_progress": "/kernel/goals/progress",
            "data_latest": "/kernel/data/latest",
            "data_history": "/kernel/data/history",
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
