import os
import asyncio
import aiohttp
import tempfile
from typing import Optional, Dict, Any
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Conversation states for registration
REGISTER_EMAIL, REGISTER_NAME, REGISTER_LASTNAME, REGISTER_CONFIRM = range(4)
# Add new conversation state
START_EMAIL = 1

class AgnoTelegramBot:
    """Telegram bot with session-based authentication"""
    
    def __init__(self, api_url: str = None):
        # Load environment variables
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.api_url = api_url or os.getenv('API_SERVICE_URL', 'http://localhost:8000')
        
        # Validate required environment variables
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
        
        print(f"🔗 Initializing bot with token: {self.token[:20]}...")
        print(f"🔗 API service URL: {self.api_url}")
        
        self.app = None
        self.registration_data: Dict[str, Dict[str, Any]] = {}

    def setup(self):
        """Setup the Telegram bot"""
        self.app = Application.builder().token(self.token).build()
        
        # Registration conversation handler
        registration_handler = ConversationHandler(
            entry_points=[CommandHandler("register", self.register_start)],
            states={
                REGISTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_email)],
                REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_name)],
                REGISTER_LASTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_lastname)],
                REGISTER_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_confirm)],
            },
            fallbacks=[CommandHandler("cancel", self.register_cancel)],
        )
        self.app.add_handler(registration_handler)
        
        # NEW: Add /start conversation for email input
        start_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start_command)],
            states={
                START_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.start_email)],
            },
            fallbacks=[CommandHandler("cancel", self.start_cancel)],
        )
        self.app.add_handler(start_handler)
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("reminders", self.reminders_command))
        self.app.add_handler(CommandHandler("profile", self.profile_command))
        
        # Photo and document handlers
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_receipt_photo))
        self.app.add_handler(MessageHandler(filters.Document.PDF, self.handle_pdf_statement))
        
        # Message handler for natural language processing
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        return self.app
    
   
    # Registration conversation handlers
    async def register_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start registration process"""
        user = update.effective_user
        telegram_id = str(user.id)
        
        # Initialize registration data
        self.registration_data[telegram_id] = {
            "telegram_id": telegram_id,
            "first_name": user.first_name,
            "language_code": user.language_code or "en"
        }
        
        await update.message.reply_text(
            "🚀 *Welcome to OkanAssist AI Registration!*\n\n"
            "I need a few details to create your account.\n\n"
            "📧 *Please enter your email address:*\n"
            "(This will be used to link your account)\n\n"
            "Type /cancel to stop registration anytime.",
            parse_mode='Markdown'
        )
        
        return REGISTER_EMAIL
    
    async def register_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle email input"""
        email = update.message.text.strip()
        telegram_id = str(update.effective_user.id)
        
        # Basic email validation
        if "@" not in email or "." not in email:
            await update.message.reply_text(
                "❌ Please enter a valid email address.\n"
                "Example: your.email@example.com"
            )
            return REGISTER_EMAIL
        
        self.registration_data[telegram_id]["email"] = email
        
        await update.message.reply_text(
            f"✅ Email: {email}\n\n"
            "👤 *What's your first name?*\n"
            f"(Press /skip to use: {self.registration_data[telegram_id]['first_name']})"
        )
        
        return REGISTER_NAME
    
    async def register_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle first name input"""
        telegram_id = str(update.effective_user.id)
        
        if update.message.text.strip().lower() != "/skip":
            first_name = update.message.text.strip()
            self.registration_data[telegram_id]["first_name"] = first_name
        
        await update.message.reply_text(
            "👤 *Last name (optional):*\n"
            "Type your last name or press /skip to continue."
        )
        
        return REGISTER_LASTNAME
    
    async def register_lastname(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle last name input"""
        telegram_id = str(update.effective_user.id)
        
        if update.message.text.strip().lower() != "/skip":
            last_name = update.message.text.strip()
            self.registration_data[telegram_id]["last_name"] = last_name
        
        # Show confirmation
        data = self.registration_data[telegram_id]
        confirmation_text = (
            "📋 *Please confirm your details:*\n\n"
            f"📧 Email: {data['email']}\n"
            f"👤 Name: {data['first_name']}"
        )
        
        if data.get("last_name"):
            confirmation_text += f" {data['last_name']}"
        
        confirmation_text += (
            f"\n🌐 Language: {data['language_code']}\n\n"
            "*Type 'confirm' to create your account*\n"
            "*Type 'cancel' to start over*"
        )
        
        await update.message.reply_text(confirmation_text, parse_mode='Markdown')
        
        return REGISTER_CONFIRM
    
    async def register_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle registration confirmation"""
        user_input = update.message.text.strip().lower()
        telegram_id = str(update.effective_user.id)
        
        if user_input == "confirm":
            # Submit registration to API
            try:
                data = self.registration_data[telegram_id]
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/api/v1/register",
                        json={
                            "telegram_id": data["telegram_id"],
                            "email": data["email"],
                            "first_name": data["first_name"],
                            "last_name": data.get("last_name"),
                            "language_code": data["language_code"],
                            "timezone": "UTC",
                            "currency": "USD"
                        }
                    ) as response:
                        result = await response.json()
                        
                        if response.status == 200 and result.get("success"):
                            await update.message.reply_text(
                                result["message"],
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text(
                                f"❌ Registration failed: {result.get('message', 'Unknown error')}"
                            )
                
                # Clean up registration data
                del self.registration_data[telegram_id]
                
            except Exception as e:
                print(f"❌ Error during registration: {e}")
                await update.message.reply_text(
                    "❌ Registration failed due to a technical error. Please try again later."
                )
        
        elif user_input == "cancel":
            await update.message.reply_text(
                "❌ Registration cancelled. Type /register to start again."
            )
            del self.registration_data[telegram_id]
        
        else:
            await update.message.reply_text(
                "Please type 'confirm' to create your account or 'cancel' to stop."
            )
            return REGISTER_CONFIRM
        
        return ConversationHandler.END
    
    async def register_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel registration"""
        telegram_id = str(update.effective_user.id)
        
        if telegram_id in self.registration_data:
            del self.registration_data[telegram_id]
        
        await update.message.reply_text(
            "❌ Registration cancelled.\n"
            "Type /register to start again anytime.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command by calling the API's handle_start directly"""
        user = update.effective_user
        args = context.args
        
        print(f"👤 /start command from {user.first_name} ({user.id})")
        
        # Check if user has passed a Supabase ID from mobile app redirect
        if args and len(args) > 0:
            supabase_user_id = args[0]
            print(f"📱 Redirect from mobile app with Supabase ID: {supabase_user_id}")
            # Proceed to call API with the Supabase ID in args
    
        # Always call the API's /api/v1/start endpoint - let the API handle authentication and responses
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/v1/start",
                    json={
                        "user_id": str(user.id),
                        "user_data": user.to_dict(),
                        "args": args
                    }
                ) as response:
                    result = await response.json()
                    await update.message.reply_text(result["message"], parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ Error in start command: {e}")
            await update.message.reply_text("❌ Welcome! There was an issue connecting to the service.")
        
        return ConversationHandler.END
    
    async def start_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle email input for direct auth"""
        email = update.message.text.strip()
        user = update.effective_user
        
        # Basic validation
        if "@" not in email or "." not in email:
            await update.message.reply_text("❌ Please enter a valid email address.")
            return START_EMAIL
        
        # Send to API with email for auth
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/v1/start",
                    json={
                        "user_id": str(user.id),
                        "user_data": user.to_dict(),
                        "email": email  # NEW: Pass email
                    }
                ) as response:
                    result = await response.json()
                    await update.message.reply_text(result["message"], parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ Error in email auth: {e}")
            await update.message.reply_text("❌ Sorry, there was an issue. Try /register instead.")
        
        return ConversationHandler.END
    
    async def start_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel /start email input"""
        await update.message.reply_text("❌ Cancelled. Type /start to try again or /register to create an account.")
        return ConversationHandler.END

   
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with authentication check"""
        user = update.effective_user
        message = update.message.text
        telegram_id = str(user.id)
        
        print(f"📱 Message from {user.first_name} ({user.id}): {message}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/v1/route-message",
                    json={
                        "user_id": telegram_id,
                        "message": message,
                        "user_data": user.to_dict()
                    }
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await update.message.reply_text(result["message"], parse_mode='Markdown')
                    elif response.status == 401:
                        # ✅ FIX: Handle 401 properly
                        error_data = await response.json()
                        error_message = error_data.get('detail', 'Authentication required')
                        await update.message.reply_text(
                            f"🔐 {error_message}\n\n"
                            "Type /register to create your account!",
                            parse_mode='Markdown'
                        )
                    else:
                        print(f"❌ Error processing message: {response.status}")
                        await update.message.reply_text(
                            "❌ Sorry, I couldn't process your message right now."
                        )
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            await update.message.reply_text(
                "❌ Sorry, I encountered an error. Please try again."
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        print(f"ℹ️ /help command from {update.effective_user.first_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/api/v1/help") as response:
                    if response.status == 200:
                        result = await response.json()
                        await update.message.reply_text(result["message"], parse_mode='Markdown')
                    else:
                        await update.message.reply_text("❌ Sorry, help is temporarily unavailable.")
        except Exception as e:
            print(f"❌ Error in help command: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't load the help. Please try again.")
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command with authentication"""
        user = update.effective_user
        telegram_id = str(user.id)
        print(f"💰 /balance command from {user.first_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/v1/get-transaction-summary",
                    json={"user_id": telegram_id, "days": 30}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await update.message.reply_text(result["message"], parse_mode='Markdown')
                    elif response.status == 401:
                        await update.message.reply_text(
                            "🔐 You need to register first to view your balance!\n"
                            "Type /register to create your account.",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Sorry, I couldn't fetch your balance right now."
                        )
        except Exception as e:
            print(f"❌ Error in balance command: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't get your balance. Please try again.")
    
    async def reminders_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reminders command with authentication"""
        user = update.effective_user
        telegram_id = str(user.id)
        print(f"⏰ /reminders command from {user.first_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/v1/get-reminders",
                    params={"user_id": telegram_id, "limit": 10}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await update.message.reply_text(result["message"], parse_mode='Markdown')
                    elif response.status == 401:
                        await update.message.reply_text(
                            "🔐 You need to register first to view reminders!\n"
                            "Type /register to create your account.",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Sorry, I couldn't fetch your reminders right now."
                        )
        except Exception as e:
            print(f"❌ Error in reminders command: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't get your reminders. Please try again.")
    
    async def handle_receipt_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process receipt photos with authentication"""
        user = update.effective_user
        telegram_id = str(user.id)
        print(f"📸 Receipt photo from {user.first_name}")
        
        try:
            # Download photo
            photo = update.message.photo[-1]
            file = await photo.get_file()
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                await file.download_to_drive(temp_file.name)
                
                # Send to API
                async with aiohttp.ClientSession() as session:
                    with open(temp_file.name, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('user_id', telegram_id)
                        data.add_field('file', f, filename='receipt.jpg', content_type='image/jpeg')
                        
                        async with session.post(
                            f"{self.api_url}/api/v1/process-receipt",
                            data=data
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                await update.message.reply_text(result["message"], parse_mode='Markdown')
                            elif response.status == 401:
                                await update.message.reply_text(
                                    "🔐 You need to register first to process receipts!\n"
                                    "Type /register to create your account.",
                                    parse_mode='Markdown'
                                )
                            else:
                                await update.message.reply_text("❌ Sorry, I couldn't process that receipt.")
                
                # Cleanup
                os.unlink(temp_file.name)
                
        except Exception as e:
            print(f"❌ Error processing receipt: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't process that receipt. Please try again.")
    
    async def handle_pdf_statement(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process bank statement PDFs with authentication"""
        user = update.effective_user
        telegram_id = str(user.id)
        print(f"📄 PDF statement from {user.first_name}")
        
        try:
            document = update.message.document
            file = await document.get_file()
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                await file.download_to_drive(temp_file.name)
                
                # Send to API
                async with aiohttp.ClientSession() as session:
                    with open(temp_file.name, 'rb') as f:
                        data = aiohttp.FormData()
                        data.add_field('user_id', telegram_id)
                        data.add_field('file', f, filename=document.file_name, content_type='application/pdf')
                        
                        async with session.post(
                            f"{self.api_url}/api/v1/process-bank-statement",
                            data=data
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                await update.message.reply_text(result["message"], parse_mode='Markdown')
                            elif response.status == 401:
                                await update.message.reply_text(
                                    "🔐 You need to register first to process documents!\n"
                                    "Type /register to create your account.",
                                    parse_mode='Markdown'
                                )
                            else:
                                await update.message.reply_text("❌ Sorry, I couldn't process that document.")
                
                # Cleanup
                os.unlink(temp_file.name)
                
        except Exception as e:
            print(f"❌ Error processing PDF: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't process that PDF. Please try again.")
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command with authentication"""
        user = update.effective_user
        telegram_id = str(user.id)
        print(f"👤 /profile command from {user.first_name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/api/v1/profile",
                    params={"user_id": telegram_id}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        await update.message.reply_text(result["message"], parse_mode='Markdown')
                    elif response.status == 401:
                        await update.message.reply_text(
                            "🔐 You need to register first to view your profile!\n"
                            "Type /register to create your account.",
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Sorry, I couldn't fetch your profile right now."
                        )
        except Exception as e:
            print(f"❌ Error in profile command: {e}")
            await update.message.reply_text("❌ Sorry, I couldn't get your profile. Please try again.")
    
    async def set_commands(self):
        """Set bot commands"""
        commands = [
            BotCommand("start", "Start using the assistant"),
            BotCommand("register", "Register your account"),
            BotCommand("help", "Get help and examples"),
            BotCommand("balance", "View financial summary"),
            BotCommand("reminders", "Show pending reminders"),
            BotCommand("profile", "View your profile"),
        ]
        await self.app.bot.set_my_commands(commands)
    
    async def run(self):
        """Start the bot"""
        if not self.app:
            self.setup()
        
        await self.set_commands()
        
        print("🤖 Telegram Bot started!")
        print("🎯 Commands: /start, /register, /help, /balance, /reminders, /profile")
        print("📸 Send photos of receipts for automatic processing")
        print("📄 Send PDF bank statements for bulk transaction import")
        
        async with self.app:
            await self.app.start()
            await self.app.updater.start_polling()
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping bot...")
            finally:
                await self.app.updater.stop()
                await self.app.stop()