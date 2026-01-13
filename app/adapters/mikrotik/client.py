from librouteros import connect

def connect_router(router):
    return connect(
        host=router["host"],
        username=router["username"],
        password=router["password"],
        port=router.get("port", 8728)
    )
