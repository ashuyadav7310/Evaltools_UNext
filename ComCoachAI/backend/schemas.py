# backend/schemas.py
from pydantic import BaseModel, EmailStr, field_serializer #v2upgrades
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta  #v2upgrades

_IST = timezone(timedelta(hours=5, minutes=30))  #v2upgrades

def _to_ist_str(dt: datetime) -> Optional[str]:  #v2upgrades
    """Convert UTC datetime to IST formatted string (UTC+5:30)."""  #v2upgrades
    if dt is None:  #v2upgrades
        return None  #v2upgrades
    if dt.tzinfo is None:  #v2upgrades
        dt = dt.replace(tzinfo=timezone.utc)  #v2upgrades
    return dt.astimezone(_IST).strftime("%d %b %Y, %I:%M %p IST")  #v2upgrades

# Trainer Schemas
class TrainerCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class TrainerLogin(BaseModel):
    email: EmailStr
    password: str

class TrainerResponse(BaseModel):
    id: int
    name: str
    email: str
    
    class Config:
        from_attributes = True

# Test Schemas
class TestCreate(BaseModel):
    test_title: str  #v2upgrades
    #training_name: str
    scenario: str
    rubric: Dict[str, int]
    rubric_descriptions: Optional[Dict[str, str]] = None  #v2upgrades      
    difficulty_level: str

class TestResponse(BaseModel):
    id: int
    test_code: str
    training_name: str
    test_title: str  #v2upgrades
    scenario: str
    rubric: Dict[str, int]
    rubric_descriptions: Optional[Dict[str, str]] = None  #v2upgrades
    difficulty_level: str
    created_at: datetime
    has_participants: bool = False  #v2upgrades
    has_completed_attempts: bool = False  #v2upgrades
    can_edit: bool = True  #v2upgrades
    can_delete: bool = False  #v2upgrades
    is_active: bool = True

    @field_serializer('created_at')  #v2upgrades
    def serialize_created_at(self, dt: datetime) -> Optional[str]:  #v2upgrades
        return _to_ist_str(dt)  #v2upgrades

    class Config:
        from_attributes = True

# Participant Schemas
class ParticipantStart(BaseModel):
    name: str
    email: Optional[EmailStr] = None

class ParticipantResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    transcript: Optional[str]
    scores: Optional[Dict[str, float]]
    total_score: Optional[float]
    strengths: Optional[str]
    improvements: Optional[str]
    completed_at: Optional[datetime] = None  #v2upgrades
    audio_analysis: Optional[Dict] = None 
    
    @field_serializer('completed_at')  #v2upgrades
    def serialize_completed_at(self, dt: Optional[datetime]) -> Optional[str]:  #v2upgrades
        return _to_ist_str(dt)  #v2upgrades    

    class Config:
        from_attributes = True

# Dashboard Schemas
class WeakArea(BaseModel):
    skill: str
    average: float

class DashboardStats(BaseModel):
    total_participants: int
    average_score: float
    weak_areas: List[WeakArea]
    participants: List[ParticipantResponse]


class TestCodeUpdate(BaseModel):  #v2upgrades
    new_test_code: str  #v2upgrades
