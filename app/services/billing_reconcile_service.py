import requests
import pandas as pd
from io import BytesIO
import os
import hashlib
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from app.adapters.mikrotik.client import connect_router
from app.adapters.mikrotik.pppoe import enable_secret, find_secret
from app.adapters.smartolt.smartolt import SmartOLTAdapter
from app.config.database import engine
from app.config.settings import ROUTERS

def build_payment_fingerprint(row) -> str:
    raw = (
        f"{row['customer_phone']}|"
        f"{row['amount']}|"
        f"{row['paid_at'].strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        
        adapter = SmartOLTAdapter()
        
        for index, row in opened_secret.iterrows():
            
            try:
                # 1. Activate router

                # activate pppoe
                if len(row['ip_secret'])< 10:
                # print(row["ip_secret"])
                # print("asdasdaqsdasd")
                    api = None
                    for router in ROUTERS:
                        api = connect_router(router)

                        secrets = find_secret(api, row['ip_secret'])
                        if not secrets:
                            continue


                        for a in secrets:
                            enable_secret(api, a[".id"])

                    if api:
                        api.close()
                
                else:
                #Enable SMARTOLT
                    adapter.enable_onu(
                            onu_id=row['ip_secret'],
                        )
                
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
