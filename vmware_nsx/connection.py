"""NSX Manager REST API client with session management.

Uses httpx for HTTP communication. Authenticates via POST /api/session/create
with Basic Auth, then reuses X-XSRF-TOKEN for subsequent requests.

Supports both Policy API (/policy/api/v1/) and Management API (/api/v1/).
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

import httpx

from vmware_nsx.config import AppConfig, TargetConfig, load_config

_log = logging.getLogger("vmware-nsx.connection")


class NsxClient:
    """REST client for a single NSX Manager."""

    def __init__(self, target: TargetConfig, password: str) -> None:
        self._target = target
        self._base_url = f"https://{target.host}:{target.port}"
        self._token: str | None = None

        # Suppress InsecureRequestWarning for self-signed certs
        if not target.verify_ssl:
            warnings.filterwarnings("ignore", message="Unverified HTTPS request")

        self._client = httpx.Client(
            base_url=self._base_url,
            verify=target.verify_ssl,
            timeout=30.0,
            auth=(target.username, password),
        )
        self._create_session()

    def _create_session(self) -> None:
        """Authenticate and store session token."""
        resp = self._client.post("/api/session/create")
        resp.raise_for_status()
        self._token = resp.headers.get("x-xsrf-token")
        if not self._token:
            raise ConnectionError("NSX session creation succeeded but no X-XSRF-TOKEN returned")
        # Store cookies from response
        _log.info("NSX session created for %s", self._target.host)

    def _headers(self) -> dict[str, str]:
        """Request headers with XSRF token."""
        h = {"Accept": "application/json"}
        if self._token:
            h["X-XSRF-TOKEN"] = self._token
        return h

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """Single GET request. Returns JSON response."""
        resp = self._client.get(path, headers=self._headers(), params=params)
        if resp.status_code in (401, 403):
            _log.info("Session expired, re-authenticating...")
            self._create_session()
            resp = self._client.get(path, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def get_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Paginated GET. Follows cursor until all results collected."""
        all_results: list[dict] = []
        params = dict(params) if params else {}
        while True:
            data = self.get(path, params=params)
            results = data.get("results", [])
            all_results.extend(results)
            cursor = data.get("cursor")
            if not cursor:
                break
            params["cursor"] = cursor
        return all_results

    def post(self, path: str, json_data: dict[str, Any] | None = None) -> dict:
        """POST request for write operations."""
        resp = self._client.post(path, headers=self._headers(), json=json_data)
        if resp.status_code in (401, 403):
            self._create_session()
            resp = self._client.post(path, headers=self._headers(), json=json_data)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def put(self, path: str, json_data: dict[str, Any]) -> dict:
        """PUT request (create or replace)."""
        resp = self._client.put(path, headers=self._headers(), json=json_data)
        if resp.status_code in (401, 403):
            self._create_session()
            resp = self._client.put(path, headers=self._headers(), json=json_data)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def patch(self, path: str, json_data: dict[str, Any]) -> dict:
        """PATCH request (partial update)."""
        resp = self._client.patch(path, headers=self._headers(), json=json_data)
        if resp.status_code in (401, 403):
            self._create_session()
            resp = self._client.patch(path, headers=self._headers(), json=json_data)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def delete(self, path: str) -> None:
        """DELETE request."""
        resp = self._client.delete(path, headers=self._headers())
        if resp.status_code in (401, 403):
            self._create_session()
            resp = self._client.delete(path, headers=self._headers())
        resp.raise_for_status()

    def is_alive(self) -> bool:
        """Check if session is still valid."""
        try:
            self.get("/api/v1/cluster/status")
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


class ConnectionManager:
    """Manages connections to multiple NSX Manager targets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._clients: dict[str, NsxClient] = {}

    @classmethod
    def from_config(cls, config: AppConfig | None = None) -> ConnectionManager:
        """Create a ConnectionManager from config, loading defaults if needed."""
        cfg = config or load_config()
        return cls(cfg)

    def connect(self, target_name: str | None = None) -> NsxClient:
        """Get or create an NsxClient for the specified target."""
        name = target_name or self._config.default_target
        if not name:
            raise ValueError("No target specified and no default target configured")

        if name in self._clients and self._clients[name].is_alive():
            return self._clients[name]

        target_cfg = self._config.get_target(name)
        if target_cfg is None:
            available = ", ".join(self._config.targets.keys())
            raise ValueError(f"Target '{name}' not found. Available: {available}")

        password = target_cfg.get_password(name)
        client = NsxClient(target_cfg, password)
        self._clients[name] = client
        return client

    def disconnect(self, target_name: str) -> None:
        """Close and remove a client."""
        if target_name in self._clients:
            self._clients[target_name].close()
            del self._clients[target_name]

    def disconnect_all(self) -> None:
        """Disconnect from all targets."""
        for name in list(self._clients):
            self.disconnect(name)

    def list_targets(self) -> list[str]:
        """List available target names."""
        return list(self._config.targets.keys())

    def list_connected(self) -> list[str]:
        """List currently connected target names."""
        return list(self._clients.keys())
