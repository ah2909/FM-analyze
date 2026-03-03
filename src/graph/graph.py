from langgraph.graph import StateGraph, START, END

from .state import AnalysisState
from .nodes.data_fetcher import fetch_market_data
from .nodes.risk_assessor import run_risk_assessor
from .nodes.alert_generator import run_alert_generator
from .nodes.insight_engine import run_insight_engine
from .nodes.aggregator import aggregate_results


def build_graph() -> StateGraph:
    """
    Assembles the LangGraph DAG:

        START
          ↓
        fetch_market_data   (CoinGecko + pandas/ta indicators)
          ↓
        risk_assessor       (Gemini structured output)
          ↓
        alert_generator     (Gemini structured output — reads risk_assessment)
          ↓
        insight_engine      (Gemini structured output — reads risk + alerts)
          ↓
        aggregate           (pure Python merge → final_output)
          ↓
        END
    """
    builder = StateGraph(AnalysisState)

    builder.add_node("fetch_market_data", fetch_market_data)
    builder.add_node("risk_assessor",     run_risk_assessor)
    builder.add_node("alert_generator",   run_alert_generator)
    builder.add_node("insight_engine",    run_insight_engine)
    builder.add_node("aggregate",         aggregate_results)

    builder.add_edge(START,               "fetch_market_data")
    builder.add_edge("fetch_market_data", "risk_assessor")
    builder.add_edge("risk_assessor",     "alert_generator")
    builder.add_edge("alert_generator",   "insight_engine")
    builder.add_edge("insight_engine",    "aggregate")
    builder.add_edge("aggregate",         END)

    return builder.compile()


# Compiled once at import time — reused across all requests
analysis_graph = build_graph()
