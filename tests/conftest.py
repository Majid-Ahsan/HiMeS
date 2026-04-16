"""Shared pytest fixtures for HiMeS tests."""

from __future__ import annotations

import pytest
import respx


@pytest.fixture
def mock_db_rest(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Mock the self-hosted db-rest and public fallback.

    Usage:
        def test_something(mock_db_rest):
            mock_db_rest.get("/locations").respond(json=[{"id": "8000259", ...}])
    """
    # Allow routing to both primary (docker internal) and fallback (public)
    return respx_mock


@pytest.fixture
def mock_nominatim(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Mock the Nominatim geocoding endpoint."""
    return respx_mock
