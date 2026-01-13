from app.config.settings import ROUTERS

def list_routers():
    """
    Return router inventory (safe fields only)
    """
    return [
        {
            "id": r["id"],
            "name": r["name"]
        }
        for r in ROUTERS
    ]
