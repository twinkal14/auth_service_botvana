# session_dependencies.py
from fastapi import Depends, Request, HTTPException
from typing import Dict, Any, Optional
from session_manager import SessionManager

def get_current_user_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency for getting current user from session"""
    return SessionManager.require_auth(request)

def get_admin_user_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency for admin-only routes"""
    return SessionManager.require_role(request, "admin")

def get_optional_user_session(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency for optional authentication"""
    return SessionManager.get_current_user(request)