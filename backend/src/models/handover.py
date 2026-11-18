from sqlalchemy import String, Double, JSON, ForeignKey, Boolean, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Handover(Base):
    """交班点固定、可断点续跑的一次封存现场。cutoff 在创建时固定，之后不再改变。"""
    __tablename__ = 'handovers'
    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(80), unique=True)
    label: Mapped[str] = mapped_column(String(160))
    cutoff: Mapped[float] = mapped_column(Double)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    phase: Mapped[str] = mapped_column(String(20), default='datasets')
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    dataset_total: Mapped[int] = mapped_column(Integer, default=0)
    job_total: Mapped[int] = mapped_column(Integer, default=0)
    delivery_total: Mapped[int] = mapped_column(Integer, default=0)
    scene_checksum: Mapped[str] = mapped_column(String(64), default='')
    error: Mapped[str] = mapped_column(String(1000), default='')
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    completed_at: Mapped[float | None] = mapped_column(Double, nullable=True)


class HandoverDataset(Base):
    __tablename__ = 'handover_datasets'
    __table_args__ = (UniqueConstraint('handover_id', 'dataset_id', name='uq_handover_dataset'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey('handovers.id'))
    dataset_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(200))
    checksum: Mapped[str] = mapped_column(String(64))
    rows_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Double)


class HandoverJob(Base):
    """分析任务在交班点的状态快照，状态由 created/started/finished 时间反推，后续补算不回改。"""
    __tablename__ = 'handover_jobs'
    __table_args__ = (UniqueConstraint('handover_id', 'job_id', name='uq_handover_job'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey('handovers.id'))
    job_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(Integer)
    dataset_name: Mapped[str] = mapped_column(String(160))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[float] = mapped_column(Double)
    started_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)


class HandoverDelivery(Base):
    """已投递简报在交班点的存档行，连同分发计划、分析任务、数据批次的出处一并固化。"""
    __tablename__ = 'handover_deliveries'
    __table_args__ = (UniqueConstraint('handover_id', 'delivery_id', name='uq_handover_delivery'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey('handovers.id'))
    delivery_id: Mapped[int] = mapped_column(Integer)
    report_id: Mapped[int] = mapped_column(Integer)
    report_name: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[int] = mapped_column(Integer)
    job_name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(Integer)
    dataset_name: Mapped[str] = mapped_column(String(160))
    dataset_checksum: Mapped[str] = mapped_column(String(64))
    checksum: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[float] = mapped_column(Double)
