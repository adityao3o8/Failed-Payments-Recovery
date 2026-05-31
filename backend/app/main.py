from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.database import Base, engine
from app.webhooks.razorpay import router as razorpay_router
from app.webhooks.stripe import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Recover — Payment Failure Recovery",
    description="Smart retry engine for failed subscription payments",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(webhook_router)
app.include_router(razorpay_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "recover"}
