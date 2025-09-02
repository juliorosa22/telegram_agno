from agno.agent import Agent
import re
from typing import Dict, Any

# Fix: Use package imports
from tools import Transaction, Reminder  # Import from package __init__.py

class MainAgent:
    """Main agent that handles user management and routes messages to specialized agents"""
    
    def __init__(self, supabase_client):
        self.supabase_client = supabase_client
        
        # Initialize Agno agent for intent classification
        self.agent = Agent(
            name="MainAssistant",
            model="groq/llama-3.1-70b",
            instructions="""
            You are the main coordinator for a personal tracking assistant.

            Your role is to:
            1. Identify user intentions from messages
            2. Route to appropriate specialized agents
            3. Provide friendly, helpful responses
            
            Classify user messages into these categories:
            - TRANSACTION: Messages about expenses, income, purchases, payments
            - REMINDER: Messages about reminders, tasks, scheduling, notifications  
            - SUMMARY: Requests for summaries, balances, reports
            - HELP: Help requests, questions about functionality
            - GREETING: Greetings, casual conversation
            
            Respond with the classification and a brief explanation.
            """
        )
    
    async def route_message(self, user_id: str, message: str, user_data: Dict[str, Any]) -> str:
        """Route user message to appropriate agent based on intent - NO AUTH CHECK"""
        try:
            # User is already authenticated at this point (checked in API layer)
            
            # Classify message intent using Agno
            intent_response = await self.agent.run(
                f"Classify this user message and explain briefly: '{message}'"
            )
            
            # Route based on intent classification
            if self._contains_intent(intent_response, "TRANSACTION"):
                from .transaction_agent import TransactionAgent
                transaction_agent = TransactionAgent(self.supabase_client)
                return await transaction_agent.process_message(user_id, message)
                
            elif self._contains_intent(intent_response, "REMINDER"):
                from .reminder_agent import ReminderAgent
                reminder_agent = ReminderAgent(self.supabase_client)
                return await reminder_agent.process_message(user_id, message)
                
            elif self._contains_intent(intent_response, "SUMMARY"):
                from .transaction_agent import TransactionAgent
                transaction_agent = TransactionAgent(self.supabase_client)
                return await transaction_agent.get_summary(user_id)
                
            elif self._contains_intent(intent_response, "HELP"):
                # Return help content directly (no auth needed here)
                return self._get_help_content()
                
            else:
                # General conversation
                return await self.agent.run(
                    f"Respond helpfully to this message about financial tracking: '{message}'. "
                    "Suggest how they can use the assistant for their financial needs."
                )
                
        except Exception as e:
            print(f"❌ Error routing message: {e}")
            return "❌ Sorry, I encountered an error. Please try rephrasing your request."
    
    def _get_help_content(self) -> str:
        """Return help content without authentication"""
        return """
🤖 *OkanAssist AI - Agno Powered*

*💰 Expense Tracking:*
• "Spent $25 on lunch at McDonald's"
• "Paid $1200 rent"
• "Bought groceries for $85"
• 📸 Send receipt photos for automatic processing

*💵 Income Tracking:*
• "Received $3000 salary"
• "Got $50 freelance payment"
• "Earned $200 from side project"

*⏰ Reminders:*
• "Remind me to pay bills tomorrow at 3pm"
• "Set reminder: doctor appointment next Friday"
• "Don't forget to call mom this weekend"

*📊 Financial Views:*
• /balance - View financial summary
• /reminders - Show pending reminders
• "Show expenses this week"
• "What's my spending pattern?"

*📄 Document Processing:*
• Send PDF bank statements for bulk import
• Receipt photos are automatically processed
• Invoices and bills can be analyzed

*🎯 Commands:*
/start - Get started
/help - Show this help
/balance - Financial summary
/reminders - View reminders

*Powered by Agno Framework with GPT-4 Vision*
Just talk to me naturally - I understand! 🎉
        """
    
    def _contains_intent(self, response: str, intent: str) -> bool:
        """Check if the response contains the specified intent"""
        return intent.lower() in response.lower()
    
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