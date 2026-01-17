{% test test_status_transition(model, status_column, event_type_column) %}
  {# Custom test: Validate status transitions are logical #}
  {# Status should match event type (e.g., CaseResolved -> RESOLVED) #}
  
  select
    {{ status_column }} as status,
    {{ event_type_column }} as event_type
  from {{ model }}
  where {{ status_column }} is not null
    and {{ event_type_column }} is not null
    and (
      ({{ event_type_column }} = 'CaseSubmitted' and {{ status_column }} not in ('OPEN', 'ASSIGNED')) or
      ({{ event_type_column }} = 'CaseAssigned' and {{ status_column }} != 'ASSIGNED') or
      ({{ event_type_column }} = 'CaseResolved' and {{ status_column }} != 'RESOLVED') or
      ({{ event_type_column }} = 'CaseClosed' and {{ status_column }} != 'CLOSED') or
      ({{ event_type_column }} = 'CaseReopened' and {{ status_column }} != 'REOPENED')
    )

{% endtest %}
