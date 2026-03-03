import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.analyzer import router
from .config.config import API

logging.basicConfig(
    level=logging.DEBUG if API.ENV == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Portfolio Analyzer",
    description="AI-powered crypto portfolio risk and insight analysis using LangGraph",
    version="1.0.0",
    docs_url="/docs" if API.ENV == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
