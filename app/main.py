from fastapi import FastAPI
from app.api.v1 import match_table, pppoe, routers, health, billing
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="ISP Ops Backend",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(pppoe.router, prefix="/api/v1")
app.include_router(routers.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(match_table.router, prefix="/api/v1")
