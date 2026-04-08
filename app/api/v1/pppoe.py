from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.models.pppoe import PPPoESecretCreateRequest
from app.models.user import User
from app.security.auth import get_current_user, get_db
from app.services.pppoe_service import change_profile, change_remote_address, create_pppoe_secret, delete_pppoe_secret, disable_pppoe_secret, disconnect_pppoe_active, enable_pppoe_secret, get_pppoe_status, list_pppoe_profiles
from app.services.ping_service import ping_pppoe_user

router = APIRouter(
    prefix="/pppoe",
    tags=["PPPoE"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/{username}")
def get_user(username: str):
    result = get_pppoe_status(username)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="PPPoE user not found"
        )

    return result

@router.get("/profile/{router_id}")
def get_profiles(router_id: str):
    result = None

    try: 
        result = list_pppoe_profiles(router_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="PPPoE profiles not found"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting profiles: {e}"
        )
    
    return result



@router.post("/{username}/ping")
def ping_user(
        username: str,
        router_id: str = Body(..., embed=True),
        count: int = Body(3, embed=True)
    ):
    result, error = ping_pppoe_user(username, router_id, count)

    if error == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if error == "USER_NOT_ACTIVE":
        raise HTTPException(status_code=409, detail="User is not active")

    if error:
        raise HTTPException(status_code=500, detail=error)

    return result

@router.post("/{username}/deactivate")
def disconnect_user(
        username: str,
        router_id: str = Body(..., embed=True)
    ):
    result = disconnect_pppoe_active(router_id, username)

    if result == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if result == "USER_NOT_ACTIVE":
        return {
            "status": "NO_ACTION",
            "message": "User is already inactive"
        }

    if result != "DISCONNECTED":
        raise HTTPException(status_code=500, detail=result)

    return {
        "status": "SUCCESS",
        "message": "User disconnected",
        "username": username,
        "router_id": router_id
    }

@router.post("/{username}/disable")
def disable_user(
        username: str,
        router_id: str = Body(..., embed=True)
    ):
    result = disable_pppoe_secret(router_id, username)

    if result == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if result == "USER_NOT_AVAILABLE":
        return {
            "status": "NO_ACTION",
            "message": "User is not available"
        }

    if result != "DISABLED":
        raise HTTPException(status_code=500, detail=result)

    return {
        "status": "SUCCESS",
        "message": "User secret disabled",
        "username": username,
        "router_id": router_id
    }

@router.post("/{username}/enable")
def enable_user(
        username: str,
        router_id: str = Body(..., embed=True)
    ):
    result = enable_pppoe_secret(router_id, username)

    if result == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if result == "USER_NOT_AVAILABLE":
        return {
            "status": "NO_ACTION",
            "message": "User is not available"
        }

    if result != "ENABLED":
        raise HTTPException(status_code=500, detail=result)

    return {
        "status": "SUCCESS",
        "message": "User secret enabled",
        "username": username,
        "router_id": router_id
    }

@router.post("/{username}/delete")
def delete_user(
    username: str,
    router_id: str = Body(..., embed=True)
):
    result = delete_pppoe_secret(router_id, username)

    if result == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if result == "USER_NOT_AVAILABLE":
        return {
            "status": "NO_ACTION",
            "message": "User is not available"
        }

    if result != "DELETED":
        raise HTTPException(status_code=500, detail=result)

    return {
        "status": "SUCCESS",
        "message": "User secret deleted",
        "username": username,
        "router_id": router_id
    }
    
@router.patch("/{username}")
def patch_profile(
        username: str,
        router_id: str = Body(..., embed=True),
        profile: str = Body(..., embed=True)
    ):

    result = change_profile(username,router_id,  profile)

    if result == "ROUTER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Router not found")

    if result == "USER_NOT_AVAILABLE":
        return {
            "status": "NO_ACTION",
            "message": "User is not available"
        }

    if result != "UPDATED":
        raise HTTPException(status_code=500, detail=result)

    return {
        "status": "SUCCESS",
        "message": "User profile updated",
        "username": username,
        "router_id": router_id
    }

@router.post("/secret")
def create_secret(
    payload: PPPoESecretCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try: 
        result = create_pppoe_secret(
            name=payload.name,
            password=payload.password,
            profile=payload.profile,
            comment=payload.comment,
            disabled=payload.disabled,
            router_id=payload.router,
            db=db,
            requested_by=current_user.username,
        )

        all_successful = all(item.get('status') == 'success' for item in result)
        all_failed = all(item.get('status') == 'failed' for item in result)

        payload = {
            "result": result
        }

        if(all_successful):
            payload["status"] = "success"
        elif(all_failed):
            payload["status"] = "failed"
        else:
            payload["status"] = "warning"

        return payload
    
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/remote/")
def remote_client(ip: str, router_id: str):
    result = None

    try: 
        result = change_remote_address(ip,router_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="IP not found"
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error changing to addresses: {e}"
        )
    
    return result
