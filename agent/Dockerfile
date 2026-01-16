FROM python:3.10-slim

WORKDIR /app

# System deps (optional but useful)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY agent/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install dbt + metricflow in-container so mf is available
RUN pip install --no-cache-dir dbt-core==1.11.2 dbt-trino metricflow==0.11.0

COPY agent/app /app/app

# Copy dbt project into container (assumes repo has dbt/ at root)
COPY dbt /app/dbt

ENV DBT_PROJECT_DIR=/app/dbt
ENV DBT_PROFILES_DIR=/app/dbt

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
