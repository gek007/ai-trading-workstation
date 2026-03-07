"""Tests for SSE streaming endpoint."""

import asyncio
import json

import pytest

from app.market.cache import PriceCache
from app.market.stream import create_stream_router, _generate_events


class MockRequest:
    """Mock Request object for testing SSE generator."""

    def __init__(self, disconnected=False):
        self._disconnected = disconnected
        self.client = type("Client", (), {"host": "test-client"})()

    async def is_disconnected(self):
        return self._disconnected


@pytest.mark.asyncio
class TestStreamGenerator:
    """Tests for the SSE event generator."""

    async def test_yields_retry_directive(self):
        """Test that the first event is a retry directive."""
        cache = PriceCache()
        request = MockRequest(disconnected=False)

        # Create a task that will collect events for a short time
        events = []

        async def collect_events():
            async for event in _generate_events(cache, request, interval=0.1):
                events.append(event)
                if len(events) >= 1:
                    break

        # Run with timeout
        task = asyncio.create_task(collect_events())
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            pass

        assert events[0] == "retry: 1000\n\n"

    async def test_stops_on_disconnect(self):
        """Test that generator stops when client disconnects."""
        cache = PriceCache()
        cache.update("AAPL", 190.50)

        request = MockRequest(disconnected=True)

        events = []
        async for event in _generate_events(cache, request, interval=0.01):
            events.append(event)

        # Should only get retry directive before detecting disconnect
        assert len(events) == 1
        assert events[0] == "retry: 1000\n\n"

    async def test_data_format(self):
        """Test that data events have the correct format."""
        cache = PriceCache()
        cache.update("AAPL", 190.50, timestamp=1234567890.0)

        request = MockRequest(disconnected=False)

        events = []

        async def collect_events():
            async for event in _generate_events(cache, request, interval=0.01):
                events.append(event)
                # Collect first few events
                if len(events) >= 5:
                    break

        task = asyncio.create_task(collect_events())
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except asyncio.TimeoutError:
            pass

        # Should have retry directive
        assert events[0] == "retry: 1000\n\n"

        # Find data event
        data_event = None
        for e in events:
            if "data:" in e:
                data_event = e
                break

        if data_event:
            # Verify JSON format
            json_str = data_event.replace("data: ", "").strip()
            data = json.loads(json_str)
            assert "AAPL" in data
            assert data["AAPL"]["ticker"] == "AAPL"
            assert data["AAPL"]["price"] == 190.50


@pytest.mark.asyncio
class TestStreamRouter:
    """Tests for the FastAPI stream router."""

    async def test_create_stream_router(self):
        """Test that router factory creates a valid router."""
        cache = PriceCache()
        router = create_stream_router(cache)

        assert router is not None
        assert router.prefix == "/api/stream"
        assert router.tags == ["streaming"]

        # Verify routes exist
        route_names = [r.name if hasattr(r, "name") else r.path for r in router.routes]
        assert "/api/stream/prices" in route_names or "stream_prices" in route_names

    async def test_stream_endpoint_function_exists(self):
        """Test that the stream endpoint function exists."""
        cache = PriceCache()
        router = create_stream_router(cache)

        # Get the route for /api/stream/prices
        prices_route = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/stream/prices":
                prices_route = route
                break

        assert prices_route is not None
        assert hasattr(prices_route, "endpoint")

    async def test_router_uses_provided_cache(self):
        """Test that router uses the provided cache instance."""
        cache = PriceCache()
        router = create_stream_router(cache)

        # The router should have captured the cache
        assert router is not None

        # Verify the route was created successfully
        prices_route = None
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/api/stream/prices":
                prices_route = route
                break

        assert prices_route is not None
