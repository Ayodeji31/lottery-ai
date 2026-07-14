from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from auth import auth_router, seed_admin, db
from lottery import lottery_router, ensure_data
from payments import payments_router, webhook_router

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="LottoPredict API")

app.include_router(auth_router)
app.include_router(lottery_router)
app.include_router(payments_router)
app.include_router(webhook_router)

cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/")
async def root():
    return {"message": "LottoPredict API running"}


@app.on_event("startup")
async def startup():
    await seed_admin()
    await ensure_data()
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    db.client.close()
