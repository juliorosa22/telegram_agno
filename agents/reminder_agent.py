from agno.agent import Agent
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio
from agno.models.groq import Groq
from tools import Reminder, ReminderType, Priority, SupabaseClient
from messages import get_message
import pytz # <-- 1. Import pytz

class ReminderAgent:
    """Specialized agent for handling reminders and tasks"""

    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        
        self.agent = Agent(
            name="ReminderProcessor",
            model=Groq(id="llama-3.3-70b-versatile", temperature=0.2),
            instructions="""
            You are a multilingual reminder and task management specialist. Your goal is to parse natural language messages to extract reminder details into a strict JSON format.

            **Thought Process:**
            1.  **Analyze the user's message** to identify the core task or event.
            2.  **Identify the due date and time**. You will be given the user's current time for context. Convert relative expressions like "tomorrow at 3pm" or "in 2 hours" into a specific UTC ISO 8601 format.
            3.  **Determine priority**: "urgent", "high", "medium", or "low". Default to "medium".
            4.  **Determine reminder type**: "task", "event", "deadline", "habit", or "general". Default to "general".

            **Rules & Output Format:**
            - You will be told the user's language. The user's message will be in that language.
            - You MUST return ONLY a valid JSON object. No explanations or surrounding text.
            - The `due_date` MUST be in UTC ISO 8601 format (e.g., "2025-09-18T15:00:00Z"). If no specific time is found, this should be null.
            - If no clear reminder is found in the message, return `{"reminder_found": false}`.
            """
        )
    
    async def process_message(self, user_id: str, message: str, language: str, user_timezone: str) -> str:
        """Process a text message for reminder data in the user's language and timezone."""
        try:
            # Get the current time IN THE USER'S TIMEZONE
            try:
                user_tz = pytz.timezone(user_timezone)
            except pytz.UnknownTimeZoneError:
                print(f"⚠️ Unknown timezone '{user_timezone}'. Defaulting to UTC.")
                user_tz = pytz.utc
            
            user_now_iso = datetime.now(user_tz).isoformat()

            # --- 2. Create a simple, dynamic prompt ---
            lang_map = {'es': 'Spanish', 'pt': 'Portuguese', 'en': 'English'}
            lang_name = lang_map.get(language.split('-')[0], 'English')

            extraction_prompt = f"""
            The user is speaking {lang_name}.
            The user's current date and time is {user_now_iso}.
            Analyze the following user message and return the JSON output based on your instructions.

            **User Message:** "{message}"
            """
            
            response_obj = await asyncio.to_thread(self.agent.run, extraction_prompt)
            response_str = str(response_obj.content)
            print(f"🤖 LLM Response: {response_str}")
            try:
                data = json.loads(response_str)
            except json.JSONDecodeError:
                data = self._fallback_parse(message, language)
            
            if not data.get("reminder_found", True):
                return get_message("reminder_not_found", language)
            
            due_datetime = self._parse_due_date(data.get("due_date")) if data.get("due_date") else None
            
            reminder = Reminder(
                user_id=user_id,
                title=data.get("title", "No Title"),
                description=data.get("description", f"{message}"),
                source_platform="telegram",
                is_completed=False,
                notification_sent=False,
                due_datetime=due_datetime,
                reminder_type=ReminderType(data.get("reminder_type", "general")),
                priority=Priority(data.get("priority", "medium")),
                tags=message
            )
            
            await self.supabase_client.database.save_reminder(reminder)
            
            # Format due date for display in user's local time
            display_due_date = "N/A"
            if due_datetime:
                local_due_date = due_datetime.astimezone(user_tz)
                display_due_date = local_due_date.strftime('%Y-%m-%d %H:%M')

            return get_message(
                "reminder_created",
                language,
                title=data['title'],
                due_date=display_due_date,
                priority=data.get('priority', 'medium').title(),
                type=data.get('reminder_type', 'general').title()
            )
            
        except Exception as e:
            print(f"❌ Error processing reminder message: {e}")
            return get_message("reminder_creation_failed", language)

    async def get_reminders(self, user_id: str, language: str, user_timezone: str, limit: int = 10) -> str:
        """Get user's pending reminders, formatted for their language and timezone."""
        try:
            reminders = await self.supabase_client.database.get_user_reminders(
                user_id, include_completed=False, limit=limit
            )
            
            if not reminders:
                return get_message("no_pending_reminders", language)
            
            # --- Also provide user's current time for relative date formatting ---
            try:
                user_tz = pytz.timezone(user_timezone)
            except pytz.UnknownTimeZoneError:
                user_tz = pytz.utc
            user_now_iso = datetime.now(user_tz).isoformat()

            reminders_data = []
            for reminder in reminders:
                reminders_data.append({
                    "title": reminder.title,
                    "due": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                    "priority": reminder.priority.value,
                    "type": reminder.reminder_type.value
                })
            
            format_prompts = {
                "en": f"""
                The user's current time is {user_now_iso}. Format this list of reminders:
                {json.dumps(reminders_data)}
                Use emojis, show relative dates (today, tomorrow, etc.), and organize by priority.
                """,
                "es": f"""
                La hora actual del usuario es {user_now_iso}. Formatea esta lista de recordatorios:
                {json.dumps(reminders_data)}
                Usa emojis, muestra fechas relativas (hoy, mañana, etc.) y organiza por prioridad.
                """,
                "pt": f"""
                A hora atual do usuário é {user_now_iso}. Formate esta lista de lembretes:
                {json.dumps(reminders_data)}
                Use emojis, mostre datas relativas (hoje, amanhã, etc.) e organize por prioridade.
                """
            }
            
            format_prompt = format_prompts.get(language, format_prompts["en"])
            response = await asyncio.to_thread(self.agent.run, format_prompt)
            formatted_list = str(response.content)
            
            return f"{get_message('pending_reminders_header', language)}\n\n{formatted_list}"
            
        except Exception as e:
            print(f"❌ Error getting reminders: {e}")
            return get_message("reminder_fetch_failed", language)
    
    async def get_due_soon(self, user_id: str, hours: int = 24) -> str:
        """Get reminders due soon"""
        try:
            due_reminders = await self.supabase_client.database.get_due_reminders(user_id, hours)
            
            if not due_reminders:
                return "✅ *No urgent reminders!*\n\nYou're on top of things! 🎯"
            
            message = f"⏰ *Reminders due in the next {hours} hours:*\n\n"
            
            for reminder in due_reminders:
                time_until = ""
                if reminder.due_datetime:
                    delta = reminder.due_datetime - datetime.now()
                    if delta.total_seconds() < 3600:  # Less than 1 hour
                        time_until = "⚡ Due very soon!"
                    elif delta.days == 0:
                        time_until = f"🕐 Due at {reminder.due_datetime.strftime('%I:%M %p')}"
                    else:
                        time_until = f"📅 Due {reminder.due_datetime.strftime('%m/%d at %I:%M %p')}"
                
                priority_emoji = {
                    "urgent": "🔥",
                    "high": "❗", 
                    "medium": "📌",
                    "low": "📝"
                }.get(reminder.priority.value, "📌")
                
                message += f"{priority_emoji} {reminder.title}\n{time_until}\n\n"
            
            return message
            
        except Exception as e:
            print(f"❌ Error getting due reminders: {e}")
            return "❌ Sorry, I couldn't check your due reminders right now."
    
    def _parse_due_date(self, date_str: str) -> Optional[datetime]:
        """Parse an ISO 8601 date/time string."""
        if not date_str:
            return None
        try:
            # The LLM is prompted to return ISO format, which is language-neutral
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            # Basic fallback for non-ISO formats (less reliable)
            print(f"⚠️ Could not parse date '{date_str}' with ISO format. Fallback may be inaccurate.")
            return None

    def _fallback_parse(self, message: str, language: str) -> Dict[str, Any]:
        """Fallback parsing when LLM doesn't return JSON, now with language support."""
        message_lower = message.lower()
        
        indicators = {
            "en": ['remind', 'remember', 'don\'t forget', 'schedule', 'appointment','meeting','task'],
            "es": ['recuérdame', 'recuerda', 'no olvides', 'agenda', 'cita'],
            "pt": ['lembre-me', 'lembre', 'não se esqueça', 'agende', 'compromisso','evento','marque','tarefa']
        }
        
        if not any(indicator in message_lower for indicator in indicators.get(language, indicators["en"])):
            return {"reminder_found": False}
        
        # This part remains basic, as it's a last resort.
        # A more advanced implementation would have language-specific keyword matching for priority/type.
        title = message
        priority = "medium"
        if "urgent" in message_lower or "urgente" in message_lower:
            priority = "urgent"
        
        return {
            "title": title,
            "priority": priority,
            "reminder_type": "general",
        }