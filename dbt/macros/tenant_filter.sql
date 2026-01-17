{% macro tenant_filter(tenant_id_column='tenant_id', tenant_context='current_tenant()') %}
  {# 
    Multi-tenant data isolation macro.
    Use this in models to filter data by tenant.
    
    Usage:
      - In models: {{ tenant_filter() }}
      - With custom tenant context: {{ tenant_filter(tenant_context='session.tenant_id') }}
  #}
  
  {% if var('tenant_id', none) is not none %}
    {{ tenant_id_column }} = '{{ var("tenant_id") }}'
  {% else %}
    -- No tenant filter applied (all tenants visible)
    -- In production, this should be enforced via row-level security
    true
  {% endif %}
{% endmacro %}
