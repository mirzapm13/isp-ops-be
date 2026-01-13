from fastapi import APIRouter, HTTPException

from app.services.match_table_service import get_active_no_billing

router = APIRouter(
    prefix="/match-table",
    tags=["Match Table"]
)

@router.get("")
def get_all():
    result = None

    try:
        result = get_active_no_billing()
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving match table: {e}"
        )

    return result

@router.get("/active-no-billing")
def active_no_billing():
    return {
        "status": "NOT_IMPLEMENTED"
    }

@router.get("/billing-no-active")
def billing_no_active():
    return {
        "status": "NOT_IMPLEMENTED"
    }

@router.get("/double-billing")
def double_billing():
    return {
        "status": "NOT_IMPLEMENTED"
    }

@router.get("/double-active")
def double_active():
    return {
        "status": "NOT_IMPLEMENTED"
    }

@router.post("/static-ip")
def reconcile():
    return {
        "status": "NOT_IMPLEMENTED"
    }