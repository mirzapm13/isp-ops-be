import requests
import pandas as pd
import os
import hashlib
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo
from decimal import Decimal

from sqlalchemy import text
from app.adapters.mikrotik.client import connect_router
from app.adapters.mikrotik.pppoe import enable_secret, find_secret
from app.adapters.smartolt.smartolt import SmartOLTAdapter
from app.config.database import engine
from app.config.database_mssql import get_mssql_engine
from app.config.settings import ROUTERS

def build_payment_fingerprint(row) -> str:
    raw = (
        f"{row['customer_phone']}|"
        f"{row['amount']}|"
        f"{row['paid_at'].strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_bmt_payment_fingerprint(row) -> str:
    raw = (
        f"{row.get('batch')}|"
        f"{row.get('notrn')}|"
        f"{row.get('inptgl')}|"
        f"{row.get('id_pelanggan')}|"
        f"{row.get('nominalrp')}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_sql_identifier(name: str, env_name: str) -> str:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(
            f"Invalid SQL identifier in {env_name}: {name!r}"
        )
    return name


def _resolve_bmt_table_name() -> str:
    schema = _validate_sql_identifier(
        os.getenv("BMT_MSSQL_SCHEMA", "dbo"),
        "BMT_MSSQL_SCHEMA",
    )
    table = _validate_sql_identifier(
        os.getenv("BMT_MSSQL_TABLE", "toftrnc"),
        "BMT_MSSQL_TABLE",
    )
    return f"[{schema}].[{table}]"


def _to_jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def fetch_bmt_payment(limit: int = 100) -> dict:
    """
    Scaffold for pulling BMT payment data from MSSQL.

    Env:
    - BMT_MSSQL_URL (recommended), or BMT_MSSQL_HOST/USER/PASSWORD/DATABASE
    - BMT_MSSQL_SCHEMA (default: dbo)
    - BMT_MSSQL_TABLE (default: toftrnc)
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    safe_limit = min(limit, 1000)
    table_name = _resolve_bmt_table_name()
    cracc_filter = (
        os.getenv("BMT_MSSQL_CRACC_FILTER")
        or os.getenv("BMT_MSSQL_DRACC_FILTER")
        or "1150100044"
    )

    query = text(f"""
        SELECT TOP {safe_limit} *
        FROM {table_name}
        WHERE cracc = :cracc
        ORDER BY inptgl DESC
    """)

    with get_mssql_engine().connect() as conn:
        rows = conn.execute(
            query,
            {"cracc": cracc_filter},
        ).mappings().all()

    items = [
        {key: _to_jsonable(value) for key, value in row.items()}
        for row in rows
    ]

    return {
        "status": "OK",
        "source": "mssql",
        "table": table_name,
        "limit": safe_limit,
        "count": len(items),
        "items": items,
    }


def _extract_id_pelanggan_from_ket(ket: str | None) -> str | None:
    if not ket:
        return None

    cleaned = re.sub(r"^\s*\[TAB\]\s*", "", str(ket), flags=re.IGNORECASE)
    left = cleaned.split("/", 1)[0].strip()
    return left or None


def _activate_ip_secret(
    ip_secret: str,
    adapter: SmartOLTAdapter | None = None,
) -> SmartOLTAdapter | None:
    if len(str(ip_secret)) < 10:
        for router in ROUTERS:
            api = None
            try:
                api = connect_router(router)
                secrets = find_secret(api, ip_secret)
                if not secrets:
                    continue

                for secret in secrets:
                    enable_secret(api, secret[".id"])
            finally:
                if api:
                    api.close()
        return adapter

    if adapter is None:
        adapter = SmartOLTAdapter()
    adapter.enable_onu(onu_id=ip_secret)
    return adapter


def reconcile_bmt_payments(limit: int = 1000) -> dict:
    payload = {
        "status": "FAILED",
        "summary": {
            "found": [],
            "processed": [],
            "failed": [],
        },
        "message": "Haven't processed yet",
        "timestamp": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
    }

    if limit < 1:
        raise ValueError("limit must be >= 1")

    safe_limit = min(limit, 5000)
    table_name = _resolve_bmt_table_name()
    cracc_filter = (
        os.getenv("BMT_MSSQL_CRACC_FILTER")
        or os.getenv("BMT_MSSQL_DRACC_FILTER")
        or "1150100044"
    )

    mssql_query = text(f"""
        SELECT TOP {safe_limit}
            tgltrn,
            trnuser,
            batch,
            notrn,
            kodetrn,
            cracc,
            ket,
            nominalrp,
            inptgl
        FROM {table_name}
        WHERE cracc = :cracc
        ORDER BY inptgl DESC
    """)

    with get_mssql_engine().connect() as conn:
        raw_rows = conn.execute(
            mssql_query,
            {"cracc": cracc_filter},
        ).mappings().all()

    if not raw_rows:
        payload["status"] = "NO_DATA"
        payload["message"] = "No BMT payment data found"
        return payload

    bmt_df = pd.DataFrame([dict(row) for row in raw_rows])
    bmt_df["id_pelanggan"] = bmt_df["ket"].apply(_extract_id_pelanggan_from_ket)
    bmt_df = bmt_df[bmt_df["id_pelanggan"].notna()].copy()

    if bmt_df.empty:
        payload["status"] = "NO_DATA"
        payload["message"] = "No valid id_pelanggan parsed from ket"
        return payload

    bmt_df["paid_at"] = pd.to_datetime(
        bmt_df["inptgl"],
        format="%Y%m%d%H%M%S",
        errors="coerce",
    )
    bmt_df["payment_fingerprint"] = bmt_df.apply(
        build_bmt_payment_fingerprint,
        axis=1,
    )

    insert_sql = text("""
        INSERT INTO payment_reconcile_bmt (
            payment_fingerprint,
            id_pelanggan,
            ket,
            dracc,
            nominalrp,
            tgltrn,
            trnuser,
            batch,
            notrn,
            inptgl,
            paid_at,
            raw_payload
        )
        VALUES (
            :payment_fingerprint,
            :id_pelanggan,
            :ket,
            :dracc,
            :nominalrp,
            :tgltrn,
            :trnuser,
            :batch,
            :notrn,
            :inptgl,
            :paid_at,
            CAST(:raw_payload AS JSONB)
        )
        ON CONFLICT (payment_fingerprint) DO NOTHING
    """)

    records = []
    for _, row in bmt_df.iterrows():
        raw_payload = {
            "tgltrn": _to_jsonable(row.get("tgltrn")),
            "trnuser": _to_jsonable(row.get("trnuser")),
            "batch": _to_jsonable(row.get("batch")),
            "notrn": _to_jsonable(row.get("notrn")),
            "kodetrn": _to_jsonable(row.get("kodetrn")),
            "dracc": _to_jsonable(row.get("dracc")),
            "cracc": _to_jsonable(row.get("cracc")),
            "ket": _to_jsonable(row.get("ket")),
            "nominalrp": _to_jsonable(row.get("nominalrp")),
            "inptgl": _to_jsonable(row.get("inptgl")),
        }

        paid_at = row.get("paid_at")
        records.append(
            {
                "payment_fingerprint": row.get("payment_fingerprint"),
                "id_pelanggan": row.get("id_pelanggan"),
                "ket": row.get("ket"),
                "dracc": row.get("cracc"),
                "nominalrp": row.get("nominalrp"),
                "tgltrn": str(row.get("tgltrn")) if row.get("tgltrn") is not None else None,
                "trnuser": row.get("trnuser"),
                "batch": int(row.get("batch")) if pd.notna(row.get("batch")) else None,
                "notrn": int(row.get("notrn")) if pd.notna(row.get("notrn")) else None,
                "inptgl": str(row.get("inptgl")) if row.get("inptgl") is not None else None,
                "paid_at": paid_at.to_pydatetime() if pd.notna(paid_at) else None,
                "raw_payload": pd.Series(raw_payload).to_json(),
            }
        )

    with engine.begin() as conn:
        conn.execute(insert_sql, records)

    match_sql = text("""
        SELECT
            prb.payment_fingerprint,
            prb.id_pelanggan,
            prb.ket,
            prb.nominalrp,
            prb.paid_at,
            bc.ip_secret
        FROM payment_reconcile_bmt prb
        INNER JOIN billing_customers bc
            ON bc.id_pelanggan = prb.id_pelanggan
        WHERE prb.processed_at IS NULL
          AND bc.ip_secret IS NOT NULL
    """)

    with engine.begin() as conn:
        opened_secret_rows = conn.execute(match_sql).mappings().all()

    if not opened_secret_rows:
        payload["status"] = "NO_DATA"
        payload["message"] = "No matching billing customer for BMT records"
        return payload

    payload["summary"]["found"] = [row["ip_secret"] for row in opened_secret_rows]

    update_query_success = text("""
        UPDATE payment_reconcile_bmt
        SET processed_at = NOW(), processed = TRUE
        WHERE payment_fingerprint = :value
          AND processed_at IS NULL
    """)

    update_query_error = text("""
        UPDATE payment_reconcile_bmt
        SET processed_at = NOW(),
            processed_error = :error
        WHERE payment_fingerprint = :value
          AND processed_at IS NULL
    """)

    adapter = None

    for row in opened_secret_rows:
        try:
            adapter = _activate_ip_secret(row["ip_secret"], adapter)

            with engine.begin() as conn:
                conn.execute(
                    update_query_success,
                    {"value": row["payment_fingerprint"]},
                )

            payload["summary"]["processed"].append(row["ip_secret"])
        except Exception as e:
            with engine.begin() as conn:
                conn.execute(
                    update_query_error,
                    {
                        "value": row["payment_fingerprint"],
                        "error": str(e),
                    },
                )
            payload["summary"]["failed"].append(row["ip_secret"])

    if len(payload["summary"]["failed"]) > 0 and len(payload["summary"]["processed"]) > 0:
        payload["status"] = "PARTIAL"
        payload["message"] = "Partially Activated"
    elif len(payload["summary"]["failed"]) > 0 and len(payload["summary"]["processed"]) == 0:
        payload["status"] = "FAILED"
        payload["message"] = "Failed to activate"
    elif len(payload["summary"]["failed"]) == 0 and len(payload["summary"]["processed"]) > 0:
        payload["status"] = "SUCCESS"
        payload["message"] = "Success to activate"
    else:
        payload["status"] = "NO_DATA"
        payload["message"] = "No activation target found"

    return payload


def fetch_successful_payments_xls() :

    response = requests.get(os.getenv("TRIPAY_URL"),headers={
        "Authorization": f"Bearer {os.getenv('TRIPAY_KEY')}"
    },params={"sort": "desc", "status": "PAID"}, timeout=30)
    
    response.raise_for_status()

    payload= {
        "status" : "FAILED",
        "summary" : {
            "found": [],
            "processed": [],
            "failed" : []
        },
            "message": "Haven't processed yet",
            "timestamp":""
    }

    try:
        res_data = response.json()['data']
        payment_df = pd.DataFrame(res_data)
        payment_df = payment_df.drop(columns=['order_items'])
        payment_df = payment_df.query("status == 'PAID'")
        payment_df['created_at'] = (
            pd.to_datetime(payment_df['created_at'], unit='s', errors='coerce')
                .dt.tz_localize('UTC')
            )

        payment_df['expired_at'] = (
            pd.to_datetime(payment_df['expired_at'], unit='s', errors='coerce')
            .dt.tz_localize('UTC')
        )

        payment_df['paid_at'] = (
            pd.to_datetime(payment_df['paid_at'],unit='s', errors='coerce')
            .dt.tz_localize('UTC')
        )
        payment_df["payment_fingerprint"] = payment_df.apply(build_payment_fingerprint,axis=1)
        # payment_df['datetime_column'] = pd.to_datetime(payment_df['unix_time'], unit='s')
        # payment_df['datetime_column'] = pd.to_datetime(payment_df['unix_time'], unit='s')

        # Load new fingerprints
        with engine.begin() as conn:
            payment_df.to_sql(
                "payment_staging",
                con=conn,
                if_exists="replace",
                index=False,
                chunksize=500,
                method="multi",
            )

        #Cari IP / Secret
        found_sql=text("""
            INSERT INTO payment_reconcile (
            reference,
            merchant_ref,
            payment_selection_type,
            payment_method,
            payment_name,
            customer_name,
            customer_email,
            customer_phone,
            callback_url,
            return_url,
            amount,
            fee_merchant,
            fee_customer,
            total_fee,
            amount_received,
            pay_code,
            pay_url,
            checkout_url,
            status,
            note,created_at,
            expired_at,
            paid_at,
            payment_fingerprint
        )
        select ps.* from payment_staging ps 
        left join payment_reconcile pr 
        ON pr.payment_fingerprint = ps.payment_fingerprint
        WHERE pr.payment_fingerprint IS NULL
        AND ps.status = 'PAID';


        select * from payment_reconcile pr inner join billing_customers bc
        on  pr.customer_phone = bc.tlp
        and pr.customer_name = bc.nama_pelanggan
        and pr.processed_at is null
        and bc.tlp is not null
        """)

        with engine.begin() as conn:
            opened_secret = conn.execute(
                found_sql,
            ).fetchall()

        opened_secret = pd.DataFrame(opened_secret)
        payload["timestamp"] = datetime.now(ZoneInfo("Asia/Jakarta")).isoformat()

        if opened_secret.empty:
            payload["status"] = "NO_DATA"
            return payload

        payload['summary']['found'] = opened_secret['ip_secret'].tolist() 

        # print(payload)

        #Open Isolir
        # open_list = opened_secret['ip_secret'].tolist()
        # print(open_list)

        #Update status open isolir
        update_query_success = text("""
                UPDATE payment_reconcile
                SET processed_at = NOW(), processed = TRUE
                WHERE payment_fingerprint = :value
                AND processed_at IS NULL;
                """)
        
        update_query_error = text("""
                UPDATE payment_reconcile
                SET processed_at = NOW(),
                processed_error = :error
                WHERE payment_fingerprint = :value
                AND processed_at IS NULL;
                """)
        
        adapter = None
        
        for index, row in opened_secret.iterrows():
            
            try:
                adapter = _activate_ip_secret(row['ip_secret'], adapter)
                
                # 2. Mark processed immediately
                with engine.begin() as conn:
                    conn.execute(update_query_success, {
                        "value": row["payment_fingerprint"]
                    })
                
                payload["summary"]["processed"].append(row['ip_secret'])
            
            except Exception as e:
                print(e)
                with engine.begin() as conn:
                    conn.execute(update_query_error, {
                        "value": row["payment_fingerprint"],
                        "error": str(e)
                    })
                
                payload["summary"]["failed"].append(row['ip_secret'])
               
                # optionally log failure in DB


    except Exception as e:
        print(e)
        payload["status"] = "FAILED"
        payload["message"] = str(e)

        return payload
    

    if len(payload["summary"]["failed"]) > 0 and len(payload["summary"]["processed"])>0:
        payload["status"] = "PARTIAL"
        payload["message"] = "Partially Activated"
    elif len(payload["summary"]["failed"]) > 0 and len(payload["summary"]["processed"])==0:
        payload["status"] = "FAILED"
        payload["message"] = "Failed to activate"
    elif len(payload["summary"]["failed"]) == 0 and len(payload["summary"]["processed"])>0:
        payload["status"] = "SUCCESS"
        payload["message"] = "Success to activate"

    return payload
