# Primary Deterministic Engine (Celery Workers)

## Queue Structure
- Use Redis as the Celery broker.
- Task name: `run_enrichment_pipeline`

## Execution Steps (Must execute in this order):
1. `validate_input()`: Pydantic check of the POST payload.
2. `fetch_apis()`: Trigger async calls to Google News, Lusha, etc. Use `tenacity` for max 3 retries.
3. `evaluate_intelligence_gate()`: Fast LLM check to see if gaps exist.
4. If gaps exist -> trigger `spawn_fallback_agent()` (See File 03).
5. If no gaps -> trigger `save_final_lineage()`.