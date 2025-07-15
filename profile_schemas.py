    # profile_schemas.py (Simple Phase 1)
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime

class ProfileCreate(BaseModel):
    """Schema for creating a new profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    
    # Simple validation
    @validator('phone')
    def validate_phone(cls, v):
        if v and len(v) < 10:
            raise ValueError('Phone number must be at least 10 characters')
        return v
    
    @validator('bio')
    def validate_bio(cls, v):
        if v and len(v) > 200:
            raise ValueError('Bio must be less than 200 characters')
        return v

class ProfileResponse(BaseModel):
    """Schema for profile responses"""
    id: int
    user_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True