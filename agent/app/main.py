import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .mf import MetricFlowClient
from .schemas import HealthResponse, CatalogResponse, QueryRequest, QueryResponse, NLQRequest, NLQResponse, PlannedQuery
from .llm import OllamaClient
from .guardrails import parse_catalog_text, validate_plan, compile_where

app = FastAPI(title="MetricFlow Agent API", version="0.1.0")

# Enable CORS for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default to dbt/ directory relative to project root (analytics/)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DBT_PROJECT_DIR = os.getenv("DBT_PROJECT_DIR", os.path.join(_project_root, "dbt"))
PROFILES_DIR = os.getenv("DBT_PROFILES_DIR", os.path.join(_project_root, "dbt"))

mf = MetricFlowClient(dbt_project_dir=DBT_PROJECT_DIR, profiles_dir=PROFILES_DIR)

# LLM configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")

llm = OllamaClient(base_url=OLLAMA_BASE_URL, model=OLLAMA_MODEL)
ALLOWLIST = {"metrics": set(), "dimensions": set()}


@app.on_event("startup")
def load_allowlist():
    global ALLOWLIST
    try:
        data = mf.list_metrics_and_dimensions()
        ALLOWLIST = parse_catalog_text(data["metrics_raw"], data["dimensions_raw"])
    except Exception as e:
        # Log error but don't fail startup - allowlist will be empty
        print(f"Warning: Failed to load allowlist: {e}")


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/catalog", response_model=CatalogResponse)
def catalog():
    try:
        data = mf.list_metrics_and_dimensions()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    try:
        result = mf.query(
            metrics=req.metrics,
            dimensions=req.dimensions,
            where=req.where,
            start_time=req.start_time,
            end_time=req.end_time,
            limit=req.limit,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nlq", response_model=NLQResponse)
async def nlq(req: NLQRequest):
    system = f"""
You are a data query planner. Convert the user question into a JSON plan for MetricFlow.

Output ONLY valid JSON with this schema:
{{
  "metrics": ["..."],
  "dimensions": ["..."],
  "start_time": null or "YYYY-MM-DD",
  "end_time": null or "YYYY-MM-DD",
  "filters": [{{"dimension":"...","op":"="|"!="|"in","value":"..."|["..."]}}],
  "limit": {req.limit}
}}

Rules:
- Do NOT output SQL.
- Use only these metrics: {sorted(list(ALLOWLIST["metrics"]))}
- Use only these dimensions: {sorted(list(ALLOWLIST["dimensions"]))}
- Keep dimensions minimal.
- If the user asks for time filtering and you can express it, use start_time/end_time (ISO dates).
- Prefer filters on sales__geo_id, sales__channel_id, sales__period_yyyymm when asked.
- For period filtering (e.g., "202412"), use filters with dimension "sales__period_yyyymm" and op "=".
"""

    try:
        plan_dict = await llm.chat_json(system=system.strip(), user=req.question)
        plan = PlannedQuery(**plan_dict)

        # Enforce requested limit
        plan.limit = req.limit

        # Validate allowlist + filter ops
        validate_plan(plan.metrics, plan.dimensions, [f.model_dump() for f in plan.filters], ALLOWLIST)

        # MetricFlow requires dimensions to be in group-by list when filtering by them
        # Automatically add filter dimensions to the dimensions list if not already present
        filter_dimensions = {f.dimension for f in plan.filters}
        existing_dimensions = set(plan.dimensions)
        missing_dimensions = filter_dimensions - existing_dimensions
        if missing_dimensions:
            plan.dimensions.extend(sorted(missing_dimensions))

        # Compile safe where clause from structured filters
        where = compile_where([f.model_dump() for f in plan.filters])

        # Execute via MetricFlow only
        result = mf.query(
            metrics=plan.metrics,
            dimensions=plan.dimensions,
            where=where,
            start_time=plan.start_time,
            end_time=plan.end_time,
            limit=plan.limit,
        )

        return {
            "plan": plan.model_dump(),
            "execution": {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
