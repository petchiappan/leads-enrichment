"""
Prometheus metrics definitions for Leads Enrichment AI.

Defines counters and histograms for pipeline execution, LLM call timings,
token consumption, external API errors, and guardrail violations.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# Pipeline execution counter
pipeline_runs_total = Counter(
    "enrichment_pipeline_total",
    "Total enrichment pipeline executions",
    ["status"],  # e.g., 'completed', 'needs_review', 'failed'
)

# Pipeline execution duration
pipeline_duration_seconds = Histogram(
    "enrichment_pipeline_duration_seconds",
    "Total end-to-end enrichment pipeline duration in seconds",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
)

# LLM call duration
llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "Duration of individual LLM completions in seconds",
    ["step_name", "model"],
    buckets=[0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
)

# Token usage counter
llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens consumed by step and direction",
    ["step_name", "token_type"],  # token_type: 'input' or 'output'
)

# External API errors
api_call_errors_total = Counter(
    "api_call_errors_total",
    "Total external data provider API errors",
    ["source"],  # 'clearbit', 'lusha', 'hunter', 'newsapi'
)

# Guardrail violations
guardrail_violations_total = Counter(
    "guardrail_violations_total",
    "Total guardrail flags triggered",
    ["field", "rule"],  # e.g. rule='confidence_threshold', 'sanitise_injection', 'max_length'
)
