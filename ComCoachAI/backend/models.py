# backend/models.py
from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base

class Trainer(Base):
    __tablename__ = "trainers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    role = Column(String, default="trainer")  # "trainer" or "admin"    
    tests = relationship("Test", back_populates="trainer")
    status = relationship("TrainerStatus", back_populates="trainer", uselist=False)  #v2upgrades

class Test(Base):
    __tablename__ = "tests"
    
    id = Column(Integer, primary_key=True, index=True)
    test_code = Column(String, unique=True, index=True, nullable=False)
    training_name = Column(String, nullable=False)
    scenario = Column(Text, nullable=False)
    rubric = Column(JSON, nullable=False)  
    rubric_descriptions = Column(JSON, nullable=True)
    difficulty_level = Column(String, nullable=False)
    trainer_id = Column(Integer, ForeignKey("trainers.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)
    
    trainer = relationship("Trainer", back_populates="tests")
    participants = relationship("Participant", back_populates="test")

    @property  #v2upgrades
    def test_title(self):  #v2upgrades
        return self.training_name  #v2upgrades

    @test_title.setter  #v2upgrades
    def test_title(self, value):  #v2upgrades
        self.training_name = value  #v2upgrades


class Participant(Base):
    __tablename__ = "participants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String)
    test_id = Column(Integer, ForeignKey("tests.id"))
    audio_path = Column(String)
    transcript = Column(Text)
    scores = Column(JSON) 
    total_score = Column(Float)
    strengths = Column(Text)
    improvements = Column(Text)
    retake_allowed = Column(Boolean, default=False)
    completed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # "in_progress", "completed", "retake_requested", "retake_approved", "retake_denied"
    
    test = relationship("Test", back_populates="participants")


class TrainerStatus(Base):  #v2upgrades
    __tablename__ = "trainer_status"  #v2upgrades

    id = Column(Integer, primary_key=True, index=True)  #v2upgrades
    trainer_id = Column(Integer, ForeignKey("trainers.id"), unique=True, nullable=False)  #v2upgrades
    is_active = Column(Boolean, default=True, nullable=False)  #v2upgrades
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  #v2upgrades

    trainer = relationship("Trainer", back_populates="status")  #v2upgrades
