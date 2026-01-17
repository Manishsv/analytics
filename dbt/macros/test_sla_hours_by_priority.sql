{% test test_sla_hours_by_priority(model, column_name) %}
  {# Custom test: Validate SLA hours match expected values by priority #}
  {# Expected SLA hours: CRITICAL=4, HIGH=24, MEDIUM=72, LOW=168 #}
  
  select
    priority,
    sla_hours
  from {{ model }}
  where priority is not null
    and sla_hours is not null
    and (
      (priority = 'CRITICAL' and sla_hours != 4) or
      (priority = 'HIGH' and sla_hours != 24) or
      (priority = 'MEDIUM' and sla_hours != 72) or
      (priority = 'LOW' and sla_hours != 168)
    )

{% endtest %}
