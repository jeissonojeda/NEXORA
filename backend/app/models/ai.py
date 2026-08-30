"""AI analysis models for the inventory system."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
import uuid


class AIAnalysis(Base):
    """Stores AI analysis results for inventory optimization."""
    __tablename__ = "ai_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    analysis_type = Column(String(50), nullable=False)  # "reorder", "trend", "anomaly", "recommendation"
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    confidence_score = Column(Integer, default=0)  # 0-100
    recommendations = Column(Text, nullable=True)  # JSON array of recommendations
    metadata_json = Column(Text, nullable=True)  # Additional metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AIAnalysis(id={self.id}, type={self.analysis_type}, product={self.product_id})>"
