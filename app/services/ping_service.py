import re
from app.config.settings import ROUTERS
from app.adapters.mikrotik.client import connect_router
from app.adapters.mikrotik.pppoe import find_active
from app.adapters.mikrotik.system import ping

"""
Ping-related business logic
"""

# def ping_ip(router_id: str, ip: str, count: int = 3):
#     # TODO: implement ping via adapter
#     return {
#         "target": ip,
#         "sent": count,
#         "received": 0
#     }

def ping_pppoe_user(username: str, router_id: str, count: int = 3):
    """
    Ping PPPoE user on a specific router.
    """

    router = next((r for r in ROUTERS if r["id"] == router_id), None)
    if not router:
        return None, "ROUTER_NOT_FOUND"

    api = None
    try:
        api = connect_router(router)

        active = find_active(api, username)
        if not active:
            return None, "USER_NOT_ACTIVE"

        ip_address = active[0].get("address")
        if not ip_address:
            return None, "NO_IP_ADDRESS"

        raw_results = ping(api, ip_address, count)

        return {
            "router": {
                "id": router["id"],
                "name": router["name"]
            },
            "target": ip_address,
            "results": _format_ping_results(raw_results)
        }, None

    except Exception as e:
        return None, str(e)

    finally:
        if api:
            api.close()


import re

def _parse_time_to_ms(time_str: str) -> float:
    """
    Parse RouterOS ping time into milliseconds.

    Examples:
      '10ms'        -> 10
      '4500us'      -> 4.5
      '1ms752us'    -> 1.752
      '2s15ms'      -> 2015
    """
    total_ms = 0.0

    # Find all (number, unit) pairs
    matches = re.findall(r'(\d+(?:\.\d+)?)(us|ms|s)', time_str)

    for value, unit in matches:
        value = float(value)

        if unit == "us":
            total_ms += value / 1000
        elif unit == "ms":
            total_ms += value
        elif unit == "s":
            total_ms += value * 1000

    return round(total_ms, 3) if total_ms > 0 else None



def _format_ping_results(raw):
    times_ms = []

    for r in raw:
        if "time" in r:
            parsed = _parse_time_to_ms(r["time"])
            if parsed is not None:
                times_ms.append(parsed)

    sent = len(raw)
    received = len(times_ms)

    return {
        "sent": sent,
        "received": received,
        "loss_percent": int(((sent - received) / sent) * 100) if sent else 100,
        "avg_ms": round(sum(times_ms) / len(times_ms), 2) if times_ms else None,
        "details": raw
    }
