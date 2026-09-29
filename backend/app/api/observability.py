"""API routes for observability and tracing."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db_session
from app.models.auth import User
from app.models.trace import Trace

router = APIRouter(prefix="/observability", tags=["observability"])

def require_evaluator(user: User):
    """Dependency to check if user is an evaluator or admin."""
    roles = [r.name for r in user.roles]
    if "admin" not in roles and "evaluator" not in roles:
        raise HTTPException(status_code=403, detail="Not authorized to view observability data.")

@router.get("/traces")
async def list_traces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50
):
    """List recent traces for the dashboard."""
    require_evaluator(current_user)
    
    stmt = (
        select(Trace)
        .order_by(desc(Trace.created_at))
        .limit(limit)
    )
    result = await db.scalars(stmt)
    
    traces = []
    for t in result.all():
        traces.append({
            "id": str(t.id),
            "request_id": t.request_id,
            "conversation_id": str(t.conversation_id) if t.conversation_id else None,
            "user_id": str(t.user_id) if t.user_id else None,
            "route": t.route,
            "status": t.status,
            "total_tokens": t.total_tokens,
            "estimated_cost": t.estimated_cost,
            "latency_ms": t.latency_ms,
            "created_at": t.created_at.isoformat()
        })
    return traces

@router.get("/traces/{trace_id}")
async def get_trace_details(
    trace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    """Get a specific trace with its spans."""
    require_evaluator(current_user)
    
    stmt = (
        select(Trace)
        .options(selectinload(Trace.spans))
        .where(Trace.id == trace_id)
    )
    result = await db.scalars(stmt)
    trace = result.first()
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
        
    # Also fetch related guardrail events
    from app.models.guardrail import GuardrailEvent
    stmt_events = select(GuardrailEvent).where(GuardrailEvent.trace_id == trace.id)
    result_events = await db.scalars(stmt_events)
    events = result_events.all()
        
    return {
        "id": str(trace.id),
        "request_id": trace.request_id,
        "route": trace.route,
        "status": trace.status,
        "total_tokens": trace.total_tokens,
        "estimated_cost": trace.estimated_cost,
        "latency_ms": trace.latency_ms,
        "created_at": trace.created_at.isoformat(),
        "spans": [
            {
                "id": str(s.id),
                "name": s.name,
                "status": s.status,
                "latency_ms": s.latency_ms,
                "metadata": s.metadata_json
            }
            for s in trace.spans
        ],
        "guardrail_events": [
            {
                "id": str(e.id),
                "guardrail_name": e.guardrail_name,
                "category": e.category,
                "action": e.action,
                "severity": e.severity,
                "latency_ms": e.latency_ms,
                "metadata": e.metadata_json
            }
            for e in events
        ]
    }

@router.get("/guardrail-events")
async def list_guardrail_events(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 50
):
    """List recent guardrail events for the security dashboard."""
    require_evaluator(current_user)
    
    from app.models.guardrail import GuardrailEvent
    stmt = (
        select(GuardrailEvent)
        .order_by(desc(GuardrailEvent.created_at))
        .limit(limit)
    )
    result = await db.scalars(stmt)
    
    events = []
    for e in result.all():
        events.append({
            "id": str(e.id),
            "trace_id": str(e.trace_id) if e.trace_id else None,
            "guardrail_name": e.guardrail_name,
            "category": e.category,
            "action": e.action,
            "severity": e.severity,
            "latency_ms": e.latency_ms,
            "created_at": e.created_at.isoformat(),
            "metadata": e.metadata_json
        })
    return events


@router.get("/liveness", tags=["health"])
async def liveness_check():
    """Liveness probe for Kubernetes."""
    return {"status": "ok", "service": "enterprise_rag"}


@router.get("/readiness", tags=["health"])
async def readiness_check(db: Annotated[AsyncSession, Depends(get_db_session)]):
    """Readiness probe."""
    try:
        from app.db.database import check_db_connection
        from app.core.dependencies import get_vector_store
        from app.core.config import settings
        
        db_ok = await check_db_connection()
        vs = get_vector_store(settings=settings)
        vs.client.get_collections()
        qdrant_ok = True
    except Exception:
        db_ok = False
        qdrant_ok = False

    if db_ok and qdrant_ok:
        return {"status": "ok", "database": "connected", "qdrant": "connected"}
    raise HTTPException(status_code=503, detail="Service degraded or dependencies unavailable.")
