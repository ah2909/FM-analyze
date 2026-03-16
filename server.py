import logging
import uvicorn

from src.config.config import API, LLM

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG if API.ENV == "development" else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if API.ENV == "development":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("debugpy listening on port 5678 — attach VS Code to debug")

    logger.info(f"Starting Portfolio Analyzer on port {API.PORT}")
    logger.info(f"LLM Model : {LLM.GEMINI_MODEL}")

    uvicorn.run(
        "src.app:app",
        host=API.HOST,
        port=API.PORT,
        reload=(API.ENV == "development"),
        log_level="debug" if API.ENV == "development" else "info",
    )
