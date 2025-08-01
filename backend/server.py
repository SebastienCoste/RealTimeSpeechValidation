from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import json
import time
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import httpx
from openai import AsyncOpenAI

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="TruthSeeker API", description="Real-time fact-checking API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Pydantic models
class FactCheckRequest(BaseModel):
    statement: str = Field(..., description="Statement to fact-check")
    context: Optional[str] = Field(None, description="Additional context")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")

class SourceCitation(BaseModel):
    title: str
    url: str
    publish_date: Optional[str] = None
    domain: str

class FactCheckResult(BaseModel):
    statement: str
    verdict: str = Field(..., description="True, False, Partially True, or Unverified")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    sources: List[SourceCitation]
    processing_time_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class TranscriptionUpdate(BaseModel):
    text: str
    is_final: bool
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Perplexity Fact Checker
class PerplexityFactChecker:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self.client = None
        if self.api_key:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.perplexity.ai"
            )
        self.rate_limit_delay = 1.0
        self.last_request_time = 0

    async def _rate_limit(self):
        """Implement basic rate limiting"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = asyncio.get_event_loop().time()

    async def fact_check_statement(self, statement: str, context: str = None) -> FactCheckResult:
        """Fact-check a single statement using Perplexity API or mock response"""
        start_time = time.time()
        
        # If no API key, return mock response
        if not self.client:
            return await self._mock_fact_check(statement)
        
        await self._rate_limit()
        
        prompt = self._construct_fact_check_prompt(statement, context)
        
        try:
            response = await self.client.chat.completions.create(
                model="sonar-pro",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Fact-check this statement: {statement}"}
                ],
                temperature=0.1,
                max_tokens=1000,
                extra_body={
                    "search_mode": "web",
                    "search_recency_filter": "month",
                    "return_related_questions": False
                }
            )
            
            content = response.choices[0].message.content
            search_results = getattr(response, 'search_results', [])
            
            sources = self._process_search_results(search_results)
            verdict, confidence, explanation = self._analyze_response(content, statement)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return FactCheckResult(
                statement=statement,
                verdict=verdict,
                confidence_score=confidence,
                explanation=explanation,
                sources=sources,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error fact-checking statement: {e}")
            return await self._mock_fact_check(statement, error=True)

    async def _mock_fact_check(self, statement: str, error: bool = False) -> FactCheckResult:
        """Mock fact-checking for when API key is not available"""
        await asyncio.sleep(0.5)  # Simulate processing time
        
        if error:
            verdict = "Unverified"
            confidence = 0.3
            explanation = "Unable to verify due to API error. Please check your Perplexity API key configuration."
        else:
            # Simple mock logic based on keywords
            statement_lower = statement.lower()
            if any(word in statement_lower for word in ['earth', 'sun', 'gravity', 'water', 'sky']):
                verdict = "True"
                confidence = 0.9
                explanation = f"Mock verification: The statement '{statement}' appears to contain factual information based on basic scientific knowledge."
            elif any(word in statement_lower for word in ['flat earth', 'fake moon', 'chemtrails']):
                verdict = "False"
                confidence = 0.95
                explanation = f"Mock verification: The statement '{statement}' contains claims that contradict established scientific evidence."
            else:
                verdict = "Partially True"
                confidence = 0.7
                explanation = f"Mock verification: The statement '{statement}' requires further investigation. Add your Perplexity API key for real fact-checking."
        
        mock_sources = [
            SourceCitation(
                title="Mock Source - Add Perplexity API Key",
                url="https://perplexity.ai",
                domain="perplexity.ai"
            )
        ]
        
        return FactCheckResult(
            statement=statement,
            verdict=verdict,
            confidence_score=confidence,
            explanation=explanation,
            sources=mock_sources,
            processing_time_ms=500
        )

    def _construct_fact_check_prompt(self, statement: str, context: str = None) -> str:
        """Create a comprehensive fact-checking prompt"""
        prompt = """You are an expert fact-checker. Your task is to verify the accuracy of statements using current, reliable sources. 

For each statement:
1. Search for recent, authoritative sources
2. Analyze the claim's accuracy based on available evidence
3. Provide a clear verdict: True, False, Partially True, or Unverified
4. Explain your reasoning with specific references to sources
5. Consider the statement's context and any nuances

Be precise, objective, and transparent about limitations in available information."""
        
        if context:
            prompt += f"\n\nContext: {context}"
        
        return prompt

    def _process_search_results(self, search_results: List[Dict]) -> List[SourceCitation]:
        """Convert search results to structured citations"""
        sources = []
        for result in search_results[:5]:
            try:
                source = SourceCitation(
                    title=result.get('title', 'Unknown Title'),
                    url=result.get('url', ''),
                    publish_date=result.get('published_date'),
                    domain=result.get('url', '').split('/')[2] if result.get('url') else 'unknown'
                )
                sources.append(source)
            except Exception as e:
                logger.warning(f"Error processing search result: {e}")
                continue
        return sources

    def _analyze_response(self, content: str, statement: str) -> tuple[str, float, str]:
        """Analyze the response to extract verdict, confidence, and explanation"""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ['true', 'correct', 'accurate', 'confirmed']):
            if any(word in content_lower for word in ['partially', 'somewhat', 'mostly']):
                verdict = "Partially True"
                confidence = 0.7
            else:
                verdict = "True"
                confidence = 0.9
        elif any(word in content_lower for word in ['false', 'incorrect', 'inaccurate', 'wrong']):
            verdict = "False"
            confidence = 0.85
        elif any(word in content_lower for word in ['unclear', 'uncertain', 'insufficient', 'cannot determine']):
            verdict = "Unverified"
            confidence = 0.3
        else:
            verdict = "Unverified"
            confidence = 0.5
        
        explanation = content.strip()
        return verdict, confidence, explanation

# Global fact checker instance
fact_checker = PerplexityFactChecker()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.session_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.session_connections[session_id] = websocket

    def disconnect(self, websocket: WebSocket, session_id: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if session_id in self.session_connections:
            del self.session_connections[session_id]

    async def send_fact_check_result(self, session_id: str, result: FactCheckResult):
        if session_id in self.session_connections:
            try:
                await self.session_connections[session_id].send_text(
                    json.dumps({
                        "type": "fact_check_result",
                        "data": result.dict()
                    })
                )
            except Exception as e:
                logger.error(f"Error sending fact check result: {e}")

manager = ConnectionManager()

# API Routes
@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "TruthSeeker",
        "perplexity_api_configured": bool(os.getenv("PERPLEXITY_API_KEY"))
    }

@api_router.post("/fact-check", response_model=FactCheckResult)
async def fact_check_statement(request: FactCheckRequest):
    """Fact-check a single statement"""
    try:
        result = await fact_checker.fact_check_statement(
            request.statement, 
            request.context
        )
        
        # Store result in database
        await db.fact_checks.insert_one({
            **result.dict(),
            "session_id": request.session_id,
            "id": str(uuid.uuid4())
        })
        
        return result
    except Exception as e:
        logger.error(f"Fact-checking error: {e}")
        raise HTTPException(status_code=500, detail="Fact-checking service error")

@api_router.post("/transcription")
async def process_transcription(update: TranscriptionUpdate):
    """Process transcription update and trigger fact-checking if needed"""
    try:
        # Store transcription in database
        await db.transcriptions.insert_one({
            **update.dict(),
            "id": str(uuid.uuid4())
        })
        
        # If it's a final transcription, trigger fact-checking
        if update.is_final and len(update.text.strip()) > 10:
            result = await fact_checker.fact_check_statement(update.text)
            
            # Store fact-check result
            await db.fact_checks.insert_one({
                **result.dict(),
                "session_id": update.session_id,
                "id": str(uuid.uuid4())
            })
            
            # Send result via WebSocket
            await manager.send_fact_check_result(update.session_id, result)
            
            return {"status": "processed", "fact_check": result}
        
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Transcription processing error: {e}")
        raise HTTPException(status_code=500, detail="Transcription processing error")

@api_router.get("/sessions/{session_id}/fact-checks")
async def get_session_fact_checks(session_id: str):
    """Get all fact-checks for a session"""
    try:
        fact_checks = await db.fact_checks.find(
            {"session_id": session_id}
        ).sort("timestamp", -1).to_list(100)
        
        # Convert ObjectId to string for JSON serialization
        for fact_check in fact_checks:
            if "_id" in fact_check:
                fact_check["_id"] = str(fact_check["_id"])
        
        return {
            "session_id": session_id,
            "fact_checks": fact_checks
        }
    except Exception as e:
        logger.error(f"Error retrieving fact checks: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving fact checks")

# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "transcription_update":
                # Process transcription update
                update = TranscriptionUpdate(
                    text=message["text"],
                    is_final=message.get("is_final", False),
                    session_id=session_id
                )
                
                # Store transcription
                await db.transcriptions.insert_one({
                    **update.dict(),
                    "id": str(uuid.uuid4())
                })
                
                # If final, trigger fact-checking
                if update.is_final and len(update.text.strip()) > 10:
                    result = await fact_checker.fact_check_statement(update.text)
                    
                    # Store result
                    await db.fact_checks.insert_one({
                        **result.dict(),
                        "session_id": session_id,
                        "id": str(uuid.uuid4())
                    })
                    
                    # Send back result
                    await websocket.send_text(json.dumps({
                        "type": "fact_check_result",
                        "data": result.dict()
                    }))
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, session_id)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()