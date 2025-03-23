#!/usr/bin/env python3
"""
Connection stress test to verify our high CPU fix under various conditions.
This test puts the connection through high load, errors, and disconnections.
"""
import asyncio
import logging
import os
import random
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# WebSocket URL
WEBSOCKET_URL = "ws://127.0.0.1:3000"

# Global variables
command_counter = 0

async def send_cdp_commands(connection, count=50, interval=0.05):
    """Send multiple CDP commands to stress test the connection."""
    global command_counter
    
    logger.info(f"Sending {count} CDP commands with {interval}s interval")
    responses = []
    
    methods = [
        'Browser.getVersion',
        'Target.getTargets',
        'SystemInfo.getInfo',
        'Performance.getMetrics',
        'Browser.getBrowserCommandLine',
        'Network.enable',
        'Target.setDiscoverTargets',
        'Network.setCacheDisabled',
        'Emulation.setDeviceMetricsOverride',
        'Browser.getWindowBounds',
        # Add method that won't exist
        'NonExistent.method'
    ]
    
    for i in range(count):
        method = random.choice(methods)
        command_id = command_counter
        command_counter += 1
        
        params = {'id': command_id}
        if method == 'Emulation.setDeviceMetricsOverride':
            params.update({
                'width': 1280,
                'height': 720,
                'deviceScaleFactor': 1,
                'mobile': False
            })
        elif method == 'Target.setDiscoverTargets':
            params.update({'discover': True})
        elif method == 'Network.setCacheDisabled':
            params.update({'cacheDisabled': True})
            
        logger.info(f"Sending command {i+1}/{count}: {method}")
        future = connection.send(method, params)
        
        try:
            # Add the future to our list
            responses.append((method, future))
        except Exception as e:
            logger.error(f"Error scheduling command {method}: {e}")
            
        # Sleep a bit between commands
        await asyncio.sleep(interval)
    
    # Wait for all responses
    logger.info("Waiting for all responses...")
    results = []
    
    for method, future in responses:
        try:
            result = await asyncio.wait_for(future, timeout=5.0)
            results.append((method, result))
            logger.info(f"Command {method} completed: {result}")
        except asyncio.TimeoutError:
            logger.warning(f"Command {method} timed out")
        except Exception as e:
            logger.info(f"Command {method} failed (expected for some): {e}")
    
    return results

async def monitor_cpu(pid, duration=10):
    """Monitor CPU usage and log results."""
    logger.info(f"Monitoring CPU usage for process {pid} for {duration} seconds")
    start_time = time.time()
    readings = []
    
    while time.time() - start_time < duration:
        try:
            cmd = f"ps -p {pid} -o %cpu | tail -n 1"
            result = subprocess.check_output(cmd, shell=True).decode().strip()
            cpu = float(result)
            readings.append(cpu)
            logger.info(f"CPU usage: {cpu}%")
            
            if cpu > 80:
                logger.error(f"HIGH CPU DETECTED: {cpu}%")
            
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Error monitoring CPU: {e}")
    
    # Calculate statistics
    if readings:
        avg_cpu = sum(readings) / len(readings)
        max_cpu = max(readings)
        min_cpu = min(readings)
        logger.info(f"CPU statistics: Min={min_cpu:.1f}%, Avg={avg_cpu:.1f}%, Max={max_cpu:.1f}%")
        
        return {
            'min': min_cpu,
            'avg': avg_cpu,
            'max': max_cpu,
            'readings': readings
        }
    else:
        return {'min': 0, 'avg': 0, 'max': 0, 'readings': []}

def cpu_background_monitor(pid, event):
    """Background thread to monitor CPU usage until event is set."""
    readings = []
    
    while not event.is_set():
        try:
            cmd = f"ps -p {pid} -o %cpu | tail -n 1"
            result = subprocess.check_output(cmd, shell=True).decode().strip()
            cpu = float(result)
            readings.append(cpu)
            print(f"{time.time():.1f} - Background CPU: {cpu}%")
            
            if cpu > 80:
                print(f"WARNING: High CPU detected: {cpu}%")
                
            time.sleep(0.5)
        except Exception as e:
            print(f"Error in background monitor: {e}")
    
    # Calculate statistics
    if readings:
        avg_cpu = sum(readings) / len(readings)
        max_cpu = max(readings)
        min_cpu = min(readings)
        print(f"Background CPU statistics: Min={min_cpu:.1f}%, Avg={avg_cpu:.1f}%, Max={max_cpu:.1f}%")

async def run_connection_stress_test():
    """Run a comprehensive connection stress test."""
    from pyppeteer.connection import Connection
    from pyppeteer.websocket_transport import WebsocketTransport
    
    # Start CPU monitoring in a background thread
    pid = os.getpid()
    stop_monitor = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(cpu_background_monitor, pid, stop_monitor)
    
    try:
        logger.info("=== TEST 1: Normal Operation ===")
        # Connect to the browser
        logger.info(f"Connecting to {WEBSOCKET_URL}")
        transport = await WebsocketTransport.create(WEBSOCKET_URL)
        connection = Connection(WEBSOCKET_URL, transport)
        logger.info("Connection established")
        
        # Test normal operation with multiple commands
        await send_cdp_commands(connection, count=20, interval=0.1)
        
        # Monitor CPU during normal operation
        cpu_normal = await monitor_cpu(pid, duration=5)
        
        logger.info("\n=== TEST 2: High Load ===")
        # Send many commands in rapid succession
        await send_cdp_commands(connection, count=50, interval=0.01)
        
        # Monitor CPU during high load
        cpu_high_load = await monitor_cpu(pid, duration=5)
        
        logger.info("\n=== TEST 3: Error Conditions ===")
        # Send invalid commands
        for i in range(10):
            method = f"Invalid.method{i}"
            logger.info(f"Sending invalid command: {method}")
            future = connection.send(method, {})
            try:
                await asyncio.wait_for(future, timeout=1.0)
            except Exception as e:
                logger.info(f"Got expected error: {e}")
        
        # Monitor CPU after errors
        cpu_errors = await monitor_cpu(pid, duration=5)
        
        logger.info("\n=== TEST 4: Connection Close ===")
        # Close the connection
        logger.info("Closing connection...")
        await connection.dispose()
        logger.info("Connection closed")
        
        # Monitor CPU after close
        cpu_after_close = await monitor_cpu(pid, duration=10)
        
        # Evaluate results
        all_stats = {
            'normal': cpu_normal,
            'high_load': cpu_high_load,
            'errors': cpu_errors,
            'after_close': cpu_after_close
        }
        
        # Check for high CPU issues
        logger.info("\n=== TEST RESULTS ===")
        
        high_cpu_detected = False
        for phase, stats in all_stats.items():
            if stats['max'] > 80:
                logger.error(f"HIGH CPU detected during {phase} phase: {stats['max']:.1f}%")
                high_cpu_detected = True
            
            logger.info(f"{phase} phase: Min={stats['min']:.1f}%, Avg={stats['avg']:.1f}%, Max={stats['max']:.1f}%")
        
        # Check if CPU decreases after close
        if cpu_after_close['readings']:
            first_reading = cpu_after_close['readings'][0]
            last_reading = cpu_after_close['readings'][-1]
            
            if last_reading > first_reading:
                logger.error(f"CPU increased after close: {first_reading:.1f}% -> {last_reading:.1f}%")
                high_cpu_detected = True
            else:
                logger.info(f"CPU decreased after close: {first_reading:.1f}% -> {last_reading:.1f}%")
        
        if high_cpu_detected:
            logger.error("\n❌ HIGH CPU ISSUE DETECTED! Fix may not be working.")
            return False
        else:
            logger.info("\n✅ NO HIGH CPU ISSUES DETECTED! Fix is working correctly.")
            return True
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False
    finally:
        # Stop the background CPU monitor
        stop_monitor.set()

def main():
    """Main entry point."""
    logger.info("Starting connection stress test...")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(run_connection_stress_test())
        return 0 if success else 1
    finally:
        loop.close()

if __name__ == "__main__":
    sys.exit(main())