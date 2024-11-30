from fastapi import FastAPI, Request, HTTPException, Depends, Response, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from msal import ConfidentialClientApplication
import uvicorn
import asyncio
import time
from typing import Dict
import os
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
import pathlib
import logging

load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = os.getenv("AUTHORITY")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = ["User.Read"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    logger.info(f"Token added: {token[:10]}... Expires in: {expires_in} seconds")
    print_current_tokens()

def remove_expired_tokens():
    """Remove tokens that have expired."""
    current_time = time.time()
    expired_tokens = [token for token, exp in token_store.items() if exp < current_time]
    for token in expired_tokens:
        del token_store[token]
        logger.info(f"Token expired and removed: {token[:10]}...")
    if expired_tokens:
        print_current_tokens()

def print_current_tokens():
    """Print the current in-memory token store."""
    logger.info("Current Token Store:")
    for token, exp in token_store.items():
        remaining = int(exp - time.time())
        if remaining > 0:
            logger.info(f"Token: {token[:10]}..., Expires in: {remaining} seconds")
        else:
            logger.info(f"Token: {token[:10]}..., Expired")

async def token_cleanup_task():
    """Background task to clean up expired tokens every 60 seconds."""
    while True:
        remove_expired_tokens()
        await asyncio.sleep(60)  # Run cleanup every 60 seconds

async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup: Start the token cleanup background task
    cleanup_task = asyncio.create_task(token_cleanup_task())
    logger.info("Application startup: Token cleanup task started.")

    yield  # Control passes to the application

    # Shutdown: Cancel the background task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Application shutdown: Token cleanup task canceled.")

# Initialize FastAPI with lifespan
app = FastAPI(lifespan=lifespan)

# Security scheme (not used for token URL, but needed for dependency)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_token(access_token: str = Cookie(None)):
    """Dependency to get and validate the current access token from cookies."""
    remove_expired_tokens()  # Clean up before validation
    if not access_token or access_token not in token_store:
        logger.warning("Unauthorized access attempt.")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return access_token

@app.get("/auth/login")
async def login():
    """Redirects the user to the OAuth2 authorization URL."""
    # Generate the authorization URL
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    logger.info("Redirecting user to OAuth2 authorization URL.")
    return RedirectResponse(auth_url)

@app.get("/", response_class=HTMLResponse)
async def read_frontend():
    """Serve the frontend HTML page."""
    frontend_path = pathlib.Path(__file__).parent / "static" / "frontend.html"
    if not frontend_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    with open(frontend_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, status_code=200)

@app.get("/auth/redirect")
async def auth_redirect(request: Request):
    """Handles the OAuth2 redirect and exchanges the authorization code for an access token."""
    # Get the authorization code from the query parameters
    code = request.query_params.get("code")
    if not code:
        logger.error("Authorization code not found in redirect.")
        raise HTTPException(status_code=400, detail="Authorization code not found")

    # Exchange the authorization code for an access token
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    if "access_token" in result:
        access_token = result["access_token"]
        expires_in = result.get("expires_in", 3600)  # Default to 1 hour if not provided
        add_token(access_token, expires_in)

        # Create a RedirectResponse and set the cookie on it
        response = RedirectResponse(url="/")
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            # secure=True,  # Uncomment when using HTTPS in production
            max_age=expires_in,
            path="/",
            samesite="Lax"  # SameSite attribute set to Lax
        )

        logger.info("Authentication successful. Redirecting to frontend.")
        return response
    else:
        error_description = result.get("error_description", "No error description provided.")
        logger.error(f"Authentication failed: {error_description}")
        raise HTTPException(status_code=400, detail=f"Authentication failed: {error_description}")

@app.get("/auth/logout")
async def logout(access_token: str = Cookie(None)):
    """Logs out the user by clearing the access token cookie."""
    # Remove the token from the token_store
    if access_token and access_token in token_store:
        del token_store[access_token]
        logger.info("Token removed from token store.")
    else:
        logger.info("No valid token found in token store.")

    response = RedirectResponse(url="/")
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="Lax",
        # secure=True,  # Uncomment when using HTTPS in production
    )
    logger.info("User logged out.")
    return response

@app.get("/namespaces")
async def get_namespaces(token: str = Depends(get_current_token)):
    """Protected endpoint that lists namespaces from namespaces.txt."""
    logger.info("Accessing /namespaces endpoint.")
    try:
        # Use absolute path for namespaces.txt
        namespaces_path = pathlib.Path(__file__).parent / "namespaces.txt"
        with open(namespaces_path, "r") as file:
            namespaces = [line.strip() for line in file.readlines()]
        return {"namespaces": namespaces}
    except FileNotFoundError:
        logger.error("namespaces.txt file not found.")
        raise HTTPException(status_code=500, detail="namespaces.txt file not found")

# Serve static files (frontend)
static_files_path = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_files_path), name="static")

if __name__ == "__main__":
    # For testing, run without SSL
    uvicorn.run(
        "OAuthV5:app",
        host="0.0.0.0",
        port=1992,
        reload=True  # Remove reload=True in production
    )
