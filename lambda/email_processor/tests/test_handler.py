"""Tests for email processor Lambda handler."""

import importlib.util
from pathlib import Path

# The 'lambda' directory name is a Python keyword; use importlib to load the module.
_handler_path = Path(__file__).resolve().parents[1] / "handler.py"
_spec = importlib.util.spec_from_file_location("email_processor_handler", _handler_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
slugify = _mod.slugify


class TestSlugify:
    def test_basic(self):
        assert slugify("My Dashboard Name") == "my-dashboard-name"

    def test_special_characters(self):
        assert slugify("Dashboard (Prod) - v2!") == "dashboard-prod-v2"

    def test_extra_whitespace(self):
        assert slugify("  lots   of   spaces  ") == "lots-of-spaces"

    def test_already_slug(self):
        assert slugify("already-a-slug") == "already-a-slug"


# Fixture-based integration tests would go here using .eml files
# and moto for S3/Lambda mocking
