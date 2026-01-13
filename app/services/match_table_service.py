# from app.adapters.mikrotik.client import connect_router
# from app.adapters.mikrotik.pppoe import find_all_active
import numpy as np
from app.config.settings import ROUTERS
from app.services.billing_service import get_all_billing
from app.services.pppoe_service import get_all_active
import pandas as pd


def get_all_billing_active():
    """
    Retrieve all active matches without billing information.
    Returns a list of active matches.
    """
    try:
        billing = get_all_billing()        # list[dict]
        active_pppoe = get_all_active()    # list[dict]

        billing_dicts = [b.to_dict() for b in billing]

        billing_df = pd.DataFrame(billing_dicts)
        active_pppoe_df = pd.DataFrame(active_pppoe)

        active_billing = pd.merge(
            active_pppoe_df,
            billing_df,
            how="left",
            left_on="name",
            right_on="ip_secret"
        )

        active_billing = active_billing.replace({np.nan : None})
        records = active_billing.to_dict(orient="records")
    except Exception as e:
        raise e
    
    return {
        "count" : len(records),
        "data" : records
    }

def get_active_no_billing():
    try: 
        billing = get_all_billing()        # list[dict]
        active_pppoe = get_all_active()    # list[dict]

        billing_dicts = [b.to_dict() for b in billing]

        billing_df = pd.DataFrame(billing_dicts)
        active_pppoe_df = pd.DataFrame(active_pppoe)

        billing_active_df = pd.merge(
            active_pppoe_df,
            billing_df,
            how="left",
            left_on="name",
            right_on="ip_secret"
        )

        active_billing_df = pd.merge(
            billing_df,
            active_pppoe_df,
            how="left",
            left_on="ip_secret",
            right_on="name"
        )

        values_to_exclude = ['GPON', 'XPON', 'TPLINK']
        
        #Active but no billing
        active_no_billing_df = billing_active_df[billing_active_df['ip_secret'].isnull()]
        active_no_billing_df = active_no_billing_df.replace({np.nan:None})
        active_no_billing_df = active_no_billing_df.to_dict(orient="records")

        #Billing but not active
        is_not_numeric_string = ~active_billing_df['ip_secret'].fillna('').astype(str).str.isnumeric()
        
        billing_no_active_df = active_billing_df[active_billing_df['name'].isnull()]
        billing_no_active_df = billing_no_active_df[is_not_numeric_string]
        billing_no_active_df = billing_no_active_df.query("ip_secret not in @values_to_exclude")
        billing_no_active_df = billing_no_active_df[billing_no_active_df['status_langganan'] == 'On']
        billing_no_active_df = billing_no_active_df.replace({np.nan:None})
        billing_no_active_df = billing_no_active_df.to_dict(orient="records")

        #Double IP
        double_df = billing_active_df.groupby('ip_secret').filter(lambda x: len(x) > 1).sort_values(by='ip_secret')
        double_df = double_df.groupby('nama_pelanggan').filter(lambda x: len(x) == 1).sort_values(by='ip_secret')
        double_df = double_df.to_dict(orient="records")

        #Double Active
        double_active_df = billing_active_df.groupby('ip_secret').filter(lambda x: len(x) > 1).sort_values(by='ip_secret')
        double_active_df = billing_active_df.groupby('id').filter(lambda x: len(x) > 1).sort_values(by='name')
        double_active_df = double_active_df.to_dict(orient="records")

        #Static IP
        static_ip = active_billing_df[active_billing_df["ip_secret"].astype(str).str.match(r"^[0-9]+$")]
        static_ip = static_ip.replace({np.nan:None})
        static_ip = static_ip.to_dict(orient="records")

    except Exception as e:
        raise e
    
    return {
        "active_no_billing": {
            "count": len(active_no_billing_df),
            "data": active_no_billing_df
        },
        "billing_no_active":{
            "count": len(billing_no_active_df),
            "data": billing_no_active_df
        },
        "double_ip":{
            "count": len(double_df),
            "data": double_df
        },
        "double_active":{
            "count":len(double_active_df),
            "data": double_active_df
        },
        "static_ip":{
            "count" : len(static_ip),
            "data": static_ip
        }
    }
    