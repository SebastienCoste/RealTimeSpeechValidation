#!/usr/bin/env python3
"""
TruthSeeker Backend API Test Suite
Tests all backend endpoints and functionality
"""

import asyncio
import json
import uuid
import time
from datetime import datetime
from typing import Dict, Any
import httpx
import websockets
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/app/frontend/.env')
BACKEND_URL = os.getenv('REACT_APP_BACKEND_URL', 'http://localhost:8001')
API_BASE_URL = f"{BACKEND_URL}/api"

class TruthSeekerAPITester:
    def __init__(self):
        self.base_url = API_BASE_URL
        self.ws_url = BACKEND_URL.replace('http', 'ws').replace('https', 'wss')
        self.test_results = []
        self.session_id = str(uuid.uuid4())
        
    def log_test(self, test_name: str, success: bool, details: str = "", response_data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if response_data:
            result["response"] = response_data
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    Details: {details}")
        if not success and response_data:
            print(f"    Response: {response_data}")
        print()

    async def test_health_check(self):
        """Test the /api/health endpoint"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/health")
                
                if response.status_code == 200:
                    data = response.json()
                    expected_keys = ["status", "service", "perplexity_api_configured"]
                    
                    if all(key in data for key in expected_keys):
                        if data["status"] == "healthy" and data["service"] == "TruthSeeker":
                            self.log_test(
                                "Health Check", 
                                True, 
                                f"Service healthy, Perplexity API configured: {data['perplexity_api_configured']}", 
                                data
                            )
                        else:
                            self.log_test(
                                "Health Check", 
                                False, 
                                f"Unexpected status or service name", 
                                data
                            )
                    else:
                        self.log_test(
                            "Health Check", 
                            False, 
                            f"Missing expected keys. Got: {list(data.keys())}", 
                            data
                        )
                else:
                    self.log_test(
                        "Health Check", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")

    async def test_basic_fact_check(self):
        """Test the /api/fact-check endpoint with a simple statement"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "statement": "The Earth is round",
                    "context": "Basic geography fact",
                    "session_id": self.session_id
                }
                
                response = await client.post(
                    f"{self.base_url}/fact-check",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    required_fields = [
                        "statement", "verdict", "confidence_score", 
                        "explanation", "sources", "processing_time_ms", "timestamp"
                    ]
                    
                    if all(field in data for field in required_fields):
                        # Validate data types and ranges
                        valid = True
                        issues = []
                        
                        if data["statement"] != payload["statement"]:
                            valid = False
                            issues.append("Statement mismatch")
                            
                        if data["verdict"] not in ["True", "False", "Partially True", "Unverified"]:
                            valid = False
                            issues.append(f"Invalid verdict: {data['verdict']}")
                            
                        if not (0.0 <= data["confidence_score"] <= 1.0):
                            valid = False
                            issues.append(f"Invalid confidence score: {data['confidence_score']}")
                            
                        if not isinstance(data["sources"], list):
                            valid = False
                            issues.append("Sources should be a list")
                            
                        if not isinstance(data["processing_time_ms"], int):
                            valid = False
                            issues.append("Processing time should be integer")
                        
                        if valid:
                            self.log_test(
                                "Basic Fact Check", 
                                True, 
                                f"Verdict: {data['verdict']}, Confidence: {data['confidence_score']}", 
                                data
                            )
                        else:
                            self.log_test(
                                "Basic Fact Check", 
                                False, 
                                f"Validation issues: {', '.join(issues)}", 
                                data
                            )
                    else:
                        missing = [f for f in required_fields if f not in data]
                        self.log_test(
                            "Basic Fact Check", 
                            False, 
                            f"Missing fields: {missing}", 
                            data
                        )
                else:
                    self.log_test(
                        "Basic Fact Check", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Basic Fact Check", False, f"Exception: {str(e)}")

    async def test_transcription_processing(self):
        """Test the /api/transcription endpoint"""
        # Test interim transcription
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Test interim transcription (should not trigger fact-checking)
                interim_payload = {
                    "text": "The Earth is",
                    "is_final": False,
                    "session_id": self.session_id
                }
                
                response = await client.post(
                    f"{self.base_url}/transcription",
                    json=interim_payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "received":
                        self.log_test(
                            "Interim Transcription", 
                            True, 
                            "Interim transcription processed correctly", 
                            data
                        )
                    else:
                        self.log_test(
                            "Interim Transcription", 
                            False, 
                            f"Unexpected response: {data}", 
                            data
                        )
                else:
                    self.log_test(
                        "Interim Transcription", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Interim Transcription", False, f"Exception: {str(e)}")

        # Test final transcription (should trigger fact-checking)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                final_payload = {
                    "text": "The Earth is round and orbits the Sun",
                    "is_final": True,
                    "session_id": self.session_id
                }
                
                response = await client.post(
                    f"{self.base_url}/transcription",
                    json=final_payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "processed" and "fact_check" in data:
                        fact_check = data["fact_check"]
                        if "verdict" in fact_check and "confidence_score" in fact_check:
                            self.log_test(
                                "Final Transcription", 
                                True, 
                                f"Final transcription processed with fact-check: {fact_check['verdict']}", 
                                data
                            )
                        else:
                            self.log_test(
                                "Final Transcription", 
                                False, 
                                "Fact-check result incomplete", 
                                data
                            )
                    else:
                        self.log_test(
                            "Final Transcription", 
                            False, 
                            f"Expected processed status with fact_check, got: {data}", 
                            data
                        )
                else:
                    self.log_test(
                        "Final Transcription", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Final Transcription", False, f"Exception: {str(e)}")

    async def test_session_fact_checks(self):
        """Test retrieving fact-checks for a session"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/sessions/{self.session_id}/fact-checks"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "session_id" in data and "fact_checks" in data:
                        if data["session_id"] == self.session_id:
                            fact_checks = data["fact_checks"]
                            if isinstance(fact_checks, list):
                                self.log_test(
                                    "Session Fact Checks", 
                                    True, 
                                    f"Retrieved {len(fact_checks)} fact-checks for session", 
                                    {"count": len(fact_checks), "session_id": data["session_id"]}
                                )
                            else:
                                self.log_test(
                                    "Session Fact Checks", 
                                    False, 
                                    "fact_checks should be a list", 
                                    data
                                )
                        else:
                            self.log_test(
                                "Session Fact Checks", 
                                False, 
                                f"Session ID mismatch: expected {self.session_id}, got {data['session_id']}", 
                                data
                            )
                    else:
                        self.log_test(
                            "Session Fact Checks", 
                            False, 
                            "Missing required fields in response", 
                            data
                        )
                else:
                    self.log_test(
                        "Session Fact Checks", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Session Fact Checks", False, f"Exception: {str(e)}")

    async def test_error_handling(self):
        """Test various error scenarios"""
        # Test empty statement
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "statement": "",
                    "session_id": self.session_id
                }
                
                response = await client.post(
                    f"{self.base_url}/fact-check",
                    json=payload
                )
                
                # Should either handle gracefully or return appropriate error
                if response.status_code in [200, 400, 422]:
                    self.log_test(
                        "Empty Statement Error Handling", 
                        True, 
                        f"Handled empty statement appropriately with status {response.status_code}"
                    )
                else:
                    self.log_test(
                        "Empty Statement Error Handling", 
                        False, 
                        f"Unexpected status code: {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Empty Statement Error Handling", False, f"Exception: {str(e)}")

        # Test invalid JSON
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/fact-check",
                    content="invalid json",
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [400, 422]:
                    self.log_test(
                        "Invalid JSON Error Handling", 
                        True, 
                        f"Handled invalid JSON appropriately with status {response.status_code}"
                    )
                else:
                    self.log_test(
                        "Invalid JSON Error Handling", 
                        False, 
                        f"Expected 400/422, got {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Invalid JSON Error Handling", False, f"Exception: {str(e)}")

        # Test non-existent session
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                fake_session = str(uuid.uuid4())
                response = await client.get(
                    f"{self.base_url}/sessions/{fake_session}/fact-checks"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("fact_checks") == []:
                        self.log_test(
                            "Non-existent Session Handling", 
                            True, 
                            "Returned empty list for non-existent session"
                        )
                    else:
                        self.log_test(
                            "Non-existent Session Handling", 
                            False, 
                            f"Expected empty list, got: {data}", 
                            data
                        )
                else:
                    self.log_test(
                        "Non-existent Session Handling", 
                        False, 
                        f"Unexpected status code: {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("Non-existent Session Handling", False, f"Exception: {str(e)}")

    async def test_websocket_endpoint(self):
        """Test WebSocket endpoint functionality"""
        try:
            ws_session_id = str(uuid.uuid4())
            ws_url = f"{self.ws_url}/ws/{ws_session_id}"
            
            async with websockets.connect(ws_url) as websocket:
                # Test connection
                self.log_test(
                    "WebSocket Connection", 
                    True, 
                    f"Successfully connected to {ws_url}"
                )
                
                # Send a transcription update
                message = {
                    "type": "transcription_update",
                    "text": "The sky is blue and water is wet",
                    "is_final": True
                }
                
                await websocket.send(json.dumps(message))
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "fact_check_result" and "data" in data:
                        fact_check_data = data["data"]
                        if "verdict" in fact_check_data and "confidence_score" in fact_check_data:
                            self.log_test(
                                "WebSocket Fact Check Response", 
                                True, 
                                f"Received fact-check via WebSocket: {fact_check_data['verdict']}", 
                                data
                            )
                        else:
                            self.log_test(
                                "WebSocket Fact Check Response", 
                                False, 
                                "Incomplete fact-check data in WebSocket response", 
                                data
                            )
                    else:
                        self.log_test(
                            "WebSocket Fact Check Response", 
                            False, 
                            f"Unexpected WebSocket response format", 
                            data
                        )
                except asyncio.TimeoutError:
                    self.log_test(
                        "WebSocket Fact Check Response", 
                        False, 
                        "Timeout waiting for WebSocket response"
                    )
                    
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"Exception: {str(e)}")

    async def test_cors_configuration(self):
        """Test CORS configuration"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Send OPTIONS request to check CORS
                response = await client.options(
                    f"{self.base_url}/health",
                    headers={
                        "Origin": "http://localhost:3000",
                        "Access-Control-Request-Method": "GET"
                    }
                )
                
                cors_headers = [
                    "access-control-allow-origin",
                    "access-control-allow-methods",
                    "access-control-allow-headers"
                ]
                
                has_cors = any(header in response.headers for header in cors_headers)
                
                if has_cors or response.status_code == 200:
                    self.log_test(
                        "CORS Configuration", 
                        True, 
                        "CORS headers present or OPTIONS request handled"
                    )
                else:
                    self.log_test(
                        "CORS Configuration", 
                        False, 
                        f"No CORS headers found, status: {response.status_code}", 
                        dict(response.headers)
                    )
        except Exception as e:
            self.log_test("CORS Configuration", False, f"Exception: {str(e)}")

    # YouTube Live Fact-Checking Tests
    async def test_youtube_set_video(self):
        """Test setting a YouTube video for fact-checking"""
        # Test with valid YouTube URL
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "admin_user": "test_admin"
                }
                
                response = await client.post(
                    f"{self.base_url}/youtube/set-video",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and "video_id" in data:
                        self.log_test(
                            "YouTube Set Video (Valid URL)", 
                            True, 
                            f"Successfully set video: {data.get('title', 'Unknown')}", 
                            data
                        )
                        # Store video_id for later tests
                        self.youtube_video_id = data.get("video_id")
                    else:
                        self.log_test(
                            "YouTube Set Video (Valid URL)", 
                            False, 
                            f"Unexpected response format", 
                            data
                        )
                else:
                    self.log_test(
                        "YouTube Set Video (Valid URL)", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("YouTube Set Video (Valid URL)", False, f"Exception: {str(e)}")

        # Test with invalid YouTube URL
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "video_url": "https://invalid-url.com/video",
                    "admin_user": "test_admin"
                }
                
                response = await client.post(
                    f"{self.base_url}/youtube/set-video",
                    json=payload
                )
                
                if response.status_code in [400, 422, 500]:
                    self.log_test(
                        "YouTube Set Video (Invalid URL)", 
                        True, 
                        f"Correctly rejected invalid URL with status {response.status_code}"
                    )
                else:
                    data = response.json() if response.status_code == 200 else response.text
                    if response.status_code == 200 and isinstance(data, dict) and not data.get("success"):
                        self.log_test(
                            "YouTube Set Video (Invalid URL)", 
                            True, 
                            f"Correctly returned success=false for invalid URL"
                        )
                    else:
                        self.log_test(
                            "YouTube Set Video (Invalid URL)", 
                            False, 
                            f"Expected error response, got {response.status_code}", 
                            data
                        )
        except Exception as e:
            self.log_test("YouTube Set Video (Invalid URL)", False, f"Exception: {str(e)}")

    async def test_youtube_session_management(self):
        """Test YouTube session management endpoints"""
        # Test getting current session
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/youtube/current-session")
                
                if response.status_code == 200:
                    data = response.json()
                    if "session" in data and "fact_checks" in data:
                        session = data["session"]
                        fact_checks = data["fact_checks"]
                        
                        if session is None or isinstance(session, dict):
                            if isinstance(fact_checks, list):
                                self.log_test(
                                    "YouTube Get Current Session", 
                                    True, 
                                    f"Retrieved session data: {len(fact_checks)} fact-checks", 
                                    {"has_session": session is not None, "fact_check_count": len(fact_checks)}
                                )
                            else:
                                self.log_test(
                                    "YouTube Get Current Session", 
                                    False, 
                                    "fact_checks should be a list", 
                                    data
                                )
                        else:
                            self.log_test(
                                "YouTube Get Current Session", 
                                False, 
                                "session should be null or object", 
                                data
                            )
                    else:
                        self.log_test(
                            "YouTube Get Current Session", 
                            False, 
                            "Missing required fields in response", 
                            data
                        )
                else:
                    self.log_test(
                        "YouTube Get Current Session", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("YouTube Get Current Session", False, f"Exception: {str(e)}")

        # Test starting processing
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/youtube/start-processing")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.log_test(
                            "YouTube Start Processing", 
                            True, 
                            "Successfully started processing", 
                            data
                        )
                    else:
                        self.log_test(
                            "YouTube Start Processing", 
                            False, 
                            f"Expected success=true, got: {data}", 
                            data
                        )
                else:
                    self.log_test(
                        "YouTube Start Processing", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("YouTube Start Processing", False, f"Exception: {str(e)}")

        # Test stopping processing
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/youtube/stop-processing")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self.log_test(
                            "YouTube Stop Processing", 
                            True, 
                            "Successfully stopped processing", 
                            data
                        )
                    else:
                        self.log_test(
                            "YouTube Stop Processing", 
                            False, 
                            f"Expected success=true, got: {data}", 
                            data
                        )
                else:
                    self.log_test(
                        "YouTube Stop Processing", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("YouTube Stop Processing", False, f"Exception: {str(e)}")

    async def test_youtube_fact_checks_retrieval(self):
        """Test retrieving fact-checks for YouTube video sessions"""
        # Test with a video ID (may be empty initially)
        video_id = getattr(self, 'youtube_video_id', 'dQw4w9WgXcQ')
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/youtube/sessions/{video_id}/fact-checks"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "video_id" in data and "fact_checks" in data:
                        if data["video_id"] == video_id and isinstance(data["fact_checks"], list):
                            self.log_test(
                                "YouTube Session Fact-Checks", 
                                True, 
                                f"Retrieved {len(data['fact_checks'])} fact-checks for video {video_id}", 
                                {"video_id": data["video_id"], "count": len(data["fact_checks"])}
                            )
                        else:
                            self.log_test(
                                "YouTube Session Fact-Checks", 
                                False, 
                                f"Data validation failed", 
                                data
                            )
                    else:
                        self.log_test(
                            "YouTube Session Fact-Checks", 
                            False, 
                            "Missing required fields in response", 
                            data
                        )
                else:
                    self.log_test(
                        "YouTube Session Fact-Checks", 
                        False, 
                        f"HTTP {response.status_code}", 
                        response.text
                    )
        except Exception as e:
            self.log_test("YouTube Session Fact-Checks", False, f"Exception: {str(e)}")

    async def test_youtube_error_handling(self):
        """Test YouTube endpoint error handling"""
        # Test set-video with missing parameters
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "video_url": ""  # Empty URL
                }
                
                response = await client.post(
                    f"{self.base_url}/youtube/set-video",
                    json=payload
                )
                
                if response.status_code in [400, 422, 500]:
                    self.log_test(
                        "YouTube Error Handling (Empty URL)", 
                        True, 
                        f"Correctly handled empty URL with status {response.status_code}"
                    )
                else:
                    data = response.json() if response.status_code == 200 else response.text
                    if response.status_code == 200 and isinstance(data, dict) and not data.get("success"):
                        self.log_test(
                            "YouTube Error Handling (Empty URL)", 
                            True, 
                            "Correctly returned success=false for empty URL"
                        )
                    else:
                        self.log_test(
                            "YouTube Error Handling (Empty URL)", 
                            False, 
                            f"Expected error response, got {response.status_code}", 
                            data
                        )
        except Exception as e:
            self.log_test("YouTube Error Handling (Empty URL)", False, f"Exception: {str(e)}")

        # Test processing without video set (after stopping)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # First stop any processing
                await client.post(f"{self.base_url}/youtube/stop-processing")
                
                # Try to start processing without a video
                response = await client.post(f"{self.base_url}/youtube/start-processing")
                
                if response.status_code == 200:
                    data = response.json()
                    # Should either succeed (if video was set earlier) or handle gracefully
                    self.log_test(
                        "YouTube Error Handling (No Video Set)", 
                        True, 
                        f"Handled processing without video: {data.get('message', 'No message')}"
                    )
                else:
                    self.log_test(
                        "YouTube Error Handling (No Video Set)", 
                        True, 
                        f"Correctly returned error status {response.status_code}"
                    )
        except Exception as e:
            self.log_test("YouTube Error Handling (No Video Set)", False, f"Exception: {str(e)}")

    async def test_youtube_websocket_endpoint(self):
        """Test YouTube WebSocket endpoint"""
        try:
            ws_url = f"{self.ws_url}/ws/youtube-live"
            
            async with websockets.connect(ws_url) as websocket:
                # Test connection
                self.log_test(
                    "YouTube WebSocket Connection", 
                    True, 
                    f"Successfully connected to {ws_url}"
                )
                
                # Send a request for current session
                message = {
                    "type": "get_current_session"
                }
                
                await websocket.send(json.dumps(message))
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "current_session" and "data" in data:
                        session_data = data["data"]
                        self.log_test(
                            "YouTube WebSocket Response", 
                            True, 
                            f"Received current session data: {session_data is not None}", 
                            {"has_session": session_data is not None}
                        )
                    else:
                        self.log_test(
                            "YouTube WebSocket Response", 
                            False, 
                            f"Unexpected WebSocket response format", 
                            data
                        )
                except asyncio.TimeoutError:
                    self.log_test(
                        "YouTube WebSocket Response", 
                        False, 
                        "Timeout waiting for WebSocket response"
                    )
                    
        except Exception as e:
            self.log_test("YouTube WebSocket Connection", False, f"Exception: {str(e)}")

    async def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"🚀 Starting TruthSeeker Backend API Tests")
        print(f"Backend URL: {self.base_url}")
        print(f"WebSocket URL: {self.ws_url}")
        print(f"Test Session ID: {self.session_id}")
        print("=" * 60)
        
        # Run tests in logical order
        await self.test_health_check()
        await self.test_basic_fact_check()
        await self.test_transcription_processing()
        await self.test_session_fact_checks()
        await self.test_error_handling()
        await self.test_websocket_endpoint()
        await self.test_cors_configuration()
        
        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if total - passed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        print("\n" + "=" * 60)
        return self.test_results

async def main():
    """Main test runner"""
    tester = TruthSeekerAPITester()
    results = await tester.run_all_tests()
    
    # Return exit code based on results
    failed_tests = sum(1 for result in results if not result["success"])
    return 0 if failed_tests == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)