"""Pytest configuration for the test suite."""

import sys
from pathlib import Path

# Ensure the backend app is importable in tests
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import pytest

# Single source of truth for the admin/test user password expected by integration tests
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "admin123")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "devansh123")

@pytest.fixture
def admin_password():
    return TEST_ADMIN_PASSWORD

