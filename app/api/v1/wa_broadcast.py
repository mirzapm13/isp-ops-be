from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.models.user import User
from app.schemas.wa_broadcast import (
    BroadcastPreviewRequest,
    BroadcastStartRequest,
)
from app.security.auth import get_current_user
from app.services.wa_broadcast_service import (
    export_broadcast_run_csv,
    get_broadcast_run_detail,
    get_templates_and_config,
    is_any_broadcast_running,
    list_broadcast_runs,
    preview_broadcast_payload,
    start_broadcast_job,
    stop_broadcast_job,
    store_uploaded_file,
)

router = APIRouter(
    prefix="/wa-broadcast",
    tags=["WhatsApp Broadcast"],
)


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    role_names = {role.name for role in current_user.roles}
    if "Superadmin" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Superadmin can access WhatsApp Broadcast",
        )
    return current_user


@router.get("/templates")
def get_wa_templates(current_user: User = Depends(require_superadmin)):
    data = get_templates_and_config()
    data["active_run_id"] = is_any_broadcast_running()
    return data


@router.post("/upload")
async def upload_broadcast_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_superadmin),
):
    filename = file.filename or "broadcast.xlsx"
    if not filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Please upload .xlsx, .xls, or .csv",
        )
    try:
        content = await file.read()
        return store_uploaded_file(content, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to read file: {str(e)}"
        )


@router.post("/preview")
def preview_payload(
    req: BroadcastPreviewRequest,
    current_user: User = Depends(require_superadmin),
):
    try:
        return preview_broadcast_payload(
            upload_id=req.upload_id,
            excel_row=req.excel_row,
            phone_column=req.phone_column,
            namespace=req.namespace,
            template_name=req.template_name,
            language_code=req.language_code,
            body_columns=req.body_columns,
            header_columns=req.header_columns,
            buttons=[b.model_dump() for b in req.buttons],
            currency_columns=req.currency_columns,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to build preview: {str(e)}"
        )


@router.post("/start")
def start_broadcast(
    req: BroadcastStartRequest,
    current_user: User = Depends(require_superadmin),
):
    if not req.template_name.strip() or not req.language_code.strip():
        raise HTTPException(
            status_code=400,
            detail="Template Name and Language Code are required.",
        )
    try:
        return start_broadcast_job(
            upload_id=req.upload_id,
            phone_column=req.phone_column,
            namespace=req.namespace,
            template_name=req.template_name,
            language_code=req.language_code,
            body_columns=req.body_columns,
            header_columns=req.header_columns,
            buttons=[b.model_dump() for b in req.buttons],
            currency_columns=req.currency_columns,
            delay_seconds=req.delay_seconds,
            dry_run=req.dry_run,
            created_by=getattr(current_user, "username", str(current_user.id)),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start broadcast: {str(e)}"
        )


@router.get("/runs")
def get_broadcast_runs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_superadmin),
):
    try:
        return list_broadcast_runs(page=page, limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broadcast runs: {str(e)}"
        )


@router.get("/runs/{run_id}")
def get_broadcast_run(
    run_id: int,
    current_user: User = Depends(require_superadmin),
):
    try:
        return get_broadcast_run_detail(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch broadcast run: {str(e)}"
        )


@router.post("/runs/{run_id}/stop")
def stop_broadcast(
    run_id: int,
    current_user: User = Depends(require_superadmin),
):
    try:
        return stop_broadcast_job(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop broadcast run: {str(e)}"
        )


@router.get("/runs/{run_id}/csv")
def download_broadcast_csv(
    run_id: int,
    current_user: User = Depends(require_superadmin),
):
    try:
        csv_content = export_broadcast_run_csv(run_id)
        encoded = csv_content.encode("utf-8-sig")
        return Response(
            content=encoded,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="qiscus_broadcast_results_{run_id}.csv"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to export CSV: {str(e)}"
        )
