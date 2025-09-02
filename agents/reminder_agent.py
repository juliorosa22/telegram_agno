from agno.agent import Agent
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Fix: Use package imports from __init__.py
from tools import Reminder, ReminderType, Priority

class ReminderAgent:
    """Specialized agent for handling reminders and tasks"""
    
    def __init__(self, supabase_client):
        self.supabase_client = supabase_client
        
        # Initialize Agno agent for reminder processing
        self.agent = Agent(
            name="ReminderProcessor",
            model="gpt-4",
            instructions="""
            You are a reminder and task management specialist.
            
            Your tasks:
            1. Parse natural language messages to extract reminder details
            2. Understand time expressions and convert to specific dates/times
            3. Categorize reminders by type and priority
            4. Generate helpful reminder summaries
            
            For reminder messages, extract:
            - Title/description of the reminder
            - Due date and time (parse natural language like "tomorrow at 3pm", "next Friday")
            - Priority level (urgent, high, medium, low)
            - Reminder type (task, event, deadline, habit, general)
            
            Always be helpful in scheduling and provide confirmation of created reminders.
            """
        )
    
    async def process_message(self, user_id: str, message: str) -> str:
        """Process a text message for reminder data"""
        try:
            # Use Agno to extract reminder details
            extraction_prompt = f"""
            Extract reminder details from this message: "{message}"
            
            Return a JSON object with:
            - title: string (main reminder text)
            - description: string (detailed description)
            - due_date: string (ISO format or null if no specific time)
            - priority: "urgent", "high", "medium", or "low"
            - reminder_type: "task", "event", "deadline", "habit", or "general"
            - confidence: number (0.0 to 1.0)
            
            If no reminder is found, return {{"reminder_found": false}}
            
            Examples:
            - "Remind me to call mom tomorrow at 3pm" -> due_date: tomorrow 3pm ISO format
            - "Don't forget doctor appointment next Friday" -> reminder_type: "event"
            - "Pay rent deadline is 1st of month" -> priority: "urgent", type: "deadline"
            """
            
            response = await self.agent.run(extraction_prompt)
            
            # Parse the JSON response
            try:
                data = json.loads(response)
            except:
                # Fallback parsing
                data = self._fallback_parse(message)
            
            if not data.get("reminder_found", True):
                return "🤔 I couldn't find reminder information in your message. Try something like 'Remind me to call doctor tomorrow at 2pm'."
            
            # Parse due date
            due_datetime = self._parse_due_date(data.get("due_date")) if data.get("due_date") else None
            
            # Create reminder
            reminder = Reminder(
                user_id=user_id,
                title=data["title"],
                description=data.get("description", data["title"]),
                source_platform="telegram",
                due_datetime=due_datetime,
                reminder_type=ReminderType(data.get("reminder_type", "general")),
                priority=Priority(data.get("priority", "medium")),
                tags=message  # Store original message as tag
            )
            
            # Save to database
            saved_reminder = await self.supabase_client.database.save_reminder(reminder)
            
            # Generate response
            due_text = ""
            if due_datetime:
                if due_datetime.date() == datetime.now().date():
                    due_text = f" for today at {due_datetime.strftime('%I:%M %p')}"
                elif due_datetime.date() == (datetime.now() + timedelta(days=1)).date():
                    due_text = f" for tomorrow at {due_datetime.strftime('%I:%M %p')}"
                else:
                    due_text = f" for {due_datetime.strftime('%B %d at %I:%M %p')}"
            
            priority_emoji = {
                "urgent": "🔥",
                "high": "❗",
                "medium": "📌",
                "low": "📝"
            }.get(data.get("priority", "medium"), "📌")
            
            return (
                f"✅ *Reminder created!*\n\n"
                f"{priority_emoji} *{data['title']}*{due_text}\n"
                f"📂 *Type:* {data.get('reminder_type', 'general').title()}\n"
                f"⚡ *Priority:* {data.get('priority', 'medium').title()}\n\n"
                f"I'll help you remember! 🎯"
            )
            
        except Exception as e:
            print(f"❌ Error processing reminder message: {e}")
            return "❌ Sorry, I couldn't create that reminder. Please try again with a clearer format."
    
    async def get_reminders(self, user_id: str, limit: int = 10) -> str:
        """Get user's pending reminders"""
        try:
            # Get reminders from database
            reminders = await self.supabase_client.database.get_user_reminders(
                user_id, include_completed=False, limit=limit
            )
            
            if not reminders:
                return "📋 *No pending reminders found!*\n\nYou're all caught up! 🎉"
            
            # Use Agno to format the reminder list nicely
            reminders_data = []
            for reminder in reminders:
                reminders_data.append({
                    "title": reminder.title,
                    "due": reminder.due_datetime.isoformat() if reminder.due_datetime else None,
                    "priority": reminder.priority.value,
                    "type": reminder.reminder_type.value
                })
            
            format_prompt = f"""
            Format this list of reminders in a clear, organized way:
            {json.dumps(reminders_data)}
            
            Use emojis, show relative dates (today, tomorrow, etc.), and organize by priority.
            Make it easy to scan and actionable.
            """
            
            formatted_list = await self.agent.run(format_prompt)
            
            return f"📋 *Your Pending Reminders*\n\n{formatted_list}"
            
        except Exception as e:
            print(f"❌ Error getting reminders: {e}")
            return "❌ Sorry, I couldn't fetch your reminders right now. Please try again later."
    
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
        """Parse natural language date/time expressions"""
        if not date_str:
            return None
        
        try:
            # Try parsing ISO format first
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass
        
        # Fallback to manual parsing
        date_str = date_str.lower().strip()
        now = datetime.now()
        
        # Handle relative dates
        if "today" in date_str:
            base_date = now.date()
        elif "tomorrow" in date_str:
            base_date = (now + timedelta(days=1)).date()
        elif "next week" in date_str:
            base_date = (now + timedelta(days=7)).date()
        elif "next month" in date_str:
            base_date = (now + timedelta(days=30)).date()
        else:
            base_date = now.date()
        
        # Extract time
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', date_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            ampm = time_match.group(3)
            
            if ampm == 'pm' and hour != 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            
            return datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
        
        # Default to 9 AM if no time specified
        return datetime.combine(base_date, datetime.min.time().replace(hour=9))
    
    def _fallback_parse(self, message: str) -> Dict[str, Any]:
        """Fallback parsing when Agno doesn't return JSON"""
        message_lower = message.lower()
        
        # Check if it's actually a reminder
        reminder_indicators = ['remind', 'remember', 'don\'t forget', 'schedule', 'appointment']
        if not any(indicator in message_lower for indicator in reminder_indicators):
            return {"reminder_found": False}
        
        # Extract title (remove reminder words)
        title = re.sub(r'\b(remind me to|remember to|don\'t forget to?|schedule)\b', '', message, flags=re.IGNORECASE).strip()
        
        # Determine priority
        priority = "medium"
        if any(word in message_lower for word in ['urgent', 'asap', 'important']):
            priority = "high"
        elif any(word in message_lower for word in ['deadline', 'due', 'must']):
            priority = "urgent"
        
        # Determine type
        reminder_type = "general"
        if any(word in message_lower for word in ['appointment', 'meeting', 'call']):
            reminder_type = "event"
        elif any(word in message_lower for word in ['pay', 'deadline', 'due']):
            reminder_type = "deadline"
        elif any(word in message_lower for word in ['task', 'do', 'complete']):
            reminder_type = "task"
        
        return {
            "title": title or message,
            "description": message,
            "priority": priority,
            "reminder_type": reminder_type,
            "confidence": 0.7
        }