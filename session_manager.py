# session_manager.py
from fastapi import Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional, Dict, Any
import json
from datetime import datetime, timedelta
import secrets

class SessionManager:
    """Production-grade session management"""
    
    @staticmethod
    def create_user_session(request: Request, user_data: Dict[str, Any]) -> None:
        """Create a new user session"""
        session_data = {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "role": user_data.get("role", "user"),
            "login_time": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "authenticated": True,
            "display_name": user_data.get("display_name"),
            "google_info": user_data.get("google_info", {})
        }
        
        # Store in session (encrypted by SessionMiddleware)
        request.session.update(session_data)
        request.session["csrf_token"] = SessionManager._generate_csrf_token()
    
    @staticmethod
    def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
        """Get current user from session"""
        if not request.session.get("authenticated"):
            return None
        
        # Update last activity
        request.session["last_activity"] = datetime.utcnow().isoformat()
        
        # Check session expiry (optional)
        if SessionManager._is_session_expired(request):
            SessionManager.clear_session(request)
            return None
        
        return {
            "user_id": request.session.get("user_id"),
            "username": request.session.get("username"),
            "email": request.session.get("email"),
            "role": request.session.get("role"),
            "login_time": request.session.get("login_time"),
            "csrf_token": request.session.get("csrf_token"),
            "display_name": request.session.get("display_name"),
            "google_info": request.session.get("google_info", {})
        }
    
    @staticmethod
    def update_session(request: Request, updates: Dict[str, Any]) -> None:
        """Update session data"""
        if request.session.get("authenticated"):
            request.session.update(updates)
            request.session["last_activity"] = datetime.utcnow().isoformat()
    
    @staticmethod
    def clear_session(request: Request) -> None:
        """Clear user session (logout)"""
        request.session.clear()
    
    @staticmethod
    def require_auth(request: Request) -> Dict[str, Any]:
        """Require authentication - raises exception if not logged in"""
        user = SessionManager.get_current_user(request)
        if not user:
            raise HTTPException(
                status_code=401, 
                detail="Authentication required. Please login first."
            )
        return user
    
    @staticmethod
    def require_role(request: Request, required_role: str) -> Dict[str, Any]:
        """Require specific role"""
        user = SessionManager.require_auth(request)
        if user["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. {required_role.title()} role required."
            )
        return user
    
    @staticmethod
    def _generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def _is_session_expired(request: Request, max_age_hours: int = 24) -> bool:
        """Check if session is expired"""
        last_activity = request.session.get("last_activity")
        if not last_activity:
            return True
        
        try:
            last_time = datetime.fromisoformat(last_activity)
            expire_time = last_time + timedelta(hours=max_age_hours)
            return datetime.utcnow() > expire_time
        except:
            return True
    
    @staticmethod
    def get_session_info(request: Request) -> Dict[str, Any]:
        """Get session debugging info"""
        if not request.session.get("authenticated"):
            return {"status": "not_authenticated"}
        
        return {
            "status": "authenticated",
            "username": request.session.get("username"),
            "role": request.session.get("role"),
            "login_time": request.session.get("login_time"),
            "last_activity": request.session.get("last_activity"),
            "session_keys": list(request.session.keys())
        }

# FastAPI Dependencies
def get_current_user_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency for getting current user from session"""
    return SessionManager.require_auth(request)

def get_admin_user_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency for admin-only routes"""
    return SessionManager.require_role(request, "admin")

def get_optional_user_session(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency for optional authentication"""
    return SessionManager.get_current_user(request)