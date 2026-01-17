{% test test_tat_reasonableness(model, tat_column, sla_column) %}
  {# Custom test: Validate TAT is reasonable compared to SLA #}
  {# TAT should be within 2x SLA for resolved cases #}
  {# Note: This test warns on outliers but doesn't fail (severity: warn) #}
  
  select
    {{ tat_column }} as tat_hours,
    {{ sla_column }} as sla_hours
  from {{ model }}
  where {{ tat_column }} is not null
    and {{ sla_column }} is not null
    and {{ tat_column }} > ({{ sla_column }} * 2)

{% endtest %}
