"""
Chowkidaar NVR - Notification Service
Sends event notifications via Telegram and Email
"""
import asyncio
import aiohttp
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.models.settings import UserSettings
from app.models.event import Event, EventSeverity
from sqlalchemy import select


class NotificationService:
    """Service for sending event notifications"""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def send_event_notification(self, event: Event, user_id: int):
        """Send notification for an event based on user settings"""
        try:
            # Get user settings
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(UserSettings).where(UserSettings.user_id == user_id)
                )
                settings = result.scalar_one_or_none()
            
            if not settings or not settings.notifications_enabled:
                logger.debug(f"Notifications disabled for user {user_id}")
                return
            
            # Check severity threshold
            severity_levels = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
            event_severity = severity_levels.get(event.severity.value, 0)
            min_severity = severity_levels.get(settings.min_severity, 2)
            
            if event_severity < min_severity:
                logger.debug(f"Event severity {event.severity.value} below threshold {settings.min_severity}")
                return
            
            # Check event type filter
            notify_types = settings.notify_event_types or []
            if notify_types and event.event_type.value not in notify_types:
                logger.debug(f"Event type {event.event_type.value} not in notification list")
                return
            
            # Send notifications
            tasks = []
            
            if settings.telegram_enabled and settings.telegram_bot_token and settings.telegram_chat_id:
                tasks.append(self._send_telegram(event, settings))
            
            if settings.email_enabled and settings.email_smtp_host and settings.email_recipients:
                tasks.append(self._send_email(event, settings))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Sent notifications for event {event.id}")
                
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    async def _send_telegram(self, event: Event, settings: UserSettings):
        """Send Telegram notification"""
        try:
            session = await self._get_session()
            bot_token = settings.telegram_bot_token
            chat_id = settings.telegram_chat_id
            
            # Build message
            message_parts = []
            
            # Header with severity emoji
            severity_emoji = {
                'low': '🟢',
                'medium': '🟡', 
                'high': '🟠',
                'critical': '🔴'
            }
            emoji = severity_emoji.get(event.severity.value, '⚪')
            
            event_type_display = event.event_type.value.replace('_', ' ').title()
            message_parts.append(f"{emoji} *{event_type_display}*")
            message_parts.append(f"🕐 {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Event details
            if settings.telegram_send_details:
                message_parts.append(f"\n📍 *Camera:* {event.camera_id}")
                message_parts.append(f"⚠️ *Severity:* {event.severity.value.upper()}")
                
                if event.detected_objects:
                    objects = event.detected_objects
                    if isinstance(objects, list) and objects:
                        detected = [obj.get('class', 'unknown') for obj in objects]
                        message_parts.append(f"🎯 *Detected:* {', '.join(detected)}")
            
            # AI Summary
            if settings.telegram_send_summary and event.summary:
                message_parts.append(f"\n📝 *Summary:*\n{event.summary}")
            
            message = '\n'.join(message_parts)
            
            # Send with photo or text only
            if settings.telegram_send_photo and event.frame_path and Path(event.frame_path).exists():
                # Send photo with caption
                url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                
                with open(event.frame_path, 'rb') as photo:
                    data = aiohttp.FormData()
                    data.add_field('chat_id', chat_id)
                    data.add_field('caption', message)
                    data.add_field('parse_mode', 'Markdown')
                    data.add_field('photo', photo, filename='event.jpg')
                    
                    async with session.post(url, data=data) as resp:
                        if resp.status != 200:
                            error = await resp.text()
                            logger.error(f"Telegram API error: {error}")
                        else:
                            logger.info(f"✅ Telegram notification sent for event {event.id}")
            else:
                # Send text only
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
                
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"Telegram API error: {error}")
                    else:
                        logger.info(f"✅ Telegram notification sent for event {event.id}")
                        
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
    
    async def _send_email(self, event: Event, settings: UserSettings):
        """Send Email notification"""
        try:
            # Run in executor since smtplib is blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_email_sync,
                event,
                settings
            )
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
    
    def _send_email_sync(self, event: Event, settings: UserSettings):
        """Synchronous email sending (runs in executor)"""
        try:
            # Create message
            msg = MIMEMultipart('related')
            
            event_type_display = event.event_type.value.replace('_', ' ').title()
            msg['Subject'] = f"🚨 Chowkidaar Alert: {event_type_display} - {event.severity.value.upper()}"
            msg['From'] = settings.email_from_address
            msg['To'] = ', '.join(settings.email_recipients)
            
            # Build HTML body
            severity_colors = {
                'low': '#22c55e',
                'medium': '#eab308',
                'high': '#f97316',
                'critical': '#ef4444'
            }
            color = severity_colors.get(event.severity.value, '#6b7280')
            
            html_parts = [f"""
            <html>
            <body style="font-family: Arial, sans-serif; background-color: #1f2937; color: #f3f4f6; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #374151; border-radius: 12px; padding: 20px;">
                    <div style="border-left: 4px solid {color}; padding-left: 15px; margin-bottom: 20px;">
                        <h1 style="margin: 0; color: {color};">{event_type_display}</h1>
                        <p style="margin: 5px 0; color: #9ca3af;">
                            🕐 {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                        </p>
                    </div>
            """]
            
            if settings.email_send_details:
                html_parts.append(f"""
                    <div style="background-color: #4b5563; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                        <h3 style="margin: 0 0 10px 0; color: #f3f4f6;">Event Details</h3>
                        <p style="margin: 5px 0;"><strong>Camera:</strong> Camera {event.camera_id}</p>
                        <p style="margin: 5px 0;"><strong>Severity:</strong> 
                            <span style="color: {color}; font-weight: bold;">{event.severity.value.upper()}</span>
                        </p>
                """)
                
                if event.detected_objects:
                    objects = event.detected_objects
                    if isinstance(objects, list) and objects:
                        detected = [obj.get('class', 'unknown') for obj in objects]
                        html_parts.append(f"<p style='margin: 5px 0;'><strong>Detected:</strong> {', '.join(detected)}</p>")
                
                html_parts.append("</div>")
            
            if settings.email_send_summary and event.summary:
                html_parts.append(f"""
                    <div style="background-color: #4b5563; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                        <h3 style="margin: 0 0 10px 0; color: #f3f4f6;">📝 AI Analysis</h3>
                        <p style="margin: 0; line-height: 1.6;">{event.summary}</p>
                    </div>
                """)
            
            if settings.email_send_photo and event.frame_path and Path(event.frame_path).exists():
                html_parts.append("""
                    <div style="text-align: center; margin-top: 15px;">
                        <img src="cid:event_image" style="max-width: 100%; border-radius: 8px;" />
                    </div>
                """)
            
            html_parts.append("""
                    <div style="text-align: center; margin-top: 20px; padding-top: 15px; border-top: 1px solid #4b5563;">
                        <p style="color: #9ca3af; font-size: 12px;">
                            🛡️ Chowkidaar NVR - AI-Powered Security System
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """)
            
            html_body = ''.join(html_parts)
            msg_html = MIMEText(html_body, 'html')
            msg.attach(msg_html)
            
            # Attach image if enabled
            if settings.email_send_photo and event.frame_path and Path(event.frame_path).exists():
                with open(event.frame_path, 'rb') as f:
                    img = MIMEImage(f.read())
                    img.add_header('Content-ID', '<event_image>')
                    img.add_header('Content-Disposition', 'inline', filename='event.jpg')
                    msg.attach(img)
            
            # Send email
            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
                server.starttls()
                if settings.email_smtp_user and settings.email_smtp_password:
                    server.login(settings.email_smtp_user, settings.email_smtp_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email notification sent for event {event.id}")
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            raise


# Global instance
_notification_service: Optional[NotificationService] = None


async def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


async def send_event_notification(event: Event, user_id: int):
    """Convenience function to send notification"""
    service = await get_notification_service()
    await service.send_event_notification(event, user_id)
