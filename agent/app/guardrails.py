from typing import Dict, List, Set, Optional
import re

_ALLOWED_OPS = {"=", "!=", "in"}

def parse_catalog_text(metrics_raw: str, dimensions_raw: str) -> Dict[str, Set[str]]:
    """
    Best-effort parsing from mf list outputs.
    You can tighten this later if you switch to a structured catalog endpoint.
    """
    metrics = set()
    for line in metrics_raw.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("available", "name", "metric", "looking", "found", "format", "list")):
            continue
        # Match bullet points: "• metric_name: ..." or "• metric_name"
        if "•" in line or "•" in line:
            parts = line.split("•")[-1].strip()
            name = parts.split(":")[0].strip()
            if re.match(r"^[a-zA-Z0-9_]+$", name):
                metrics.add(name)
        # Also match plain metric names
        elif re.match(r"^[a-zA-Z0-9_]+", line):
            name = line.split()[0]
            if re.match(r"^[a-zA-Z0-9_]+$", name):
                metrics.add(name)

    dimensions = set()
    for line in dimensions_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip header lines
        if line.lower().startswith(("available", "name", "dimension", "looking", "found", "format", "list", "we've")):
            continue
        # Match bullet points: "• dimension_name" or "• dimension_name," 
        # The bullet can be unicode "•" (U+2022) or similar
        if "•" in line or "•" in line or line.startswith("•"):
            # Extract after bullet - handle both unicode bullets
            for bullet_char in ["•", "•"]:
                if bullet_char in line:
                    parts = line.split(bullet_char, 1)[-1].strip()
                    break
            else:
                parts = line.lstrip("•").strip()
            # Extract dimension name (may have double underscores like complaint__ward_id)
            # Handle both "complaint__ward_id" and "complaint__ward_id," and "complaint__ward_id and 3 more"
            name = parts.split(",")[0].split(" and")[0].strip()
            # Allow underscores (including double underscores like complaint__ward_id)
            if re.match(r"^[a-zA-Z0-9_]+$", name) and name and len(name) > 1:
                dimensions.add(name)
        # Also match plain dimension names starting with letter/underscore (may have underscores)
        elif re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*", line):
            name = line.split(",")[0].split(" and")[0].strip()
            # Allow underscores (including double underscores for entity-prefixed dimensions)
            if re.match(r"^[a-zA-Z0-9_]+$", name) and name and len(name) > 1:
                dimensions.add(name)

    return {"metrics": metrics, "dimensions": dimensions}

def validate_plan(metrics: List[str], dimensions: List[str], filters: List[dict], allow: Dict[str, Set[str]]) -> None:
    for m in metrics:
        if m not in allow["metrics"]:
            raise ValueError(f"Metric not allowed: {m}")

    for d in dimensions:
        if d not in allow["dimensions"]:
            raise ValueError(f"Dimension not allowed: {d}")

    for f in filters:
        dim = f.get("dimension")
        op = f.get("op")
        if dim not in allow["dimensions"]:
            raise ValueError(f"Filter dimension not allowed: {dim}")
        if op not in _ALLOWED_OPS:
            raise ValueError(f"Filter op not allowed: {op}")

def _quote(v: str) -> str:
    # conservative quoting; rejects control chars
    if any(c in v for c in ["'", ";", "\n", "\r", "\t"]):
        raise ValueError("Unsafe filter value.")
    return f"'{v}'"

def compile_where(filters: List[dict]) -> Optional[str]:
    if not filters:
        return None

    clauses = []
    for f in filters:
        dim = f["dimension"]
        op = f["op"]
        val = f["value"]

        if op in ("=", "!="):
            if not isinstance(val, str):
                raise ValueError("Filter value must be a string for '=' or '!='.")
            # Normalize status-like values to uppercase for PGR status dimensions
            # This handles case mismatches where LLM generates "Closed" but data has "CLOSED"
            if dim.endswith("__last_status") or dim.endswith("__status"):
                val = val.upper()
            clauses.append(f"{dim} {op} {_quote(val)}")

        elif op == "in":
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                raise ValueError("Filter value must be a list of strings for 'in'.")
            quoted = ", ".join(_quote(x) for x in val)
            clauses.append(f"{dim} IN ({quoted})")

    return " AND ".join(clauses)
