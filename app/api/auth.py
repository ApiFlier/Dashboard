from fastapi import Header, HTTPException, status
from app.core.config import settings

async def verify_admin_token(x_admin_token: str = Header(None)):
    """
    Dependency to verify admin token if public read-only mode is enabled.
    """
    if not settings.PUBLIC_READONLY_MODE:
        return

    if not settings.ADMIN_API_TOKEN:
        # If token is not configured but we are in read-only mode, block all mutations
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This public instance is read-only."
        )

    if x_admin_token != settings.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This public instance is read-only. Invalid admin token."
        )
