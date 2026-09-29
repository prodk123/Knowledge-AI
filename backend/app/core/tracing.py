import contextvars
import uuid
import time
import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_factory
from app.models.trace import Trace, Span

logger = logging.getLogger(__name__)

# Context variables for tracing
current_trace_id = contextvars.ContextVar("current_trace_id", default=None)
current_span_id = contextvars.ContextVar("current_span_id", default=None)

# We store traces in-memory temporarily until they complete, then flush to DB to minimize DB locks
_active_traces: Dict[uuid.UUID, Dict[str, Any]] = {}
_active_spans: Dict[uuid.UUID, list] = {}

class Tracer:
    @staticmethod
    @asynccontextmanager
    async def start_trace(
        request_id: Optional[str] = None, 
        user_id: Optional[uuid.UUID] = None, 
        conversation_id: Optional[uuid.UUID] = None
    ):
        trace_id = uuid.uuid4()
        token = current_trace_id.set(trace_id)
        
        start_time = time.time()
        
        _active_traces[trace_id] = {
            "id": trace_id,
            "request_id": request_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "route": None,
            "status": "ok",
            "total_tokens": 0,
            "estimated_cost": 0.0,
        }
        _active_spans[trace_id] = []
        
        try:
            async with async_session_factory() as session:
                initial_trace = Trace(
                    id=trace_id,
                    request_id=request_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    route=None,
                    status="running",
                    latency_ms=0.0
                )
                session.add(initial_trace)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to create initial trace {trace_id}: {e}")
        
        trace_ctx = _active_traces[trace_id]
        
        try:
            yield trace_ctx
        except Exception:
            trace_ctx["status"] = "error"
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            
            # Persist trace and its spans to DB
            try:
                async with async_session_factory() as session:
                    from sqlalchemy import select
                    stmt = select(Trace).where(Trace.id == trace_id)
                    result = await session.execute(stmt)
                    trace = result.scalars().first()
                    if trace:
                        trace.route = trace_ctx["route"]
                        trace.status = trace_ctx["status"]
                        trace.total_tokens = trace_ctx.get("total_tokens", 0)
                        trace.estimated_cost = trace_ctx.get("estimated_cost", 0.0)
                        trace.latency_ms = latency_ms
                    
                    for span_data in _active_spans[trace_id]:
                        span = Span(
                            id=span_data["id"],
                            trace_id=trace_id,
                            name=span_data["name"],
                            status=span_data["status"],
                            latency_ms=span_data["latency_ms"],
                            metadata_json=span_data["metadata"]
                        )
                        session.add(span)
                        
                    await session.commit()
            except Exception as e:
                logger.error(f"Failed to persist trace {trace_id}: {e}")
            finally:
                _active_traces.pop(trace_id, None)
                _active_spans.pop(trace_id, None)
                current_trace_id.reset(token)

    @staticmethod
    @contextmanager
    def start_span(name: str):
        trace_id = current_trace_id.get()
        if not trace_id:
            # Not in a trace context
            yield {}
            return

        span_id = uuid.uuid4()
        token = current_span_id.set(span_id)
        
        start_time = time.time()
        status = "ok"
        metadata = {}
        
        try:
            yield metadata
        except Exception:
            status = "error"
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            
            if trace_id in _active_spans:
                _active_spans[trace_id].append({
                    "id": span_id,
                    "name": name,
                    "status": status,
                    "latency_ms": latency_ms,
                    "metadata": metadata
                })
                
            current_span_id.reset(token)

