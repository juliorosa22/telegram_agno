# core/models.py - Supabase integrated version
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal
from enum import Enum

class ReminderType(Enum):
    """Reminder type enumeration"""
    TASK = "task"
    EVENT = "event"
    DEADLINE = "deadline"
    HABIT = "habit"
    GENERAL = "general"

class Priority(Enum):
    """Priority level enumeration"""
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class PlatformType(Enum):
    """Platform type enumeration"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    MOBILE_APP = "mobile_app"
    WEB_APP = "web_app"

class TransactionType(Enum):
    """Transaction type enumeration"""
    EXPENSE = "expense"
    INCOME = "income"

@dataclass
class Transaction:
    """Transaction model - handles both expenses and income"""
    user_id: str  # Supabase auth.users.id (UUID)
    amount: Decimal
    description: str
    category: str
    transaction_type: str   # 'expense' or 'income'
    original_message: str
    source_platform: str = PlatformType.WEB_APP.value
    merchant: Optional[str] = None
    date: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Enhanced fields
    receipt_image_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None  # {'lat': x, 'lng': y}
    is_recurring: bool = False
    recurring_pattern: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence_score: Optional[float] = None  # For ML-parsed transactions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'description': self.description,
            'category': self.category,
            'transaction_type': self.transaction_type,
            'original_message': self.original_message,
            'source_platform': self.source_platform,
            'merchant': self.merchant,
            'date': self.date.isoformat() if self.date else None,
            'receipt_image_url': self.receipt_image_url,
            'location': self.location,
            'is_recurring': self.is_recurring,
            'recurring_pattern': self.recurring_pattern,
            'tags': self.tags,
            'confidence_score': self.confidence_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expense(self) -> bool:
        """Check if this is an expense"""
        return self.transaction_type == TransactionType.EXPENSE.value
    
    def is_income(self) -> bool:
        """Check if this is income"""
        return self.transaction_type == TransactionType.INCOME.value

@dataclass
class Reminder:
    """Reminder model - updated for Supabase"""
    user_id: str  # Supabase auth.users.id (UUID)
    title: str
    description: str
    source_platform: str = PlatformType.WEB_APP.value
    due_datetime: Optional[datetime] = None
    reminder_type: str = ReminderType.GENERAL.value
    priority: str = Priority.MEDIUM.value
    is_completed: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    notification_sent: bool = False
    snooze_until: Optional[datetime] = None
    tags: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Enhanced fields
    location_reminder: Optional[Dict[str, Any]] = None
    attachments: List[str] = field(default_factory=list)
    assigned_to_platforms: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'source_platform': self.source_platform,
            'due_datetime': self.due_datetime.isoformat() if self.due_datetime else None,
            'reminder_type': self.reminder_type,
            'priority': self.priority,
            'is_completed': self.is_completed,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'notification_sent': self.notification_sent,
            'snooze_until': self.snooze_until.isoformat() if self.snooze_until else None,
            'tags': self.tags,
            'location_reminder': self.location_reminder,
            'attachments': self.attachments,
            'assigned_to_platforms': self.assigned_to_platforms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def is_overdue(self) -> bool:
        """Check if reminder is overdue"""
        if not self.due_datetime or self.is_completed:
            return False
        return datetime.now() > self.due_datetime

    def get_formatted_summary(self) -> str:
        """Get formatted summary for display"""
        status_emoji = "✅" if self.is_completed else ("⚠️" if self.is_overdue() else "⏰")
        priority_indicator = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(self.priority, "🟡")
        
        due_text = ""
        if self.due_datetime:
            due_text = f" (Due: {self.due_datetime.strftime('%m/%d %H:%M')})"
        
        return f"{status_emoji} {priority_indicator} {self.title}{due_text}"

    def get_status_text(self) -> str:
        """Get status text for the reminder"""
        if self.is_completed:
            return "completed"
        elif self.is_overdue():
            return "overdue"
        elif self.due_datetime and self.due_datetime.date() == datetime.now().date():
            return "due_today"
        elif self.due_datetime and self.due_datetime.date() == (datetime.now() + timedelta(days=1)).date():
            return "due_tomorrow"
        else:
            return "pending"

@dataclass
class TransactionSummary:
    """Summary of user transactions over a period"""
    user_id: str
    period_days: int
    total_income: float = 0.0
    total_expenses: float = 0.0
    income_count: int = 0
    expense_count: int = 0
    total_transactions: int = 0
    expense_categories: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "period_days": self.period_days,
            "total_income": self.total_income,
            "total_expenses": self.total_expenses,
            "income_count": self.income_count,
            "expense_count": self.expense_count,
            "total_transactions": self.total_transactions,
            "expense_categories": self.expense_categories
        }

@dataclass 
class ReminderSummary:
    """Summary of user reminders"""
    total_count: int
    completed_count: int
    pending_count: int
    overdue_count: int
    due_today_count: int
    due_tomorrow_count: int
    by_priority: Dict[str, int]
    by_type: Dict[str, int]
    period_days: int
    
    def get_completion_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return (self.completed_count / self.total_count) * 100

    def has_urgent_items(self) -> bool:
        """Check if there are any urgent priority items"""
        return self.by_priority.get('urgent', 0) > 0

@dataclass
class UserActivity:
    """Overall user activity summary (Supabase version)"""
    user_id: str  # Supabase auth.users.id
    transaction_summary: Optional[TransactionSummary] = None
    reminder_summary: Optional[ReminderSummary] = None
    last_transaction_date: Optional[datetime] = None
    last_reminder_date: Optional[datetime] = None
    total_interactions: int = 0
    
    def is_active_user(self, days: int = 7) -> bool:
        cutoff = datetime.now() - timedelta(days=days)
        return (
            (self.last_transaction_date and self.last_transaction_date > cutoff) or
            (self.last_reminder_date and self.last_reminder_date > cutoff)
        )

@dataclass
class UserSettings:
    """User settings for currency, language, timezone, and premium status"""
    user_id: str  # Supabase auth.users.id (UUID)
    currency: str = "USD"
    language: str = "en"
    timezone: str = "UTC"
    is_premium: bool = False
    telegram_id: Optional[str] = None
    name: Optional[str] = None
    premium_until: Optional[datetime] = None
    freemium_credits: Optional[int] = None
    credits_reset_date: Optional[datetime] = None
    last_bot_interaction: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "currency": self.currency,
            "language": self.language,
            "timezone": self.timezone,
            "is_premium": self.is_premium,
            "telegram_id": self.telegram_id,
            "premium_until": self.premium_until.isoformat() if self.premium_until else None,
            "freemium_credits": self.freemium_credits,
            "credits_reset_date": self.credits_reset_date.isoformat() if self.credits_reset_date else None,
            "last_bot_interaction": self.last_bot_interaction.isoformat() if self.last_bot_interaction else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def is_premium_active(self) -> bool:
        """Check if premium subscription is currently active"""
        if not self.is_premium:
            return False
        if self.premium_until is None:
            return True  # Lifetime premium
        return datetime.now() < self.premium_until
    
    def has_credits(self) -> bool:
        """Check if user has freemium credits available"""
        if self.freemium_credits is None:
            return False
        if self.credits_reset_date and datetime.now() >= self.credits_reset_date:
            return True  # Credits should be reset
        return self.freemium_credits > 0
    

    def get_premium_status(self) -> str:
        """Get human-readable premium status"""
        if not self.is_premium:
            return "Free"
        if self.premium_until is None:
            return "Premium (Lifetime)"
        if self.is_premium_active():
            return f"Premium (until {self.premium_until.strftime('%Y-%m-%d')})"
        else:
            return "Premium (Expired)"

@dataclass
class Payment:
    """Payment model for subscription management"""
    user_id: str  # Supabase auth.users.id (UUID)
    provider: str  # 'paypal' or 'mercadopago'
    amount: Decimal
    currency: str
    status: str  # 'pending', 'success', 'failed', 'cancelled'
    transaction_id: Optional[str] = None  # External payment provider transaction ID
    subscription_id: Optional[str] = None  # Provider subscription ID
    valid_until: Optional[datetime] = None
    id: Optional[str] = None  # UUID primary key
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'provider': self.provider,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'transaction_id': self.transaction_id,
            'subscription_id': self.subscription_id,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_successful(self) -> bool:
        """Check if payment was successful"""
        return self.status == 'success'
    
    def is_pending(self) -> bool:
        """Check if payment is pending"""
        return self.status == 'pending'
    
    def is_failed(self) -> bool:
        """Check if payment failed"""
        return self.status in ['failed', 'cancelled']
    
    def get_status_emoji(self) -> str:
        """Get emoji representation of payment status"""
        status_emojis = {
            'pending': '⏳',
            'success': '✅',
            'failed': '❌',
            'cancelled': '🚫'
        }
        return status_emojis.get(self.status, '❓')
    
    def get_provider_name(self) -> str:
        """Get formatted provider name"""
        provider_names = {
            'paypal': 'PayPal',
            'mercadopago': 'MercadoPago'
        }
        return provider_names.get(self.provider, self.provider.title())
    
    def is_subscription(self) -> bool:
        """Check if this is a subscription payment"""
        return self.subscription_id is not None

# Transaction categories for intelligent classification
TRANSACTION_CATEGORIES = {
    # Expense categories
     "expense": {
        "Essentials": [
          "rent", "mortgage", "utility", "electric", "water", "gas", "fuel", "groceries", "grocery", "food", "insurance", "phone", "internet", "healthcare", "doctor", "pharmacy", "medicine", "medical", "dentist"
        ],
        "Food & Dining": ["restaurant", "coffee", "lunch", "dinner", "takeout", "starbucks", "mcdonalds"],
        "Transportation": ["uber", "taxi", "parking", "bus", "train", "flight", "lyft"],
        "Shopping": ["amazon", "store", "clothes", "electronics", "book", "shopping", "mall"],
        "Entertainment": ["movie", "game", "concert", "netflix", "spotify", "streaming", "music"],
        "Utilities": ["utility"],
        "Healthcare": ["doctor", "hospital", "pharmacy", "medicine", "dentist", "medical"],  # Also in Essentials
        "Travel": ["hotel", "airbnb", "vacation", "trip", "booking", "travel"],
        "Education": ["school", "course", "tuition", "book", "education", "training"]
      },
    # Income categories
    "income": {
        "Salary": ["salary", "paycheck", "wage", "income", "pay"],
        "Freelance": ["freelance", "contract", "consulting", "gig", "project"],
        "Business": ["business", "revenue", "sales", "profit", "commission"],
        "Investment": ["dividend", "interest", "stock", "crypto", "investment", "return"],
        "Gift": ["gift", "bonus", "present", "reward", "prize"],
        "Refund": ["refund", "return", "reimbursement", "cashback"],
        "Rental": ["rent", "rental", "lease", "property"],
        "Other": []
    }
}

def categorize_transaction(description: str, transaction_type: str) -> str:
    """
    Categorize transaction based on description keywords and type
    
    Args:
        description: Transaction description text
        transaction_type: 'expense' or 'income'
        
    Returns:
        Category name as string
    """
    if not description or transaction_type not in TRANSACTION_CATEGORIES:
        return "Other"
    
    description_lower = description.lower()
    categories = TRANSACTION_CATEGORIES[transaction_type]
    
    # Score each category based on keyword matches
    category_scores = {}
    for category, keywords in categories.items():
        if keywords:  # Skip empty keyword lists (like "Other")
            score = sum(1 for keyword in keywords if keyword in description_lower)
            if score > 0:
                category_scores[category] = score
    
    # Return category with highest score or "Other" if no matches
    if category_scores:
        return max(category_scores.keys(), key=lambda k: category_scores[k])
    
    return "Other"

def get_all_categories(transaction_type: str) -> List[str]:
    """Get list of all available categories for a transaction type"""
    if transaction_type in TRANSACTION_CATEGORIES:
        return list(TRANSACTION_CATEGORIES[transaction_type].keys())
    return ["Other"]