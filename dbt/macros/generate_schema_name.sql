{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        tenhou_{{ custom_schema_name }}
    {%- endif -%}
{%- endmacro %}
