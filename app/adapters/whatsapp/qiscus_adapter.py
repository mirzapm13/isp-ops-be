import os
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


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
        self.channel_id = channel_id or os.getenv("QISCUS_CHANNEL_ID", "")
        self.namespace = (
            namespace
            or os.getenv(
                "QISCUS_WABA_NAMESPACE",
                "c1d1cc94_9127_4c26_992e_5231627f5299",
            )
        )

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
            # "to": to_phone,
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

        # print(payload, headers)

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
