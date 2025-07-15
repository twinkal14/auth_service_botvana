# main.py (Production-Grade with Session Management)
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import time
from typing import List, Optional

from database import SessionLocal, engine, Base
from models import User
from auth_utils import hash_password, verify_password
from jwt_utils import create_jwt_token  # Still used for API endpoints

# Import production session management
from session_manager import SessionManager, get_current_user_session, get_admin_user_session, get_optional_user_session

# Import profile models and routes
from profile_models import UserProfile
from profile_routes import router as profile_router

# For Google Login with sessions
from starlette.middleware.sessions import SessionMiddleware
from oauth import router as oauth_router
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title="Production User Management Service", 
    version="2.0.0",
    description="Production-grade user management with session-based authentication"
)

# PRODUCTION SESSION MIDDLEWARE
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY,
    max_age=86400,  # 24 hours
    same_site="lax",
    https_only=False,  # Set to True in production with HTTPS
    session_cookie="auth_session"  # Custom cookie name
)

# Rate limiting middleware
from middlewares import combined_logger_and_limiter
app.middleware("http")(combined_logger_and_limiter)

# Include routers
app.include_router(oauth_router)
app.include_router(profile_router)

# Setup templates
templates = Jinja2Templates(directory="templates")

# Request models
class UserIn(BaseModel):
    username: str
    password: str
    role: str = "user"

class LoginRequest(BaseModel):
    username: str
    password: str

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============== AUTHENTICATION ROUTES ==============

@app.post("/signup")
def signup(user: UserIn, db: Session = Depends(get_db)):
    """Create new user account"""
    existing = db.query(User).filter(User.username == user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    new_user = User(
        username=user.username,
        hashed_password=hash_password(user.password),
        role=user.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"message": "User created successfully", "user_id": new_user.id}

@app.post("/login")
def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login with username/password - creates session"""
    user = db.query(User).filter(User.username == login_data.username).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # CREATE SESSION (Production approach)
    session_data = {
        "user_id": user.id,
        "username": user.username,
        "email": user.username if "@" in user.username else None,
        "role": user.role
    }
    
    SessionManager.create_user_session(request, session_data)
    
    return {
        "message": "Login successful",
        "redirect_url": "/dashboard",
        "user": {
            "username": user.username,
            "role": user.role
        }
    }

@app.post("/logout")
def logout(request: Request):
    """Logout user - clears session"""
    SessionManager.clear_session(request)
    return {"message": "Logged out successfully"}

# ============== PROTECTED ROUTES (Session-based) ==============

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user: dict = Depends(get_current_user_session)):
    """Production dashboard with session authentication"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user["username"],
        "role": current_user["role"],
        "user_id": current_user["user_id"],
        "display_name": current_user.get("display_name", current_user["username"])
    })

@app.get("/protected", response_class=HTMLResponse)
def protected_legacy(request: Request, current_user: dict = Depends(get_current_user_session)):
    """Legacy protected route - redirects to dashboard"""
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/profile", response_class=HTMLResponse)
def profile_redirect(request: Request, current_user: dict = Depends(get_current_user_session)):
    """Redirect to profile page"""
    return RedirectResponse(url="/profile/me", status_code=302)

# ============== ADMIN ROUTES ==============

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request, admin_user: dict = Depends(get_admin_user_session)):
    """Admin panel - requires admin role"""
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "admin": admin_user
    })

@app.get("/users")
def list_users(current_user: dict = Depends(get_admin_user_session), db: Session = Depends(get_db)):
    """List all users - admin only"""
    users = db.query(User).all()
    return {
        "users": [{"id": u.id, "username": u.username, "role": u.role} for u in users],
        "total": len(users)
    }

# ============== API ROUTES (Still use JWT for external access) ==============

@app.post("/api/login")
def api_login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """API login - returns JWT token for external clients"""
    user = db.query(User).filter(User.username == login_data.username).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer"}

# ============== PUBLIC ROUTES ==============

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request, current_user: Optional[dict] = Depends(get_optional_user_session)):
    """Login page - redirects to dashboard if already logged in"""
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=302)
    
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/welcome", response_class=HTMLResponse)
def welcome_legacy(request: Request):
    """Legacy welcome route - redirects to dashboard"""
    return RedirectResponse(url="/dashboard", status_code=302)

# ============== SYSTEM ROUTES ==============

@app.get("/health")
def health_check(request: Request):
    """Health check endpoint"""
    session_status = "authenticated" if SessionManager.get_current_user(request) else "anonymous"
    return {
        "status": "ok",
        "session_status": session_status,
        "timestamp": time.time()
    }

start_time = time.time()

@app.get("/info")
def system_info(request: Request, current_user: Optional[dict] = Depends(get_optional_user_session)):
    """System information"""
    uptime = round(time.time() - start_time, 2)
    
    info = {
        "service": "production_user_management_service",
        "version": "2.0.0",
        "uptime_seconds": uptime,
        "features": [
            "session_based_authentication",
            "oauth2_google_login", 
            "role_based_access_control",
            "user_profiles",
            "admin_panel",
            "api_endpoints",
            "csrf_protection"
        ],
        "authentication": "session_based",
        "session_info": SessionManager.get_session_info(request)
    }
    
    return info

@app.get("/session/debug")
def debug_session(request: Request):
    """Debug session information"""
    return {
        "session_data": dict(request.session),
        "session_info": SessionManager.get_session_info(request),
        "cookies": dict(request.cookies)
    }

# Error handlers
@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    """Handle authentication errors"""
    if request.url.path.startswith("/api/"):
        return {"detail": exc.detail}
    else:
        return RedirectResponse(url="/?error=auth_required", status_code=302)

@app.exception_handler(403)
async def permission_exception_handler(request: Request, exc: HTTPException):
    """Handle permission errors"""
    if request.url.path.startswith("/api/"):
        return {"detail": exc.detail}
    else:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Access Denied",
            "message": exc.detail
        }, status_code=403)