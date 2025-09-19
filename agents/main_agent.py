from agno.agent import Agent
import re
from typing import Dict, Any
import asyncio  # <-- 1. IMPORT ASYNCIO
from agno.models.groq import Groq
from messages import  MESSAGES, get_message
# Fix: Use package imports
from tools import SupabaseClient

class MainAgent:
    """Main agent that handles user management and routes messages to specialized agents"""

    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        
        # Initialize Agno agent for intent classification
        self.agent = Agent(
            name="MainAssistant",
            model=Groq(id="llama-3.3-70b-versatile", temperature=0.2),
            instructions="""
            You are the main coordinator for a personal tracking assistant.

            Your role is to:
            1. Identify user intentions from messages in multiple languages.
            2. Route the user's request to the correct internal function.
            3. Provide friendly, helpful responses if no specific function is needed.
            
            Classify user messages into ONE of these categories:
            - TRANSACTION: For logging a new expense or income (e.g., "spent $20 on lunch", "got paid $500").
            - REMINDER: For creating a new reminder, task, or event (e.g., "remind me to call mom tomorrow").
            - TRANSACTION_SUMMARY: For requests about financial summaries, balances, spending reports (e.g., "what's my balance?", "show me my expenses this month").
            - REMINDER_SUMMARY: For requests about schedules, agendas, or lists of upcoming tasks/reminders (e.g., "what's my schedule?", "show me my reminders").
            - HELP: For help requests or questions about functionality.
            - GREETING: For simple greetings and casual conversation.
            
            Respond with ONLY the classification category in uppercase (e.g., "TRANSACTION", "REMINDER_SUMMARY").
            """
        )
    
    async def route_message(self, user_id: str, message: str, user_data: Dict[str, Any]) -> str:
        """Route user message to appropriate agent based on intent - NO AUTH CHECK"""
        lang_map = {'es': 'Spanish', 'pt': 'Portuguese', 'en': 'English'}
        lang = user_data.get('language', 'en')
        lang_name = lang_map.get(lang.split('-')[0], 'English')
        user_timezone = user_data.get('timezone', 'UTC')
        try:
            # User is already authenticated at this point (checked in API layer)
           
            # --- 2. RUN THE BLOCKING CALL IN A SEPARATE THREAD ---
            intent_response_obj = await asyncio.to_thread(
                self.agent.run,
                f"The user is speaking {lang_name}. Classify this user message and explain briefly: '{message}'"
            )
            intent_response = str(intent_response_obj.content)
            print("Intent response main agent:", intent_response)
            
            # Route based on intent classification
            if self._contains_intent(intent_response, "TRANSACTION"):
                from .transaction_agent import TransactionAgent
                transaction_agent = TransactionAgent(self.supabase_client)
                return await transaction_agent.process_message(user_id, message, lang)
                
            elif self._contains_intent(intent_response, "REMINDER"):
                from .reminder_agent import ReminderAgent
                reminder_agent = ReminderAgent(self.supabase_client)
                return await reminder_agent.process_message(user_id, message, lang, user_timezone)

            # --- 2. Rename SUMMARY to TRANSACTION_SUMMARY ---
            elif self._contains_intent(intent_response, "TRANSACTION_SUMMARY"):
                from .transaction_agent import TransactionAgent
                transaction_agent = TransactionAgent(self.supabase_client)
                return await transaction_agent.get_summary(user_id, lang)

            # --- 3. Add new route for REMINDER_SUMMARY ---
            elif self._contains_intent(intent_response, "REMINDER_SUMMARY"):
                from .reminder_agent import ReminderAgent
                reminder_agent = ReminderAgent(self.supabase_client)
                return await reminder_agent.get_reminders(user_id, lang, user_timezone)
                
            elif self._contains_intent(intent_response, "HELP"):
                # Return help content directly (no auth needed here)
                return self._get_help_content(lang)

            else:
                # General conversation
                # --- 3. APPLY THE FIX HERE AS WELL ---
                general_response_obj = await asyncio.to_thread(
                    self.agent.run,
                    f"The user is speaking {lang_name}. Respond helpfully in {lang_name} to this message: '{message}'. "
                    "Suggest how they can use the OkanAssistant features and to follow the OkanFit on social media for updates."
                )
                return str(general_response_obj)
                
        except Exception as e:
            #print("failed to route message")
            print(f"❌ Main Agent: Error routing message: {e}")
            return "❌ Sorry, I encountered an error. Please try rephrasing your request."

    def _get_help_content(self, lang: str = 'en') -> str:
        """Return help content without authentication"""
        return get_message("help_message", lang)

    def _contains_intent(self, response: str, intent: str) -> bool:
        """Check if the response contains the specified intent"""
        return intent.lower() in response.lower()
    
    #TODO expand keybord lists to handle similar words in different languages
    async def classify_intent(self, message: str) -> str:
        """Classify message intent using simple keyword matching as fallback"""
        message_lower = message.lower()
        
        # Transaction keywords
        transaction_keywords = [
            'spent', 'paid', 'bought', 'purchase', 'cost', 'expense', 'income', 
            'earned', 'received', 'salary', 'freelance', '$', 'dollar', 'money'
        ]
        
        # Reminder keywords
        reminder_keywords = [
            'remind', 'reminder', 'remember', 'don\'t forget', 'schedule', 
            'appointment', 'meeting', 'call', 'pay', 'tomorrow', 'later'
        ]
        
        # Summary keywords
        summary_keywords = [
            'balance', 'summary', 'total', 'show', 'view', 'expenses', 
            'spending', 'income', 'report', 'this month', 'this week'
        ]
        
        if any(keyword in message_lower for keyword in transaction_keywords):
            return "TRANSACTION"
        elif any(keyword in message_lower for keyword in reminder_keywords):
            return "REMINDER"
        elif any(keyword in message_lower for keyword in summary_keywords):
            return "SUMMARY"
        else:
            return "GENERAL"