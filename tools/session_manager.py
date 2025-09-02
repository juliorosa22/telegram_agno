import asyncio
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

class SessionManager:
    """In-memory session manager for user authentication"""
    
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_expired_sessions())
    
    def create_session(self, telegram_id: str, user_data: Dict[str, Any]) -> None:
        """Create or update user session"""
        self.sessions[telegram_id] = {
            **user_data,
            'last_activity': datetime.now(),
            'authenticated': True
        }
    
    def get_session(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Get user session if valid"""
        session = self.sessions.get(telegram_id)
        if not session:
            return None
        
        # Check if session expired
        if datetime.now() - session['last_activity'] > self.session_timeout:
            self.sessions.pop(telegram_id, None)
            return None
        
        # Update last activity
        session['last_activity'] = datetime.now()
        return session
    
    def is_authenticated(self, telegram_id: str) -> bool:
        """Check if user is authenticated"""
        session = self.get_session(telegram_id)
        return session is not None and session.get('authenticated', False)
    
    def invalidate_session(self, telegram_id: str) -> None:
        """Remove user session"""
        self.sessions.pop(telegram_id, None)
    
    async def _cleanup_expired_sessions(self) -> None:
        """Cleanup expired sessions periodically"""
        while True:
            try:
                now = datetime.now()
                expired_sessions = [
                    telegram_id for telegram_id, session in self.sessions.items()
                    if now - session['last_activity'] > self.session_timeout
                ]
                
                for telegram_id in expired_sessions:
                    self.sessions.pop(telegram_id, None)
                
                if expired_sessions:
                    print(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
                
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)
            except Exception as e:
                print(f"❌ Error in session cleanup: {e}")
                await asyncio.sleep(300)