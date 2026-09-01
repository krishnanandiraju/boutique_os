from __future__ import annotations

from datetime import datetime
from typing import Any

from app.integrations.dto import ExternalReference
from app.schemas import AppSchema
from app.models import ChannelConnectionStatus, CommerceChannelType, ExternalResourceType, IntegrationOutboxStatus, MappingSyncStatus


class ChannelConnectionRead(AppSchema):
    id: int
    merchant_id: int
    channel_type: CommerceChannelType
    status: ChannelConnectionStatus
    external_account_id: str | None = None
    configuration_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class ExternalResourceMappingRead(AppSchema):
    id: int
    merchant_id: int
    system: CommerceChannelType
    resource_type: ExternalResourceType
    internal_id: int
    external_id: str
    sync_status: MappingSyncStatus
    last_synced_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationOutboxRead(AppSchema):
    id: int
    event_id: str
    merchant_id: int
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload_json: dict[str, Any]
    status: IntegrationOutboxStatus
    attempt_count: int
    last_error: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    next_attempt_at: datetime | None = None


class IntegrationOutboxDetailRead(IntegrationOutboxRead):
    external_reference: ExternalReference | None = None
