"""NATS client connection management."""
import logging
from typing import Optional

import nats
from nats.aio.client import Client as NatsClient
from nats.js import JetStreamContext

from app.config import settings

logger = logging.getLogger(__name__)


class NatsConnection:
    """NATS connection manager."""

    def __init__(self, url: str = settings.nats_url):
        self._url = url
        self._client: Optional[NatsClient] = None
        self._jetstream: Optional[JetStreamContext] = None

    async def connect(self) -> None:
        """Connect to NATS server."""
        if self._client is not None:
            return

        try:
            self._client = await nats.connect(self._url)
            self._jetstream = self._client.jetstream()
            logger.info(f"Connected to NATS at {self._url}")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from NATS server."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._jetstream = None
            logger.info("Disconnected from NATS")

    @property
    def client(self) -> NatsClient:
        """Get NATS client."""
        if self._client is None:
            raise RuntimeError("NATS client not connected")
        return self._client

    @property
    def jetstream(self) -> JetStreamContext:
        """Get JetStream context."""
        if self._jetstream is None:
            raise RuntimeError("JetStream not initialized")
        return self._jetstream

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._client is not None and self._client.is_connected


# Global NATS connection instance
_nats_connection: Optional[NatsConnection] = None


async def get_nats_client() -> NatsConnection:
    """Get or create NATS connection."""
    global _nats_connection
    if _nats_connection is None:
        _nats_connection = NatsConnection()
        await _nats_connection.connect()
    return _nats_connection


async def close_nats_client() -> None:
    """Close NATS connection."""
    global _nats_connection
    if _nats_connection is not None:
        await _nats_connection.disconnect()
        _nats_connection = None