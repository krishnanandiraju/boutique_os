from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.service import IntegrationEventService
from app.models import Order, OrderLine, OrderStatus, TailoringStage, TailoringTask

router = APIRouter()
logger = logging.getLogger(__name__)
integration_events = IntegrationEventService()


class TailoringTransitionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    stage: TailoringStage


class TailoringTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    task_id: int
    order_id: int
    stage: TailoringStage
    order_status: OrderStatus
    order_became_ready: bool
    remaining_tailoring_items: int


def _tailoring_lines(db: Session, order_id: int) -> list[OrderLine]:
    return list(
        db.scalars(
            select(OrderLine).where(
                OrderLine.order_id == order_id,
                OrderLine.requires_tailoring.is_(True),
            )
        )
    )


@router.post("/api/tailoring/tasks/{task_id}/transition", response_model=TailoringTransitionResponse)
def transition_tailoring_task(
    task_id: int,
    payload: TailoringTransitionRequest,
    db: Session = Depends(get_db),
) -> TailoringTransitionResponse:
    task = db.scalar(select(TailoringTask).where(TailoringTask.id == task_id))
    if not task:
        raise HTTPException(404, "Tailoring task not found")

    line = db.scalar(select(OrderLine).where(OrderLine.id == task.order_line_id))
    if not line:
        raise HTTPException(404, "Order line not found")
    order = db.scalar(select(Order).where(Order.id == line.order_id))
    if not order:
        raise HTTPException(404, "Order not found")

    # READY is only reachable through QC. Rework can explicitly move the task back
    # to an earlier stage instead of silently treating QC as a decorative column.
    if payload.stage == TailoringStage.READY and task.stage != TailoringStage.QC:
        raise HTTPException(409, "Complete quality check before marking this garment ready")

    task.stage = payload.stage
    line.tailoring_stage = payload.stage

    tailoring_lines = _tailoring_lines(db, order.id)
    remaining = sum(1 for candidate in tailoring_lines if candidate.tailoring_stage != TailoringStage.READY)
    became_ready = False

    if payload.stage == TailoringStage.READY and remaining == 0 and order.status != OrderStatus.READY:
        order.status = OrderStatus.READY
        became_ready = True
        integration_events.enqueue(
            db,
            merchant_id=order.merchant_id,
            event_type="order.ready",
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={
                "order_id": order.id,
                "customer_id": order.customer_id,
                "status": OrderStatus.READY.value,
                "reason": "all_tailoring_items_ready",
            },
        )
    elif payload.stage != TailoringStage.READY and order.status == OrderStatus.READY:
        # A ready garment sent back for alteration/QC makes the order not ready again.
        order.status = OrderStatus.TAILORING

    db.commit()
    db.refresh(task)
    db.refresh(order)

    logger.info(
        "tailoring.lifecycle.transitioned",
        extra={
            "task_id": task.id,
            "order_id": order.id,
            "stage": task.stage.value,
            "order_status": order.status.value,
            "remaining_tailoring_items": remaining,
            "order_became_ready": became_ready,
        },
    )

    return TailoringTransitionResponse(
        task_id=task.id,
        order_id=order.id,
        stage=task.stage,
        order_status=order.status,
        order_became_ready=became_ready,
        remaining_tailoring_items=remaining,
    )
