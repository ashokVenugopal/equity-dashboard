"""
Equity Dashboard — FastAPI backend entry point.

Thin API layer over equity-shared views and query helpers.
Serves JSON to the Next.js frontend via SSR fetch calls.
"""
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_server_config
from backend.core.logging_setup import setup_logging

# Setup logging before anything else
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Equity Dashboard API",
    description="Market data, fundamentals, and observation logging for the equity dashboard.",
    version="0.1.0",
)

# CORS for Next.js frontend
server_config = get_server_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=server_config["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from backend.api.health import router as health_router
from backend.api.market import router as market_router
from backend.api.observations import router as observations_router
from backend.api.index import router as index_router
from backend.api.instrument import router as instrument_router
from backend.api.derivatives import router as derivatives_router
from backend.api.charts import router as charts_router
from backend.api.company import router as company_router
from backend.api.sectors import router as sectors_router
from backend.api.search import router as search_router
from backend.api.heatmap import router as heatmap_router
from backend.api.global_view import router as global_view_router
from backend.api.pine import router as pine_router
from backend.api.export import router as export_router

app.include_router(health_router)
app.include_router(market_router)
app.include_router(observations_router)
app.include_router(index_router)
app.include_router(instrument_router)
app.include_router(derivatives_router)
app.include_router(charts_router)
app.include_router(company_router)
app.include_router(sectors_router)
app.include_router(search_router)
app.include_router(heatmap_router)
app.include_router(global_view_router)
app.include_router(pine_router)
app.include_router(export_router)

logger.info("Equity Dashboard API initialized. Routes: %d", len(app.routes))


def main():
    """Run the server."""
    config = get_server_config()
    logger.info("Starting server on %s:%d", config["host"], config["port"])
    uvicorn.run(
        "backend.main:app",
        host=config["host"],
        port=config["port"],
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
