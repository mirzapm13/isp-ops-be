import json
import os
import requests
import logging
from typing import Dict, Any, List, Optional

from app.services.utils.whatsapp_formatter import (
    format_field_value,
    remove_url_domain,
)

logger = logging.getLogger(__name__)

QISCUS_BASE_URL = "https://omnichannel.qiscus.com/whatsapp/v1"


def extract_qiscus_error(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("message", "error", "error_message", "details"):
            if data.get(key):
                return str(data[key])
        if data.get("errors"):
            return json.dumps(data["errors"], ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


class QiscusWhatsAppAdapter:
    def __init__(
        self,
        app_id: str | None = None,
        secret_key: str | None = None,
        channel_id: int | str | None = None,
        namespace: str | None = None,
    ):
        self.app_id = app_id or os.getenv("QISCUS_APP_ID", "")
        self.secret_key = secret_key or os.getenv("QISCUS_SECRET_KEY", "")
        self.channel_id = str(channel_id or os.getenv("QISCUS_CHANNEL_ID", ""))
        self.namespace = (
            namespace
            or os.getenv("QISCUS_WABA_NAMESPACE")
            or os.getenv("QISCUS_NAMESPACE")
            or ""
        )

    def is_configured(self) -> bool:
        return bool(
            self.app_id.strip()
            and self.secret_key.strip()
            and self.channel_id.strip()
            and self.namespace.strip()
        )

    @staticmethod
    def build_template_payload(
        phone: str,
        namespace: str,
        template_name: str,
        language_code: str,
        body_columns: List[str],
        header_columns: List[str],
        button_configs: List[Dict[str, Any]],
        row: Any,
        currency_columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        curr_set = set(currency_columns) if currency_columns is not None else None
        components: List[Dict[str, Any]] = []

        if header_columns:
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "text",
                            "text": (
                                format_field_value(col, row.get(col, ""), curr_set)
                                if col != "__NO_VALUE__"
                                else "-"
                            ),
                        }
                        for col in header_columns
                    ],
                }
            )

        if body_columns:
            components.append(
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": (
                                format_field_value(col, row.get(col, ""), curr_set)
                                if col != "__NO_VALUE__"
                                else "-"
                            ),
                        }
                        for col in body_columns
                    ],
                }
            )

        for button in button_configs:
            btn_col = button.get("column", "__NO_VALUE__")
            value = (
                "-"
                if btn_col == "__NO_VALUE__"
                else format_field_value(btn_col, row.get(btn_col, ""), curr_set)
            )
            sub_type = button.get("sub_type", "quick_reply")
            parameters = (
                [{"type": "payload", "payload": value}]
                if sub_type == "quick_reply"
                else [{"type": "text", "text": remove_url_domain(value)}]
            )
            components.append(
                {
                    "type": "button",
                    "sub_type": sub_type,
                    "index": str(button.get("index", 0)),
                    "parameters": parameters,
                }
            )

        template: Dict[str, Any] = {
            "namespace": namespace,
            "name": template_name,
            "language": {"policy": "deterministic", "code": language_code},
        }
        if components:
            template["components"] = components

        return {"to": phone, "type": "template", "template": template}

    def send_template_message(
        self, payload: Dict[str, Any], timeout: int = 30
    ) -> Dict[str, Any]:
        url = (
            os.getenv("QISCUS_BASE_URL")
            or f"{QISCUS_BASE_URL}/{self.app_id}/{self.channel_id}/messages"
        )
        headers = {
            "Qiscus-App-Id": self.app_id,
            "Qiscus-Secret-Key": self.secret_key,
            "content-type": "application/json",
        }
        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=timeout
            )
            try:
                data = response.json()
            except ValueError:
                data = {"raw_text": response.text}

            contacts = data.get("contacts", []) if isinstance(data, dict) else []
            messages = data.get("messages", []) if isinstance(data, dict) else []
            message_id = (
                messages[0].get("id", "")
                if messages and isinstance(messages[0], dict)
                else ""
            )
            wa_id = (
                contacts[0].get("wa_id", "")
                if contacts and isinstance(contacts[0], dict)
                else ""
            )
            input_number = (
                contacts[0].get("input", "")
                if contacts and isinstance(contacts[0], dict)
                else ""
            )
            ok = 200 <= response.status_code < 300
            return {
                "success": ok,
                "http_status": response.status_code,
                "message_id": message_id,
                "wa_id": wa_id,
                "input": input_number,
                "response": data,
                "error": "" if ok else extract_qiscus_error(data),
            }
        except requests.Timeout:
            return {
                "success": False,
                "http_status": None,
                "message_id": "",
                "wa_id": "",
                "input": "",
                "response": {},
                "error": "Request timed out",
            }
        except requests.RequestException as exc:
            return {
                "success": False,
                "http_status": None,
                "message_id": "",
                "wa_id": "",
                "input": "",
                "response": {},
                "error": f"Request error: {exc}",
            }

    def send_receipt_template(
        self,
        to_phone: str,
        customer_name: str,
        address: str,
        amount: str,
        package_name: str,
        package_desc: str,
        month: str,
        receipt_url: str,
        template_name: str = "kwitansi_pembayaran",
    ) -> Dict[str, Any]:
        """
        Sends WhatsApp receipt template message via Qiscus WhatsApp Omnichannel API v1.
        Endpoint: https://omnichannel.qiscus.com/whatsapp/v1/{app_id}/{channel_id}/messages
        """
        url = (
            os.getenv("QISCUS_BASE_URL")
            or f"https://omnichannel.qiscus.com/whatsapp/v1/{self.app_id}/{self.channel_id}/messages"
        )

        headers = {
            "Qiscus-App-Id": self.app_id,
            "Qiscus-Secret-Key": self.secret_key,
            "Content-Type": "application/json",
        }

        # Body variable parameters {{1}} to {{7}}
        body_parameters = [
            {"type": "text", "text": str(customer_name or "-")},
            {"type": "text", "text": str(address or "-")},
            {"type": "text", "text": str(amount or "-")},
            {"type": "text", "text": str(package_name or "-")},
            {"type": "text", "text": str(package_desc or "-")},
            {"type": "text", "text": str(month or "-")},
            {"type": "text", "text": str(receipt_url or "-")},
        ]

        payload = {
            "to": to_phone,
            "type": "template",
            "template": {
                "namespace": self.namespace,
                "name": template_name,
                "language": {
                    "policy": "deterministic",
                    "code": "id",
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": body_parameters,
                    }
                ],
            },
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=20
            )
            response.raise_for_status()
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.content else {},
            }
        except requests.exceptions.RequestException as e:
            error_data = None
            if e.response is not None and e.response.content:
                try:
                    error_data = e.response.json()
                except Exception:
                    error_data = e.response.text
            else:
                error_data = str(e)

            logger.error(f"Failed to send Qiscus WhatsApp to {to_phone}: {error_data}")
            return {
                "success": False,
                "status_code": e.response.status_code if e.response is not None else 500,
                "error": error_data,
            }
