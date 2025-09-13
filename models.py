from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class MessageRequest(BaseModel):
    user_id: str
    message: str
    user_data: Optional[Dict[str, Any]] = {}

class TransactionResponse(BaseModel):
    success: bool
    message: str
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None

class ReminderResponse(BaseModel):
    success: bool
    message: str
    reminder_id: Optional[str] = None

class SummaryRequest(BaseModel):
    user_id: str
    days: int = 30

class StartRequest(BaseModel):
    user_id: str
    user_data: Dict[str, Any]
    args: Optional[List[str]] = None
    email: Optional[str] = None  # NEW

class UserCheckRequest(BaseModel):
    telegram_id: str
    user_data: Dict[str, Any]

class RegisterRequest(BaseModel):
    telegram_id: str
    email: str
    first_name: str
    last_name: Optional[str] = None
    language_code: str = "en"

class AuthCheckRequest(BaseModel):
    telegram_id: str
    user_name: Optional[str] = None
    supabase_user_id: Optional[str] = None


