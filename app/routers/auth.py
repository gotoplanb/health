from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.google import oauth, verify_hd_claim

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo", {})

    if not verify_hd_claim(user_info):
        raise HTTPException(status_code=403, detail="Unauthorized domain")

    request.session["user"] = {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
    }
    return RedirectResponse(url="/")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login")
