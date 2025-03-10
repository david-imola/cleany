"""
Schema Validation
"""

import yaml
import fastjsonschema

def _load_schema_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


def validate_yaml(yaml_data, schema_path):
    """Validate YAML data against a JSON schema file."""
    schema = _load_schema_file(schema_path)
    val = fastjsonschema.compile(schema)
    val(yaml_data)


def validate(doc_path, schema_path):
    """Validate YAML document file against a JSON schema file."""
    with open(doc_path, 'r', encoding='utf-8') as file:
        doc = yaml.safe_load(file)
    validate_yaml(doc, schema_path)
