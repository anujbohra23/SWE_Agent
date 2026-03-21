"""
Assemble the LangGraph StateGraph for the SWE agent.

Graph topology:

  START
    │
    ▼
  retriever          (index repo, retrieve chunks)
    │
    ▼
  planner            (decide target files, write plan)
    │
    ▼
  patcher            (generate search/replace edits)
    │
    ▼
  executor           (sandbox copy → apply patch → run tests)
    │
    ▼ should_retry? ─────────────────────┐
    │  (success or retries exhausted)    │  (failure + retries remain)
    ▼                                    ▼
  reporter                           reflector
    │                                    │
    ▼                                    └──→ executor (loop)
   END
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, END

from app.state import AgentState
from app.nodes.retriever import retriever_node
from app.nodes.planner import planner_node
from app.nodes.patcher import patcher_node
from app.nodes.executor import executor_node
from app.nodes.reflector import reflector_node
from app.nodes.reporter import reporter_node
from app.config import settings


# ---------------------------------------------------------------------------
# Conditional edge logic
# ---------------------------------------------------------------------------

def should_retry(state: AgentState) -> Literal["reflector", "reporter"]:
    """
    After executor: decide whether to reflect+retry or report.
    """
    test_result = state.get("test_result")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", settings.max_retries)

    # If tests passed → go to reporter
    if test_result and test_result.success:
        return "reporter"

    # If we've hit the retry limit → report (as failure)
    if retry_count >= max_retries:
        return "reporter"

    # Otherwise reflect and retry
    return "reflector"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Construct and compile the agent graph.
    Returns the compiled graph ready for .invoke().
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("retriever", retriever_node)
    graph.add_node("planner", planner_node)
    graph.add_node("patcher", patcher_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("reporter", reporter_node)

    # Entry point
    graph.set_entry_point("retriever")

    # Linear edges
    graph.add_edge("retriever", "planner")
    graph.add_edge("planner", "patcher")
    graph.add_edge("patcher", "executor")

    # Conditional branch after executor
    graph.add_conditional_edges(
        "executor",
        should_retry,
        {
            "reflector": "reflector",
            "reporter": "reporter",
        },
    )

    # After reflection: go back to executor with revised patch
    graph.add_edge("reflector", "executor")

    # Terminal
    graph.add_edge("reporter", END)

    return graph.compile()