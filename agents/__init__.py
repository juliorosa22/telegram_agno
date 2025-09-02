"""
Agno-powered agents for the Telegram financial assistant bot.

This package contains specialized agents that handle different aspects
of financial tracking and personal assistance:

- MainAgent: Routes messages and handles user management
- TransactionAgent: Processes financial transactions and receipts
- ReminderAgent: Manages reminders and scheduling
"""

from .main_agent import MainAgent
from .transaction_agent import TransactionAgent
from .reminder_agent import ReminderAgent

__all__ = [
    'MainAgent',
    'TransactionAgent', 
    'ReminderAgent'
]

# Version info
__version__ = '1.0.0'
__author__ = 'OkanFit Team'
__description__ = 'Agno-powered financial assistant agents'