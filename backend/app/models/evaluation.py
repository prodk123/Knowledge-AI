import uuid
from datetime import datetime
from sqlalchemy import String, Column, ForeignKey, Integer, Float, Boolean, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

class EvaluationDataset(Base):
    """A versioned dataset used for evaluation."""
    __tablename__ = "evaluation_datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cases = relationship("EvaluationCase", back_populates="dataset", cascade="all, delete-orphan")
    runs = relationship("EvaluationRun", back_populates="dataset")

class EvaluationCase(Base):
    """A specific test case within a dataset."""
    __tablename__ = "evaluation_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_datasets.id"), nullable=False)
    case_id = Column(String, nullable=False) # e.g. 'routing_01'
    name = Column(String, nullable=False)
    input_data = Column(JSON, nullable=False) # The input query / context
    expected_route = Column(String, nullable=True)
    expected_tools = Column(JSON, nullable=True)
    expected_agents = Column(JSON, nullable=True)
    expected_answer = Column(String, nullable=True)
    ground_truth = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    dataset = relationship("EvaluationDataset", back_populates="cases")

class EvaluationRun(Base):
    """An execution of a dataset against a specific configuration."""
    __tablename__ = "evaluation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_datasets.id"), nullable=False)
    run_name = Column(String, nullable=False)
    status = Column(String, nullable=False) # RUNNING, COMPLETED, FAILED
    is_baseline = Column(Boolean, default=False)
    configuration = Column(JSON, nullable=True) # Models used, budgets, etc.
    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    failed_cases = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    dataset = relationship("EvaluationDataset", back_populates="runs")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")

class EvaluationResult(Base):
    """The result of a single case within a run."""
    __tablename__ = "evaluation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id"), nullable=False)
    case_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_cases.id"), nullable=False)
    status = Column(String, nullable=False) # PASS, FAIL, ERROR, SKIPPED, BLOCKED
    trace_id = Column(UUID(as_uuid=True), nullable=True)
    actual_route = Column(String, nullable=True)
    actual_tools = Column(JSON, nullable=True)
    actual_agents = Column(JSON, nullable=True)
    actual_answer = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    tokens = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    failure_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("EvaluationRun", back_populates="results")
    metrics = relationship("EvaluationMetric", back_populates="result", cascade="all, delete-orphan")

class EvaluationMetric(Base):
    """A specific metric scored for a result."""
    __tablename__ = "evaluation_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_results.id"), nullable=False)
    metric_name = Column(String, nullable=False) # e.g., 'routing_accuracy', 'groundedness'
    score = Column(Float, nullable=False) # 0.0 to 1.0
    reason = Column(String, nullable=True)
    is_llm_judged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    result = relationship("EvaluationResult", back_populates="metrics")
