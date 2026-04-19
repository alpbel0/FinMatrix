"""Agents module for RAG pipeline.

This module contains agents for the chat RAG system:
- Query Understanding Agent: Extract intent, symbol, document type
- Symbol Resolver: Convert candidate symbols to canonical symbols
- Retrieval Agent: Retrieve relevant document chunks
- Response Agent: Generate Turkish responses with citations
"""

from app.services.agents.code_executor import (
    build_code_executor_agent,
    get_code_executor_agent,
    run_numerical_analysis,
)
from app.services.agents.orchestrator import (
    build_orchestrator_agent,
    get_orchestrator_agent,
    run_orchestrated_pipeline,
)
from app.services.agents.merger import merge_analysis_results
from app.services.agents.query_understanding_agent import analyze_query, is_greeting
from app.services.agents.query_classifier import classify_query, classify_query_heuristic
from app.services.agents.retrieval_agent import check_sufficient_context, prepare_source_items, run_retrieval
from app.services.agents.response_agent import generate_response
from app.services.agents.symbol_resolver import HARDCODED_ALIAS_MAP, normalize_symbol_input, resolve_symbol

__all__ = [
    # Code Executor
    "run_numerical_analysis",
    "build_code_executor_agent",
    "get_code_executor_agent",
    # Orchestrator
    "run_orchestrated_pipeline",
    "build_orchestrator_agent",
    "get_orchestrator_agent",
    "merge_analysis_results",
    # Query Understanding
    "analyze_query",
    "is_greeting",
    # Query Classifier
    "classify_query",
    "classify_query_heuristic",
    # Symbol Resolver
    "resolve_symbol",
    "normalize_symbol_input",
    "HARDCODED_ALIAS_MAP",
    # Retrieval
    "run_retrieval",
    "check_sufficient_context",
    "prepare_source_items",
    # Response
    "generate_response",
]
