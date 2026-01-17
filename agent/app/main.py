import os
import time
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .mf import MetricFlowClient
from .schemas import HealthResponse, CatalogResponse, QueryRequest, QueryResponse, NLQRequest, NLQResponse, PlannedQuery, QueryExplanation, MetricDefinition
from .llm import OllamaClient
from .guardrails import parse_catalog_text, validate_plan, compile_where

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MetricFlow Agent API", version="0.1.0")

# Enable CORS for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (configurable via env vars)
from .middleware import RateLimiter
import os
REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
REQUESTS_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
app.add_middleware(RateLimiter, requests_per_minute=REQUESTS_PER_MINUTE, requests_per_hour=REQUESTS_PER_HOUR)
logger.info(f"Rate limiting enabled: {REQUESTS_PER_MINUTE} req/min, {REQUESTS_PER_HOUR} req/hour")

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
        logger.info(f"Loaded allowlist: {len(ALLOWLIST['metrics'])} metrics, {len(ALLOWLIST['dimensions'])} dimensions")
        # Log sample PGR dimensions if present
        pgr_dims = [d for d in ALLOWLIST['dimensions'] if 'complaint' in d.lower()]
        if pgr_dims:
            logger.info(f"PGR dimensions detected: {sorted(pgr_dims)[:5]}")
    except Exception as e:
        # Log error but don't fail startup - allowlist will be empty
        logger.warning(f"Failed to load allowlist: {e}")


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
async def nlq(req: NLQRequest, request: Request):
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(f"[NLQ] Request from {client_ip}: question='{req.question[:100]}', limit={req.limit}")
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
    - For PGR queries: Use complaint__ward_id, complaint__channel, complaint__priority, complaint__complaint_type dimensions.
    - For Sales queries: Use sales__geo_id, sales__channel_id, sales__period_yyyymm dimensions.
    - For period filtering (e.g., "202412"), use filters with dimension "sales__period_yyyymm" and op "=".
"""

    try:
        plan_start = time.time()
        plan_dict = await llm.chat_json(system=system.strip(), user=req.question)
        plan = PlannedQuery(**plan_dict)
        plan_time = time.time() - plan_start
        
        logger.info(f"[NLQ] Plan generated in {plan_time:.2f}s: metrics={plan.metrics}, dimensions={plan.dimensions}, filters={len(plan.filters)}")

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
        mf_start = time.time()
        result = mf.query(
            metrics=plan.metrics,
            dimensions=plan.dimensions,
            where=where,
            start_time=plan.start_time,
            end_time=plan.end_time,
            limit=plan.limit,
        )
        mf_time = time.time() - mf_start
        
        # Estimate row count from stdout (best effort)
        row_count = 0
        if result.stdout:
            # Count non-header, non-separator lines in output
            lines = result.stdout.split('\n')
            for line in lines:
                line = line.strip()
                if line and not any(x in line for x in ['Initiating', 'Success', '─', '==', '⠋', '⠙', '⠹', '⠸', '✔']):
                    # Check if it looks like data (has columns)
                    if line and len(line.split()) > 1:
                        row_count += 1
        
        total_time = time.time() - start_time
        
        logger.info(f"[NLQ] Query executed in {mf_time:.2f}s, total={total_time:.2f}s, returncode={result.returncode}, rows~={row_count}")

        # Build explanation for audit/transparency
        # Get metric definitions from catalog (best effort - may be empty if catalog parse failed)
        metric_definitions = []
        for metric_name in plan.metrics:
            # Try to find description from catalog or use defaults
            metric_info = {
                "name": metric_name,
                "description": None,  # Could be enhanced to parse from catalog
                "type": None,  # Could be enhanced to parse from catalog
            }
            metric_definitions.append(MetricDefinition(**metric_info))

        explanation = QueryExplanation(
            metrics=metric_definitions,
            dimensions=plan.dimensions,
            filters=plan.filters,
            time_range={
                "start": plan.start_time,
                "end": plan.end_time,
            } if plan.start_time or plan.end_time else None,
            where_clause=where,
        )

        return {
            "plan": plan.model_dump(),
            "execution": {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
            "explanation": explanation.model_dump(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
