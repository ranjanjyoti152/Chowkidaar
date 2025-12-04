"""
Chowkidaar NVR - Unified VLM Service
Supports Ollama, OpenAI, and Google Gemini APIs
"""
import asyncio
import base64
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from loguru import logger
import numpy as np
import cv2
from io import BytesIO
from PIL import Image

from app.core.config import settings


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def check_health(self) -> bool:
        """Check if the service is available"""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models"""
        pass
    
    @abstractmethod
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        """Generate description for a frame"""
        pass
    
    @abstractmethod
    async def chat(
        self,
        message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        has_images: bool = False
    ) -> str:
        """Chat with the model"""
        pass
    
    def _frame_to_base64(self, frame: np.ndarray) -> str:
        """Convert numpy frame to base64 string"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM Provider"""
    
    def __init__(self, base_url: str, vlm_model: str, chat_model: str = None):
        self.base_url = base_url
        self.vlm_model = vlm_model
        self.chat_model = chat_model or vlm_model
        self._client: Optional[httpx.AsyncClient] = None
    
    def configure(self, base_url: str = None, vlm_model: str = None, chat_model: str = None):
        """Update configuration"""
        if base_url and base_url != self.base_url:
            self.base_url = base_url
            if self._client and not self._client.is_closed:
                asyncio.create_task(self._client.aclose())
            self._client = None
        if vlm_model:
            self.vlm_model = vlm_model
        if chat_model:
            self.chat_model = chat_model
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        return self._client
    
    async def check_health(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []
    
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        try:
            client = await self._get_client()
            image_base64 = self._frame_to_base64(frame)
            
            context = ""
            if detected_objects:
                objects_str = ", ".join([
                    f"{obj['class_name']} ({obj['confidence']:.0%})"
                    for obj in detected_objects
                ])
                context = f"Detected objects: {objects_str}. "
            
            if not prompt:
                prompt = f"""Analyze this security camera frame. {context}

Describe what you see in 2-3 simple sentences. Be factual and direct.
Do not use markdown formatting, bullet points, or asterisks.
Do not add notes, disclaimers, recommendations, or suggestions."""
            
            max_tokens = 300 if prompt else 150
            
            response = await client.post(
                "/api/generate",
                json={
                    "model": self.vlm_model,
                    "prompt": prompt,
                    "images": [image_base64],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": max_tokens}
                },
                timeout=90.0
            )
            
            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logger.error(f"Ollama VLM API error: {response.status_code}")
                return "Failed to generate description"
        except Exception as e:
            logger.error(f"Ollama frame description error: {e}")
            return f"Error: {str(e)}"
    
    async def chat(
        self,
        message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        has_images: bool = False
    ) -> str:
        try:
            client = await self._get_client()
            messages = []
            
            system_prompt = self._build_system_prompt(context, has_images)
            messages.append({"role": "system", "content": system_prompt})
            
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            response = await client.post(
                "/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 500}
                }
            )
            
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "").strip()
            else:
                logger.error(f"Ollama Chat API error: {response.status_code}")
                return "I'm sorry, I encountered an error processing your request."
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return f"Error: {str(e)}"
    
    def _build_system_prompt(self, context: Optional[str], has_images: bool) -> str:
        system_prompt = """You are Chowkidaar AI, an intelligent security assistant for a surveillance system.
You have access to event summaries and can help users understand security events.

IMPORTANT RULES:
1. ONLY describe what is mentioned in the event summaries - do NOT make up details
2. If user asks about an event, use ONLY the summary provided - do not imagine what might have happened
3. Be factual and honest - say "based on the event summary" when describing events
4. If you don't have enough information, say so honestly
5. Do not use markdown formatting like ** or * for emphasis."""
        
        if context:
            system_prompt += f"\n\nEvent summaries:\n{context}"
        if has_images:
            system_prompt += "\n\nNote: Event images are being displayed to the user."
        
        return system_prompt
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API Provider (also supports OpenAI-compatible APIs)"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self._client: Optional[httpx.AsyncClient] = None
    
    def configure(self, api_key: str = None, model: str = None, base_url: str = None):
        """Update configuration"""
        if api_key:
            self.api_key = api_key
        if model:
            self.model = model
        if base_url:
            self.base_url = base_url
        # Reset client on config change
        if self._client and not self._client.is_closed:
            asyncio.create_task(self._client.aclose())
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def check_health(self) -> bool:
        if not self.api_key:
            return False
        try:
            client = await self._get_client()
            response = await client.get("/models")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        if not self.api_key:
            return []
        try:
            client = await self._get_client()
            response = await client.get("/models")
            if response.status_code == 200:
                data = response.json()
                # Return ALL models without filtering
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            return []
        except Exception as e:
            logger.error(f"Failed to list OpenAI models: {e}")
            return []
    
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        if not self.api_key:
            return "OpenAI API key not configured"
        
        try:
            client = await self._get_client()
            image_base64 = self._frame_to_base64(frame)
            
            context = ""
            if detected_objects:
                objects_str = ", ".join([
                    f"{obj['class_name']} ({obj['confidence']:.0%})"
                    for obj in detected_objects
                ])
                context = f"Detected objects: {objects_str}. "
            
            if not prompt:
                prompt = f"""Analyze this security camera frame. {context}

Describe what you see in 2-3 simple sentences. Be factual and direct.
Do not use markdown formatting, bullet points, or asterisks."""
            
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}",
                                        "detail": "low"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.2
                },
                timeout=90.0
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"OpenAI VLM API error: {response.status_code} - {response.text}")
                return "Failed to generate description"
        except Exception as e:
            logger.error(f"OpenAI frame description error: {e}")
            return f"Error: {str(e)}"
    
    async def chat(
        self,
        message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        has_images: bool = False
    ) -> str:
        if not self.api_key:
            return "OpenAI API key not configured"
        
        try:
            client = await self._get_client()
            messages = []
            
            system_prompt = self._build_system_prompt(context, has_images)
            messages.append({"role": "system", "content": system_prompt})
            
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": message})
            
            response = await client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7
                }
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"OpenAI Chat API error: {response.status_code}")
                return "I'm sorry, I encountered an error processing your request."
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            return f"Error: {str(e)}"
    
    def _build_system_prompt(self, context: Optional[str], has_images: bool) -> str:
        system_prompt = """You are Chowkidaar AI, an intelligent security assistant for a surveillance system.
You have access to event summaries and can help users understand security events.

IMPORTANT RULES:
1. ONLY describe what is mentioned in the event summaries - do NOT make up details
2. Be factual and honest
3. If you don't have enough information, say so honestly
4. Do not use markdown formatting like ** or * for emphasis."""
        
        if context:
            system_prompt += f"\n\nEvent summaries:\n{context}"
        if has_images:
            system_prompt += "\n\nNote: Event images are being displayed to the user."
        
        return system_prompt
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self._client: Optional[httpx.AsyncClient] = None
    
    def configure(self, api_key: str = None, model: str = None):
        """Update configuration"""
        if api_key:
            self.api_key = api_key
        if model:
            self.model = model
        if self._client and not self._client.is_closed:
            asyncio.create_task(self._client.aclose())
        self._client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
                headers={"Content-Type": "application/json"}
            )
        return self._client
    
    async def check_health(self) -> bool:
        if not self.api_key:
            return False
        try:
            client = await self._get_client()
            response = await client.get(f"/models?key={self.api_key}")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        if not self.api_key:
            return []
        try:
            client = await self._get_client()
            response = await client.get(f"/models?key={self.api_key}")
            if response.status_code == 200:
                data = response.json()
                # Return ALL models without filtering
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "").replace("models/", "")
                    models.append(name)
                return sorted(models)
            return []
        except Exception as e:
            logger.error(f"Failed to list Gemini models: {e}")
            return []
    
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        if not self.api_key:
            return "Gemini API key not configured"
        
        try:
            client = await self._get_client()
            image_base64 = self._frame_to_base64(frame)
            
            context = ""
            if detected_objects:
                objects_str = ", ".join([
                    f"{obj['class_name']} ({obj['confidence']:.0%})"
                    for obj in detected_objects
                ])
                context = f"Detected objects: {objects_str}. "
            
            if not prompt:
                prompt = f"""Analyze this security camera frame. {context}

Describe what you see in 2-3 simple sentences. Be factual and direct.
Do not use markdown formatting, bullet points, or asterisks."""
            
            response = await client.post(
                f"/models/{self.model}:generateContent?key={self.api_key}",
                json={
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": image_base64
                                    }
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": 300
                    }
                },
                timeout=90.0
            )
            
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return "No response generated"
            else:
                logger.error(f"Gemini VLM API error: {response.status_code} - {response.text}")
                return "Failed to generate description"
        except Exception as e:
            logger.error(f"Gemini frame description error: {e}")
            return f"Error: {str(e)}"
    
    async def chat(
        self,
        message: str,
        context: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        has_images: bool = False
    ) -> str:
        if not self.api_key:
            return "Gemini API key not configured"
        
        try:
            client = await self._get_client()
            
            # Build conversation
            system_prompt = self._build_system_prompt(context, has_images)
            contents = []
            
            # Add system instruction as first message
            contents.append({
                "role": "user",
                "parts": [{"text": f"System instructions: {system_prompt}\n\nNow, respond to user queries."}]
            })
            contents.append({
                "role": "model", 
                "parts": [{"text": "I understand. I am Chowkidaar AI, ready to help with security analysis."}]
            })
            
            # Add history
            if history:
                for msg in history:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            
            # Add current message
            contents.append({"role": "user", "parts": [{"text": message}]})
            
            response = await client.post(
                f"/models/{self.model}:generateContent?key={self.api_key}",
                json={
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 500
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
                return "No response generated"
            elif response.status_code == 429:
                logger.error(f"Gemini Chat API rate limit exceeded: {response.text}")
                return "Rate limit exceeded. Please wait a moment and try again, or check your Gemini API quota."
            else:
                logger.error(f"Gemini Chat API error: {response.status_code} - {response.text}")
                return f"API error ({response.status_code}). Please try again."
        except Exception as e:
            logger.error(f"Gemini chat error: {e}")
            return f"Error: {str(e)}"
    
    def _build_system_prompt(self, context: Optional[str], has_images: bool) -> str:
        system_prompt = """You are Chowkidaar AI, an intelligent security assistant for a surveillance system.
You have access to event summaries and can help users understand security events.

IMPORTANT RULES:
1. ONLY describe what is mentioned in the event summaries - do NOT make up details
2. Be factual and honest
3. If you don't have enough information, say so honestly
4. Do not use markdown formatting like ** or * for emphasis."""
        
        if context:
            system_prompt += f"\n\nEvent summaries:\n{context}"
        if has_images:
            system_prompt += "\n\nNote: Event images are being displayed to the user."
        
        return system_prompt
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class UnifiedVLMService:
    """
    Unified VLM Service that manages multiple LLM providers
    Automatically routes requests to the configured provider
    """
    
    def __init__(self):
        self.current_provider = "ollama"
        
        # Initialize providers
        self.ollama = OllamaProvider(
            base_url=settings.ollama_base_url,
            vlm_model=settings.ollama_vlm_model,
            chat_model=settings.ollama_chat_model
        )
        self.openai: Optional[OpenAIProvider] = None
        self.gemini: Optional[GeminiProvider] = None
    
    def configure(
        self,
        provider: str = None,
        ollama_url: str = None,
        ollama_model: str = None,
        openai_api_key: str = None,
        openai_model: str = None,
        openai_base_url: str = None,
        gemini_api_key: str = None,
        gemini_model: str = None
    ):
        """Configure the VLM service with provider settings"""
        
        if provider:
            self.current_provider = provider
            logger.info(f"VLM provider set to: {provider}")
        
        # Configure Ollama
        if ollama_url or ollama_model:
            self.ollama.configure(base_url=ollama_url, vlm_model=ollama_model, chat_model=ollama_model)
        
        # Configure OpenAI
        if openai_api_key:
            if not self.openai:
                self.openai = OpenAIProvider(
                    api_key=openai_api_key,
                    model=openai_model or "gpt-4o",
                    base_url=openai_base_url
                )
            else:
                self.openai.configure(api_key=openai_api_key, model=openai_model, base_url=openai_base_url)
        
        # Configure Gemini
        if gemini_api_key:
            if not self.gemini:
                self.gemini = GeminiProvider(
                    api_key=gemini_api_key,
                    model=gemini_model or "gemini-2.0-flash-exp"
                )
            else:
                self.gemini.configure(api_key=gemini_api_key, model=gemini_model)
    
    def _get_provider(self) -> BaseLLMProvider:
        """Get the current active provider"""
        if self.current_provider == "openai" and self.openai:
            return self.openai
        elif self.current_provider == "gemini" and self.gemini:
            return self.gemini
        return self.ollama
    
    async def check_health(self) -> bool:
        """Check if the current provider is healthy"""
        return await self._get_provider().check_health()
    
    async def list_models(self) -> List[str]:
        """List models from the current provider"""
        return await self._get_provider().list_models()
    
    async def describe_frame(
        self,
        frame: np.ndarray,
        detected_objects: List[Dict[str, Any]] = None,
        prompt: Optional[str] = None
    ) -> str:
        """Generate description using the current provider"""
        return await self._get_provider().describe_frame(frame, detected_objects, prompt)
    
    async def generate_event_summary(
        self,
        frame: np.ndarray,
        event_type: str,
        detected_objects: List[Dict[str, Any]],
        camera_name: str,
        timestamp: datetime
    ) -> str:
        """Generate a detailed event summary"""
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
        """Chat using the current provider"""
        return await self._get_provider().chat(message, context, history, has_images)
    
    async def analyze_events(
        self,
        events_summary: str,
        query: str,
        has_images: bool = False
    ) -> str:
        """Analyze multiple events and answer questions"""
        image_note = "\n\nNote: Event images will be shown alongside your response." if has_images else ""
        
        prompt = f"""Based on the following security events:

{events_summary}

User Question: {query}{image_note}

Provide a helpful and accurate response based on the events data.
Do not use markdown formatting like ** or * for emphasis."""
        
        return await self.chat(prompt)
    
    async def test_provider(self, provider: str, **kwargs) -> Dict[str, Any]:
        """Test a specific provider with given configuration"""
        try:
            if provider == "ollama":
                temp_provider = OllamaProvider(
                    base_url=kwargs.get("ollama_url", settings.ollama_base_url),
                    vlm_model=kwargs.get("model", "llava"),
                    chat_model=kwargs.get("model", "llava")
                )
            elif provider == "openai":
                api_key = kwargs.get("openai_api_key")
                if not api_key:
                    return {"status": "error", "error": "API key required"}
                temp_provider = OpenAIProvider(
                    api_key=api_key,
                    model=kwargs.get("openai_model", "gpt-4o"),
                    base_url=kwargs.get("openai_base_url")
                )
            elif provider == "gemini":
                api_key = kwargs.get("gemini_api_key")
                if not api_key:
                    return {"status": "error", "error": "API key required"}
                temp_provider = GeminiProvider(
                    api_key=api_key,
                    model=kwargs.get("gemini_model", "gemini-2.0-flash-exp")
                )
            else:
                return {"status": "error", "error": f"Unknown provider: {provider}"}
            
            is_healthy = await temp_provider.check_health()
            models = await temp_provider.list_models() if is_healthy else []
            await temp_provider.close()
            
            return {
                "status": "online" if is_healthy else "offline",
                "models": models,
                "model_count": len(models)
            }
        except Exception as e:
            logger.error(f"Provider test failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def close(self):
        """Close all provider connections"""
        await self.ollama.close()
        if self.openai:
            await self.openai.close()
        if self.gemini:
            await self.gemini.close()


# Global service instance
vlm_service = UnifiedVLMService()


def get_unified_vlm_service() -> UnifiedVLMService:
    """Get the unified VLM service instance (sync version)"""
    return vlm_service


async def get_vlm_service() -> UnifiedVLMService:
    """Get the unified VLM service instance (async version for backwards compat)"""
    return vlm_service
