import os
import re
from typing import Any, Dict, Optional
from urllib.parse import quote
import requests


class SmartOLTError(Exception):
    pass


def _clean_response_error(text: str, max_len: int = 200) -> str:
    if not text:
        return "Empty error response"
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        return cleaned[: max_len - 3] + "..."
    return cleaned


class SmartOLTAdapter:
    def __init__(self):
        if not os.getenv("SMARTOLT_API_KEY"):
            raise RuntimeError("SMARTOLT_API_KEY not configured")

        self.base_url = os.getenv("SMARTOLT_BASE_URL")
        self.session = requests.Session()
        self.session.headers.update({
            "X-Token": os.getenv("SMARTOLT_API_KEY"),
            "Content-Type": "application/json"
        })

    # ---------- Internal Request Wrapper ----------
    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        response = self.session.request(
            method=method,
            url=url,
            json=json,
            params=params,
            timeout=timeout
        )

        if not response.ok:
            error_detail = _clean_response_error(response.text)
            raise SmartOLTError(
                f"SmartOLT API error {response.status_code}: {error_detail}"
            )

        return response.json()

    # ---------- Public API Methods ----------

    # def get_olts(self) -> Dict:
    #     return self._request("GET", "olts")

    # def get_onus(self, olt_id: int) -> Dict:
    #     return self._request("GET", f"onus", params={"olt_id": olt_id})

    # def authorize_onu(self, olt_id: int, data: Dict) -> Dict:
    #     """
    #     data example:
    #     {
    #         "sn": "...",
    #         "name": "...",
    #         "profile": "...",
    #         ...
    #     }
    #     """
    #     return self._request("POST", f"onus/authorize", json=data)

    # def update_onu(self, onu_id: int, data: Dict) -> Dict:
    #     return self._request("PUT", f"onus/{onu_id}", json=data)

    # def delete_onu(self, onu_id: int) -> Dict:
    #     return self._request("DELETE", f"onus/{onu_id}")
    
    def disable_onu(self, onu_id):
        safe_onu_id = quote(str(onu_id).strip(), safe="")
        return self._request("POST", f"/api/onu/disable/{safe_onu_id}")
    
    def enable_onu(self, onu_id):
        safe_onu_id = quote(str(onu_id).strip(), safe="")
        return self._request("POST", f"/api/onu/enable/{safe_onu_id}")

