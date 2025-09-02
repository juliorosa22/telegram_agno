from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import uvicorn
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv

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

# Pydantic models for API
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

# API Endpoints
@app.post("/api/v1/start")
async def handle_start(request: StartRequest):
    """Handle /start command with authentication handling"""
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")

        # This handle when the user has been redirected from the APP
        if request.args:
            try:
                # Check if user is authenticated for premium linking
                user_data = await require_authentication(request.user_id)
                
                # Handle premium user linking
                supabase_user_id = request.args[0]
                await supabase_client.link_telegram_user(supabase_user_id, request.user_id)
                
                # Generate PayPal payment link
                paypal_url = f"https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=YOUR_BUTTON_ID&custom={supabase_user_id}"
                
                return {
                    "success": True,
                    "message": (
                        "🎉 *Welcome to OkanFit Personal Tracker!*\n\n"
                        "To unlock premium AI features, complete your payment:\n"
                        f"💳 [Pay with PayPal]({paypal_url})\n\n"
                        "After payment, you'll have access to:\n"
                        "🤖 AI-powered expense tracking\n"
                        "📊 Smart financial insights\n"
                        "⏰ Intelligent reminders\n"
                        "📈 Advanced analytics"
                    )
                }
            except HTTPException as e:
                if e.status_code == 401:
                    # User not authenticated for premium linking
                    return {
                        "success": True,
                        "message": (
                            "🔐 You need to register first to link premium features.\n\n"
                            "Type /register to create your account, then try again."
                        )
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
                "message": (
                    f"👋 *Hello {first_name}!*\n\n"
                    "I'm your AI financial assistant powered by Agno. I can help you:\n\n"
                    "💰 *Track expenses and income*\n"
                    "📸 *Process receipt photos*\n"
                    "📄 *Import bank statements*\n"
                    "⏰ *Manage reminders*\n"
                    "📊 *View financial summaries*\n\n"
                    "*Just send me messages like:*\n"
                    "• 'Spent $50 on groceries'\n"
                    "• 'Remind me to pay rent tomorrow'\n"
                    "• 'Show my expenses this month'\n"
                    "• Send a photo of your receipt\n\n"
                    "Type /help for more examples!"
                )
            }
            
        except HTTPException as e:
            if e.status_code == 401:
                # User not authenticated - show registration prompt
                return {
                    "success": True,
                    "message": (
                        "👋 *Welcome to OkanFit Personal Tracker!*\n\n"
                        "🤖 I'm your personal financial assistant powered by AI.\n\n"
                        "🔐 To get started, please register your account:\n"
                        "Type /register to create your account\n\n"
                        "✨ After registration, you can:\n"
                        "💰 Track expenses with natural language\n"
                        "📸 Process receipt photos automatically\n"
                        "⏰ Set smart reminders\n"
                        "📊 Get financial insights"
                    )
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
        help_message = """
🤖 *OkanFit Personal Tracker - Agno Powered*

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
/register - Create your account
/help - Show this help
/balance - Financial summary
/reminders - View reminders

*🔐 Authentication Required:*
Most features require registration. Use /register to get started!

*Powered by Agno Framework with GPT-4 Vision*
Just talk to me naturally - I understand! 🎉
        """
        
        return {"success": True, "message": help_message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/route-message")
async def route_message(request: MessageRequest):
    """Route message through main agent - REQUIRES AUTHENTICATION + CREDITS"""
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Require authentication before processing ANY message
        user_data = await require_authentication(request.user_id)
        
        # Check and consume credits for text message processing (1 credit)
        credit_result = await check_and_consume_credits(
            request.user_id, 
            'text_message', 
            1
        )
        
        # Process the message
        result = await main_agent.route_message(request.user_id, request.message, user_data)
        
        # Add credit info to response if not premium
        if not credit_result.get('is_premium', False):
            credits_remaining = credit_result.get('credits_remaining', 0)
            
            # Add credit warning if low
            if credits_remaining <= 5:
                result += f"\n\n💳 **Credits remaining: {credits_remaining}**"
                if credits_remaining <= 1:
                    result += "\n🚨 Almost out of credits! Type /upgrade for unlimited usage."
        
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
        
        # Require authentication before processing
        await require_authentication(user_id)
        
        # Check and consume credits for receipt processing (5 credits)
        credit_result = await check_and_consume_credits(
            user_id, 
            'receipt_processing', 
            5
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
            result += f"\n\n💳 Credits remaining: {credits_remaining}"
        
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
        
        # Require authentication before processing
        await require_authentication(user_id)
        
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
        
        # Require authentication before processing
        await require_authentication(request.user_id)
        
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
        
        # Require authentication before processing
        await require_authentication(user_id)
        
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
        #print(f"inside require auth:{user_result}")
        if not user_result.get("success", False) or not user_result.get("authenticated", False):
            #print("AQUIII correto")
            error_message = user_result.get("message", "User not registered. Please use /register command first.")
            raise HTTPException(status_code=401, detail=error_message)
        #print("veio parar aqui")        
        # Create session with authenticated user data
        user_data = user_result["user_data"]
        session_manager.create_session(telegram_id, user_data)
        return user_data
    
    return session_manager.get_session(telegram_id)

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
                "message": f"❌ This Telegram account is already registered with email: {existing_user.get('email', 'unknown')}"
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
                    "message": f"✅ Telegram account linked to existing email! Welcome back {request.first_name}!",
                    "user_data": user_data
                }
            else:
                return {
                    "success": False,
                    "message": "❌ Failed to link accounts. Please contact support."
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
                "message": f"❌ Registration failed: {auth_result['message']}"
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
                "message": f"✅ Registration successful! Welcome {request.first_name}!\n\n💡 You can manage your account at the Supabase dashboard.",
                "user_data": user_data
            }
        else:
            return {
                "success": False,
                "message": "❌ Registration failed during account linking. Please try again."
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
            
            error_msg = (
                f"❌ **Insufficient Credits**\n\n"
                f"💳 Available: {credits_available} credits\n"
                f"🔧 Needed: {credits_needed} credits\n\n"
                f"🎯 **Upgrade to Premium for unlimited usage!**\n"
                f"💎 Premium includes:\n"
                f"• ♾️ Unlimited AI processing\n"
                f"• 📊 Advanced analytics\n"
                f"• 🔄 Priority support\n"
                f"• 📱 Cross-platform sync\n\n"
                f"Type /upgrade to get premium access!"
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