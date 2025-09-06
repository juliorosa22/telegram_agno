from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
from contextlib import asynccontextmanager
import uvicorn
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv

# Import standardized messages
from messages import MESSAGES

# Import models
from models import (
    MessageRequest,
    TransactionResponse,
    ReminderResponse,
    SummaryRequest,
    StartRequest,
    UserCheckRequest,
    RegisterRequest,
    AuthCheckRequest
)

# Load environment
load_dotenv()

# Import existing components
from tools.supabase_tools import SupabaseClient
from agents.transaction_agent import TransactionAgent
from agents.reminder_agent import ReminderAgent
from agents.main_agent import MainAgent
from tools.session_manager import SessionManager

# Global services (initialized in lifespan)
supabase_client = None
transaction_agent = None
reminder_agent = None
main_agent = None
session_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global supabase_client, transaction_agent, reminder_agent, main_agent, session_manager
    
    # Startup
    try:
        print("🚀 Starting API services...")
        
        # Initialize Supabase client
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SECRET_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
        
        supabase_client = SupabaseClient(supabase_url, supabase_key)
        await supabase_client.connect()
        
        # Initialize agents
        transaction_agent = TransactionAgent(supabase_client)
        reminder_agent = ReminderAgent(supabase_client)
        main_agent = MainAgent(supabase_client)
        
        # Initialize session manager
        session_manager = SessionManager(session_timeout_minutes=30)
        
        print("✅ API services initialized successfully")
        
        # Yield control to the application
        yield
        
    except Exception as e:
        print(f"❌ Error initializing API services: {e}")
        raise
    
    finally:
        # Shutdown
        print("🛑 Shutting down API services...")
        
        if supabase_client:
            try:
                await supabase_client.disconnect()
                print("✅ Database disconnected")
            except Exception as e:
                print(f"❌ Error disconnecting database: {e}")
        
        print("🛑 API services stopped")

# Create FastAPI app with lifespan
app = FastAPI(
    title="OkanFit Assist AI API",
    description="Financial AI processing service",
    version="1.0.0",
    lifespan=lifespan  # Use the lifespan context manager
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints

@app.post("/api/v1/start")

async def handle_start(request: StartRequest):
    """Handle /start command with authentication handling"""
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")

        # NEW: Handle email-based auth if provided and not authenticated
        if request.email and not session_manager.is_authenticated(request.user_id):
            # Attempt auth via email
            auth_user = await supabase_client.get_user_by_email_auth(request.email)
            if auth_user:
                # Link Telegram and create session
                await supabase_client.link_telegram_to_auth_user(auth_user['user_id'], request.user_id, request.user_data)
                user_data = {
                    'user_id': auth_user['user_id'],
                    'email': request.email,
                    'first_name': auth_user.get('user_metadata', {}).get('first_name', request.user_data.get('first_name')),
                    'authenticated': True
                }
                session_manager.create_session(request.user_id, user_data)
                return {
                    "success": True,
                    "message": MESSAGES["welcome_authenticated"].format(first_name=user_data.get("first_name", "there"))
                }
            else:
                return {
                    "success": False,
                    "message": "❌ Email not found. Please use /register to create an account."
                }

        # This handle when the user has been redirected from the APP
        if request.args:
            try:
                # Check if user is authenticated for premium linking
                user_data = await require_authentication(request.user_id)
                
                # NEW: Check if already linked to prevent redundant linking
                supabase_user_id = request.args[0]
                existing_link = await supabase_client.get_user_by_telegram_id_auth(request.user_id)
                if existing_link and existing_link.get('user_id') == supabase_user_id:
                    # Already linked - skip linking and proceed to premium check
                    pass  # Proceed below
                else:
                    # Not linked - perform linking
                    await supabase_client.link_telegram_user(supabase_user_id, request.user_id)
                
                # Check premium status before generating payment link
                is_premium = await supabase_client.check_premium_status(supabase_user_id)
                if is_premium:
                    return {
                        "success": True,
                        "message": MESSAGES["welcome_authenticated"].format(first_name=user_data.get("first_name", "there"))
                    }
                else:
                    # Not premium - get credits and send payment link with credit info
                    credit_info = await supabase_client.database.get_user_credits(supabase_user_id)
                    credits_remaining = credit_info.get('credits', 0)
                    paypal_url = f"https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=YOUR_BUTTON_ID&custom={supabase_user_id}"
                    
                    message = MESSAGES["welcome_premium"].format(paypal_url=paypal_url)
                    message += f"\n\n💳 You have {credits_remaining} credits remaining for freemium features."
                    
                    return {
                        "success": True,
                        "message": message
                    }
            except HTTPException as e:
                if e.status_code == 401:
                    # User not authenticated for premium linking
                    return {
                        "success": True,
                        "message": MESSAGES["need_register_premium"]
                    }
                raise e
        
        # Handle regular /start command
        try:
            # Try to get authenticated user data
            user_data = await require_authentication(request.user_id)
            
            # User is authenticated - show personalized welcome
            first_name = user_data.get("first_name", request.user_data.get("first_name", "there"))
            return {
                "success": True,
                "message": MESSAGES["welcome_authenticated"].format(first_name=first_name)
            }
            
        except HTTPException as e:
            if e.status_code == 401:
                # User not authenticated - show registration prompt
                return {
                    "success": True,
                    "message": MESSAGES["welcome_unauthenticated"]
                }
            raise e
        
    except Exception as e:
        print(f"❌ Error in handle_start: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/help")
async def handle_help():
    """Handle /help command - No authentication required"""
    try:
        # Help is available to everyone, no authentication needed
        return {"success": True, "message": MESSAGES["help_message"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/route-message")
async def route_message(request: MessageRequest):
    """Route message through main agent - REQUIRES AUTHENTICATION + CREDITS"""
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # REPLACED: Use the new helper for auth and credits
        user_data, credit_result = await authenticate_and_check_credits(
            request.user_id, 'text_message', 1
        )
        
        # Process the message
        result = await main_agent.route_message(request.user_id, request.message, user_data)
        
        # Add credit info to response if not premium
        if not credit_result.get('is_premium', False):
            credits_remaining = credit_result.get('credits_remaining', 0)
            result += MESSAGES["credit_warning"].format(credits_remaining=credits_remaining)
            if credits_remaining <= 1:
                result += MESSAGES["credit_low"]
        
        return {"success": True, "message": result}
        
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 402, 503, etc.) without modification
        raise
    except Exception as e:
        # ❌ Only catch non-HTTP exceptions
        print(f"❌ Unexpected error in route_message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Transactions Endpoints

@app.post("/api/v1/process-receipt")
async def process_receipt(user_id: str, file: UploadFile = File(...)):
    """Process receipt image - REQUIRES AUTHENTICATION + CREDITS"""
    try:
        if not transaction_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # REPLACED: Use the new helper for auth and credits
        user_data, credit_result = await authenticate_and_check_credits(
            user_id, 'receipt_processing', 5
        )
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        result = await transaction_agent.process_receipt_image(user_id, temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Add credit info to response if not premium
        if not credit_result.get('is_premium', False):
            credits_remaining = credit_result.get('credits_remaining', 0)
            result += MESSAGES["credits_remaining"].format(credits_remaining=credits_remaining)
        
        return TransactionResponse(success=True, message=result)
        
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 402, 503, etc.)
        raise
    except Exception as e:
        # Clean up temp file on error
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        print(f"❌ Unexpected error in process_receipt: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/process-bank-statement")
async def process_bank_statement(user_id: str, file: UploadFile = File(...)):
    """Process bank statement PDF - REQUIRES AUTHENTICATION"""
    try:
        if not transaction_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # REPLACED: Use the new helper (no credits needed for this endpoint, so pass 0)
        user_data, _ = await authenticate_and_check_credits(user_id, 'bank_statement', 0)
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        result = await transaction_agent.process_bank_statement(user_id, temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        return TransactionResponse(success=True, message=result)
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 503, etc.)
        raise
    except Exception as e:
        # Clean up temp file on error
        if 'temp_path' in locals():
            try:
                os.unlink(temp_path)
            except:
                pass
        print(f"❌ Unexpected error in process_bank_statement: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/get-transaction-summary")
async def get_transaction_summary(request: SummaryRequest):
    """Get transaction summary - REQUIRES AUTHENTICATION"""
    try:
        if not transaction_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # UPDATED: Use the new helper for auth (no credits needed, so pass 0)
        user_data, _ = await authenticate_and_check_credits(request.user_id, 'summary', 0)
        
        result = await transaction_agent.get_summary(request.user_id, request.days)
        return {"success": True, "message": result}
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 503, etc.)
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_transaction_summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/v1/get-reminders")
async def get_reminders(user_id: str, limit: int = 10):
    """Get user reminders - REQUIRES AUTHENTICATION"""
    try:
        if not reminder_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # UPDATED: Use the new helper for auth (no credits needed, so pass 0)
        user_data, _ = await authenticate_and_check_credits(user_id, 'reminders', 0)
        
        result = await reminder_agent.get_reminders(user_id, limit)
        return {"success": True, "message": result}
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 503, etc.)
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_reminders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

#Auth endpoints
async def require_authentication(telegram_id: str) -> Dict[str, Any]:
    """Check if user is authenticated, return session data or raise exception"""
    if not session_manager.is_authenticated(telegram_id):
        # Try to authenticate from database via Supabase Auth
        user_result = await supabase_client.ensure_user_exists_auth(telegram_id, {})
        if not user_result.get("success", False) or not user_result.get("authenticated", False):
            raise HTTPException(status_code=401, detail=MESSAGES["user_not_registered"])
        # Create session with authenticated user data
        user_data = user_result["user_data"]
        session_manager.create_session(telegram_id, user_data)
        return user_data
    
    return session_manager.get_session(telegram_id)

# NEW: Reusable helper for authentication and credit checking
async def authenticate_and_check_credits(user_id: str, operation_type: str, credits_needed: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Unified function for authentication and credit consumption.
    Returns (user_data, credit_result).
    Raises HTTPException on failure.
    """
    # Step 1: Authenticate user
    user_data = await require_authentication(user_id)
    
    # Step 2: Check and consume credits
    credit_result = await check_and_consume_credits(user_id, operation_type, credits_needed)
    
    return user_data, credit_result

@app.post("/api/v1/register")
async def register_user(request: RegisterRequest):
    """Register new user using Supabase Auth"""
    try:
        if not supabase_client:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Check if telegram_id is already linked
        existing_user = await supabase_client.get_user_by_telegram_id_auth(request.telegram_id)
        if existing_user and existing_user.get('authenticated', False):
            return {
                "success": False, 
                "message": MESSAGES["telegram_already_registered"].format(email=existing_user.get('email', 'unknown'))
            }
        
        # Check if email already exists in Supabase Auth
        existing_auth_user = await supabase_client.get_user_by_email_auth(request.email)
        if existing_auth_user:
            # Email exists, try to link it to this Telegram account
            success = await supabase_client.link_telegram_to_auth_user(
                existing_auth_user['user_id'],
                request.telegram_id,
                {
                    'first_name': request.first_name,
                    'last_name': request.last_name,
                    'language_code': request.language_code
                }
            )
            
            if success:
                # Create session
                user_data = {
                    'user_id': existing_auth_user['user_id'],
                    'email': request.email,
                    'first_name': existing_auth_user['user_metadata'].get('first_name', request.first_name),
                    'last_name': existing_auth_user['user_metadata'].get('last_name', request.last_name),
                    'currency': 'USD',
                    'language': request.language_code,
                    'timezone': 'UTC',
                    'is_premium': False,
                    'premium_until': None,
                    'telegram_id': request.telegram_id,
                    'authenticated': True
                }
                session_manager.create_session(request.telegram_id, user_data)
                
                return {
                    "success": True,
                    "message": MESSAGES["link_success"].format(first_name=request.first_name),
                    "user_data": user_data
                }
            else:
                return {
                    "success": False,
                    "message": MESSAGES["link_failed"]
                }
        
        # Create new user in Supabase Auth
        auth_result = await supabase_client.sign_up_user_with_auth(
            email=request.email,
            password=None,  # Will generate random password
            user_metadata={
                'first_name': request.first_name,
                'last_name': request.last_name,
                'telegram_id': request.telegram_id,
                'language_code': request.language_code,
                'registration_source': 'telegram_bot'
            }
        )
        
        if not auth_result['success']:
            return {
                "success": False,
                "message": MESSAGES["registration_failed"].format(message=auth_result['message'])
            }
        
        # Link Telegram ID to the new auth user
        success = await supabase_client.link_telegram_to_auth_user(
            auth_result['user_id'],
            request.telegram_id,
            {
                'first_name': request.first_name,
                'last_name': request.last_name,
                'language_code': request.language_code
            }
        )
        
        if success:
            # Create session
            user_data = {
                'user_id': auth_result['user_id'],
                'email': request.email,
                'first_name': request.first_name,
                'last_name': request.last_name,
                'currency': 'USD',
                'language': request.language_code,
                'timezone': 'UTC',
                'is_premium': False,
                'premium_until': None,
                'telegram_id': request.telegram_id,
                'authenticated': True
            }
            session_manager.create_session(request.telegram_id, user_data)
            
            return {
                "success": True,
                "message": MESSAGES["registration_success"].format(first_name=request.first_name),
                "user_data": user_data
            }
        else:
            return {
                "success": False,
                "message": MESSAGES["registration_linking_failed"]
            }
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Update check_authentication endpoint
@app.post("/api/v1/check-auth")
async def check_authentication(request: AuthCheckRequest):
    """Check user authentication status"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        user_data = await require_authentication(request.telegram_id)
        return {
            "success": True,
            "authenticated": True,
            "user_data": user_data
        }
    except HTTPException as e:
        return {
            "success": False,
            "authenticated": False,
            "message": e.detail
        }

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "okanassist-ai",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "supabase_client": supabase_client is not None,
            "transaction_agent": transaction_agent is not None,
            "reminder_agent": reminder_agent is not None,
            "main_agent": main_agent is not None
        }
    }

# Add this helper function to api.py

async def check_and_consume_credits(user_id: str, operation_type: str, credits_needed: int) -> dict:
    """Check and consume credits before processing"""
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Try to consume credits
    result = await supabase_client.database.consume_credits(
        user_id, operation_type, credits_needed
    )
    
    if not result['success']:
        if result.get('error') == 'insufficient_credits':
            # Format friendly error message
            credits_available = result.get('credits_available', 0)
            credits_needed = result.get('credits_needed', 0)
            
            error_msg = MESSAGES["insufficient_credits"].format(
                credits_available=credits_available,
                credits_needed=credits_needed
            )
            
            raise HTTPException(status_code=402, detail=error_msg)  # 402 Payment Required
        else:
            raise HTTPException(status_code=400, detail=result.get('message', 'Credit operation failed'))
    
    return result

@app.get("/api/v1/credits/{user_id}")
async def get_credit_status(user_id: str):
    """Get user's credit status"""
    try:
        # Require authentication
        await require_authentication(user_id)
        
        credit_info = await supabase_client.database.get_user_credits(user_id)
        
        if credit_info.get('error'):
            raise HTTPException(status_code=404, detail=credit_info['error'])
        
        return {
            "success": True,
            "credits": credit_info['credits'],
            "is_premium": credit_info['is_premium'],
            "credits_reset_date": credit_info['credits_reset_date'],
            "premium_until": credit_info['premium_until']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting credit status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

def run_api():
    """Run the API server"""
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    run_api()