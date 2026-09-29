"""Evaluation and Observability API endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db_session
from app.models.auth import User
from app.models.evaluation import EvaluationRun, EvaluationResult, EvaluationDataset

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

def require_evaluator(user: User):
    """Check if user is an evaluator or admin."""
    roles = [r.name for r in user.roles]
    if "admin" not in roles and "evaluator" not in roles:
        raise HTTPException(status_code=403, detail="Not authorized to view evaluation data.")

@router.get("/runs")
async def list_runs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50
):
    require_evaluator(current_user)
    stmt = select(EvaluationRun).order_by(desc(EvaluationRun.created_at)).limit(limit)
    result = await db.scalars(stmt)
    
    runs = []
    for r in result.all():
        runs.append({
            "id": str(r.id),
            "run_name": r.run_name,
            "status": r.status,
            "is_baseline": r.is_baseline,
            "total_cases": r.total_cases,
            "passed_cases": r.passed_cases,
            "failed_cases": r.failed_cases,
            "total_cost": r.total_cost,
            "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return runs

@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    require_evaluator(current_user)
    stmt = (
        select(EvaluationRun)
        .options(selectinload(EvaluationRun.results).selectinload(EvaluationResult.metrics))
        .where(EvaluationRun.id == run_id)
    )
    result = await db.scalars(stmt)
    run = result.first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return {
        "id": str(run.id),
        "run_name": run.run_name,
        "status": run.status,
        "is_baseline": run.is_baseline,
        "total_cases": run.total_cases,
        "passed_cases": run.passed_cases,
        "failed_cases": run.failed_cases,
        "total_cost": run.total_cost,
        "total_tokens": run.total_tokens,
        "results": [
            {
                "id": str(res.id),
                "status": res.status,
                "actual_route": res.actual_route,
                "cost": res.cost,
                "tokens": res.tokens,
                "latency_ms": res.latency_ms,
                "failure_type": res.failure_type,
                "error_message": res.error_message,
                "metrics": [
                    {
                        "metric_name": m.metric_name,
                        "score": m.score,
                        "reason": m.reason
                    } for m in res.metrics
                ]
            } for res in run.results
        ]
    }
