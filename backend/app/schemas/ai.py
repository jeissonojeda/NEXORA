"""AI schemas for request validation and response formatting."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class AIAnalysisRequest(BaseModel):
    """Request schema for AI analysis."""
    analysis_type: str = Field(..., min_length=1, max_length=50, description="Type of analysis")
    product_id: Optional[UUID] = Field(None, description="Specific product to analyze")
    category_id: Optional[UUID] = Field(None, description="Specific category to analyze")
    query: str = Field(..., min_length=10, max_length=1000, description="Natural language query")
    include_recommendations: bool = Field(True, description="Include actionable recommendations")
    time_range_days: int = Field(30, ge=7, le=365, description="Time range for analysis")


class AIAnalysisResponse(BaseModel):
    """Response schema for AI analysis."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID
    analysis_type: str
    product_id: Optional[UUID]
    category_id: Optional[UUID]
    query: str
    response: str
    confidence_score: int = Field(0, ge=0, le=100)
    recommendations: Optional[List[str]] = None
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class AITrendRequest(BaseModel):
    """Request schema for trend analysis."""
    product_id: Optional[UUID] = Field(None, description="Specific product to analyze")
    category_id: Optional[UUID] = Field(None, description="Specific category to analyze")
    period_days: int = Field(30, ge=7, le=365, description="Analysis period")
    include_forecast: bool = Field(True, description="Include demand forecast")


class AITrendResponse(BaseModel):
    """Response schema for trend analysis."""
    product_id: Optional[UUID]
    category_id: Optional[UUID]
    trend_direction: str = Field(..., description="up, down, or stable")
    trend_strength: int = Field(0, ge=0, le=100, description="Trend strength percentage")
    forecast: Optional[List[dict]] = None
    insights: List[str] = []
    recommendations: List[str] = []
    confidence_score: int = Field(0, ge=0, le=100)


class AIBatchAnalysisRequest(BaseModel):
    """Request schema for batch analysis of multiple products."""
    product_ids: List[UUID] = Field(..., min_length=1, max_length=100, description="Product IDs to analyze")
    analysis_type: str = Field("reorder", description="Type of analysis")
    include_cross_selling: bool = Field(True, description="Include cross-selling opportunities")


class AIBatchAnalysisResponse(BaseModel):
    """Response schema for batch analysis."""
    analyses: List[AIAnalysisResponse]
    summary: str
    total_products: int
    products_needing_attention: int
    estimated_stockout_risk: int
