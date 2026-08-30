"""AI routes for business intelligence and recommendations."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_permission
from app.models.user import User
from app.schemas.ai import (
    AIAnalysisRequest, AIAnalysisResponse,
    AITrendRequest, AITrendResponse,
    AIBatchAnalysisRequest, AIBatchAnalysisResponse
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/analyze", response_model=AIAnalysisResponse)
def analyze_inventory(
    request: AIAnalysisRequest,
    current_user: User = Depends(require_permission("ai.analyze")),
    db: Session = Depends(get_db)
):
    """Perform AI-powered inventory analysis."""
    service = AIService(db)
    return service.analyze_inventory(request, current_user.id)


@router.get("/trends", response_model=AITrendResponse)
def get_trends(
    product_id: UUID = None,
    category_id: UUID = None,
    period_days: int = 30,
    include_forecast: bool = True,
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db)
):
    """Get inventory trend analysis."""
    request = AITrendRequest(
        product_id=product_id,
        category_id=category_id,
        period_days=period_days,
        include_forecast=include_forecast
    )
    service = AIService(db)
    return service.get_trends(request)


@router.post("/batch-analyze", response_model=AIBatchAnalysisResponse)
def batch_analyze(
    request: AIBatchAnalysisRequest,
    current_user: User = Depends(require_permission("ai.analyze")),
    db: Session = Depends(get_db)
):
    """Perform batch analysis of multiple products."""
    service = AIService(db)
    return service.batch_analyze(request, current_user.id)


@router.get("/analysis/{analysis_id}", response_model=AIAnalysisResponse)
def get_analysis(
    analysis_id: UUID,
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db)
):
    """Get specific AI analysis by ID."""
    from app.models.ai import AIAnalysis
    analysis = db.query(AIAnalysis).filter(AIAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    return AIAnalysisResponse.model_validate(analysis)


@router.get("/analysis", response_model=List[AIAnalysisResponse])
def list_analyses(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_permission("ai.read")),
    db: Session = Depends(get_db)
):
    """List AI analyses for current user."""
    from app.models.ai import AIAnalysis
    analyses = db.query(AIAnalysis)\
        .filter(AIAnalysis.user_id == current_user.id)\
        .order_by(AIAnalysis.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return [AIAnalysisResponse.model_validate(a) for a in analyses]
