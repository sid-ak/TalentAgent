"""Firestore emulator REST harness for testing security rules (Spec §11, ADR-0012).

Drives the Firestore emulator's REST API directly with unsigned JWT bearer tokens without
requiring Node runtime or admin SDK.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

PROJECT_ID = "demo-talentagent"
"""The pinned demo project ID ensuring the emulator never contacts real Google Cloud services."""

DEFAULT_EMULATOR_HOST = "127.0.0.1:8080"
"""Default host and port for the local Firestore emulator."""


def get_emulator_host() -> str | None:
    """Return the Firestore emulator host from environment or None if not set."""
    return os.environ.get("FIRESTORE_EMULATOR_HOST")


def make_jwt(component: str | None = None, sub: str = "test-user") -> str:
    """Build an unsigned JWT token accepted by the Firestore emulator in demo projects."""
    header = {"alg": "none", "typ": "JWT"}
    now = int(time.time())
    payload: dict[str, Any] = {
        "iss": f"https://securetoken.google.com/{PROJECT_ID}",
        "aud": PROJECT_ID,
        "auth_time": now,
        "user_id": sub,
        "sub": sub,
        "iat": now,
        "exp": now + 3600,
        "firebase": {"sign_in_provider": "custom", "identities": {}},
    }
    if component is not None:
        payload["component"] = component

    def b64_url(d: dict[str, Any]) -> str:
        s = json.dumps(d, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(s).rstrip(b"=").decode("utf-8")

    return f"{b64_url(header)}.{b64_url(payload)}."


def _py_to_firestore(val: Any) -> dict[str, Any]:
    """Convert Python value to Firestore REST value representation."""
    if val is None:
        return {"nullValue": None}
    if isinstance(val, bool):
        return {"booleanValue": val}
    if isinstance(val, int):
        return {"integerValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, list):
        return {"arrayValue": {"values": [_py_to_firestore(v) for v in val]}}
    if isinstance(val, dict):
        return {"mapValue": {"fields": {k: _py_to_firestore(v) for k, v in val.items()}}}
    raise TypeError(f"Unsupported Firestore type: {type(val)}")


def _firestore_to_py(val: dict[str, Any]) -> Any:
    """Convert Firestore REST value representation to Python value."""
    if "nullValue" in val:
        return None
    if "booleanValue" in val:
        return val["booleanValue"]
    if "integerValue" in val:
        return int(val["integerValue"])
    if "doubleValue" in val:
        return float(val["doubleValue"])
    if "stringValue" in val:
        return val["stringValue"]
    if "arrayValue" in val:
        values = val["arrayValue"].get("values", [])
        return [_firestore_to_py(v) for v in values]
    if "mapValue" in val:
        fields = val["mapValue"].get("fields", {})
        return {k: _firestore_to_py(v) for k, v in fields.items()}
    return None


class EmulatorClient:
    """HTTP REST client interacting with the Firestore emulator."""

    def __init__(self, host: str | None = None) -> None:
        """Initialize the client pointing to the emulator host."""
        self.host = host or get_emulator_host() or DEFAULT_EMULATOR_HOST
        self.base_url = f"http://{self.host}/v1/projects/{PROJECT_ID}/databases/(default)/documents"

    def clear(self) -> None:
        """Delete all documents in the emulator database."""
        url = f"http://{self.host}/emulator/v1/projects/{PROJECT_ID}/databases/(default)/documents"
        req = urllib.request.Request(url, method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                _ = resp.read()
        except Exception:
            pass

    def create_document(
        self,
        collection: str,
        doc_id: str,
        data: dict[str, Any],
        component: str | None = None,
        admin: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Create a document in the specified collection using REST API."""
        url = f"{self.base_url}/{collection}?documentId={doc_id}"
        fields = {k: _py_to_firestore(v) for k, v in data.items()}
        body = json.dumps({"fields": fields}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if admin:
            headers["Authorization"] = "Bearer owner"
        elif component is not None:
            headers["Authorization"] = f"Bearer {make_jwt(component=component)}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                return resp.status, resp_body
        except urllib.error.HTTPError as e:
            err_body = {}
            with contextlib.suppress(Exception):
                err_body = json.loads(e.read().decode("utf-8"))
            return e.code, err_body

    def get_document(
        self,
        collection: str,
        doc_id: str,
        component: str | None = None,
        admin: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Retrieve a document from the specified collection."""
        url = f"{self.base_url}/{collection}/{doc_id}"
        headers = {}
        if admin:
            headers["Authorization"] = "Bearer owner"
        elif component is not None:
            headers["Authorization"] = f"Bearer {make_jwt(component=component)}"

        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                fields = resp_body.get("fields", {})
                return resp.status, {k: _firestore_to_py(v) for k, v in fields.items()}
        except urllib.error.HTTPError as e:
            return e.code, {}

    def update_document(
        self,
        collection: str,
        doc_id: str,
        data: dict[str, Any],
        component: str | None = None,
        admin: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Update an existing document in the specified collection."""
        url = f"{self.base_url}/{collection}/{doc_id}"
        fields = {k: _py_to_firestore(v) for k, v in data.items()}
        body = json.dumps({"fields": fields}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if admin:
            headers["Authorization"] = "Bearer owner"
        elif component is not None:
            headers["Authorization"] = f"Bearer {make_jwt(component=component)}"

        req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
        try:
            with urllib.request.urlopen(req) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
                return resp.status, resp_body
        except urllib.error.HTTPError as e:
            return e.code, {}

    def delete_document(
        self,
        collection: str,
        doc_id: str,
        component: str | None = None,
        admin: bool = False,
    ) -> tuple[int, dict[str, Any]]:
        """Delete a document in the specified collection."""
        url = f"{self.base_url}/{collection}/{doc_id}"
        headers = {}
        if admin:
            headers["Authorization"] = "Bearer owner"
        elif component is not None:
            headers["Authorization"] = f"Bearer {make_jwt(component=component)}"

        req = urllib.request.Request(url, headers=headers, method="DELETE")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, {}
        except urllib.error.HTTPError as e:
            return e.code, {}
