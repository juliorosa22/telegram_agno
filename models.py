from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class MessageRequest(BaseModel):
    user_id: str
    message: str
    user_data: Optional[Dict[str, Any]] = {}
    language_code: Optional[str]= 'en'  # NEW

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
    language_code: Optional[str]= 'en'  # NEW

class UserCheckRequest(BaseModel):
    telegram_id: str
    user_data: Dict[str, Any]

class RegisterRequest(BaseModel):
    telegram_id: str
    email: str
    name: str #includes first name and last name
    language_code: Optional[str] = "en"
    timezone: Optional[str] = "UTC"
    currency: Optional[str] = "USD"

class AuthCheckRequest(BaseModel):
    telegram_id: str
    user_name: Optional[str] = None
    supabase_user_id: Optional[str] = None
    language: Optional[str] = "en"
    timezone: Optional[str] = "UTC"
    currency: Optional[str] = "USD"

class UpgradeRequest(BaseModel):
    user_id: str

