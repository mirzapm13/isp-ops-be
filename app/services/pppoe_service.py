from app.config.settings import ROUTERS
from app.adapters.mikrotik.client import connect_router
from app.adapters.mikrotik.pppoe import add_pppoe_secret, change_nat_to_addresses, change_pppoe_profile, delete_secret, get_pppoe_profiles, isolir_on_router,disable_secret, enable_secret, find_all_active, find_all_secret, find_secret, find_active, disconnect_active
from app.services.log_service import log_event
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session


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

def disconnect_pppoe_active(router_id: str, username: str):
    router = next((r for r in ROUTERS if r["id"] == router_id), None)
    if not router:
        return "ROUTER_NOT_FOUND"

    api = None

    try:
        api = connect_router(router)

        actives = find_active(api, username)
        if not actives:
            return "USER_NOT_ACTIVE"

        for a in actives:
            disconnect_active(api, a[".id"])
            # print(a[".id"])
    
        return "DISCONNECTED"

    except Exception as e:
        raise e

    finally:
        if api:
            api.close()

def disable_pppoe_secret(router_id: str, username: str):
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
            disable_secret(api, a[".id"])
            # print(a[".id"])
    
        return "DISABLED"

    except Exception as e:
        raise e

    finally:
        if api:
            api.close()

def enable_pppoe_secret(router_id: str, username: str):
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
            enable_secret(api, a[".id"])
    
        return "ENABLED"

    except Exception as e:
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

def delete_pppoe_secret(router_id: str, username: str):
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
            delete_secret(api, a[".id"])
            # print(a[".id"])
    
        return "DELETED"

    except Exception as e:
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
    requested_by: str | None = None,
):
    
    routers = resolve_target_routers(router_id)

    _safe_log(
        db,
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
            "requested_by": requested_by,
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
                    "requested_by": requested_by,
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
                    "requested_by": requested_by,
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
        event_type="PPPOE_SECRET_CREATE_SUMMARY",
        entity_type="pppoe_secret",
        entity_id=name,
        message="Create PPPoE secret request completed",
        payload={
            "name": name,
            "requested_by": requested_by,
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
