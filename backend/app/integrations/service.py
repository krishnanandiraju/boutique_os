from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.dto import ExternalReference
from app.models import ExternalResourceMapping, IntegrationOutbox, IntegrationOutboxStatus, MappingSyncStatus, CommerceChannelType, ExternalResourceType


logger = logging.getLogger(__name__)


class IntegrationEventService:
    def record_mapping(
        self,
        db: Session,
        *,
        merchant_id: int,
        system: CommerceChannelType,
        resource_type: ExternalResourceType,
        internal_id: int,
        external_id: str,
        sync_status: MappingSyncStatus = MappingSyncStatus.PENDING,
    ) -> ExternalResourceMapping:
        mapping = db.scalar(
            select(ExternalResourceMapping).where(
                ExternalResourceMapping.merchant_id == merchant_id,
                ExternalResourceMapping.system == system,
                ExternalResourceMapping.resource_type == resource_type,
                ExternalResourceMapping.internal_id == internal_id,
            )
        )
        if mapping:
            mapping.external_id = external_id
            mapping.sync_status = sync_status
            mapping.last_synced_at = datetime.now(UTC)
        else:
            mapping = ExternalResourceMapping(
                merchant_id=merchant_id,
                system=system,
                resource_type=resource_type,
                internal_id=internal_id,
                external_id=external_id,
                sync_status=sync_status,
                last_synced_at=datetime.now(UTC),
            )
            db.add(mapping)
        logger.info(
            "integration.mapping.created",
            extra={
                "merchant_id": merchant_id,
                "system": system.value,
                "resource_type": resource_type.value,
                "internal_id": internal_id,
                "external_id": external_id,
            },
        )
        return mapping

    def enqueue(
        self,
        db: Session,
        *,
        merchant_id: int,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict,
        event_id: str | None = None,
    ) -> IntegrationOutbox:
        event = IntegrationOutbox(
            merchant_id=merchant_id,
            event_id=event_id or str(uuid.uuid4()),
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload_json=payload,
            status=IntegrationOutboxStatus.PENDING,
            attempt_count=0,
        )
        db.add(event)
        logger.info(
            "integration.event.enqueued",
            extra={
                "merchant_id": merchant_id,
                "event_id": event.event_id,
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
            },
        )
        return event

    def list_pending(self, db: Session, limit: int = 100) -> list[IntegrationOutbox]:
        return list(
            db.scalars(
                select(IntegrationOutbox)
                .where(IntegrationOutbox.status == IntegrationOutboxStatus.PENDING)
                .order_by(IntegrationOutbox.created_at.asc())
                .limit(limit)
            )
        )

    def claim(self, db: Session, event_id: str) -> IntegrationOutbox | None:
        event = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.event_id == event_id))
        if not event:
            return None
        if event.status == IntegrationOutboxStatus.PROCESSED:
            return event
        event.status = IntegrationOutboxStatus.PROCESSING
        event.attempt_count += 1
        event.last_error = None
        event.next_attempt_at = None
        logger.info(
            "integration.event.processing",
            extra={
                "merchant_id": event.merchant_id,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "attempt_count": event.attempt_count,
            },
        )
        return event

    def mark_processed(self, db: Session, event: IntegrationOutbox) -> IntegrationOutbox:
        event.status = IntegrationOutboxStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        event.last_error = None
        event.next_attempt_at = None
        logger.info(
            "integration.event.processed",
            extra={
                "merchant_id": event.merchant_id,
                "event_id": event.event_id,
                "event_type": event.event_type,
            },
        )
        return event

    def mark_failed(self, db: Session, event: IntegrationOutbox, error: str) -> IntegrationOutbox:
        event.status = IntegrationOutboxStatus.FAILED
        event.last_error = error[:1000]
        event.next_attempt_at = datetime.now(UTC) + timedelta(minutes=min(60, max(1, event.attempt_count)))
        logger.info(
            "integration.event.failed",
            extra={
                "merchant_id": event.merchant_id,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "attempt_count": event.attempt_count,
            },
        )
        return event

    def retry(self, db: Session, event_id: str) -> IntegrationOutbox | None:
        event = db.scalar(select(IntegrationOutbox).where(IntegrationOutbox.event_id == event_id))
        if not event:
            return None
        if event.status == IntegrationOutboxStatus.PROCESSED:
            return event
        event.status = IntegrationOutboxStatus.PENDING
        event.last_error = None
        event.next_attempt_at = None
        logger.info(
            "integration.event.retry",
            extra={
                "merchant_id": event.merchant_id,
                "event_id": event.event_id,
                "event_type": event.event_type,
            },
        )
        return event


class IntegrationProcessor:
    def __init__(self, event_service: IntegrationEventService | None = None, handlers: dict[str, Callable[[dict], ExternalReference | None]] | None = None) -> None:
        self.event_service = event_service or IntegrationEventService()
        self.handlers = handlers or {}

    def process_event(self, db: Session, event_id: str) -> str:
        event = self.event_service.claim(db, event_id)
        if not event:
            return "missing"
        if event.status == IntegrationOutboxStatus.PROCESSED:
            return "already_processed"

        handler = self.handlers.get(event.event_type)
        if handler is None:
            self.event_service.mark_failed(db, event, f"No handler registered for {event.event_type}")
            db.commit()
            return "failed"

        try:
            handler(event.payload_json)
        except Exception as exc:
            self.event_service.mark_failed(db, event, str(exc))
            db.commit()
            return "failed"

        self.event_service.mark_processed(db, event)
        db.commit()
        return "processed"

    def process_pending(self, db: Session, limit: int = 20) -> int:
        limit = min(limit, settings.integration_processing_batch_size)
        count = 0
        for event in self.event_service.list_pending(db, limit=limit):
            if self.process_event(db, event.event_id) == "processed":
                count += 1
        return count
