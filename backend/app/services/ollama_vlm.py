"""
Chowkidaar NVR - Ollama VLM Integration Service
"""
import asyncio
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from loguru import logger
import numpy as np
import cv2
from io import BytesIO
from PIL import Image

from app.core.config import settings


class OllamaVLMService:
    """Service for interacting with Ollama Vision-Language Models"""
    
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.vlm_model = settings.ollama_vlm_model
        self.chat_model = settings.ollama_chat_model
        self._client: Optional[httpx.AsyncClient] = None
    
    def configure(self, base_url: str, vlm_model: str, chat_model: str = None):
        """Configure Ollama with custom settings"""
        if base_url and base_url != self.base_url:
            self.base_url = base_url
            # Close existing client to use new URL
            if self._client and not self._client.is_closed:
                asyncio.create_task(self._client.aclose())
            self._client = None
        if vlm_model:
            self.vlm_model = vlm_model
        if chat_model:
            self.chat_model = chat_model
        logger.debug(f"Ollama configured: {self.base_url}, model: {self.vlm_model}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0
            )
        return self._client
    
    async def check_health(self) -> bool:
        """Check if Ollama is running and accessible"""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """List available models"""
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []
    
    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """Convert numpy frame to base64 string"""
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to PIL Image
        image = Image.fromarray(rgb_frame)
        
        # Save to bytes
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        
        # Encode to base64
        return base64.b64encode(buffer.read()).decode("utf-8")
    
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        """
        Generate a description of a frame using VLM
        
        Args:
            frame: numpy array of the image
            detected_objects: List of detected objects from YOLO
            prompt: Custom prompt (optional)
        
        Returns:
            Description string
        """
        try:
            client = await self._get_client()
            
            # Convert frame to base64
            image_base64 = self._frame_to_base64(frame)
            
            # Build context from detections
            context = ""
            if detected_objects:
                objects_str = ", ".join([
                    f"{obj['class_name']} ({obj['confidence']:.0%})"
                    for obj in detected_objects
                ])
                context = f"Detected objects: {objects_str}. "
            
            # Build prompt
            if prompt:
                full_prompt = prompt
            else:
                full_prompt = f"""Analyze this security camera frame. {context}

Describe what you see in 2-3 simple sentences. Be factual and direct.
Do not use markdown formatting, bullet points, or asterisks.
Do not add notes, disclaimers, recommendations, or suggestions."""
            
            # Call Ollama API
            # Use longer num_predict for custom prompts (like security analysis)
            max_tokens = 300 if prompt else 150
            
            response = await client.post(
                "/api/generate",
                json={
                    "model": self.vlm_model,
                    "prompt": full_prompt,
                    "images": [image_base64],
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": max_tokens
                    }
                },
                timeout=90.0  # Longer timeout for VLM analysis
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
            else:
                logger.error(f"VLM API error: {response.status_code} - {response.text}")
                return "Failed to generate description"
                
        except Exception as e:
            logger.error(f"Frame description error: {e}")
            return f"Error generating description: {str(e)}"
    
    async def generate_event_summary(
        self,
        frame: np.ndarray,
        event_type: str,
        detected_objects: List[Dict[str, Any]],
        camera_name: str,
        timestamp: datetime
    ) -> str:
        """Generate a detailed event summary for storage"""
        
        prompt = f"""You are analyzing a security event captured at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}.
Camera: {camera_name}
Event Type: {event_type}
Detected: {', '.join([f"{obj['class_name']}" for obj in detected_objects])}

Analyze this frame and provide a detailed security event summary including:
1. Description of what's happening
2. Number and description of people/objects
3. Any concerning behaviors or situations
4. Environmental context (lighting, weather if visible)
5. Recommended actions if any

Be specific and factual. Keep under 150 words."""

        return await self.describe_frame(frame, detected_objects, prompt)
    
    async def chat(
        self,
        message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        has_images: bool = False
    ) -> str:
        """
        Chat with the assistant model
        
        Args:
            message: User message
            context: Additional context (e.g., event summaries)
            history: Chat history
            has_images: Whether images will be shown to user
        
        Returns:
            Assistant response
        """
        try:
            client = await self._get_client()
            
            # Build messages
            messages = []
            
            # System message
            system_prompt = """You are Chowkidaar AI, an intelligent security assistant for a surveillance system.
You have access to event summaries and can help users understand security events, analyze patterns, and answer questions about their camera footage.

IMPORTANT: When users ask about images, events, or what happened - the system WILL display relevant event images alongside your response. So do NOT say you cannot show images. Instead, describe what happened based on the event summaries and tell the user they can see the images below.

Be helpful, concise, and focus on security-related insights.
Do not use markdown formatting like ** or * for emphasis.
Speak naturally and directly."""
            
            if context:
                system_prompt += f"\n\nContext from recent events:\n{context}"
            
            if has_images:
                system_prompt += "\n\nNote: Event images will be displayed to the user along with your response. Refer to them naturally."
            
            messages.append({"role": "system", "content": system_prompt})
            
            # Add history
            if history:
                messages.extend(history)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Call Ollama API
            response = await client.post(
                "/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                logger.error(f"Chat API error: {response.status_code}")
                return "I'm sorry, I encountered an error processing your request."
                
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Error: {str(e)}"
    
    async def analyze_events(
        self,
        events_summary: str,
        query: str,
        has_images: bool = False
    ) -> str:
        """Analyze multiple events and answer questions"""
        
        image_note = ""
        if has_images:
            image_note = "\n\nNote: The relevant event images will be shown to the user alongside your response. Reference them naturally."
        
        prompt = f"""Based on the following security events:

{events_summary}

User Question: {query}{image_note}

Provide a helpful and accurate response based on the events data.
Do not use markdown formatting like ** or * for emphasis.
Do NOT say you cannot display images - images ARE being shown to the user."""
        
        return await self.chat(prompt)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# Global VLM service instance
vlm_service = OllamaVLMService()


async def get_vlm_service() -> OllamaVLMService:
    """Get the VLM service instance"""
    return vlm_service
