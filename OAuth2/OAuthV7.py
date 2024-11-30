from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from msal import ConfidentialClientApplication
import aiofiles
import json
import uvicorn
import asyncio
import time
from typing import Dict, Optional
import os
from dotenv import load_dotenv
import pathlib
import logging
import uuid

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

# Define an asyncio lock for file operations
file_lock = asyncio.Lock()

TOKEN_STORE_FILE = 'tokens_v7.json'

async def read_token_store() -> Dict[str, Dict]:
    """Read the token_store from the JSON file."""
    async with file_lock:
        try:
            async with aiofiles.open(TOKEN_STORE_FILE, 'r') as f:
                data = await f.read()
                token_store = json.loads(data)
                return token_store
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

async def write_token_store(token_store: Dict[str, Dict]):
    """Write the token_store to the JSON file."""
    async with file_lock:
        async with aiofiles.open(TOKEN_STORE_FILE, 'w') as f:
            data = json.dumps(token_store)
            await f.write(data)

async def add_backend_token(user_info: Dict, expires_in: int) -> str:
    """Generate a backend token, store it with user info and expiration."""
    token = str(uuid.uuid4())
    expiration_time = time.time() + expires_in
    token_store = await read_token_store()
    token_store[token] = {
        "expiration": expiration_time,
        "user": user_info
    }
    await write_token_store(token_store)
    logger.info(f"Backend Token added: {token[:10]}... Expires in: {expires_in} seconds")
    await print_current_tokens()
    return token

async def remove_expired_tokens():
    """Remove tokens that have expired."""
    current_time = time.time()
    token_store = await read_token_store()
    expired_tokens = [token for token, info in token_store.items() if info["expiration"] < current_time]
    for token in expired_tokens:
        del token_store[token]
        logger.info(f"Token expired and removed: {token[:10]}...")
    if expired_tokens:
        await write_token_store(token_store)
        await print_current_tokens()

async def print_current_tokens():
    """Print the current token store."""
    token_store = await read_token_store()
    logger.info("Current Token Store:")
    for token, info in token_store.items():
        remaining = int(info["expiration"] - time.time())
        if remaining > 0:
            logger.info(f"Token: {token[:10]}..., Expires in: {remaining} seconds")
        else:
            logger.info(f"Token: {token[:10]}..., Expired")

async def token_cleanup_task():
    """Background task to clean up expired tokens every 60 seconds."""
    while True:
        await remove_expired_tokens()
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

# Security scheme (OAuth2PasswordBearer is kept for dependency purposes)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_current_token(authorization: Optional[str] = Depends(oauth2_scheme)):
    """Dependency to get and validate the current access token from Authorization header."""
    await remove_expired_tokens()  # Clean up before validation
    if not authorization:
        logger.warning("Unauthorized access attempt. No access token provided.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            logger.warning("Invalid authorization scheme.")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")
    except ValueError:
        logger.warning("Malformed authorization header.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed authorization header")

    token_store = await read_token_store()
    token_info = token_store.get(token)
    if not token_info:
        logger.warning("Unauthorized access attempt. Token not found.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if token_info["expiration"] < time.time():
        logger.warning("Unauthorized access attempt. Token expired.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    return token_info["user"]

@app.get("/auth/login")
async def login():
    """
    Redirects the user to the OAuth2 authorization URL with prompt=login.
    This URL is to be used by the ClientApp to initiate the OAuth2 flow.
    """
    # Generate the authorization URL with prompt=login
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        prompt='login'  # Forces the user to login every time
    )
    logger.info("Redirecting user to OAuth2 authorization URL with prompt=login.")
    return RedirectResponse(auth_url)

@app.get("/auth/redirect")
async def auth_redirect(request: Request):
    """
    Handles the OAuth2 redirect after user authentication.
    Typically, this endpoint is used by the ClientApp to capture the authorization code.
    """
    # Get the authorization code from the query parameters
    code = request.query_params.get("code")
    if not code:
        logger.error("Authorization code not found in redirect.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code not found")

    # For security, you might want to implement state verification here

    # Redirect the client to a page or return a message
    # For simplicity, we'll just inform that the code has been received
    return JSONResponse(content={"message": "Authorization code received. Please exchange it for a token via /auth/token."})

@app.post("/auth/token")
async def exchange_token(request: Request):
    """
    Exchanges the authorization code for an access token.
    Returns a backend token to the ClientApp.
    """
    form = await request.form()
    code = form.get("code")
    if not code:
        logger.error("Authorization code not provided in token exchange.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization code is required")

    # Exchange the authorization code for an access token using MSAL
    result = msal_app.acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    if "access_token" in result:
        # Extract user information from the ID token or user info endpoint
        user_info = result.get("id_token_claims", {})
        if not user_info:
            # Fallback to /me endpoint
            graph_client = msal_app.get("/me")
            user_info = graph_client

        expires_in = result.get("expires_in", 3600)  # Default to 1 hour if not provided

        # Generate and store backend token
        backend_token = await add_backend_token(user_info, expires_in)

        logger.info("Token exchange successful. Returning backend token.")
        return {"access_token": backend_token, "token_type": "bearer", "expires_in": expires_in}
    else:
        error_description = result.get("error_description", "No error description provided.")
        logger.error(f"Token exchange failed: {error_description}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Token exchange failed: {error_description}")

@app.get("/auth/logout")
async def logout(token: str = Depends(get_current_token)):
    """
    Logs out the user by removing the token from the store.
    """
    token_store = await read_token_store()
    # Find the token key associated with the user
    token_to_remove = None
    for stored_token, info in token_store.items():
        if info["user"] == token:
            token_to_remove = stored_token
            break

    if token_to_remove:
        del token_store[token_to_remove]
        await write_token_store(token_store)
        logger.info("Token removed from token store.")
    else:
        logger.info("No valid token found in token store.")

    return {"message": "Logged out successfully."}

@app.get("/namespaces")
async def get_namespaces(user: Dict = Depends(get_current_token)):
    """
    Protected endpoint that lists namespaces from namespaces.txt.
    """
    logger.info(f"User {user.get('name', 'Unknown')} accessing /namespaces endpoint.")
    try:
        # Use absolute path for namespaces.txt
        namespaces_path = pathlib.Path(__file__).parent / "namespaces.txt"
        async with aiofiles.open(namespaces_path, "r") as file:
            contents = await file.read()
            namespaces = [line.strip() for line in contents.splitlines()]
        return {"namespaces": namespaces}
    except FileNotFoundError:
        logger.error("namespaces.txt file not found.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="namespaces.txt file not found")

@app.get("/summary")
async def get_summary(namespace: str, user: Dict = Depends(get_current_token)):
    """
    Protected endpoint that returns a summary for the given namespace.
    Currently, it returns the namespace repeated 50 times.
    """
    logger.info(f"User {user.get('name', 'Unknown')} accessing /summary endpoint for namespace: {namespace}")
    # Simulate a delay for future database calls
    await asyncio.sleep(0)  # No actual delay, but keeps the function async
    summary = namespace * 50
    return {"namespace": namespace, "summary": summary}

@app.get("/search")
async def search_namespace(namespace: str, query: str, user: Dict = Depends(get_current_token)):
    """
    Protected endpoint that searches within a namespace using the given query.
    Currently, it returns the query concatenated with the namespace repeated 50 times.
    """
    logger.info(f"User {user.get('name', 'Unknown')} accessing /search endpoint for namespace: {namespace} with query: {query}")
    # Simulate a delay for future database calls
    await asyncio.sleep(0)  # No actual delay, but keeps the function async
    search_result = query + (namespace * 50)
    return {"namespace": namespace, "query": query, "result": search_result}

@app.get("/images/{filename}")
async def get_image(filename: str, user: Dict = Depends(get_current_token)):
    """
    Protected endpoint that returns an image file.
    """
    logger.info(f"User {user.get('name', 'Unknown')} accessing /images endpoint for filename: {filename}")

    # Define the images directory
    images_dir = pathlib.Path(__file__).parent / "images"

    # Construct the full path
    image_path = images_dir / filename

    # Verify that the file exists and is within the images directory
    try:
        # Resolve the path to prevent directory traversal attacks
        image_path = image_path.resolve()
        if not str(image_path).startswith(str(images_dir.resolve())):
            logger.error("Invalid file path detected.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")

        if not image_path.exists() or not image_path.is_file():
            logger.error(f"Image file not found: {image_path}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

        return RedirectResponse(url=f"/static/images/{filename}")
    except Exception as e:
        logger.error(f"Error serving image: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# Serve static images
from fastapi.staticfiles import StaticFiles
app.mount("/static/images", StaticFiles(directory="images"), name="static-images")

if __name__ == "__main__":
    # For testing, run without SSL
    uvicorn.run(
        "OAuthV7:app",
        host="0.0.0.0",
        port=1992,
        reload=True  # Remove reload=True in production
    )
