from fastapi import FastAPI, Request, HTTPException, Depends, Response, Cookie, Query
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from msal import ConfidentialClientApplication
import aiofiles
import json
import uvicorn
import asyncio
import time
from typing import Dict
import os
from dotenv import load_dotenv
import pathlib
import logging
import aiofiles
import json


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

# Remove the in-memory token store
# token_store: Dict[str, float] = {}

# Define an asyncio lock for file operations
file_lock = asyncio.Lock()

# Asynchronous functions to read and write the token store
async def read_token_store() -> Dict[str, float]:
    """Read the token_store from the JSON file."""
    async with file_lock:
        try:
            async with aiofiles.open('token_store.json', 'r') as f:
                data = await f.read()
                token_store = json.loads(data)
                return token_store
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}

async def write_token_store(token_store: Dict[str, float]):
    """Write the token_store to the JSON file."""
    async with file_lock:
        async with aiofiles.open('token_store.json', 'w') as f:
            data = json.dumps(token_store)
            await f.write(data)

async def add_token(token: str, expires_in: int):
    """Add a token to the store with its expiration time."""
    expiration_time = time.time() + expires_in
    token_store = await read_token_store()
    token_store[token] = expiration_time
    await write_token_store(token_store)
    logger.info(f"Token added: {token[:10]}... Expires in: {expires_in} seconds")
    await print_current_tokens()

async def remove_expired_tokens():
    """Remove tokens that have expired."""
    current_time = time.time()
    token_store = await read_token_store()
    expired_tokens = [token for token, exp in token_store.items() if exp < current_time]
    for token in expired_tokens:
        del token_store[token]
        logger.info(f"Token expired and removed: {token[:10]}...")
    if expired_tokens:
        await write_token_store(token_store)
        await print_current_tokens()

async def print_current_tokens():
    """Print the current in-memory token store."""
    token_store = await read_token_store()
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

# Security scheme (not used for token URL, but needed for dependency)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_token(access_token: str = Cookie(None)):
    """Dependency to get and validate the current access token from cookies."""
    await remove_expired_tokens()  # Clean up before validation
    if not access_token:
        logger.warning("Unauthorized access attempt. No access token provided.")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    token_store = await read_token_store()
    if access_token not in token_store:
        logger.warning("Unauthorized access attempt. Token not in store.")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return access_token

@app.get("/auth/login")
async def login():
    """Redirects the user to the OAuth2 authorization URL with prompt=login."""
    # Generate the authorization URL with prompt=login
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        prompt='login'  # Add this parameter
    )
    logger.info("Redirecting user to OAuth2 authorization URL with prompt=login.")
    return RedirectResponse(auth_url)


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
        await add_token(access_token, expires_in)

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
    """Logs out the user by clearing the access token cookie and redirecting to Azure AD logout."""
    token_store = await read_token_store()
    # Remove the token from the token_store
    if access_token and access_token in token_store:
        del token_store[access_token]
        await write_token_store(token_store)
        logger.info("Token removed from token store.")
    else:
        logger.info("No valid token found in token store.")

    # Delete the access token cookie
    response = RedirectResponse(url=f"https://login.microsoftonline.com/common/oauth2/v2.0/logout?post_logout_redirect_uri={REDIRECT_URI}")
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="Lax",
        # secure=True,  # Uncomment when using HTTPS in production
    )
    logger.info("User logged out and redirected to Azure AD logout.")
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

# New Endpoint: /summary
@app.get("/summary")
async def get_summary(namespace: str = Query(...), token: str = Depends(get_current_token)):
    """
    Protected endpoint that returns a summary for the given namespace.
    Currently, it returns the namespace repeated 50 times.
    """
    logger.info(f"Accessing /summary endpoint for namespace: {namespace}")
    # Simulate a delay for future database calls
    await asyncio.sleep(0)  # No actual delay, but keeps the function async
    summary = namespace * 50
    return {"namespace": namespace, "summary": summary}

# New Endpoint: /search
@app.get("/search")
async def search_namespace(
    namespace: str = Query(...),
    query: str = Query(...),
    token: str = Depends(get_current_token)
):
    """
    Protected endpoint that searches within a namespace using the given query.
    Currently, it returns the query concatenated with the namespace repeated 50 times.
    """
    logger.info(f"Accessing /search endpoint for namespace: {namespace} with query: {query}")
    # Simulate a delay for future database calls
    await asyncio.sleep(0)  # No actual delay, but keeps the function async
    search_result = query + (namespace * 50)
    return {"namespace": namespace, "query": query, "result": search_result}




@app.get("/images/{filename}")
async def get_image(filename: str, token: str = Depends(get_current_token)):
    """Protected endpoint that returns an image file."""
    logger.info(f"Accessing /images endpoint for filename: {filename}")

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
            raise HTTPException(status_code=400, detail="Invalid file path")

        if not image_path.exists() or not image_path.is_file():
            logger.error(f"Image file not found: {image_path}")
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Error serving image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/images/{filename}")
async def get_image(filename: str, token: str = Depends(get_current_token)):
    """Protected endpoint that returns an image file."""
    logger.info(f"Accessing /images endpoint for filename: {filename}")

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
            raise HTTPException(status_code=400, detail="Invalid file path")

        if not image_path.exists() or not image_path.is_file():
            logger.error(f"Image file not found: {image_path}")
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Error serving image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    # For testing, run without SSL
    uvicorn.run(
        "OAuthV6_v2:app",
        host="0.0.0.0",
        port=1992,
        reload=True  # Remove reload=True in production
    )
