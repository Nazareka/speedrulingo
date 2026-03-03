from fastapi import APIRouter

from api.auth.routes import router as auth_router
from api.content.routes import router as content_router
from api.explain.routes import router as explain_router
from api.learning.routes import router as learning_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(content_router)
router.include_router(learning_router)
router.include_router(explain_router)
