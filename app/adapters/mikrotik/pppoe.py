"""
MikroTik PPPoE adapter
"""
from librouteros.query import Key

name = Key('name')
profile = Key('profile')
uptime = Key('uptime')
disabled = Key('disabled')
address = Key('address')
comment = Key('comment')
id = Key('.id')

def find_all_active(api):
    return list(
        api.path("ppp", "active")
           .select(name, profile, uptime, address, comment)
    )

def find_all_secret(api):
    return list(
        api.path("ppp", "secret")
           .select(name, profile, disabled)
    )

def find_secret(api, username: str):
    return list(
        api.path("ppp", "secret")
           .select(name, profile, disabled, id)
           .where(name == username)
    )

def find_active(api, username: str):
    return list(
        api.path("ppp", "active")
           .select(name, uptime, address, id)
           .where(name == username)
    )

def disconnect_active(api, active_id: str):
    """
    Disconnect PPPoE active session by .id
    """
    api.path("ppp", "active").remove(active_id)

def disable_secret(api, secret_id:str):
    api.path("ppp", "secret").update(**{
        ".id": secret_id,
        "disabled": "yes"
    })

def enable_secret(api, secret_id:str):
    api.path("ppp", "secret").update(**{
        ".id": secret_id,
        "disabled": "no"
    })

def delete_secret(api, secret_id: str) -> None:
    """
    Delete PPPoE secret by internal .id
    """
    api.path("ppp", "secret").remove(secret_id)

def change_pppoe_profile(api, secret_id: str, profile: str) -> None:
    """
    Change PPPoE secret profile by internal .id
    """
    api.path("ppp", "secret").update(
        **{
            ".id": secret_id,
            "profile": profile
        }
    )

def get_pppoe_profiles(api) -> list[dict]:
    """
    Get PPPoE profiles from a router
    """
    return list(api.path("ppp", "profile").select(
        ".id",
        "name",
        "comment"
    ))

def isolir_on_router(api, username: str) -> dict:
    print("checking" + username)

    try:
        result = {
            "found": False,
            "active_disconnected": 0,
            "secret_disabled": False,
        }

        # 1. Find secret
        secrets = list(
            api.path("ppp", "secret")
            .select(".id", "name", "disabled")
            .where(name==username)
        )

        if not secrets:
            return result

        result["found"] = True
        secret_id = secrets[0][".id"]

        

        # 2. Disable secret
        # api.path("ppp", "secret").update(
        #     **{".id": secret_id},
        #     disabled="yes"
        # )

        # 3. Disconnect active sessions

        result["secret_disabled"] = True

        actives = list(
            api.path("ppp", "active")
            .select(".id")
            .where(name==username)
        )

        # for a in actives:
        #     api.path("ppp", "active").remove(a[".id"])

        if(len(actives)):
            result["active_disconnected"] = True

       

        return result
    
    except Exception as e:
        raise e
    
def add_pppoe_secret(
    api,
    *,
    name: str,
    password: str,
    profile: str,
    enabled: bool = True,
    comment: str | None = None,
):
    payload = {
        "name": name,
        "password": password,
        "service": "pppoe",
        "profile": profile,
        "disabled": "no" if enabled else "yes",
    }

    if comment:
        payload["comment"] = comment

    return api.path("ppp", "secret").add(**payload)
