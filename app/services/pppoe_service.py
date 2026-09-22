from app.config.settings import ROUTERS
from app.adapters.mikrotik.client import connect_router
from app.adapters.mikrotik.pppoe import add_pppoe_secret, change_nat_to_addresses, change_pppoe_profile, delete_secret, get_pppoe_profiles, isolir_on_router,disable_secret, enable_secret, find_all_active, find_all_secret, find_secret, find_active, disconnect_active, find_active_by_caller_id, find_secret_by_last_caller_id
from app.services.log_service import log_event
import difflib
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

MAC_PREFIX_LENGTH = 10


def _normalize_mac(mac_address: str | None) -> str:
    if not mac_address:
        return ""
    return "".join(char for char in mac_address.lower() if char.isalnum())


def _mac_matches(search_mac: str, candidate_mac: str | None) -> bool:
    normalized_search = _normalize_mac(search_mac)
    normalized_candidate = _normalize_mac(candidate_mac)

    if len(normalized_search) < MAC_PREFIX_LENGTH:
        return normalized_search and normalized_search == normalized_candidate

    return normalized_candidate.startswith(normalized_search[:MAC_PREFIX_LENGTH])


def _mac_similarity_score(search_mac: str, candidate_mac: str | None) -> tuple[int, int, float]:
    s = _normalize_mac(search_mac)
    c = _normalize_mac(candidate_mac)
    if not s or not c:
        return (0, 0, 0.0)

    exact_match = 1 if s == c else 0

    prefix_len = 0
    for char_s, char_c in zip(s, c):
        if char_s == char_c:
            prefix_len += 1
        else:
            break

    ratio = difflib.SequenceMatcher(None, s, c).ratio()
    return (exact_match, prefix_len, ratio)


def _safe_log(db: Session | None, **kwargs):
    if db is None:
        return
    try:
        log_event(db, **kwargs)
    except Exception:
        db.rollback()

def get_all_active():
    """
    Find ALL PPPoE secrets with active status.
    """

    all_data = []

    for router in ROUTERS:
        api = None

        try:
            api = connect_router(router)

            secrets = find_all_secret(api)
            actives = find_all_active(api)

            # print(actives)

            df_active = pd.DataFrame(actives)
            df_secret = pd.DataFrame(secrets)

            df_secret["router_id"] = router["id"]
            df_secret["router_name"] = router["name"]

            df_active.rename(
                columns={"address": "ip"},
                inplace=True,
            )

            df_active = df_active.replace({np.nan : None})

            df_join = df_active.merge(df_secret, on="name", how="inner")

            all_data.append(df_join)

        except Exception as e:
            raise f"[WARN] {router['name']} unreachable: {e}"

        finally:
            if api:
                api.close()

    active_secret_df = pd.concat(all_data, ignore_index=True)
    return active_secret_df

def get_pppoe_status(username: str):
    """
    Find ALL PPPoE secrets with the same username
    across all routers.
    """

    matches = []

    for router in ROUTERS:
        api = None

        try:
            api = connect_router(router)

            secrets = find_secret(api, username)
            if not secrets:
                continue  # no secret on this router

            active = find_active(api, username)

            if active:
                matches.append({
                    "router": {
                        "id": router["id"],
                        "name": router["name"]
                    },
                    "secret": secrets[0].get("disabled"),
                    "status": "ACTIVE",
                    "profile": secrets[0].get("profile"),
                    "name": secrets[0].get("name"),
                    "password": secrets[0].get("password"),
                    "comment": secrets[0].get("comment"),
                    "matched_mac": active[0].get("caller-id"),
                    "connection": {
                        "ip": active[0].get("address"),
                        "uptime": active[0].get("uptime")
                    }
                })
            else:
                matches.append({
                    "router": {
                        "id": router["id"],
                        "name": router["name"]
                    },
                    "secret": secrets[0].get("disabled"),
                    "status": "INACTIVE",
                    "profile": secrets[0].get("profile"),
                    "name": secrets[0].get("name"),
                    "password": secrets[0].get("password"),
                    "comment": secrets[0].get("comment"),
                    "connection": None
                })

        except Exception as e:
            # Router down should not break the whole lookup
            raise f"[WARN] {router['name']} unreachable: {e}"

        finally:
            if api:
                api.close()

    if not matches:
        return None

    return {
        "username": username,
        "matches": matches,
        "has_multiple_matches": len(matches) > 1
    }

def get_pppoe_status_by_mac(mac_address: str):
    """
    Find PPPoE secrets across all routers by MAC address.

    Active sessions are matched by `caller-id`, while inactive secrets are
    matched by `last-caller-id`.
    """

    matches = []

    for router in ROUTERS:
        api = None

        try:
            api = connect_router(router)

            active_matches = [
                active for active in find_active_by_caller_id(api)
                if _mac_matches(mac_address, active.get("caller-id"))
            ]
            active_names = set()

            for active in active_matches:
                username = active.get("name")
                if not username:
                    continue

                secrets = find_secret(api, username)
                if not secrets:
                    continue

                active_names.add(username)
                secret = secrets[0]

                matches.append({
                    "router": {
                        "id": router["id"],
                        "name": router["name"]
                    },
                    "secret": secret.get("disabled"),
                    "status": "ACTIVE",
                    "profile": secret.get("profile"),
                    "name": secret.get("name"),
                    "password": secret.get("password"),
                    "comment": secret.get("comment"),
                    "matched_mac": active.get("caller-id"),
                    "matched_by": "caller-id",
                    "connection": {
                        "ip": active.get("address"),
                        "uptime": active.get("uptime")
                    }
                })

            inactive_matches = [
                secret for secret in find_secret_by_last_caller_id(api)
                if _mac_matches(mac_address, secret.get("last-caller-id"))
            ]

            for secret in inactive_matches:
                username = secret.get("name")
                if username in active_names:
                    continue

                matches.append({
                    "router": {
                        "id": router["id"],
                        "name": router["name"]
                    },
                    "secret": secret.get("disabled"),
                    "status": "INACTIVE",
                    "profile": secret.get("profile"),
                    "name": secret.get("name"),
                    "password": secret.get("password"),
                    "comment": secret.get("comment"),
                    "matched_mac": secret.get("last-caller-id"),
                    "matched_by": "last-caller-id",
                    "connection": None
                })

        except Exception as e:
            raise Exception(f"[WARN] {router['name']} unreachable: {e}")

        finally:
            if api:
                api.close()

    if not matches:
        return None

    matches.sort(
        key=lambda m: (
            *_mac_similarity_score(mac_address, m.get("matched_mac")),
            1 if m.get("status") == "ACTIVE" else 0,
        ),
        reverse=True,
    )

    return {
        "mac_address": mac_address,
        "matches": matches,
        "has_multiple_matches": len(matches) > 1
    }

def disconnect_pppoe_active(
    router_id: str,
    username: str,
    db: Session | None = None,
    actor_id: str | None = None,
):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)
    if not router:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DEACTIVATE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Router not found for deactivate",
            payload={"username": username, "router_id": router_id},
            severity="WARNING",
        )
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        actives = find_active(api, username)
        if not actives:
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_DEACTIVATE_NO_ACTION",
                entity_type="pppoe_secret",
                entity_id=username,
                message="User is not active",
                payload={"username": username, "router_id": router_id},
                severity="WARNING",
            )
            return "USER_NOT_ACTIVE"

        for a in actives:
            disconnect_active(api, a[".id"])
            # print(a[".id"])

        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DEACTIVATED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Active PPPoE session disconnected",
            payload={
                "username": username,
                "router_id": router_id,
                "disconnected_count": len(actives),
            },
        )
    
        return "DISCONNECTED"

    except Exception as e:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DEACTIVATE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Failed to deactivate PPPoE session",
            payload={"username": username, "router_id": router_id, "error": str(e)},
            severity="ERROR",
        )
        raise e

    finally:
        if api:
            api.close()

def disable_pppoe_secret(
    router_id: str,
    username: str,
    db: Session | None = None,
    actor_id: str | None = None,
):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)

    if not router:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DISABLE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Router not found for disable",
            payload={"username": username, "router_id": router_id},
            severity="WARNING",
        )
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        secrets = find_secret(api, username)
        if not secrets:
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_DISABLE_NO_ACTION",
                entity_type="pppoe_secret",
                entity_id=username,
                message="User secret not available",
                payload={"username": username, "router_id": router_id},
                severity="WARNING",
            )
            return "USER_NOT_AVAILABLE"

        for a in secrets:
            disable_secret(api, a[".id"])
            # print(a[".id"])

        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DISABLED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="PPPoE secret disabled",
            payload={
                "username": username,
                "router_id": router_id,
                "affected_count": len(secrets),
            },
        )
    
        return "DISABLED"

    except Exception as e:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DISABLE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Failed to disable PPPoE secret",
            payload={"username": username, "router_id": router_id, "error": str(e)},
            severity="ERROR",
        )
        raise e

    finally:
        if api:
            api.close()

def enable_pppoe_secret(
    router_id: str,
    username: str,
    db: Session | None = None,
    actor_id: str | None = None,
):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)
    if not router:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_ENABLE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Router not found for enable",
            payload={"username": username, "router_id": router_id},
            severity="WARNING",
        )
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        secrets = find_secret(api, username)
        if not secrets:
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_ENABLE_NO_ACTION",
                entity_type="pppoe_secret",
                entity_id=username,
                message="User secret not available",
                payload={"username": username, "router_id": router_id},
                severity="WARNING",
            )
            return "USER_NOT_AVAILABLE"

        for a in secrets:
            enable_secret(api, a[".id"])

        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_ENABLED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="PPPoE secret enabled",
            payload={
                "username": username,
                "router_id": router_id,
                "affected_count": len(secrets),
            },
        )
    
        return "ENABLED"

    except Exception as e:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_ENABLE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Failed to enable PPPoE secret",
            payload={"username": username, "router_id": router_id, "error": str(e)},
            severity="ERROR",
        )
        raise e

    finally:
        if api:
            api.close()

def list_pppoe_profiles(router_id: str):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)

    if not router:
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)
        result = get_pppoe_profiles(api)

        return result
    
    except Exception as e:
        raise e

    finally:
        if api:
            api.close()

def delete_pppoe_secret(
    router_id: str,
    username: str,
    db: Session | None = None,
    actor_id: str | None = None,
):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)
    if not router:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DELETE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Router not found for delete",
            payload={"username": username, "router_id": router_id},
            severity="WARNING",
        )
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        secrets = find_secret(api, username)
        if not secrets:
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_DELETE_NO_ACTION",
                entity_type="pppoe_secret",
                entity_id=username,
                message="User secret not available",
                payload={"username": username, "router_id": router_id},
                severity="WARNING",
            )
            return "USER_NOT_AVAILABLE"

        for a in secrets:
            delete_secret(api, a[".id"])
            # print(a[".id"])

        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DELETED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="PPPoE secret deleted",
            payload={
                "username": username,
                "router_id": router_id,
                "affected_count": len(secrets),
            },
        )
    
        return "DELETED"

    except Exception as e:
        _safe_log(
            db,
            actor_type="user",
            actor_id=actor_id,
            event_type="PPPOE_DELETE_FAILED",
            entity_type="pppoe_secret",
            entity_id=username,
            message="Failed to delete PPPoE secret",
            payload={"username": username, "router_id": router_id, "error": str(e)},
            severity="ERROR",
        )
        raise e

    finally:
        if api:
            api.close()

def isolir_user_all_routers(username: str) -> dict:
    report = {
        "username": username,
        "routers": {},
        "found_on": [],
        "not_found_on": [],
        "disconnected": [],
        "status": None,
        "errors": None
    }

    for router in ROUTERS:
        api = None
        try:
            api = connect_router(router)
            
            result = isolir_on_router(api, username)

            report["routers"][router["id"]] = result

            if result["found"]:
                report["found_on"].append(router["id"])

                if(result["active_disconnected"]): report["disconnected"].append(router["id"])

            else:
                report["not_found_on"].append(router["id"])

        except Exception as e:
            report["status"] = "error"
            report["errors"]= str(e)
            report["routers"][router["id"]] = {
                "error": str(e)
            }

    if(len(report["found_on"]) == 0): report["status"] = "secret_not_found"
    if(len(report["disconnected"]) == 0 ): report["status"] = "active_not_found"


    return report

def change_profile( username: str, router_id: str, profile:str):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)

    if not router:
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        secrets = find_secret(api, username)
        if not secrets:
            return "USER_NOT_AVAILABLE"

        for a in secrets:
            change_pppoe_profile(api, a[".id"], profile)
    
        return "UPDATED"

    except Exception as e:
        raise e

    finally:
        if api:
            api.close()

def resolve_target_routers(router_id: str):
    if router_id == "all":
        return ROUTERS
    return [r for r in ROUTERS if r["id"] == router_id]

def create_pppoe_secret(
    *,
    name: str,
    password: str,
    profile: str,
    comment: str,
    disabled: bool,
    router_id: str,
    db: Session | None = None,
    actor_id: str | None = None,
):
    
    routers = resolve_target_routers(router_id)

    _safe_log(
        db,
        actor_type="user",
        actor_id=actor_id,
        event_type="PPPOE_SECRET_CREATE_REQUESTED",
        entity_type="pppoe_secret",
        entity_id=name,
        message="Create PPPoE secret requested",
        payload={
            "name": name,
            "profile": profile,
            "disabled": disabled,
            "router_id": router_id,
            "routers_count": len(routers),
        },
    )

    results = []

    for router in routers:
        api = None
        try:
            api = connect_router(router)

            add_pppoe_secret(
                api=api,
                name=name,
                password=password,
                profile=profile,
                comment=comment,
                disabled=disabled,
            )

            results.append({
                "router_id": router["id"],
                "status": "success",
            })
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_SECRET_CREATED",
                entity_type="pppoe_secret",
                entity_id=name,
                message="PPPoE secret created on router",
                payload={
                    "name": name,
                    "profile": profile,
                    "disabled": disabled,
                    "router_id": router["id"],
                    "router_name": router.get("name"),
                },
            )

        except Exception as e:
            results.append({
                "router_id": router["id"],
                "status": "failed",
                "error": str(e),
            })
            _safe_log(
                db,
                actor_type="user",
                actor_id=actor_id,
                event_type="PPPOE_SECRET_CREATE_FAILED",
                entity_type="pppoe_secret",
                entity_id=name,
                message="Failed creating PPPoE secret on router",
                payload={
                    "name": name,
                    "profile": profile,
                    "disabled": disabled,
                    "router_id": router["id"],
                    "router_name": router.get("name"),
                    "error": str(e),
                },
                severity="ERROR",
            )
        finally:
            if api:
                api.close()

    success_count = sum(1 for item in results if item.get("status") == "success")
    failed_count = sum(1 for item in results if item.get("status") == "failed")
    _safe_log(
        db,
        actor_type="user",
        actor_id=actor_id,
        event_type="PPPOE_SECRET_CREATE_SUMMARY",
        entity_type="pppoe_secret",
        entity_id=name,
        message="Create PPPoE secret request completed",
        payload={
            "name": name,
            "target_router_id": router_id,
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
        },
        severity="ERROR" if failed_count > 0 else "INFO",
    )

    return results

def change_remote_address(ip: str, router_id):
    routers = resolve_target_routers(router_id)
    # print(routers)
    result = {"updated": False}

    for router in routers:
        api = None

        try:
            api = connect_router(router)

            res=change_nat_to_addresses(
                api=api,
                ip=ip
            )

            result = res
            

        except Exception as e:
            raise Exception(f"{router['name']} failed: {str(e)}")

        finally:
            if api:
                api.close()

    return result
