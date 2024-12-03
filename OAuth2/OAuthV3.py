from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from msal import ConfidentialClientApplication
import uvicorn
import asyncio
import time
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

token_store: Dict[str, float] = {}


def add_token(token: str, expires_in: int):
    """Add a token to the store with its expiration time."""
    expiration_time = time.time() + expires_in
    token_store[token] = expiration_time
    print(f"Token added: {token}")
    print_current_tokens()


def remove_expired_tokens():
    """Remove tokens that have expired."""
    current_time = time.time()
    expired_tokens = [token for token, exp in token_store.items() if exp < current_time]
    for token in expired_tokens:
        del token_store[token]
        print(f"Token expired and removed: {token}")
    if expired_tokens:
        print_current_tokens()


def print_current_tokens():
    """Print the current in-memory token store."""
    print("Current Token Store:")
    for token, exp in token_store.items():
        remaining = int(exp - time.time())
        if remaining > 0:
            print(f"Token: {token}, Expires in: {remaining} seconds")
        else:
            print(f"Token: {token}, Expired")


async def token_cleanup_task():
    """Background task to clean up expired tokens every 60 seconds."""
    while True:
        remove_expired_tokens()
        await asyncio.sleep(60)


async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    cleanup_task = asyncio.create_task(token_cleanup_task())
    print("Application startup: Token cleanup task started.")

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        print("Application shutdown: Token cleanup task canceled.")


app = FastAPI(lifespan=lifespan)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_token(token: str = Depends(oauth2_scheme)):
    remove_expired_tokens()
    if token not in token_store:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return token


@app.get("/auth/login")
async def login():
    """Redirects the user to the OAuth2 authorization URL."""
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    return RedirectResponse(auth_url)


@app.get("/")
async def root():
    """Root endpoint welcoming users."""
    return {"message": "Welcome to the OAuth2 FastAPI App! Navigate to /auth/login to begin."}


@app.get("/auth/redirect")
async def auth_redirect(request: Request):
    """Handles the OAuth2 redirect and exchanges the authorization code for an access token."""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    if "access_token" in result:
        access_token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        add_token(access_token, expires_in)
        return {"message": "Authentication successful", "access_token": access_token}
    else:
        error_description = result.get("error_description", "No error description provided.")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {error_description}")


@app.get("/namespaces")
async def get_namespaces(token: str = Depends(get_current_token)):
    """Protected endpoint that lists namespaces from namespaces.txt."""
    try:
        with open("namespaces.txt", "r") as file:
            namespaces = [line.strip() for line in file.readlines()]
        return {"namespaces": namespaces}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="namespaces.txt file not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1992)
