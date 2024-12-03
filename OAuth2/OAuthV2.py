from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from msal import ConfidentialClientApplication
import uvicorn
from typing import *
token_store: Dict[str, float] = {}
app = FastAPI()

CLIENT_ID = "34d78561-afe4-4890-85fc-e2b042be0176"
CLIENT_SECRET = "nmV8Q~8qRT7quSpKiY_OaAZvpWfZCtQkpF7KpciG"
AUTHORITY = "https://login.microsoftonline.com/4130bd39-7c53-419c-b1e5-8758d6d63f21"
REDIRECT_URI = "http://localhost:1992/auth/redirect"
SCOPES = ["User.Read"]

msal_app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=AUTHORITY
)


@app.get("/auth/login")
async def login():
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    return RedirectResponse(auth_url)


@app.get("/")
async def root():
    return {"message": "Welcome to the OAuth2 FastAPI App! Navigate to /auth/login to begin."}


@app.get("/auth/redirect")
async def auth_redirect(request: Request):
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    if "access_token" in result:
        return {"message": "YAYY", "access_token": result["access_token"]}
    else:
        raise HTTPException(status_code=400, detail="Authentication failed")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1992)
