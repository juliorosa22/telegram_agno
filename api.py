from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles # <-- 1. Import StaticFiles
from fastapi.templating import Jinja2Templates # <-- 2. Import Jinja2Templates
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
from messages import MESSAGES, get_message

# Import models
from models import (
    MessageRequest,
    TransactionResponse,
    ReminderResponse,
    SummaryRequest,
    StartRequest,
    UserCheckRequest,
    RegisterRequest,
    AuthCheckRequest,
    UpgradeRequest
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

# Create FastAPI app
app = FastAPI(
    title="OkanFit Assist AI API",
    description="Financial AI processing service",
    version="1.0.0",
    lifespan=lifespan
)

# --- 3. Mount the static directory and configure templates ---
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. Create the root endpoint to serve the website ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main landing page."""
    return templates.TemplateResponse("index.html", {"request": request})

# You can add placeholder pages for privacy and terms to satisfy Stripe
@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return "<h1>Privacy Policy</h1><p>Details coming soon.</p>"

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service(request: Request):
    return "<h1>Terms of Service</h1><p>Details coming soon.</p>"


# API Endpoints
@app.get("/api/v1/auth/confirm", response_class=HTMLResponse)
async def handle_email_confirmation():
    """
    Serves a simple HTML page for when a user successfully confirms their email.
    This URL should be set as the confirmation redirect in Supabase Auth settings.
    """
    # Use the URL from the new static files mount
    logo_url = "/static/images/okan_assist_upscale.png" 
    download_url = os.getenv("APP_DOWNLOAD_URL", "https://play.google.com/store/apps/details?id=com.okanassist")

    html_content = MESSAGES["registration_html_success"].format(
        logo_url=logo_url,
        download_url=download_url
    )
    return HTMLResponse(content=html_content)


@app.post("/api/v1/start")
async def handle_start(request: StartRequest):
    """Handle /start command with authentication handling"""
    lang = request.language_code
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        user_data = None
        if not session_manager.is_authenticated(request.user_id):
            # NEW: Use centralized authentication
            auth_request = AuthCheckRequest(
                telegram_id=request.user_id,
                user_name=request.user_data.get("first_name", None),
                supabase_user_id=request.args[0] if request.args else None
            )
            print(f"🔍 Checking auth for /start: {auth_request.user_name}")
            auth_result = await check_authentication(auth_request)
            print(f"🔍 Auth result for /start: {auth_result}")
            if not auth_result.get("authenticated", False):
                if auth_result.get("must_register", False):
                    return {
                        "success": True,
                        "message": get_message("welcome_unauthenticated", lang)
                    }
                else:
                    return {
                        "success": False,
                        "message": auth_result.get("message", "Authentication failed")
                    }
        

        user_data = session_manager.get_session(request.user_id)

        # Handle regular /start command
        try:
            # User is authenticated - show personalized welcome
            first_name = user_data.get("first_name", request.user_data.get("first_name", "there"))
            return {
                "success": True,
                "message": get_message("welcome_authenticated", lang, first_name=first_name)
            }
            
        except Exception as e:
            print(f"❌ Error in regular start: {e}")
            return {
                "success": False,
                "message": "❌ Welcome! There was an issue connecting to the service."
            }
        
    except Exception as e:
        print(f"❌ Error in handle_start: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/help")
async def handle_help(language_code: Optional[str] = 'en'):
    """Handle /help command - No authentication required"""
    try:
        # Help is available to everyone, no authentication needed
        return {"success": True, "message": get_message("help_message", language_code)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/upgrade")
async def handle_upgrade(request: UpgradeRequest):
    """Handles the premium upgrade request and generates a payment link."""
    try:
        # 1. Authenticate the user and get their data
        auth_request = AuthCheckRequest(telegram_id=request.user_id)
        user_data = await get_user_data(auth_request)

        # 2. Check if the user is already premium
        if user_data.get("is_premium"):
            return {
                "success": False,
                "message": "✅ You are already a Premium user! You have unlimited access to all features."
            }

        # 3. Generate the payment link
        payment_details = await supabase_client.create_upgrade_link(user_data)

        if not payment_details.get("success"):
            raise HTTPException(status_code=500, detail="Could not generate payment link.")

        # 4. Format the response message for the user
        message = MESSAGES["upgrade_to_premium"].format(
            first_name=user_data.get("first_name", "there"),
            stripe_url=payment_details["stripe_url"] # <-- 1. Use stripe_url
        )
        
        return {"success": True, "message": message}

    except HTTPException as e:
        if e.status_code == 401:
            # User is not registered, re-raise the exception for the bot handler
            raise
        # For other HTTP exceptions, return a structured error
        return {"success": False, "message": e.detail}
    except Exception as e:
        print(f"❌ Error in handle_upgrade: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your upgrade request.")



@app.post("/api/v1/webhooks/stripe")
async def handle_stripe_webhook(request: Request):
    """Handles incoming webhooks from Stripe to confirm payments."""
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Service not ready")

    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        # Pass the raw payload and signature header to the handler
        success = await supabase_client.handle_stripe_webhook(payload, sig_header)
        
        if success:
            # Acknowledged and processed successfully
            return JSONResponse(content={"status": "success"}, status_code=200)
        else:
            # Acknowledged but failed to process
            return JSONResponse(content={"status": "failed"}, status_code=400)

    except Exception as e:
        print(f"❌ Error processing Stripe webhook: {e}")
        # Return an error to Stripe so it knows the webhook failed
        return JSONResponse(content={"status": "error"}, status_code=500)


@app.post("/api/v1/route-message")
async def route_message(request: MessageRequest):
    """Route message through main agent - REQUIRES AUTHENTICATION + CREDITS"""
    lang = request.language_code
    try:
        if not main_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=request.user_id))
        supabase_id = user_data.get('user_id', None)
        telegram_id = request.user_id
        print("user_data:", user_data)
        # Step 2: Consume credits (since auth is now verified)
        credit_result = await check_and_consume_credits(supabase_id, 'text_message', 1, user_data)
        print("credit_result:", credit_result)
        user_data.setdefault('language', lang)  # Ensure language is set in user_data
        # Step 3: Process the message
        if credit_result["success"]:
            result = await main_agent.route_message(supabase_id, request.message, user_data)
            # Add credit info to response if not premium
            if not credit_result.get('is_premium', False):
                credits_remaining = credit_result.get('credits_remaining', 0)
                result += get_message("credit_warning", lang, credits_remaining=credits_remaining)
                if credits_remaining <= 1:
                    result += get_message("credit_low", lang)

            return {"success": True, "message": result}
        else:
           
            return {"success": False, "message": credit_result.get("message")}
        
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 402, 503, etc.) without modification
        raise
    except Exception as e:
        # ❌ Only catch non-HTTP exceptions
        print(f"❌ Unexpected error in route_message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

####### Transactions Endpoints

@app.post("/api/v1/process-receipt")
async def process_receipt(user_id: str, file: UploadFile = File(...)):
    """Process receipt image - REQUIRES AUTHENTICATION + CREDITS"""
    try:
        if not transaction_agent:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=user_id))
        supabase_id = user_data.get('user_id', None)
        # Step 2: Consume credits (since auth is now verified)
        credit_result = await check_and_consume_credits(supabase_id, 'receipt_processing', 5, user_data)

        # Step 3: Process the receipt
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        result = await transaction_agent.process_receipt_image(supabase_id, temp_path)

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
        
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=user_id))
        supabase_id = user_data.get('user_id', None)
        # Step 2: Consume credits (since auth is now verified) - Note: 0 credits for bank statement
        credit_result = await check_and_consume_credits(supabase_id, 'bank_statement', 0, user_data)

        # Step 3: Process the bank statement
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        result = await transaction_agent.process_bank_statement(supabase_id, temp_path)

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
        
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=request.user_id))
        supabase_id = user_data.get('user_id', None)
        # Step 2: Process the summary (no credits needed)
        result = await transaction_agent.get_summary(supabase_id, request.days)
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
        
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=user_id))
        supabase_id = user_data.get('user_id', None)
        # Step 2: Process the reminders (no credits needed)
        result = await reminder_agent.get_reminders(supabase_id, limit)
        return {"success": True, "message": result}
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 503, etc.)
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_reminders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
            success = await supabase_client.link_telegram_user( 
                existing_auth_user['user_id'],
                request.telegram_id,
                f"{request.first_name} {request.last_name}",
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
        success = await supabase_client.link_telegram_user(
            auth_result['user_id'],
            request.telegram_id,
            f"{request.first_name} {request.last_name}"
        )

               
        
        if success.get("success"):
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


##### Others endpoints

@app.get("/api/v1/profile")
async def get_profile(user_id: str):
    """Get user profile - REQUIRES AUTHENTICATION"""
    try:
        # Step 1: Get user data using centralized helper
        user_data = await get_user_data(AuthCheckRequest(telegram_id=user_id))
        
        # Step 2: Format and return profile (no credits needed)
        profile_message = (
            f"👤 *Your Profile*\n\n"
            f"📧 Email: {user_data.get('email', 'Not set')}\n"
            f"👤 Name: {user_data.get('first_name', 'Unknown')} {user_data.get('last_name', '')}\n"
            f"🌐 Language: {user_data.get('language', 'en')}\n"
            f"💰 Currency: {user_data.get('currency', 'USD')}\n"
            f"⏰ Timezone: {user_data.get('timezone', 'UTC')}\n"
            f"⭐ Premium: {'Yes' if user_data.get('is_premium') else 'No'}\n"
        )
        
        return {"success": True, "message": profile_message}
    except HTTPException:
        # ✅ Re-raise HTTPExceptions (401, 503, etc.)
        raise
    except Exception as e:
        print(f"❌ Unexpected error in get_profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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


##### HELPER FUNCTIONS #####
# Centralized authentication function
async def check_authentication(request: AuthCheckRequest) -> Dict[str, Any]:
    """Centralized user authentication flow"""
    try:
        # First, check if the telegram_id is linked to a supabase user
        user_data = await supabase_client.get_user_by_telegram_id_auth(request.telegram_id)
        #print(f"🔍 Initial user_data in check_authentication: {user_data}")
        if user_data is None:
            # No linked telegram user
            if request.supabase_user_id:
                
                print("Trying to link:",request)
                # Try to authenticate from database via Supabase Auth
                # Verify the Supabase ID exists in the auth table and try to link
                # Here the link still might fail if the supabase_user_id is invalid
                result = await supabase_client.link_telegram_user(request.supabase_user_id, request.telegram_id, request.user_name)
                if result.get("success"):
                    user_data = await supabase_client.get_user_by_telegram_id_auth(request.telegram_id)
                    is_authenticated = user_data.get("authenticated", False) if user_data else False
                    if is_authenticated and user_data:
                        # Validate and complete user_data if needed
                        user_data = await _validate_and_complete_user_data(user_data, request.telegram_id)
                        # Create session
                        session_manager.create_session(request.telegram_id, user_data)
                    return {
                        "success": is_authenticated,
                        "authenticated": is_authenticated,
                        "user_data": user_data if is_authenticated else None,
                        "message": MESSAGES["link_success"].format(first_name=user_data.get("name", "there") if is_authenticated else MESSAGES["failed_retrieve_user_data"])
                    }
                else:
                    # Linking failed
                    return {
                        "success": False,
                        "authenticated": False,
                        "user_data": None,
                        "message": MESSAGES["link_failed"]
                    }
            else:# First time user - not linked and no supabase_user_id provided
                #Means user doesnt have installed the app nor have registered
                # No supabase_user_id provided, cannot link
                # This means the user is not registered
                print(f"⚠️ User {request.telegram_id} not registered and no supabase_user_id provided")
                return {
                    "success": False,
                    "authenticated": False,
                    "user_data": None,
                    "must_register": True,
                    "message": MESSAGES["user_not_registered"]
                }
        else:
            # User is already linked - check if authenticated and data is complete
            is_authenticated = user_data.get("authenticated", False)
            if is_authenticated:
                # Validate and complete user_data
                user_data = await _validate_and_complete_user_data(user_data, request.telegram_id)
                session_manager.create_session(request.telegram_id, user_data)
                return {
                    "success": True,
                    "authenticated": True,
                    "user_data": user_data
                }
            else:
                # User data exists but not authenticated (edge case)
                return {
                    "success": False,
                    "authenticated": False,
                    "user_data": None,
                    "message": "User data found but not authenticated"
                }
    except Exception as e:
        print(f"❌ Error in check_authentication: {e}")
        return {
            "success": False,
            "authenticated": False,
            "user_data": None,
            "message": "Authentication check failed"
        }

# Wrap the session manager access in a try-except to avoid crashes and uses the check_authentication function
async def get_user_data(auth_request: AuthCheckRequest) -> Dict[str, Any]:
    """Helper to get user data from session or database with fallback to authentication"""
    try:
        if session_manager.is_authenticated(auth_request.telegram_id):
            session = session_manager.get_session(auth_request.telegram_id)
            if session and _is_user_data_complete(session):
                print(f"✅ Retrieved complete user data from session for {auth_request.telegram_id}")
                return session
            else:
                # Session authenticated but data missing or incomplete - re-authenticate
                print(f"⚠️ Session authenticated but data incomplete for {auth_request.telegram_id} - re-authenticating")
                auth_result = await check_authentication(auth_request)
                if auth_result.get("authenticated", False):
                    return auth_result["user_data"]
                else:
                    raise HTTPException(status_code=401, detail=auth_result.get("message", "Authentication failed"))
        else:
            # Not authenticated - perform authentication
            print("🔍 No valid session - performing authentication")
            auth_result = await check_authentication(auth_request)
            if auth_result.get("authenticated", False):
                return auth_result["user_data"]
            else:
                raise HTTPException(status_code=401, detail=auth_result.get("message", "Authentication failed"))
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_user_data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Helper function to validate and complete user data
async def _validate_and_complete_user_data(user_data: Dict[str, Any], telegram_id: str) -> Dict[str, Any]:
    """Validate user data completeness and fill in missing fields if possible"""
    required_fields = ['user_id', 'email', 'first_name', 'authenticated']
    
    # Check if all required fields are present and non-empty
    for field in required_fields:
        if not user_data.get(field):
            print(f"⚠️ Missing or empty field '{field}' in user data for {telegram_id} - attempting to complete")
            # Try to fetch from Supabase Auth if user_id is available
            if user_data.get('user_id'):
                try:
                    auth_user = await supabase_client.supabase.auth.admin.get_user_by_id(user_data['user_id'])
                    if auth_user.user:
                        user_data['email'] = auth_user.user.email or user_data.get('email', '')
                        user_data['first_name'] = auth_user.user.user_metadata.get('first_name', user_data.get('first_name', 'Unknown'))
                        user_data['last_name'] = auth_user.user.user_metadata.get('last_name', user_data.get('last_name', ''))
                        user_data['authenticated'] = True
                        print(f"✅ Completed user data for {telegram_id}")
                except Exception as e:
                    print(f"❌ Failed to complete user data for {telegram_id}: {e}")
            break  # Stop after first missing field to avoid redundant calls
    
    return user_data

# Helper function to check if user data is complete
def _is_user_data_complete(user_data: Dict[str, Any]) -> bool:
    """Check if user data has all required fields"""
    required_fields = ['user_id', 'email', 'first_name', 'authenticated']
    return all(user_data.get(field) for field in required_fields)


async def check_and_consume_credits(user_id: str, operation_type: str, credits_needed: int, user_data: Dict[str, Any] = None) -> dict:
    """Check and consume credits before processing - Assumes auth is already verified"""
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # REMOVED: No need to re-check authentication here (it's done upstream)
    # Use the provided user_data or raise an error if not provided
    if not user_data:
        raise HTTPException(status_code=401, detail="User data not provided - authentication required")
    
    # Try to consume credits
    result = await supabase_client.consume_credits(
        user_id, operation_type, credits_needed
    )
    
    if not result['success']:
        if result.get('error') == 'insufficient_credits':
            credits_available = result.get('credits_available', 0)
            credits_needed = result.get('credits_needed', 0)
            
            error_msg = MESSAGES["insufficient_credits"].format(
                credits_available=credits_available,
                credits_needed=credits_needed
            )
            return {
                "success": False,
                "message": error_msg
            }
    
    return result


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