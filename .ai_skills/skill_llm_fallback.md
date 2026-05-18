# Fallback Agent & Micro Extractor

When the Hybrid Escalation Gate is triggered, the AI agent must output data matching this exact Pydantic schema structure.

## Required Pydantic Models
- `MissingGapsRequest`: list of missing fields (e.g., `["ceo_email", "company_revenue"]`).
- `AgenticExtractionResult`:
  - `company_name`: str
  - `ceo_name`: str | None
  - `ceo_email`: str | None
  - `company_description`: str | None
  - `linkedin_url`: str | None
  - `linkedin_company_url`: str | None
  - `employee_count`: int | None
  - `company_website`: str | None
  - `funding_raised`: str | None
  - `industry`: str | None
  - `founding_year`: int | None
  - `news_articles`: list[str] | None
  - `confidence_score`: float
  - `sources_used`: list[str]

**Strict Rule:** Use `client.chat.completions.create` with `response_format={"type": "json_object"}`.