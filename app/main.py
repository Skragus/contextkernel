from fastapi import FastAPI

from app.kernel.router import router as kernel_router

app = FastAPI(title="ContextKernel", version="0.1.0")
app.include_router(kernel_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
