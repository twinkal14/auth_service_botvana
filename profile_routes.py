# profile_routes.py (Production with Session Management)
from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import SessionLocal
from session_manager import get_current_user_session, get_admin_user_session
from jwt_utils import get_current_user  # Still used for API endpoints
from profile_models import UserProfile
from profile_schemas import ProfileCreate, ProfileResponse
from models import User

router = APIRouter(prefix="/profile", tags=["User Profile"])
templates = Jinja2Templates(directory="templates")

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============== HTML ROUTES (Session-based) ==============

@router.get("/create", response_class=HTMLResponse)
def show_create_profile_form(
    request: Request, 
    current_user: dict = Depends(get_current_user_session)
):
    """Show create profile form - Production session authentication"""
    
    return templates.TemplateResponse("create_profile.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "display_name": current_user.get("display_name", current_user["username"])
    })

@router.post("/create", response_class=HTMLResponse)
def create_profile_form(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    bio: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_session)
):
    """Create profile from HTML form - Production version"""
    
    user_id = current_user["user_id"]
    username = current_user["username"]
    
    print(f"DEBUG: Creating profile for user_id: {user_id}, username: {username}")
    
    # Check if profile already exists
    existing_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if existing_profile:
        print(f"DEBUG: Profile already exists for user {user_id}")
        return templates.TemplateResponse("my_profile.html", {
            "request": request,
            "username": username,
            "profile": existing_profile,
            "current_user": current_user
        })
    
    try:
        # Create new profile
        profile = UserProfile(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone if phone else None,
            bio=bio if bio else None
        )
        
        db.add(profile)
        db.commit()
        db.refresh(profile)
        
        print(f"DEBUG: Successfully created profile for user {user_id}")
        
        return templates.TemplateResponse("profile_success.html", {
            "request": request,
            "message": "Profile created successfully!",
            "profile": profile,
            "current_user": current_user
        })
        
    except Exception as e:
        print(f"DEBUG: Error creating profile: {str(e)}")
        return templates.TemplateResponse("create_profile.html", {
            "request": request,
            "username": username,
            "current_user": current_user,
            "error": f"Error creating profile: {str(e)}"
        })

@router.get("/me", response_class=HTMLResponse)
def get_my_profile_page(
    request: Request, 
    current_user: dict = Depends(get_current_user_session),
    db: Session = Depends(get_db)
):
    """Get current user's profile page - Production session auth"""
    
    user_id = current_user["user_id"]
    username = current_user["username"]
    
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if not profile:
        return templates.TemplateResponse("no_profile.html", {
            "request": request,
            "username": username,
            "current_user": current_user
        })
    
    return templates.TemplateResponse("my_profile.html", {
        "request": request,
        "username": username,
        "profile": profile,
        "current_user": current_user
    })

@router.get("/edit", response_class=HTMLResponse)
def edit_profile_form(
    request: Request,
    current_user: dict = Depends(get_current_user_session),
    db: Session = Depends(get_db)
):
    """Show edit profile form"""
    
    user_id = current_user["user_id"]
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if not profile:
        return RedirectResponse(url="/profile/create", status_code=302)
    
    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "username": current_user["username"],
        "profile": profile,
        "current_user": current_user
    })

@router.post("/edit", response_class=HTMLResponse)
def update_profile_form(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    bio: str = Form(""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_session)
):
    """Update profile from HTML form"""
    
    user_id = current_user["user_id"]
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if not profile:
        return RedirectResponse(url="/profile/create", status_code=302)
    
    try:
        # Update profile
        profile.first_name = first_name
        profile.last_name = last_name
        profile.email = email
        profile.phone = phone if phone else None
        profile.bio = bio if bio else None
        
        db.commit()
        db.refresh(profile)
        
        return templates.TemplateResponse("profile_success.html", {
            "request": request,
            "message": "Profile updated successfully!",
            "profile": profile,
            "current_user": current_user
        })
        
    except Exception as e:
        return templates.TemplateResponse("edit_profile.html", {
            "request": request,
            "username": current_user["username"],
            "profile": profile,
            "current_user": current_user,
            "error": f"Error updating profile: {str(e)}"
        })

@router.post("/delete", response_class=HTMLResponse)
def delete_profile(
    request: Request,
    current_user: dict = Depends(get_current_user_session),
    db: Session = Depends(get_db)
):
    """Delete user profile"""
    
    user_id = current_user["user_id"]
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if profile:
        db.delete(profile)
        db.commit()
    
    return RedirectResponse(url="/dashboard?message=profile_deleted", status_code=302)

# ============== ADMIN ROUTES ==============

@router.get("/all", response_class=HTMLResponse)
def list_all_profiles(
    request: Request,
    admin_user: dict = Depends(get_admin_user_session),
    db: Session = Depends(get_db)
):
    """List all profiles - Admin only"""
    
    profiles = db.query(UserProfile).join(User).all()
    
    return templates.TemplateResponse("admin_profiles.html", {
        "request": request,
        "profiles": profiles,
        "admin_user": admin_user
    })

# ============== API ROUTES (JWT-based for external clients) ==============

@router.post("/", response_model=ProfileResponse)
def create_profile_api(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # JWT-based for API
):
    """Create profile via API - Requires JWT token"""
    
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if profile already exists
    existing_profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="Profile already exists for this user")
    
    # Create new profile
    profile = UserProfile(
        user_id=user.id,
        **profile_data.dict(exclude_unset=True)
    )
    
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

@router.get("/me/api", response_model=ProfileResponse)
def get_my_profile_api(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # JWT-based for API
):
    """Get profile data via API - Requires JWT token"""
    
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile

@router.put("/me/api", response_model=ProfileResponse)
def update_profile_api(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # JWT-based for API
):
    """Update profile via API - Requires JWT token"""
    
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Update profile fields
    update_data = profile_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)
    
    db.commit()
    db.refresh(profile)
    return profile

@router.delete("/me/api")
def delete_profile_api(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # JWT-based for API
):
    """Delete profile via API - Requires JWT token"""
    
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db.delete(profile)
    db.commit()
    return {"message": "Profile deleted successfully"}

# ============== SESSION-BASED API ROUTES (Alternative) ==============

@router.get("/me/session", response_model=ProfileResponse)
def get_profile_session_api(
    current_user: dict = Depends(get_current_user_session),
    db: Session = Depends(get_db)
):
    """Get profile via session authentication - Alternative API"""
    
    user_id = current_user["user_id"]
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profile