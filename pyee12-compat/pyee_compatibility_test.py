#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script to verify compatibility with pyee >= 12.0.0.
This script tests the refactored functions in helpers.py.
"""

import asyncio
from pyee.asyncio import AsyncIOEventEmitter
from pyppeteer.helpers import future_race, addEventListener, removeEventListeners, waitForEvent

async def test_future_race():
    print("Testing future_race...")
    
    # Create two coroutines with different completion times
    async def coro1():
        await asyncio.sleep(0.1)
        return "Coro1 done"
    
    async def coro2():
        await asyncio.sleep(0.2)
        return "Coro2 done"
    
    # Test with coroutines directly
    result = await future_race(coro1(), coro2())
    assert result == "Coro1 done", f"Expected 'Coro1 done' but got {result}"
    
    # Test with tasks
    task1 = asyncio.create_task(coro1())
    task2 = asyncio.create_task(coro2())
    result = await future_race(task1, task2)
    assert result == "Coro1 done", f"Expected 'Coro1 done' but got {result}"
    
    print("future_race test passed!")

async def test_event_emitter():
    print("Testing event emitter...")
    
    emitter = AsyncIOEventEmitter()
    received_events = []
    
    # Define event handler
    def handler(data):
        received_events.append(data)
    
    # Add listener and verify it works
    listener = addEventListener(emitter, "test-event", handler)
    emitter.emit("test-event", "test-data-1")
    assert received_events == ["test-data-1"], f"Expected ['test-data-1'] but got {received_events}"
    
    # Remove listener and verify it no longer receives events
    removeEventListeners([listener])
    emitter.emit("test-event", "test-data-2")
    assert received_events == ["test-data-1"], f"Expected ['test-data-1'] but got {received_events}"
    
    print("Event emitter test passed!")

async def test_wait_for_event():
    print("Testing waitForEvent...")
    
    emitter = AsyncIOEventEmitter()
    loop = asyncio.get_event_loop()
    
    # Setup a predicate that only accepts certain events
    def predicate(data):
        return data.get("accept", False)
    
    # Create a future and emit an event that should resolve it
    event_future = waitForEvent(emitter, "target-event", predicate, None, loop)
    
    # Emit an event that should NOT trigger the predicate
    emitter.emit("target-event", {"accept": False})
    
    # Schedule an event that SHOULD trigger the predicate
    async def emit_matching_event():
        await asyncio.sleep(0.1)
        emitter.emit("target-event", {"accept": True, "data": "target-data"})
    
    asyncio.create_task(emit_matching_event())
    
    # Wait for the event and verify it received the correct data
    result = await event_future
    assert result.get("data") == "target-data", f"Expected 'target-data' but got {result.get('data')}"
    
    print("waitForEvent test passed!")
    
async def test_wait_for_event_simple_predicate():
    print("Testing waitForEvent with simple predicate...")
    
    emitter = AsyncIOEventEmitter()
    loop = asyncio.get_event_loop()
    
    # Use a simple always-true predicate
    def always_true(data):
        return True
    
    # Create a future using the simple predicate
    event_future = waitForEvent(emitter, "simple-event", always_true, None, loop)
    
    # Schedule an event emission
    async def emit_event():
        await asyncio.sleep(0.1)
        emitter.emit("simple-event", {"data": "simple-predicate-data"})
    
    asyncio.create_task(emit_event())
    
    # Wait for the event and verify it received the correct data
    result = await event_future
    assert result.get("data") == "simple-predicate-data", f"Expected 'simple-predicate-data' but got {result.get('data')}"
    
    print("waitForEvent with simple predicate test passed!")

async def test_wait_for_event_timeout():
    print("Testing waitForEvent with timeout...")
    
    emitter = AsyncIOEventEmitter()
    loop = asyncio.get_event_loop()
    
    # Always accept events in this test
    def predicate(data):
        return True
    
    # Set a short timeout
    timeout_ms = 100  # 100ms timeout
    
    # Create a future with a timeout
    event_future = waitForEvent(emitter, "timeout-event", predicate, timeout_ms, loop)
    
    # Don't emit any events and let it time out
    try:
        await event_future
        assert False, "Event future should have timed out but didn't"
    except Exception as e:
        # Should get a TimeoutError
        assert "Timeout exceeded" in str(e), f"Expected timeout error but got: {e}"
    
    print("waitForEvent timeout test passed!")

async def main():
    print("Running compatibility tests for pyee >=12.0.0...")
    
    await test_future_race()
    await test_event_emitter()
    await test_wait_for_event()
    await test_wait_for_event_simple_predicate()
    await test_wait_for_event_timeout()
    
    print("All tests passed! The code should now be compatible with pyee >=12.0.0")

if __name__ == "__main__":
    asyncio.run(main())