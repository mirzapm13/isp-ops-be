import requests
from typing import Any, Dict, Optional
import os


class SmartOLTError(Exception):
    pass


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
            raise SmartOLTError(
                f"SmartOLT API error {response.status_code}: {response.text}"
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
        return self._request("POST", f"/api/onu/disable/{onu_id}")
    
    def enable_onu(self, onu_id):
        return self._request("POST", f"/api/onu/enable/{onu_id}")

