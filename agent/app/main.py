import os
import time
import re
import logging
from datetime import datetime
from collections import defaultdict
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


def parse_date_from_formatted(date_str: str) -> datetime:
    """Parse formatted date strings like 'Oct 15 2024' or '2024-10-15T00:00:00'"""
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Try ISO timestamp format first
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})T', date_str)
    if iso_match:
        return datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
    
    # Try formatted date like "Oct 15 2024"
    parts = date_str.split()
    if len(parts) == 3:
        month_name, day, year = parts
        try:
            month = month_names.index(month_name) + 1
            return datetime(int(year), month, int(day))
        except (ValueError, IndexError):
            pass
    
    return None


def aggregate_time_granularity(stdout: str, target_granularity: str) -> str:
    """
    Post-process MetricFlow output to aggregate day-level data into weeks/months/years.
    Only aggregates if the output appears to be day-level data.
    """
    if target_granularity not in ['week', 'month', 'year']:
        return stdout
    
    lines = stdout.split('\n')
    if len(lines) < 2:
        return stdout
    
    # Find header and data start - skip progress/spinner lines
    header = None
    data_start_idx = None
    separator_idx = None
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Skip progress messages
        if any(x in line_stripped for x in ['Initiating', 'Success', '⠋', '⠙', '⠹', '⠸', '✔', '🦄', 'query completed']):
            continue
        # Skip separator lines, but track them
        if re.match(r'^[-=]+$', line_stripped):
            if header:
                separator_idx = i
            continue
        # Find header (contains time/date keywords)
        if header is None and any(x in line_stripped.lower() for x in ['time', 'date', 'day', 'month', 'year', 'metric_time']):
            header = line_stripped
            continue
        # Data starts after separator (or next line after header if no separator)
        if header and data_start_idx is None:
            if separator_idx is not None and i > separator_idx:
                data_start_idx = i
                break
            elif separator_idx is None:
                # No separator, data should be on next non-empty line after header
                header_line_idx = next((j for j, l in enumerate(lines) if header in l), None)
                if header_line_idx is not None and i > header_line_idx:
                    data_start_idx = i
                    break
    
    if not header or data_start_idx is None:
        return stdout  # Can't find header or data
    
    # Parse header to find time column index
    header_parts = re.split(r'\s{2,}|\t', header.strip())
    time_col_idx = None
    metric_col_idx = None
    for idx, col in enumerate(header_parts):
        if any(x in col.lower() for x in ['time', 'date', 'day', 'month', 'year']):
            time_col_idx = idx
        elif any(x in col.lower() for x in ['complaint', 'metric', 'value', 'count']):
            metric_col_idx = idx
    
    if time_col_idx is None or metric_col_idx is None:
        return stdout  # Can't determine columns
    
    # Parse data rows
    data_rows = []
    for line in lines[data_start_idx:]:
        line = line.strip()
        if not line or re.match(r'^[-=]+$', line) or any(x in line for x in ['Initiating', 'Success', '⠋', '⠙', '⠹', '⠸', '✔']):
            continue
        
        # Split by multiple spaces or tabs
        parts = re.split(r'\s{2,}|\t', line)
        if len(parts) <= max(time_col_idx, metric_col_idx):
            continue
        
        date_str = parts[time_col_idx].strip()
        value_str = parts[metric_col_idx].strip().replace(',', '')
        
        try:
            # Try parsing date (handles both ISO timestamps and formatted dates)
            date = parse_date_from_formatted(date_str)
            # Skip if we couldn't parse the date or if value is not numeric
            if not date:
                continue
            value = float(value_str)
            data_rows.append((date, value))
        except (ValueError, IndexError, TypeError):
            continue
    
    if not data_rows:
        return stdout  # No data to aggregate
    
    # Aggregate by target granularity
    aggregated = defaultdict(float)
    for date, value in data_rows:
        if target_granularity == 'week':
            # ISO week
            iso_year, iso_week, _ = date.isocalendar()
            key = (iso_year, iso_week)
        elif target_granularity == 'month':
            key = (date.year, date.month)
        elif target_granularity == 'year':
            key = date.year
        else:
            continue
        aggregated[key] += value
    
    # Format output
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    result_lines = []
    
    # Update header
    granularity_name = target_granularity.capitalize()
    new_header = header.replace('Day', granularity_name).replace('metric_time', granularity_name.lower())
    result_lines.append(new_header)
    result_lines.append('-' * len(new_header))
    
    # Format aggregated rows
    sorted_keys = sorted(aggregated.keys())
    for key in sorted_keys:
        if target_granularity == 'week':
            year, week = key
            # Get first day of ISO week
            first_day = datetime.strptime(f'{year}-W{week:02d}-1', '%G-W%V-%u')
            label = f"Week of {month_names[first_day.month - 1]} {first_day.day}, {year}"
        elif target_granularity == 'month':
            year, month = key
            label = f"{month_names[month - 1]} {year}"
        elif target_granularity == 'year':
            label = str(key)
        else:
            continue
        
        value = aggregated[key]
        # Format value with commas if it's a whole number
        if value == int(value):
            value_str = f"{int(value):,}"
        else:
            value_str = f"{value:,.2f}"
        
        result_lines.append(f"{label}\t{value_str}")
    
    return '\n'.join(result_lines)


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
  "time_granularity": null or "day"|"week"|"month"|"year",
  "limit": {req.limit}
}}

    Rules:
    - Do NOT output SQL.
    - Use only these metrics: {sorted(list(ALLOWLIST["metrics"]))}
    - Use only these dimensions: {sorted(list(ALLOWLIST["dimensions"]))}
    - Keep dimensions minimal.
    - For "which X has the most Y" queries (e.g., "which ward has the most complaints?"):
      * Only include the grouping dimension (X) in dimensions list, NOT filtering dimensions
      * If filtering by status (e.g., "not closed"), use the filter but DON'T include status in dimensions (aggregate across all non-filtered statuses)
      * Set limit to 1 to return only the top result
      * Example: "which ward has the most complaints that are not closed?" → dimensions: ["complaint__ward_id"], filters: [{{"dimension": "complaint__last_status", "op": "!=", "value": "CLOSED"}}], limit: 1
    - If the user asks for time filtering and you can express it, use start_time/end_time (ISO dates in YYYY-MM-DD format).
    - For "last 2 years", calculate start_time as exactly 2 years before today (e.g., if today is 2025-01-17, use "2023-01-17"). Use null for end_time (means current date).
    - For time-based queries, detect granularity from user request:
      * "by days", "daily", "per day" → time_granularity: "day"
      * "by weeks", "weekly", "per week" → time_granularity: "week"  
      * "by months", "monthly", "per month", "month wise" → time_granularity: "month"
      * "by years", "yearly", "per year", "year over year" → time_granularity: "year"
    - Always include metric_time in dimensions for time-based queries.
    - Include time_granularity in your JSON response if the user specifies a granularity.
    - For PGR queries: Use complaint__ward_id, complaint__channel, complaint__priority, complaint__complaint_type dimensions.
    - For PGR status filtering: Use uppercase status values - "CLOSED", "ASSIGNED", "RESOLVED", "REOPENED", "OPEN" (not "Closed", "Assigned", etc.).
    - For Sales queries: Use sales__geo_id, sales__channel_id, sales__period_yyyymm dimensions.
    - For period filtering (e.g., "202412"), use filters with dimension "sales__period_yyyymm" and op "=".
"""

    try:
        plan_start = time.time()
        plan_dict = await llm.chat_json(system=system.strip(), user=req.question)
        plan = PlannedQuery(**plan_dict)
        plan_time = time.time() - plan_start
        
        logger.info(f"[NLQ] Plan generated in {plan_time:.2f}s: metrics={plan.metrics}, dimensions={plan.dimensions}, filters={len(plan.filters)}, limit={plan.limit}")

        # Check if this is a "which X has the most" query for post-processing
        # We'll aggregate results client-side after MetricFlow returns grouped data
        is_top_query = (plan.limit == 1 or "which" in req.question.lower() and ("most" in req.question.lower() or "highest" in req.question.lower()))
        
        # For top N queries, keep the LLM's limit of 1 (don't overwrite with req.limit)
        # For other queries, enforce requested limit
        if not is_top_query:
            plan.limit = req.limit

        # Validate allowlist + filter ops
        validate_plan(plan.metrics, plan.dimensions, [f.model_dump() for f in plan.filters], ALLOWLIST)

        # MetricFlow requires dimensions to be in group-by list when filtering by them
        # Always add filter dimensions to dimensions list (required by MetricFlow)
        filter_dimensions = {f.dimension for f in plan.filters}
        existing_dimensions = set(plan.dimensions)
        missing_dimensions = filter_dimensions - existing_dimensions
        if missing_dimensions:
            plan.dimensions.extend(sorted(missing_dimensions))

        # Compile safe where clause from structured filters
        where = compile_where([f.model_dump() for f in plan.filters])

        # For "which X has the most" queries, we need to allow MetricFlow to return more results
        # so we can aggregate across filter dimensions client-side
        # Set limit higher to get all groups, then aggregate and filter client-side
        query_limit = plan.limit
        if is_top_query:
            # Get enough rows to aggregate across filter dimensions
            query_limit = min(plan.limit * 100, 1000)  # Allow up to 1000 rows for aggregation

        # Execute via MetricFlow only
        mf_start = time.time()
        result = mf.query(
            metrics=plan.metrics,
            dimensions=plan.dimensions,
            where=where,
            start_time=plan.start_time,
            end_time=plan.end_time,
            limit=query_limit,
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

        # Post-process result if time_granularity is week/month/year and we have day-level data
        if plan.time_granularity and plan.time_granularity in ['week', 'month', 'year'] and result.stdout:
            result.stdout = aggregate_time_granularity(result.stdout, plan.time_granularity)

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
            "is_top_query": is_top_query,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
