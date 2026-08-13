"""Resilient API client that hides technical exceptions from users."""

import os
from typing import Any

import httpx

API_BASE = os.getenv("IRMA_API_BASE_URL", "http://localhost:8000").rstrip("/")


class ApiUnavailable(RuntimeError):
    pass


def get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = httpx.get(f"{API_BASE}{path}", params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiUnavailable from exc


def post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.post(f"{API_BASE}{path}", json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiUnavailable from exc
