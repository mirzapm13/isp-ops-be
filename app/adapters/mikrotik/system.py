"""
MikroTik system-level functions
"""

from librouteros.query import Key
address = Key('address')
count = Key('count')


def get_system_resource(api):
    return list(
        api.path("system", "resource").select()
    )

def ping(api, address: str, count: int = 3):
    """
    Run ping from MikroTik router.
    Returns raw ping results.
    """
    results = list(
       api(
            cmd = "/ping",
            address=address,
            count=count
        )
    )
    return results
