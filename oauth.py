# oauth.py (Updated for Production Session Management)
from fastapi import APIRouter, Request, Depends
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from session_manager import SessionManager  # Import our session manager

# Step 1: Load .env automatically from root
config = Config(".env")

# Step 2: Read OAuth config values safely
google_client_id = config("GOOGLE_CLIENT_ID", cast=str, default="")
google_client_secret = config("GOOGLE_CLIENT_SECRET", cast=str, default="")

# Step 3: Init router
router = APIRouter()

# Step 4: Validate credentials and configure OAuth
if not google_client_id or not google_client_secret:
    print("⚠️ GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are missing or invalid")
    oauth = None
else:
    print(f"✅ Google OAuth configured with Client ID: {google_client_id[:10]}...")
    oauth = OAuth(config)
    oauth.register(
        name='google',
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile',
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'select_account'
        }
    )

# Step 5: Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Step 6: OAuth login route
@router.get("/login/google")
async def login_via_google(request: Request):
    if not oauth:
        return HTMLResponse(
            content="""<h1>OAuth Not Configured</h1>
            <p>Missing Google credentials. Please update your .env file.</p>
            <a href="/">← Back to Login</a>""",
            status_code=500
        )
    
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    redirect_uri = f"{base_url}/auth/callback"

    print(f"DEBUG: Using redirect_uri: {redirect_uri}")

    # Clear any existing session before OAuth
    SessionManager.clear_session(request)

    try:
        return await oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        print(f"DEBUG: Error in authorize_redirect: {e}")
        return HTMLResponse(
            content=f"<h1>OAuth Error</h1><p>{str(e)}</p><a href='/'>← Back</a>",
            status_code=500
        )

# Step 7: OAuth callback route (UPDATED for session management)
@router.get("/auth/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    if not oauth:
        return HTMLResponse(
            content="<h1>OAuth Error</h1><p>Google OAuth is not configured.</p>",
            status_code=500
        )

    print("DEBUG: OAuth callback received")
    try:
        # Get the authorization token
        token = await oauth.google.authorize_access_token(request)
        
        # Get user info
        user_info = None
        if 'id_token' in token:
            try:
                user_info = await oauth.google.parse_id_token(request, token)
            except Exception as e:
                print(f"DEBUG: ID token parse failed: {e}")
        
        if not user_info:
            resp = await oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo', token=token)
            user_info = resp.json()

        if not user_info or 'email' not in user_info:
            raise Exception("Email not returned by Google")

        # Find or create user in database
        existing_user = db.query(User).filter(User.username == user_info['email']).first()
        if not existing_user:
            new_user = User(
                username=user_info['email'],
                hashed_password="",  # No password for OAuth users
                role="user"
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            existing_user = new_user
            print(f"DEBUG: Created new user: {user_info['email']}")

        # CREATE SESSION (This is the key change!)
        session_data = {
            "user_id": existing_user.id,
            "username": existing_user.username,
            "email": user_info['email'],
            "role": existing_user.role,
            "display_name": user_info.get('name', user_info.get('email', 'User')),
            "google_info": {
                "name": user_info.get('name'),
                "picture": user_info.get('picture'),
                "google_id": user_info.get('sub')
            }
        }
        
        SessionManager.create_user_session(request, session_data)
        
        print(f"DEBUG: Session created for user: {existing_user.username}")
        
        # Redirect to dashboard (no more tokens in URL!)
        return RedirectResponse(url="/dashboard", status_code=302)

    except Exception as e:
        import traceback
        print(f"DEBUG: OAuth callback error: {traceback.format_exc()}")
        return HTMLResponse(
            content=f"<h1>Auth Error</h1><p>{str(e)}</p><a href='/'>← Back</a>",
            status_code=400
        )

# Step 8: Logout route
@router.get("/logout")
def logout(request: Request):
    """Logout user and clear session"""
    SessionManager.clear_session(request)
    return RedirectResponse(url="/", status_code=302)

# Step 9: Session info route (for debugging)
@router.get("/session/info")
def session_info(request: Request):
    """Get current session information (for debugging)"""
    return SessionManager.get_session_info(request)