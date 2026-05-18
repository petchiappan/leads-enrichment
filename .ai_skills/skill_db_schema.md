# Database Architecture (Postgres + pgvector)

## Tables to Implement (Alembic Migrations)
1. `leads`: Stores final enriched data. Columns: id, raw_input, enriched_data (JSONB), status.
2. `pipeline_logs`: Layer 3 requirement. Columns: request_id, step_name, status, payload (JSONB), timestamp.
3. `admin_config`: Layer 3 requirement. Columns: setting_key, setting_value (e.g., 'enable_redis_cache': 'true').
4. `vector_embeddings`: Layer 5 requirement. Columns: lead_id, embedding (pgvector vector type).

**Strict Rule:** Use SQLAlchemy 2.0 syntax. Do not use Pinecone; strictly use `pgvector` for the embeddings table.