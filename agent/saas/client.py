"""
HTTP Client for RF Suite Hosted SaaS Microservice.
Used by AI Agents and CLI scripts to invoke remote cloud solvers over HTTPS.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional, List


class RFSaasClient:
    """Client for communicating with the Hosted RF Suite SaaS service."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("RF_SAAS_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("RF_SAAS_API_KEY", "")

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        raw_response: bool = False
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "User-Agent": "rf-agent-saas-client/1.0"
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                if raw_response:
                    return resp.read()
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("detail", err_body)
            except Exception:
                msg = err_body
            raise RuntimeError(f"SaaS API Error ({e.code}) on {method} {url}: {msg}")
        except Exception as e:
            raise RuntimeError(f"Connection failed to SaaS service at {url}: {str(e)}")

    def check_health(self) -> Dict[str, Any]:
        """Checks remote API health and toolchain status."""
        return self._request("GET", "/health")

    def synthesize_spec(
        self,
        prompt: str,
        name: Optional[str] = None,
        f_0_ghz: Optional[float] = None,
        z0_ohm: float = 50.0,
        substrate: str = "FR4",
        er: float = 4.4,
        h_mm: float = 1.6
    ) -> Dict[str, Any]:
        """Synthesizes CircuitSpec mathematically via remote service."""
        payload = {
            "prompt": prompt,
            "name": name,
            "f_0_ghz": f_0_ghz,
            "z0_ohm": z0_ohm,
            "substrate": substrate,
            "er": er,
            "h_mm": h_mm
        }
        return self._request("POST", "/v1/specs/synthesize", payload=payload)

    def run_stages(
        self,
        project_name: str,
        stages: Optional[List[str]] = None,
        spec: Optional[Dict[str, Any]] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executes one or more engineering stages on the remote service."""
        payload = {
            "stages": stages,
            "spec": spec,
            "desc": desc
        }
        return self._request("POST", f"/v1/projects/{project_name}/run", payload=payload)

    def get_summary(self, project_name: str) -> Dict[str, Any]:
        """Retrieves project metrics, DRC count, and artifacts."""
        return self._request("GET", f"/v1/projects/{project_name}/summary")

    def download_artifact(self, project_name: str, remote_file_path: str, local_save_path: str) -> str:
        """Downloads a specific artifact file from the SaaS service."""
        os.makedirs(os.path.dirname(local_save_path), exist_ok=True)
        raw_bytes = self._request(
            "GET",
            f"/v1/projects/{project_name}/artifacts/{remote_file_path}",
            raw_response=True
        )
        with open(local_save_path, "wb") as f:
            f.write(raw_bytes)
        return local_save_path

    def sync_all_artifacts(self, project_name: str, local_project_dir: str) -> List[str]:
        """Downloads all generated artifacts for a project into the local directory."""
        summary = self.get_summary(project_name)
        artifacts = summary.get("artifacts", {})
        downloaded = []

        for rel_path in artifacts.keys():
            dest = os.path.join(local_project_dir, rel_path)
            self.download_artifact(project_name, rel_path, dest)
            downloaded.append(dest)

        return downloaded
