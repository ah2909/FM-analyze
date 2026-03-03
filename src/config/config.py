import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)



class LLMConfig:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.4"))
    MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "8192"))


class CoinGeckoConfig:
    API_KEY: str = os.getenv("COINGECKO_API_KEY", "")
    BASE_URL: str = os.getenv("COINGECKO_URL", "https://api.coingecko.com/api/v3")
    HISTORY_DAYS: int = int(os.getenv("COINGECKO_HISTORY_DAYS", "90"))


class IndicatorConfig:
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    BB_PERIOD: int = 20
    BB_STD_DEV: float = 2.0


class APIConfig:
    PORT: int = int(os.getenv("PORT", "7070"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    CACHE_TTL: int = int(os.getenv("ANALYSIS_CACHE_TTL", "300"))
    ENV: str = os.getenv("APP_ENV", "development")
    GRAPH_TIMEOUT: int = int(os.getenv("GRAPH_TIMEOUT", "90"))


LLM = LLMConfig()
COINGECKO = CoinGeckoConfig()
INDICATORS = IndicatorConfig()
API = APIConfig()
