from typing import Dict, Any, List, Optional
from .database import Database
from .models import Transaction, Reminder, TransactionType, ReminderType, Priority
from datetime import datetime, timedelta
import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from gotrue.errors import AuthApiError
import json


class SupabaseClient:
    """Supabase client for direct database operations"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.database = Database(database_url)
        self.connected = False
    
    async def connect(self):
        """Connect to the database"""
        if not self.connected:
            await self.database.connect()
            self.connected = True
            print("✅ Database connected successfully")
    
    async def disconnect(self):
        """Disconnect from the database"""
        if self.connected:
            await self.database.close()
            self.connected = False
            print("✅ Database disconnected")

    async def ensure_user_exists(self, telegram_id: str, user_data: dict):
        """
        Ensure user exists in user_settings table with Telegram data.
        1. If user exists and premium is enabled, return user info.
        2. If no user_id found, prompt to download the app.
        3. If user_id found but subscription expired, generate PayPal renewal link.
        """
        try:
            # Make sure database is connected
            if not self.connected:
                await self.connect()
            
            # Check if user exists by telegram_id
            async with self.database.pool.acquire() as conn:
                existing_user = await conn.fetchrow("""
                    SELECT user_id, currency, language, timezone, is_premium, premium_until 
                    FROM user_settings WHERE telegram_id = $1
                """, telegram_id)
                
                if not existing_user:
                    # No user_id found: prompt to download the app
                    return {
                        "success": False,
                        "message": (
                            "🚫 Your Telegram account is not linked to a registered user.\n"
                            "👉 Please download the OkanFit app from the Play Store and register to use all features:\n"
                            "https://play.google.com/store/apps/details?id=com.okanfit.app"
                        )
                    }
                else:
                    # Update last interaction
                    await conn.execute("""
                        UPDATE user_settings 
                        SET last_bot_interaction = NOW(), updated_at = NOW()
                        WHERE telegram_id = $1
                    """, telegram_id)
                    
                    user_id = str(existing_user['user_id'])
                    currency = existing_user['currency']
                    language = existing_user['language']
                    timezone = existing_user['timezone']
                    is_premium = existing_user['is_premium']
                    premium_until = existing_user['premium_until']

                    # Check premium status
                    premium_active = False
                    if is_premium and premium_until:
                        premium_active = datetime.now() < premium_until.replace(tzinfo=None)

                    if premium_active:
                        # Premium enabled: return user info
                        return {
                            "success": True,
                            "user_id": user_id,
                            "currency": currency,
                            "language": language,
                            "timezone": timezone,
                            "is_premium": True,
                            "premium_until": premium_until
                        }
                    else:
                        # Subscription expired: create payment and generate PayPal renewal link
                        payment_id = await self.database.create_payment(user_id, "paypal", 9.99, currency)
                        paypal_url = f"https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=YOUR_BUTTON_ID&custom={payment_id}"
                        
                        return {
                            "success": False,
                            "message": (
                                "⚠️ Your premium subscription has expired.\n"
                                "To renew and unlock all features, please complete your payment:\n"
                                f"💳 [Renew with PayPal]({paypal_url})\n\n"
                                "After payment, you'll have access to:\n"
                                "🤖 AI-powered expense tracking\n"
                                "📊 Smart financial insights\n"
                                "⏰ Intelligent reminders\n"
                                "📈 Advanced analytics"
                            ),
                            "user_id": user_id,
                            "currency": currency,
                            "language": language,
                            "timezone": timezone,
                            "is_premium": False,
                            "premium_until": premium_until,
                            "payment_id": payment_id,
                            "paypal_url": paypal_url
                        }
        except Exception as e:
            print(f"❌ Error ensuring user exists: {e}")
            return {"success": False, "message": "❌ Internal error. Please try again later."}

    #adjust this function to also get the user name and insert it into the database
    async def link_telegram_user(self, supabase_user_id: str, telegram_id: str, user_name: str ):
        """Link a Telegram user to a Supabase user"""
        try:
            if not self.connected:
                await self.connect()
            
            # Update user_settings with telegram_id
            async with self.database.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_settings (user_id, telegram_id, name, last_bot_interaction)
                    VALUES ($1, $2, $3, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        telegram_id = $2,
                        name = $3,
                        last_bot_interaction = NOW(),
                        updated_at = NOW()
                """, supabase_user_id, telegram_id, user_name)
                print(f"inserted {user_name}")
                print(f"✅ Linked Telegram user {telegram_id} to Supabase user {supabase_user_id}")
                
        except Exception as e:
            print(f"❌ Error linking Telegram user: {e}")
            raise
    
    async def get_user_by_telegram_id(self, telegram_id: str) -> str:
        """Get Supabase user_id by telegram_id"""
        try:
            if not self.connected:
                await self.connect()
                
            async with self.database.pool.acquire() as conn:
                result = await conn.fetchrow("""
                    SELECT user_id FROM user_settings WHERE telegram_id = $1
                """, telegram_id)
                
                return str(result['user_id']) if result else None
                
        except Exception as e:
            print(f"❌ Error getting user by telegram ID: {e}")
            return None
    
    async def check_premium_status(self, user_id: str) -> bool:
        """Check if user has premium access"""
        try:
            if not self.connected:
                await self.connect()
                
            async with self.database.pool.acquire() as conn:
                result = await conn.fetchrow("""
                    SELECT is_premium, premium_until 
                    FROM user_settings 
                    WHERE user_id = $1
                """, user_id)
                
                if result:
                    # Check if premium is active and not expired
                    is_premium = result['is_premium']
                    premium_until = result['premium_until']
                    
                    if is_premium and premium_until:
                        return datetime.now() < premium_until.replace(tzinfo=None)
                    
                    return is_premium
                
                return False
                
        except Exception as e:
            print(f"❌ Error checking premium status: {e}")
            return False

    # Payment-related methods
    async def create_payment_record(self, user_id: str, provider: str = "paypal", amount: float = 9.99, currency: str = "USD") -> str:
        """Create a payment record and return payment ID"""
        if not self.connected:
            await self.connect()
        
        return await self.database.create_payment(user_id, provider, amount, currency)

    async def process_payment_success(self, payment_id: str, transaction_id: str, subscription_id: str = None):
        """Process successful payment and update user premium status"""
        if not self.connected:
            await self.connect()
        
        # Update payment status
        await self.database.update_payment_status(payment_id, "success", transaction_id, subscription_id)
        print(f"✅ Payment {payment_id} processed successfully")

    async def process_payment_failure(self, payment_id: str, reason: str = "failed"):
        """Process failed payment"""
        if not self.connected:
            await self.connect()
        
        await self.database.update_payment_status(payment_id, reason)
        print(f"❌ Payment {payment_id} failed: {reason}")

    async def get_user_payment_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user payment history"""
        if not self.connected:
            await self.connect()
        
        return await self.database.get_user_payments(user_id)

    # PayPal webhook handler
    async def handle_paypal_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Handle PayPal payment webhook"""
        try:
            if not self.connected:
                await self.connect()
            
            event_type = webhook_data.get('event_type')
            resource = webhook_data.get('resource', {})
            
            # Extract payment ID from custom field
            custom_data = resource.get('custom', '')
            if not custom_data:
                print("❌ No payment ID in PayPal webhook")
                return False
            
            payment_id = custom_data
            transaction_id = resource.get('id')
            
            if event_type == 'PAYMENT.SALE.COMPLETED':
                await self.process_payment_success(payment_id, transaction_id)
                return True
            elif event_type in ['PAYMENT.SALE.DENIED', 'PAYMENT.SALE.CANCELLED']:
                await self.process_payment_failure(payment_id, "cancelled")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error processing PayPal webhook: {e}")
            return False

    async def sign_up_user_with_auth(self, email: str, password: str, user_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Sign up user with Supabase Auth"""
        try:
            # Generate password if not provided
            if not password:
                import secrets
                password = secrets.token_urlsafe(16)
            
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata or {}
                }
            })
            
            if response.user:
                return {
                    "success": True,
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "user_metadata": response.user.user_metadata,
                    "message": "User created successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to create user"
                }
                
        except AuthApiError as e:
            return {
                "success": False,
                "message": f"Auth error: {e.message}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def get_user_by_email_auth(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from Supabase Auth (requires service role)"""
        try:
            # Use admin client to list users and find by email
            response = self.supabase.auth.admin.list_users()
            
            if response and hasattr(response, 'users'):
                for user in response.users:
                    if user.email == email:
                        return {
                            "user_id": user.id,
                            "email": user.email,
                            "user_metadata": user.user_metadata or {},
                            "created_at": user.created_at
                        }
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting user by email: {e}")
            return None

    async def link_telegram_to_auth_user(self, auth_user_id: str, telegram_id: str, telegram_data: Dict[str, Any]) -> bool:
        """Link Telegram ID to Supabase Auth user"""
        try:
            # Update user_settings table to link telegram_id to auth user
            async with self.database.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_settings (
                        user_id, telegram_id, last_bot_interaction, created_at, updated_at
                    ) VALUES ($1, $2, NOW(), NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        telegram_id = $2,
                        last_bot_interaction = NOW(),
                        updated_at = NOW()
                """, auth_user_id, telegram_id)
                
                # Log activity
                await self.database._log_user_activity(
                    auth_user_id,
                    'telegram_linked',
                    {'telegram_id': telegram_id, **telegram_data},
                    'telegram'
                )
            
            return True
            
        except Exception as e:
            print(f"❌ Error linking Telegram to auth user: {e}")
            return False

    async def get_user_by_telegram_id_auth(self, telegram_id: str) -> Optional[Dict[str, Any]]:
        """Get user info by Telegram ID using auth system"""
        try:
            async with self.database.pool.acquire() as conn:
                # Get user_id from user_settings
                user_row = await conn.fetchrow("""
                    SELECT user_id, currency, name, language, timezone, is_premium, premium_until, freemium_credits
                    FROM user_settings
                    WHERE telegram_id = $1
                """, telegram_id)
                
                if not user_row:
                    return None
                
                # Get auth user data
                auth_user_id = str(user_row['user_id'])
                
                try:
                    # Get user from Supabase Auth
                    auth_response = self.supabase.auth.admin.get_user_by_id(auth_user_id)
                    
                    if auth_response.user:
                        return {
                            'user_id': auth_user_id,
                            'email': auth_response.user.email,
                            'first_name': auth_response.user.user_metadata.get('name'),
                            'currency': user_row['currency'],
                            'language': user_row['language'],
                            'timezone': user_row['timezone'],
                            'is_premium': user_row['is_premium'],
                            'premium_until': user_row['premium_until'],
                            'freemium_credits': user_row['freemium_credits'],
                            'telegram_id': telegram_id,
                            'authenticated': True
                        }
                except Exception as auth_error:
                    print(f"❌ Error getting auth user: {auth_error}")
                    # Fallback: return basic data from user_settings
                    return {
                        'user_id': auth_user_id,
                        'email': None,
                        'first_name': None,
                        'currency': user_row['currency'],
                        'language': user_row['language'],
                        'timezone': user_row['timezone'],
                        'is_premium': user_row['is_premium'],
                        'premium_until': user_row['premium_until'],
                        'freemium_credits': 0,
                        'telegram_id': telegram_id,
                        'authenticated': False  # Not authenticated if can't get auth data
                    }
                
                return None
                
        except Exception as e:
            print(f"❌ Error getting user by telegram ID: {e}")
            return None

    # Update ensure_user_exists method to work with auth
    async def ensure_user_exists_auth(self, telegram_id: str, user_data: dict):
        """
        Ensure user exists and is authenticated with Supabase Auth.
        Returns session data or registration requirement.
        """
        try:
            # Make sure database is connected
            if not self.connected:
                await self.connect()
            
            # Check if user exists by telegram_id and has auth
            user_info = await self.get_user_by_telegram_id_auth(telegram_id)
            
            if not user_info:
                # No user found: require registration
                return {
                    "success": False,
                    "requires_registration": True,
                    "message": (
                        "🚫 You need to register first.\n\n"
                        "Please use /register to create your account and link your Telegram to the system."
                    )
                }
            
            if not user_info.get('authenticated', False):
                # User exists but not properly authenticated
                return {
                    "success": False,
                    "requires_registration": True,
                    "message": (
                        "⚠️ Your account needs to be re-registered.\n\n"
                        "Please use /register to update your account information."
                    )
                }
            
            # Update last interaction
            async with self.database.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE user_settings 
                    SET last_bot_interaction = NOW(), updated_at = NOW()
                    WHERE telegram_id = $1
                """, telegram_id)
            
            # Check premium status
            is_premium = user_info.get('is_premium', False)
            premium_until = user_info.get('premium_until')
            premium_active = False
            
            if is_premium and premium_until:
                premium_active = datetime.now() < premium_until.replace(tzinfo=None)
            
            if premium_active:
                # Premium enabled: return user info
                return {
                    "success": True,
                    "authenticated": True,
                    "user_data": user_info
                }
            else:
                # Subscription expired: create payment
                payment_id = await self.database.create_payment(
                    user_info['user_id'], "paypal", 9.99, user_info.get('currency', 'USD')
                )
                paypal_url = f"https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=YOUR_BUTTON_ID&custom={payment_id}"
                
                return {
                    "success": False,
                    "authenticated": True,
                    "requires_payment": True,
                    "user_data": user_info,
                    "message": (
                        "⚠️ Your premium subscription has expired.\n"
                        "To renew and unlock all features, please complete your payment:\n"
                        f"💳 [Renew with PayPal]({paypal_url})\n\n"
                        "After payment, you'll have access to all AI features."
                    ),
                    "payment_id": payment_id,
                    "paypal_url": paypal_url
                }
                
        except Exception as e:
            print(f"❌ Error ensuring user exists: {e}")
            return {"success": False, "message": "❌ Internal error. Please try again later."}

    async def check_user_by_baseid(self, supabase_user_id: str) -> bool:
        """Check if user exists in Supabase Auth by user ID"""
        try:
            # Attempt to get user by ID from Supabase Auth
            auth_response = self.supabase.auth.admin.get_user_by_id(supabase_user_id)
            
            if auth_response.user:
                return True
            else:
                return False
            
        except Exception as e:
            print(f"❌ Error checking user by base ID: {e}")
            return False

    async def consume_credits(self, user_id: str, operation_type: str, credits_needed: int, activity_data: dict = None) -> dict:
        """Consume freemium credits for an operation"""
        async with self.database.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT consume_freemium_credits($1, $2, $3, $4) as result
            """, user_id, operation_type, credits_needed, json.dumps(activity_data or {}))
            
            return json.loads(result['result'])
    
    async def get_user_credits(self, user_id: str) -> dict:
        """Get user's current credit status"""
        if not self.connected:
            await self.connect()
        
        async with self.database.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT freemium_credits, is_premium, credits_reset_date, premium_until
                FROM user_settings 
                WHERE user_id = $1
            """, user_id)
            
            if not row:
                return {"credits": 0, "is_premium": False, "error": "User not found"}
            
            return {
                "credits": row['freemium_credits'],
                "is_premium": row['is_premium'],
                "credits_reset_date": row['credits_reset_date'],
                "premium_until": row['premium_until']
            }

    async def reset_monthly_credits(self) -> int:
        """Reset monthly credits for all eligible users"""
        if not self.connected:
            await self.connect()
        
        async with self.database.pool.acquire() as conn:
            result = await conn.fetchval("SELECT reset_monthly_credits()")
            return result

    async def ensure_user_exists(self, user_id: str, user_data: dict = None):
        """Ensure user exists in user_settings table"""
        if not self.connected:
            await self.connect()
        
        async with self.database.pool.acquire() as conn:
            # Check if user exists
            existing_user = await conn.fetchrow(
                "SELECT user_id FROM user_settings WHERE user_id = $1", 
                user_id
            )
            
            if not existing_user:
                # Create new user with defaults
                await conn.execute("""
                    INSERT INTO user_settings (
                        user_id, name, currency, language, timezone
                    ) VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO NOTHING
                """, 
                user_id, 
                user_data.get("name", "") if user_data else "",
                user_data.get("currency", "USD") if user_data else "USD",
                user_data.get("language", "en") if user_data else "en",
                user_data.get("timezone", "UTC") if user_data else "UTC"
                )
                
                print(f"✅ Created user settings for user ID: {user_id}")
            else:
                print(f"✅ User {user_id} already exists")