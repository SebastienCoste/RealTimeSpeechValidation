import asyncio
import logging
import json
import time
from typing import Optional, Dict, List, Any
import httpx
import yt_dlp
from openai import AsyncOpenAI
import os
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
import subprocess
import tempfile

logger = logging.getLogger(__name__)

class YouTubeProcessor:
    def __init__(self, db, fact_checker):
        self.db = db
        self.fact_checker = fact_checker
        self.openai_client = None
        self.current_video_id = None
        self.is_processing = False
        self.video_info = None
        self.processed_segments = set()
        
        # Initialize OpenAI client for Whisper
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.openai_client = AsyncOpenAI(api_key=api_key)

    async def set_video(self, video_url: str, admin_user: str) -> Dict[str, Any]:
        """Set the current video for fact-checking"""
        try:
            # Extract video ID from URL
            video_id = self.extract_video_id(video_url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            # Get video information
            video_info = await self.get_video_info(video_url)
            
            # Store video session in database
            video_session = {
                "id": str(uuid.uuid4()),
                "video_id": video_id,
                "video_url": video_url,
                "title": video_info.get("title", "Unknown Video"),
                "duration": video_info.get("duration", 0),
                "is_live": video_info.get("is_live", False),
                "admin_user": admin_user,
                "created_at": datetime.utcnow(),
                "status": "active",
                "transcript_segments": [],
                "fact_checks": []
            }
            
            # Deactivate previous sessions
            await self.db.youtube_sessions.update_many(
                {"status": "active"},
                {"$set": {"status": "inactive"}}
            )
            
            # Insert new session
            await self.db.youtube_sessions.insert_one(video_session)
            
            self.current_video_id = video_id
            self.video_info = video_info
            self.processed_segments.clear()
            
            logger.info(f"Set video: {video_info.get('title')} ({video_id})")
            
            return {
                "success": True,
                "video_id": video_id,
                "title": video_info.get("title"),
                "duration": video_info.get("duration"),
                "is_live": video_info.get("is_live", False)
            }
            
        except Exception as e:
            logger.error(f"Error setting video: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        try:
            if "youtube.com/watch?v=" in url:
                return url.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                return url.split("youtu.be/")[1].split("?")[0]
            elif "youtube.com/embed/" in url:
                return url.split("embed/")[1].split("?")[0]
            return None
        except Exception:
            return None

    async def get_video_info(self, video_url: str) -> Dict[str, Any]:
        """Get video information using yt-dlp"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                
                return {
                    "title": info.get("title", "Unknown Video"),
                    "duration": info.get("duration", 0),
                    "is_live": info.get("is_live", False),
                    "uploader": info.get("uploader", "Unknown"),
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count", 0),
                    "upload_date": info.get("upload_date", ""),
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            return {
                "title": "Unknown Video",
                "duration": 0,
                "is_live": False
            }

    async def start_processing(self):
        """Start processing the current video"""
        if not self.current_video_id or self.is_processing:
            return
            
        self.is_processing = True
        logger.info(f"Starting processing for video: {self.current_video_id}")
        
        try:
            if self.video_info and self.video_info.get("is_live", False):
                await self.process_live_video()
            else:
                await self.process_static_video()
        except Exception as e:
            logger.error(f"Error processing video: {e}")
        finally:
            self.is_processing = False

    async def process_live_video(self):
        """Process live video with continuous audio extraction"""
        logger.info("Processing live video...")
        
        video_url = f"https://www.youtube.com/watch?v={self.current_video_id}"
        segment_duration = 30  # Process 30-second segments
        
        while self.is_processing and self.current_video_id:
            try:
                # Extract audio segment from live stream
                audio_file = await self.extract_live_audio_segment(video_url, segment_duration)
                
                if audio_file:
                    # Transcribe audio segment
                    transcript = await self.transcribe_audio(audio_file)
                    
                    if transcript and transcript.strip():
                        # Process transcript for fact-checking
                        await self.process_transcript_segment(transcript)
                    
                    # Clean up audio file
                    try:
                        os.unlink(audio_file)
                    except:
                        pass
                
                # Wait before processing next segment
                await asyncio.sleep(segment_duration)
                
            except Exception as e:
                logger.error(f"Error processing live segment: {e}")
                await asyncio.sleep(10)  # Wait before retrying

    async def process_static_video(self):
        """Process static video by extracting full audio and processing in chunks"""
        logger.info("Processing static video...")
        
        video_url = f"https://www.youtube.com/watch?v={self.current_video_id}"
        
        try:
            # Extract audio from video
            audio_file = await self.extract_full_audio(video_url)
            
            if audio_file:
                # Process audio in segments for better fact-checking
                await self.process_audio_file(audio_file)
                
                # Clean up
                try:
                    os.unlink(audio_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error processing static video: {e}")

    async def extract_live_audio_segment(self, video_url: str, duration: int) -> Optional[str]:
        """Extract audio segment from live stream"""
        try:
            # Create temporary file
            temp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_audio.close()
            
            # Use yt-dlp to extract live audio segment
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--output", temp_audio.name.replace(".mp3", ".%(ext)s"),
                "--external-downloader", "ffmpeg",
                "--external-downloader-args", f"-t {duration}",
                video_url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(temp_audio.name):
                return temp_audio.name
            else:
                logger.error(f"yt-dlp error: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting live audio: {e}")
            return None

    async def extract_full_audio(self, video_url: str) -> Optional[str]:
        """Extract full audio from video"""
        try:
            # Create temporary file
            temp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_audio.close()
            
            # Use yt-dlp to extract audio
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--output", temp_audio.name.replace(".mp3", ".%(ext)s"),
                video_url
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(temp_audio.name):
                return temp_audio.name
            else:
                logger.error(f"yt-dlp error: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None

    async def transcribe_audio(self, audio_file: str) -> Optional[str]:
        """Transcribe audio using OpenAI Whisper"""
        if not self.openai_client:
            logger.warning("OpenAI client not configured, using mock transcription")
            return self.mock_transcription()
        
        try:
            with open(audio_file, "rb") as audio:
                transcript = await self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="text"
                )
                return transcript
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return self.mock_transcription()

    def mock_transcription(self) -> str:
        """Mock transcription for testing"""
        mock_segments = [
            "Climate change is affecting weather patterns globally.",
            "The Earth's temperature has risen by 1.1 degrees Celsius since pre-industrial times.",
            "Renewable energy sources are becoming more cost-effective.",
            "Electric vehicles are projected to reach price parity with gas cars by 2025.",
            "The moon landing occurred on July 20, 1969.",
            "Artificial intelligence is transforming various industries.",
        ]
        import random
        return random.choice(mock_segments)

    async def process_audio_file(self, audio_file: str):
        """Process audio file in segments"""
        try:
            # For now, transcribe the whole file
            # In production, you might want to split into segments
            transcript = await self.transcribe_audio(audio_file)
            
            if transcript and transcript.strip():
                # Split transcript into sentences for better fact-checking
                sentences = self.split_into_sentences(transcript)
                
                for sentence in sentences:
                    if len(sentence.strip()) > 10:  # Only process meaningful sentences
                        await self.process_transcript_segment(sentence.strip())
                        await asyncio.sleep(2)  # Throttle processing
                        
        except Exception as e:
            logger.error(f"Error processing audio file: {e}")

    def split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    async def process_transcript_segment(self, transcript: str):
        """Process transcript segment and fact-check"""
        try:
            segment_id = f"{self.current_video_id}_{len(self.processed_segments)}"
            
            if segment_id in self.processed_segments:
                return
            
            # Store transcript segment
            segment_doc = {
                "id": segment_id,
                "video_id": self.current_video_id,
                "transcript": transcript,
                "timestamp": datetime.utcnow(),
                "processed": False
            }
            
            await self.db.transcript_segments.insert_one(segment_doc)
            
            # Fact-check the transcript
            fact_check_result = await self.fact_checker.fact_check_statement(transcript)
            
            # Store fact-check result
            fact_check_doc = {
                "id": str(uuid.uuid4()),
                "segment_id": segment_id,
                "video_id": self.current_video_id,
                **fact_check_result.dict(),
                "created_at": datetime.utcnow()
            }
            
            await self.db.youtube_fact_checks.insert_one(fact_check_doc)
            
            # Update session
            await self.db.youtube_sessions.update_one(
                {"video_id": self.current_video_id, "status": "active"},
                {
                    "$push": {
                        "transcript_segments": segment_doc,
                        "fact_checks": fact_check_doc
                    }
                }
            )
            
            # Mark as processed
            self.processed_segments.add(segment_id)
            
            # Broadcast to connected clients
            await self.broadcast_fact_check(fact_check_doc)
            
            logger.info(f"Processed segment: {transcript[:50]}...")
            
        except Exception as e:
            logger.error(f"Error processing transcript segment: {e}")

    async def broadcast_fact_check(self, fact_check: Dict[str, Any]):
        """Broadcast fact-check result to all connected clients"""
        # This will be implemented in the WebSocket manager
        pass

    async def get_current_session(self) -> Optional[Dict[str, Any]]:
        """Get current active video session"""
        try:
            session = await self.db.youtube_sessions.find_one(
                {"status": "active"},
                sort=[("created_at", -1)]
            )
            
            if session:
                # Convert ObjectId to string
                session["_id"] = str(session["_id"])
                return session
            return None
            
        except Exception as e:
            logger.error(f"Error getting current session: {e}")
            return None

    async def get_session_fact_checks(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all fact-checks for a video session"""
        try:
            fact_checks = await self.db.youtube_fact_checks.find(
                {"video_id": video_id}
            ).sort("created_at", 1).to_list(1000)
            
            # Convert ObjectIds to strings
            for fc in fact_checks:
                fc["_id"] = str(fc["_id"])
            
            return fact_checks
            
        except Exception as e:
            logger.error(f"Error getting session fact-checks: {e}")
            return []

    async def stop_processing(self):
        """Stop processing current video"""
        self.is_processing = False
        logger.info("Stopped video processing")