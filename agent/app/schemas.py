from typing import List, Optional, Union
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class CatalogResponse(BaseModel):
    metrics_raw: str
    dimensions_raw: str


class QueryRequest(BaseModel):
    metrics: List[str] = Field(..., description="Metric names, e.g. ['sales_value_lc']")
    dimensions: Optional[List[str]] = Field(
        default=None,
        description="Dimension names, e.g. ['sales__geo_id','sales__channel_id']",
    )
    where: Optional[str] = Field(
        default=None,
        description="Optional MetricFlow where clause. Prefer structured filters in future.",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Optional start time, format depends on your semantic time configuration.",
    )
    end_time: Optional[str] = Field(
        default=None,
        description="Optional end time, format depends on your semantic time configuration.",
    )
    limit: int = Field(default=200, ge=1, le=1000)


class QueryResponse(BaseModel):
    returncode: int
    stdout: str
    stderr: str


class StructuredFilter(BaseModel):
    dimension: str
    op: str  # "=", "!=", "in"
    value: Union[str, List[str]]


class PlannedQuery(BaseModel):
    metrics: List[str]
    dimensions: List[str] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    filters: List[StructuredFilter] = Field(default_factory=list)
    limit: int = 200


class NLQRequest(BaseModel):
    question: str
    limit: int = Field(default=200, ge=1, le=1000)


class MetricDefinition(BaseModel):
    name: str
    description: Optional[str] = None
    type: Optional[str] = None  # simple, ratio, derived, etc.


class QueryExplanation(BaseModel):
    metrics: List[MetricDefinition] = Field(default_factory=list)
    dimensions: List[str] = Field(default_factory=list)
    filters: List[StructuredFilter] = Field(default_factory=list)
    time_range: Optional[dict] = None  # {"start": "...", "end": "..."}
    where_clause: Optional[str] = None  # Compiled where clause for audit


class NLQResponse(BaseModel):
    plan: PlannedQuery
    execution: QueryResponse
    explanation: QueryExplanation