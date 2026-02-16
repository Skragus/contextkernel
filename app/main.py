from fastapi import FastAPI

from app.kernel.router import router as kernel_router

app = FastAPI(title="ContextKernel", version="0.1.0")
app.include_router(kernel_router)


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
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
