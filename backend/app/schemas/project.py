"""Pydantic schemas for projects."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ProjectResponse(BaseModel):
    """Schema for project response."""
    id: str
    name: str
    description: Optional[str] = None
    status: str
    data_file: Optional[str] = None
    ontology_file: Optional[str] = None
    config: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProjectList(BaseModel):
    """Schema for listing projects."""
    projects: list[ProjectResponse]
    total: int

