from fastapi import APIRouter
from app.api.v1.health import router as health
from app.api.v1.admin_sync import router as admin
from app.api.v1.catalog import router as catalog
from app.api.v1.prices import router as prices
from app.api.v1.auth import router as auth_router
from app.api.v1.rules import router as rules_router
from app.api.v1.me import router as me_router
from app.api.v1.owned_sites import router as owned_sites_router
from app.api.v1 import competitors  # new



api = APIRouter()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],     # GET, POST, OPTIONS, etc
    allow_headers=["*"],     # Content-Type, Authorization, etc
)

api.include_router(health, prefix="/v1")
api.include_router(admin, prefix="/v1")
api.include_router(catalog, prefix="/v1")
api.include_router(prices, prefix="/v1")
api.include_router(auth_router, prefix="/v1")
api.include_router(rules_router, prefix="/v1")
api.include_router(me_router, prefix="/v1", tags=["me"])
api.include_router(owned_sites_router, prefix="/v1")
api.include_router(competitors.router, prefix="/v1")
