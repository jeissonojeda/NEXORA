"""AI service for business intelligence and recommendations."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.ai import AIAnalysis
from app.models.product import Product
from app.models.category import Category
from app.models.inventory import InventoryMovement
from app.models.sale import Sale, SaleItem
from app.models.purchase import Purchase, PurchaseItem
from app.schemas.ai import (
    AIAnalysisRequest, AIAnalysisResponse,
    AITrendRequest, AITrendResponse,
    AIBatchAnalysisRequest, AIBatchAnalysisResponse
)


class AIService:
    """Service for AI-powered business intelligence."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_inventory(self, request: AIAnalysisRequest, user_id: UUID) -> AIAnalysisResponse:
        """Perform inventory analysis using AI."""
        # Get context data
        context = self._gather_inventory_context(request.product_id, request.category_id)
        
        # Generate analysis (placeholder for actual AI model integration)
        analysis_result = self._generate_analysis(request, context)
        
        # Store analysis
        analysis = AIAnalysis(
            user_id=user_id,
            analysis_type=request.analysis_type,
            product_id=request.product_id,
            category_id=request.category_id,
            query=request.query,
            response=analysis_result["response"],
            confidence_score=analysis_result["confidence_score"],
            recommendations=analysis_result.get("recommendations"),
            metadata_json=analysis_result.get("metadata")
        )
        
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        return AIAnalysisResponse.model_validate(analysis)

    def get_trends(self, request: AITrendRequest) -> AITrendResponse:
        """Analyze inventory trends."""
        # Get historical data
        history = self._get_movement_history(request.product_id, request.category_id, request.period_days)
        
        # Analyze trend
        trend_analysis = self._analyze_trend(history, request.include_forecast)
        
        return AITrendResponse(
            product_id=request.product_id,
            category_id=request.category_id,
            trend_direction=trend_analysis["direction"],
            trend_strength=trend_analysis["strength"],
            forecast=trend_analysis.get("forecast"),
            insights=trend_analysis.get("insights", []),
            recommendations=trend_analysis.get("recommendations", []),
            confidence_score=trend_analysis.get("confidence_score", 0)
        )

    def batch_analyze(self, request: AIBatchAnalysisRequest, user_id: UUID) -> AIBatchAnalysisResponse:
        """Perform batch analysis of multiple products."""
        analyses = []
        products_needing_attention = 0
        
        for product_id in request.product_ids:
            # Create individual analysis request
            individual_request = AIAnalysisRequest(
                analysis_type=request.analysis_type,
                product_id=product_id,
                query=f"Analyze product {product_id} for {request.analysis_type}",
                include_recommendations=True
            )
            
            # Perform analysis
            analysis = self.analyze_inventory(individual_request, user_id)
            analyses.append(analysis)
            
            # Count products needing attention
            if analysis.confidence_score < 70 or "low stock" in analysis.response.lower():
                products_needing_attention += 1
        
        return AIBatchAnalysisResponse(
            analyses=analyses,
            summary=f"Analyzed {len(analyses)} products. {products_needing_attention} need attention.",
            total_products=len(analyses),
            products_needing_attention=products_needing_attention,
            estimated_stockout_risk=products_needing_attention
        )

    def _gather_inventory_context(self, product_id: Optional[UUID], category_id: Optional[UUID]) -> dict:
        """Gather context data for analysis."""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "products": [],
            "categories": [],
            "recent_movements": []
        }
        
        # Get products
        if product_id:
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if product:
                context["products"].append({
                    "id": str(product.id),
                    "name": product.name,
                    "stock": product.stock,
                    "min_stock": product.min_stock,
                    "price": float(product.price)
                })
        else:
            # Get all products or filtered by category
            query = self.db.query(Product)
            if category_id:
                query = query.filter(Product.category_id == category_id)
            
            products = query.limit(50).all()  # Limit for performance
            for product in products:
                context["products"].append({
                    "id": str(product.id),
                    "name": product.name,
                    "stock": product.stock,
                    "min_stock": product.min_stock,
                    "price": float(product.price)
                })
        
        # Get recent movements
        movements = self.db.query(InventoryMovement)\
            .order_by(desc(InventoryMovement.created_at))\
            .limit(100)\
            .all()
        
        for movement in movements:
            context["recent_movements"].append({
                "product_id": str(movement.product_id),
                "type": movement.movement_type,
                "quantity": movement.quantity,
                "date": movement.created_at.isoformat()
            })
        
        return context

    def _generate_analysis(self, request: AIAnalysisRequest, context: dict) -> dict:
        """Generate AI analysis (placeholder for actual AI model)."""
        # This is a placeholder - in production, this would call an AI model
        products = context.get("products", [])
        movements = context.get("recent_movements", [])
        
        # Simple rule-based analysis for demonstration
        response_parts = []
        recommendations = []
        confidence_score = 75
        
        if not products:
            response_parts.append("No se encontraron productos para analizar.")
            confidence_score = 0
        else:
            # Analyze stock levels
            low_stock_products = [p for p in products if p["stock"] <= p.get("min_stock", 0)]
            out_of_stock = [p for p in products if p["stock"] == 0]
            
            if out_of_stock:
                response_parts.append(f"Hay {len(out_of_stock)} productos sin stock.")
                recommendations.append("Reabastecer urgentemente productos sin stock.")
                confidence_score = 90
            
            if low_stock_products:
                response_parts.append(f"Hay {len(low_stock_products)} productos con stock bajo.")
                recommendations.append("Considerar reordenar productos con stock bajo.")
                confidence_score = 85
            
            # Analyze movement patterns
            if movements:
                recent_movements = [m for m in movements 
                                  if datetime.fromisoformat(m["date"].replace('Z', '+00:00')) > 
                                  datetime.utcnow() - timedelta(days=7)]
                
                if recent_movements:
                    movement_types = {}
                    for m in recent_movements:
                        movement_types[m["type"]] = movement_types.get(m["type"], 0) + 1
                    
                    if "out" in movement_types and movement_types["out"] > 10:
                        response_parts.append("Alta rotación de productos detectada.")
                        recommendations.append("Considerar aumentar stock de seguridad.")
                        confidence_score = 80
            
            # Generate response
            if not response_parts:
                response_parts.append("Inventario en niveles normales. No se requieren acciones inmediatas.")
                recommendations.append("Mantener monitoreo regular del inventario.")
        
        return {
            "response": " ".join(response_parts),
            "confidence_score": confidence_score,
            "recommendations": recommendations,
            "metadata": {
                "products_analyzed": len(products),
                "movements_analyzed": len(movements)
            }
        }

    def _get_movement_history(self, product_id: Optional[UUID], category_id: Optional[UUID], period_days: int) -> List[dict]:
        """Get movement history for trend analysis."""
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)
        
        query = self.db.query(InventoryMovement)\
            .filter(InventoryMovement.created_at >= cutoff_date)
        
        if product_id:
            query = query.filter(InventoryMovement.product_id == product_id)
        
        movements = query.order_by(desc(InventoryMovement.created_at)).all()
        
        return [{
            "product_id": str(m.product_id),
            "type": m.movement_type,
            "quantity": m.quantity,
            "date": m.created_at.isoformat()
        } for m in movements]

    def _analyze_trend(self, history: List[dict], include_forecast: bool) -> dict:
        """Analyze trend from movement history."""
        if not history:
            return {
                "direction": "stable",
                "strength": 0,
                "insights": ["No hay datos históricos disponibles."],
                "recommendations": ["Comenzar a registrar movimientos de inventario."],
                "confidence_score": 0
            }
        
        # Simple trend analysis
        total_out = sum(m["quantity"] for m in history if m["type"] == "out")
        total_in = sum(m["quantity"] for m in history if m["type"] == "in")
        
        if total_out > total_in * 1.2:
            direction = "down"
            strength = min(100, int((total_out / max(total_in, 1)) * 30))
            insights = ["La salida de productos supera las entradas."]
            recommendations = ["Considerar reabastecer inventario."]
        elif total_in > total_out * 1.2:
            direction = "up"
            strength = min(100, int((total_in / max(total_out, 1)) * 30))
            insights = ["Las entradas de productos superan las salidas."]
            recommendations = ["Revisar niveles de stock óptimos."]
        else:
            direction = "stable"
            strength = 20
            insights = ["Movimientos de inventario equilibrados."]
            recommendations = ["Mantener estrategia actual."]
        
        forecast = None
        if include_forecast:
            # Simple forecast placeholder
            avg_daily_movement = total_out / max(len(history), 1)
            forecast = [{
                "date": (datetime.utcnow() + timedelta(days=i)).isoformat(),
                "predicted_quantity": int(avg_daily_movement * (0.9 + (i * 0.02)))
            } for i in range(1, 8)]
        
        return {
            "direction": direction,
            "strength": strength,
            "forecast": forecast,
            "insights": insights,
            "recommendations": recommendations,
            "confidence_score": min(100, strength + 20)
        }
