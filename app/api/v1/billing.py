from fastapi import APIRouter, Body, HTTPException, UploadFile, File
import tempfile
import os


from app.services.billing_reconcile_service import fetch_successful_payments_xls
from app.services.billing_service import (
    bulk_isolir_from_file,
    import_billing_data,
    insert_billing_records,
    get_billing_by_ip_secret,
    isolir_from_gsheet
)

router = APIRouter(
    prefix="/billing",
    tags=["Billing"]
)

@router.post("/import")
async def import_billing(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        records = import_billing_data(tmp_path, file.filename)

        if not records:
            raise HTTPException(
                status_code=400,
                detail="No valid billing records found"
            )

        insert_billing_records(records)

        return {
            "status": "OK",
            "rows_imported": len(records)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import billing data: {str(e)}"
        )

    finally:
        os.unlink(tmp_path)

@router.get("/customers/{ip_secret}")
def get_billing_customer(ip_secret: str):
    rows = get_billing_by_ip_secret(ip_secret)

    return {
        "ip_secret": ip_secret,
        "count": len(rows),
        "data": [
            {
                "id": r.id,
                "id_pelanggan": r.id_pelanggan,
                "ip_secret": r.ip_secret,
                "nama_pelanggan": r.nama_pelanggan,
                "nama_langganan": r.nama_langganan,
                "harga": r.harga,
                "status_langganan": r.status_langganan,
                "jatuh_tempo": r.jatuh_tempo,
                "nama_router": r.nama_router,
                "id_olt": r.id_olt,
                "id_odp": r.id_odp,
                "source_file": r.source_file,
                "imported_at": r.imported_at,
            }
            for r in rows
        ]
    }

@router.post("/import-isolir")
async def isolir_billing(file: UploadFile=File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        records = import_billing_data(tmp_path, file.filename)

        if not records:
            raise HTTPException(
                status_code=400,
                detail="No valid billing records found"
            )

        insert_billing_records(records)

        return {
            "status": "OK",
            "rows_isolr": len(records)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to isolir billing data: {str(e)}"
        )

    finally:
        os.unlink(tmp_path)

@router.post("/bulk-isolir")
async def bulk_isolir(file: UploadFile = File(...)):
    result = bulk_isolir_from_file(await file.read())
    return result

@router.post("/gdrive-isolir")
def gdrive_isolir(
    sheet_id: str = Body(..., embed=True),
    worksheet_gid: str = Body(..., embed=True)
):
    result = isolir_from_gsheet(sheet_id, worksheet_gid)

    return result

@router.post("/reconcile")
def reconcile_billing():

    try:
        df = fetch_successful_payments_xls()
        # return df

        # TEMP: just return row count to verify pipeline
        return {
            "status": "ok",
            "rows": len(df),
            # "columns": list(df.columns),
            "data": df.to_dict(orient="records")
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reconcile payment data: {str(e)}"
        )