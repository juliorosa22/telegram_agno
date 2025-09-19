# Simple database manager with RLS policies
import asyncpg
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import (
    Transaction, TransactionSummary, Reminder, ReminderSummary, 
    UserActivity, ReminderType, Priority, TransactionType, UserSettings
)

class Database:
    """Simplified Database manager with RLS policies"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Initialize database connection"""
        self.pool = await asyncpg.create_pool(self.database_url)
        print("✅ Database connected")

    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            print("✅ Database disconnected")
    
    async def _create_tables(self):
        """Create simplified tables with RLS policies and proper permissions"""
        async with self.pool.acquire() as conn:
            # Create update timestamp function first (with security fixes)
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER 
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$;
            """)
            
            # 1. Transactions table (expenses + income)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL,
                    amount DECIMAL(12,2) NOT NULL CHECK (amount > 0),
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('expense', 'income')),
                    original_message TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'web_app' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    merchant TEXT,
                    date TIMESTAMP DEFAULT NOW() NOT NULL,
                    receipt_image_url TEXT,
                    location JSONB,
                    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
                    recurring_pattern TEXT,
                    tags JSONB DEFAULT '[]' NOT NULL,
                    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.00 AND confidence_score <= 1.00),
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for transactions
                CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
                CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);
                CREATE INDEX IF NOT EXISTS idx_transactions_platform ON transactions(source_platform);
                CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount);
                CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, date);
                
                -- Table comments
                COMMENT ON TABLE transactions IS 'User financial transactions (expenses and income)';
                COMMENT ON COLUMN transactions.user_id IS 'User ID from authentication system';
                COMMENT ON COLUMN transactions.amount IS 'Transaction amount (positive values only)';
                COMMENT ON COLUMN transactions.transaction_type IS 'Type: expense or income';
                COMMENT ON COLUMN transactions.source_platform IS 'Platform where transaction was created';
                COMMENT ON COLUMN transactions.confidence_score IS 'AI parsing confidence (0.00-1.00)';
            """)
            
            # 2. Reminders table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_platform TEXT DEFAULT 'web_app' CHECK (source_platform IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    due_datetime TIMESTAMP,
                    reminder_type TEXT DEFAULT 'general' CHECK (reminder_type IN ('task', 'event', 'deadline', 'habit', 'general')),
                    priority TEXT DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
                    is_completed BOOLEAN DEFAULT FALSE NOT NULL,
                    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
                    recurrence_pattern TEXT,
                    notification_sent BOOLEAN DEFAULT FALSE NOT NULL,
                    snooze_until TIMESTAMP,
                    tags TEXT,
                    location_reminder JSONB,
                    attachments JSONB DEFAULT '[]' NOT NULL,
                    assigned_to_platforms JSONB DEFAULT '[]' NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for reminders
                CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id);
                CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_datetime);
                CREATE INDEX IF NOT EXISTS idx_reminders_platform ON reminders(source_platform);
                CREATE INDEX IF NOT EXISTS idx_reminders_completed ON reminders(is_completed);
                CREATE INDEX IF NOT EXISTS idx_reminders_priority ON reminders(priority);
                CREATE INDEX IF NOT EXISTS idx_reminders_type ON reminders(reminder_type);
                CREATE INDEX IF NOT EXISTS idx_reminders_notification ON reminders(notification_sent, due_datetime);
                CREATE INDEX IF NOT EXISTS idx_reminders_user_due ON reminders(user_id, due_datetime);
                
                -- Table comments
                COMMENT ON TABLE reminders IS 'User reminders and tasks with scheduling and notification features';
                COMMENT ON COLUMN reminders.user_id IS 'User ID from authentication system';
                COMMENT ON COLUMN reminders.reminder_type IS 'Type: task, event, deadline, habit, or general';
                COMMENT ON COLUMN reminders.priority IS 'Priority: urgent, high, medium, or low';
                COMMENT ON COLUMN reminders.source_platform IS 'Platform where reminder was created';
            """)
            
            # 3. User settings table with freemium credits
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id UUID PRIMARY KEY,
                    name TEXT,
                    currency TEXT DEFAULT 'USD' NOT NULL,
                    language TEXT DEFAULT 'en' NOT NULL,
                    timezone TEXT DEFAULT 'UTC' NOT NULL,
                    is_premium BOOLEAN DEFAULT FALSE NOT NULL,
                    telegram_id TEXT UNIQUE,
                    premium_until TIMESTAMPTZ,
                    freemium_credits INTEGER DEFAULT 50 NOT NULL CHECK (freemium_credits >= 0),
                    credits_reset_date DATE DEFAULT (CURRENT_DATE + INTERVAL '30 days') NOT NULL,
                    last_bot_interaction TIMESTAMP DEFAULT NOW(),
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for user_settings
                CREATE INDEX IF NOT EXISTS idx_user_settings_telegram_id ON user_settings(telegram_id);
                CREATE INDEX IF NOT EXISTS idx_user_settings_is_premium ON user_settings(is_premium);
                CREATE INDEX IF NOT EXISTS idx_user_settings_premium_until ON user_settings(premium_until);
                CREATE INDEX IF NOT EXISTS idx_user_settings_credits ON user_settings(freemium_credits);
                CREATE INDEX IF NOT EXISTS idx_user_settings_reset_date ON user_settings(credits_reset_date);
                
                -- Table comments
                COMMENT ON TABLE user_settings IS 'User preferences, premium status, and freemium credits';
                COMMENT ON COLUMN user_settings.user_id IS 'User ID from authentication system';
                COMMENT ON COLUMN user_settings.currency IS 'User preferred currency code (e.g., USD, EUR, GBP)';
                COMMENT ON COLUMN user_settings.language IS 'User preferred language code (e.g., en, es, fr)';
                COMMENT ON COLUMN user_settings.timezone IS 'User timezone (e.g., UTC, America/New_York)';
                COMMENT ON COLUMN user_settings.is_premium IS 'Whether user has active premium subscription';
                COMMENT ON COLUMN user_settings.telegram_id IS 'Telegram user ID for bot integration (unique)';
                COMMENT ON COLUMN user_settings.premium_until IS 'Premium subscription expiration date';
                COMMENT ON COLUMN user_settings.freemium_credits IS 'Available freemium credits for AI processing';
                COMMENT ON COLUMN user_settings.credits_reset_date IS 'Date when credits were last reset';
                COMMENT ON COLUMN user_settings.last_bot_interaction IS 'Last time user interacted with Telegram bot';
            """)
            
            # 4. Payments table for subscription management
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    provider TEXT NOT NULL CHECK (provider IN ('paypal', 'mercadopago', 'stripe')),
                    amount NUMERIC NOT NULL CHECK (amount > 0),
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'success', 'failed', 'cancelled')),
                    transaction_id TEXT, -- External payment provider transaction ID
                    subscription_id TEXT, -- Provider subscription ID
                    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
                    valid_until TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for payments
                CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
                CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
                CREATE INDEX IF NOT EXISTS idx_payments_provider ON payments(provider);
                CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);
                CREATE INDEX IF NOT EXISTS idx_payments_valid_until ON payments(valid_until);
                CREATE INDEX IF NOT EXISTS idx_payments_transaction_id ON payments(transaction_id);
                
                -- Table comments
                COMMENT ON TABLE payments IS 'Payment records for premium subscriptions';
                COMMENT ON COLUMN payments.user_id IS 'User ID from authentication system';
                COMMENT ON COLUMN payments.provider IS 'Payment provider: paypal or mercadopago';
                COMMENT ON COLUMN payments.amount IS 'Payment amount (positive values only)';
                COMMENT ON COLUMN payments.status IS 'Payment status: pending, success, failed, or cancelled';
                COMMENT ON COLUMN payments.transaction_id IS 'External payment provider transaction ID';
                COMMENT ON COLUMN payments.subscription_id IS 'Provider subscription ID for recurring payments';
                COMMENT ON COLUMN payments.valid_until IS 'Premium access valid until this date';
            """)
            
            # ============================================================================
            # ENABLE ROW LEVEL SECURITY ON ALL TABLES
            # ============================================================================
            await conn.execute("""
                ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
                ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
                ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
                ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
            """)
            
            # ============================================================================
            # CREATE RLS POLICIES FOR TRANSACTIONS
            # ============================================================================
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own transactions" ON transactions;
                DROP POLICY IF EXISTS "Users can insert own transactions" ON transactions;
                DROP POLICY IF EXISTS "Users can update own transactions" ON transactions;
                DROP POLICY IF EXISTS "Users can delete own transactions" ON transactions;
                
                CREATE POLICY "Users can view own transactions" ON transactions
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own transactions" ON transactions
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can update own transactions" ON transactions
                    FOR UPDATE USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can delete own transactions" ON transactions
                    FOR DELETE USING ((SELECT auth.uid()) = user_id);
            """)
            
            # ============================================================================
            # CREATE RLS POLICIES FOR REMINDERS
            # ============================================================================
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own reminders" ON reminders;
                DROP POLICY IF EXISTS "Users can insert own reminders" ON reminders;
                DROP POLICY IF EXISTS "Users can update own reminders" ON reminders;
                DROP POLICY IF EXISTS "Users can delete own reminders" ON reminders;
                
                CREATE POLICY "Users can view own reminders" ON reminders
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own reminders" ON reminders
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can update own reminders" ON reminders
                    FOR UPDATE USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can delete own reminders" ON reminders
                    FOR DELETE USING ((SELECT auth.uid()) = user_id);
            """)
            
            # ============================================================================
            # CREATE RLS POLICIES FOR USER_SETTINGS
            # ============================================================================
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own settings" ON user_settings;
                DROP POLICY IF EXISTS "Users can insert own settings" ON user_settings;
                DROP POLICY IF EXISTS "Users can update own settings" ON user_settings;
                DROP POLICY IF EXISTS "Users can delete own settings" ON user_settings;
                
                CREATE POLICY "Users can view own settings" ON user_settings
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own settings" ON user_settings
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can update own settings" ON user_settings
                    FOR UPDATE USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can delete own settings" ON user_settings
                    FOR DELETE USING ((SELECT auth.uid()) = user_id);
            """)
            
            # ============================================================================
            # CREATE RLS POLICIES FOR PAYMENTS
            # ============================================================================
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own payments" ON payments;
                DROP POLICY IF EXISTS "Users can insert own payments" ON payments;
                DROP POLICY IF EXISTS "Users can update own payments" ON payments;
                
                CREATE POLICY "Users can view own payments" ON payments
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own payments" ON payments
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can update own payments" ON payments
                    FOR UPDATE USING ((SELECT auth.uid()) = user_id);
            """)
            
            # Create automatic timestamp triggers
            await conn.execute("""
                DROP TRIGGER IF EXISTS update_transactions_updated_at ON transactions;
                DROP TRIGGER IF EXISTS update_reminders_updated_at ON reminders;
                DROP TRIGGER IF EXISTS update_user_settings_updated_at ON user_settings;
                DROP TRIGGER IF EXISTS update_payments_updated_at ON payments;
                
                CREATE TRIGGER update_transactions_updated_at
                    BEFORE UPDATE ON transactions
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
                
                CREATE TRIGGER update_reminders_updated_at
                    BEFORE UPDATE ON reminders
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
                
                CREATE TRIGGER update_user_settings_updated_at
                    BEFORE UPDATE ON user_settings
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
                
                CREATE TRIGGER update_payments_updated_at
                    BEFORE UPDATE ON payments
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """)
            
            # Function to automatically update premium status based on payments (security fixed)
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_premium_status()
                RETURNS TRIGGER 
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                BEGIN
                    -- Update user_settings when a payment is successful
                    IF NEW.status = 'success' AND NEW.valid_until IS NOT NULL THEN
                        INSERT INTO user_settings (user_id, is_premium, premium_until)
                        VALUES (NEW.user_id, TRUE, NEW.valid_until)
                        ON CONFLICT (user_id) DO UPDATE SET
                            is_premium = TRUE,
                            premium_until = NEW.valid_until,
                            updated_at = NOW();
                    END IF;
                    
                    RETURN NEW;
                END;
                $$;
            """)
            
            # Trigger to automatically update premium status on payment success
            await conn.execute("""
                DROP TRIGGER IF EXISTS payment_success_trigger ON payments;
                CREATE TRIGGER payment_success_trigger
                    AFTER INSERT OR UPDATE ON payments
                    FOR EACH ROW
                    EXECUTE FUNCTION update_premium_status();
            """)
            
            # Function to check and update expired premium subscriptions (security fixed)
            await conn.execute("""
                CREATE OR REPLACE FUNCTION check_expired_premium()
                RETURNS void 
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                BEGIN
                    UPDATE user_settings 
                    SET is_premium = FALSE, updated_at = NOW()
                    WHERE is_premium = TRUE 
                    AND premium_until IS NOT NULL 
                    AND premium_until < NOW();
                END;
                $$;
            """)
            
            # Function to reset monthly freemium credits (security fixed)
            await conn.execute("""
                CREATE OR REPLACE FUNCTION reset_monthly_credits()
                RETURNS INTEGER 
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                DECLARE
                    affected_users INTEGER;
                BEGIN
                    -- Reset credits for non-premium users whose reset date has passed
                    UPDATE user_settings 
                    SET freemium_credits = 20,
                        credits_reset_date = CURRENT_DATE + INTERVAL '30 days',
                        updated_at = NOW()
                    WHERE is_premium = FALSE
                    AND credits_reset_date < CURRENT_DATE;
                    
                    GET DIAGNOSTICS affected_users = ROW_COUNT;
                    
                    RETURN affected_users;
                END;
                $$;
            """)
            
            # Simplified function to consume freemium credits (security fixed)
            await conn.execute("""
                CREATE OR REPLACE FUNCTION consume_freemium_credits(
                    p_user_id UUID,
                    p_operation_type TEXT,
                    p_credits_needed INTEGER,
                    p_activity_data JSONB DEFAULT '{}'
                )
                RETURNS JSONB 
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $$
                DECLARE
                    current_credits INTEGER;
                    is_premium_user BOOLEAN;
                    credits_after INTEGER;
                BEGIN
                    -- Get current user status
                    SELECT freemium_credits, is_premium 
                    INTO current_credits, is_premium_user
                    FROM user_settings 
                    WHERE user_id = p_user_id;
                    
                    -- If user not found, return error
                    IF NOT FOUND THEN
                        RETURN jsonb_build_object(
                            'success', false,
                            'error', 'user_not_found',
                            'message', 'User not found'
                        );
                    END IF;
                    
                    -- Premium users get unlimited usage
                    IF is_premium_user THEN
                        RETURN jsonb_build_object(
                            'success', true,
                            'is_premium', true,
                            'credits_used', 0,
                            'credits_remaining', -1,
                            'message', 'Premium user - unlimited usage'
                        );
                    END IF;
                    
                    -- Check if user has enough credits
                    IF current_credits < p_credits_needed THEN
                        RETURN jsonb_build_object(
                            'success', false,
                            'error', 'insufficient_credits',
                            'message', 'Not enough credits available',
                            'credits_available', current_credits,
                            'credits_needed', p_credits_needed
                        );
                    END IF;
                    
                    -- Consume credits (only update user_settings)
                    credits_after := current_credits - p_credits_needed;
                    
                    UPDATE user_settings 
                    SET freemium_credits = credits_after,
                        updated_at = NOW()
                    WHERE user_id = p_user_id;
                    
                    RETURN jsonb_build_object(
                        'success', true,
                        'is_premium', false,
                        'credits_used', p_credits_needed,
                        'credits_remaining', credits_after,
                        'message', 'Credits consumed successfully'
                    );
                END;
                $$;
            """)
            
            # ✅ GRANT PROPER PERMISSIONS TO SUPABASE ROLES
            await conn.execute("""
                -- Grant full table access to Supabase roles
                GRANT ALL PRIVILEGES ON TABLE user_settings TO authenticated;
                GRANT ALL PRIVILEGES ON TABLE user_settings TO anon;
                GRANT ALL PRIVILEGES ON TABLE transactions TO authenticated;
                GRANT ALL PRIVILEGES ON TABLE transactions TO anon;
                GRANT ALL PRIVILEGES ON TABLE reminders TO authenticated;
                GRANT ALL PRIVILEGES ON TABLE reminders TO anon;
                GRANT ALL PRIVILEGES ON TABLE payments TO authenticated;
                GRANT ALL PRIVILEGES ON TABLE payments TO anon;
                
                -- Grant sequence permissions for auto-increment IDs
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon;
                
                -- Grant function execution permissions
                GRANT EXECUTE ON FUNCTION update_updated_at_column() TO authenticated;
                GRANT EXECUTE ON FUNCTION update_updated_at_column() TO anon;
                GRANT EXECUTE ON FUNCTION update_premium_status() TO authenticated;
                GRANT EXECUTE ON FUNCTION update_premium_status() TO anon;
                GRANT EXECUTE ON FUNCTION check_expired_premium() TO authenticated;
                GRANT EXECUTE ON FUNCTION check_expired_premium() TO anon;
                GRANT EXECUTE ON FUNCTION reset_monthly_credits() TO authenticated;
                GRANT EXECUTE ON FUNCTION reset_monthly_credits() TO anon;
                GRANT EXECUTE ON FUNCTION consume_freemium_credits(UUID, TEXT, INTEGER, JSONB) TO authenticated;
                GRANT EXECUTE ON FUNCTION consume_freemium_credits(UUID, TEXT, INTEGER, JSONB) TO anon;
                
                -- Set default privileges for future objects
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO authenticated;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO anon;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO authenticated;
                ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon;
            """)
            
            print("✅ Database tables created with RLS policies, security fixes, and proper Supabase permissions")
    
    # ============================================================================
    # TRANSACTION OPERATIONS (Expenses + Income)
    # ============================================================================
    
    async def save_transaction(self, transaction: Transaction) -> Transaction:
        """Save a transaction to the database"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO transactions (
                    user_id, amount, description, category, transaction_type,
                    original_message, source_platform, merchant, confidence_score, tags
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, created_at
            """, 
            transaction.user_id, transaction.amount, transaction.description,
            transaction.category, transaction.transaction_type.value,
            transaction.original_message, transaction.source_platform,
            transaction.merchant, transaction.confidence_score, 
            json.dumps(transaction.tags)
            )
            
            transaction.id = result['id']
            transaction.created_at = result['created_at']
            return transaction

    async def get_user_transactions(self, user_id: str, days: int = 30, 
                          transaction_type: str = None) -> List[Transaction]:
        """Get user transactions for the specified period"""
        async with self.pool.acquire() as conn:
            where_clause = "WHERE user_id = $1 AND date >= $2"
            params = [user_id, datetime.now() - timedelta(days=days)]
            
            if transaction_type:
                where_clause += " AND transaction_type = $3"
                params.append(transaction_type)
            
            query = f"""
                SELECT * FROM transactions 
                {where_clause}
                ORDER BY date DESC
            """
            
            rows = await conn.fetch(query, *params)
            
            return [self._row_to_transaction(row) for row in rows]

    async def get_transaction_summary(self, user_id: str, days: int = 30) -> TransactionSummary:
        """Get transaction summary for the specified period"""
        async with self.pool.acquire() as conn:
            start_date = datetime.now() - timedelta(days=days)
            
            # Get summary data
            summary_row = await conn.fetchrow("""
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type = 'income' THEN amount ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN transaction_type = 'expense' THEN amount ELSE 0 END), 0) as total_expenses,
                    COUNT(CASE WHEN transaction_type = 'income' THEN 1 END) as income_count,
                    COUNT(CASE WHEN transaction_type = 'expense' THEN 1 END) as expense_count,
                    COUNT(*) as total_transactions
                FROM transactions 
                WHERE user_id = $1 AND date >= $2
            """, user_id, start_date)
            
            # Get expense categories
            category_rows = await conn.fetch("""
                SELECT category, SUM(amount) as total
                FROM transactions 
                WHERE user_id = $1 AND date >= $2 AND transaction_type = 'expense'
                GROUP BY category
                ORDER BY total DESC
                LIMIT 5
            """, user_id, start_date)
            
            expense_categories = [
                {"category": row['category'], "total": float(row['total'])}
                for row in category_rows
            ]
            
            return TransactionSummary(
                user_id=user_id,
                period_days=days,
                total_income=float(summary_row['total_income']),
                total_expenses=float(summary_row['total_expenses']),
                income_count=summary_row['income_count'],
                expense_count=summary_row['expense_count'],
                total_transactions=summary_row['total_transactions'],
                expense_categories=expense_categories
            )

    # ============================================================================
    # REMINDER OPERATIONS
    # ============================================================================
    
    async def save_reminder(self, reminder: Reminder) -> Reminder:
        """Save a reminder to the database"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO reminders (
                    user_id, title, description, source_platform, due_datetime,
                    reminder_type, priority, tags
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id, created_at
            """,
            reminder.user_id, reminder.title, reminder.description,
            reminder.source_platform, reminder.due_datetime,
            reminder.reminder_type.value, reminder.priority.value,
            reminder.tags
            )
            
            reminder.id = result['id']
            reminder.created_at = result['created_at']
            return reminder

    async def get_user_reminders(self, user_id: str, include_completed: bool = False, 
                       limit: int = 10) -> List[Reminder]:
        """Get user reminders"""
        async with self.pool.acquire() as conn:
            where_clause = "WHERE user_id = $1"
            params = [user_id]
            
            if not include_completed:
                where_clause += " AND is_completed = FALSE"
            
            query = f"""
                SELECT * FROM reminders 
                {where_clause}
                ORDER BY due_datetime ASC NULLS LAST, created_at DESC
                LIMIT $2
            """
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def get_due_reminders(self, user_id: str, hours_ahead: int = 24) -> List[Reminder]:
        """Get reminders due within specified hours"""
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() + timedelta(hours=hours_ahead)
            
            rows = await conn.fetch("""
                SELECT * FROM reminders 
                WHERE user_id = $1 
                AND is_completed = FALSE
                AND due_datetime IS NOT NULL
                AND due_datetime <= $2
                AND (snooze_until IS NULL OR snooze_until <= NOW())
                ORDER BY due_datetime ASC, priority DESC
            """, user_id, cutoff_time)
            
            return [self._row_to_reminder(row) for row in rows]
    
    async def mark_reminder_complete(self, reminder_id: int, user_id: str) -> bool:
        """Mark reminder as completed"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE reminders 
                SET is_completed = TRUE, completed_at = NOW(), updated_at = NOW()
                WHERE id = $1 AND user_id = $2 AND is_completed = FALSE
            """, reminder_id, user_id)
            
            return result != "UPDATE 0"

    # ============================================================================
    # USER SETTINGS OPERATIONS
    # ============================================================================
    
    async def get_user_settings(self, user_id: str) -> Optional[UserSettings]:
        """Get user settings by user_id"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_settings WHERE user_id = $1", user_id
            )
            if row:
                return UserSettings(
                    user_id=str(row['user_id']),
                    name=row['name'],
                    currency=row['currency'],
                    language=row['language'],
                    timezone=row['timezone'],
                    is_premium=row['is_premium'],
                    telegram_id=row['telegram_id'],
                    premium_until=row['premium_until'],
                    freemium_credits=row['freemium_credits'],
                    credits_reset_date=row['credits_reset_date'],
                    last_bot_interaction=row['last_bot_interaction'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    async def get_user_settings_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user settings as a dict by user_id"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_settings WHERE user_id = $1", user_id
            )
            if row:
                return {
                    'user_id': str(row['user_id']),
                    'name': row['name'],
                    'currency': row['currency'],
                    'language': row['language'],
                    'timezone': row['timezone'],
                    'is_premium': row['is_premium'],
                    'telegram_id': row['telegram_id'],
                    'premium_until': row['premium_until'],
                    'freemium_credits': row['freemium_credits'],
                    'credits_reset_date': row['credits_reset_date'],
                    'last_bot_interaction': row['last_bot_interaction'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
            return None
    
    async def save_user_settings(self, settings: UserSettings) -> UserSettings:
        """Save or update user settings"""
        async with self.pool.acquire() as conn:
            # Use UPSERT to insert or update
            result = await conn.fetchrow("""
                INSERT INTO user_settings (
                    user_id, name, currency, language, timezone, 
                    telegram_id
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    currency = EXCLUDED.currency,
                    language = EXCLUDED.language,
                    timezone = EXCLUDED.timezone,                    
                    telegram_id = EXCLUDED.telegram_id,                    
                    updated_at = NOW()
                RETURNING *
            """, 
            settings.user_id, settings.name, settings.currency, settings.language, 
            settings.timezone, settings.telegram_id
            )
            
            return UserSettings(
                user_id=str(result['user_id']),
                name=result['name'],
                currency=result['currency'],
                language=result['language'],
                timezone=result['timezone'],
                is_premium=result['is_premium'],
                telegram_id=result['telegram_id'],
                premium_until=result['premium_until'],
                freemium_credits=result['freemium_credits'],
                credits_reset_date=result['credits_reset_date'],
                last_bot_interaction=result['last_bot_interaction'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            )

    # ============================================================================
    # PAYMENT OPERATIONS
    # ============================================================================

    async def create_payment(self, user_id: str, provider: str = "paypal", amount: float = 9.99, currency: str = "USD") -> str:
        """Create a payment record and return payment ID"""
        async with self.pool.acquire() as conn:
            # Calculate valid_until date (1 month from now for premium subscription)
            valid_until = datetime.now() + timedelta(days=30)
            
            result = await conn.fetchrow("""
                INSERT INTO payments (
                    user_id, provider, amount, currency, status, valid_until
                ) VALUES ($1, $2, $3, $4, 'pending', $5)
                RETURNING id
            """, user_id, provider, amount, currency, valid_until)
            
            payment_id = str(result['id'])
            print(f"✅ Created payment record {payment_id} for user {user_id}")
            return payment_id

    async def update_payment_status(self, payment_id: str, status: str, transaction_id: str = None, subscription_id: str = None):
        """Update payment status and related fields"""
        async with self.pool.acquire() as conn:
            # Update payment record
            result = await conn.fetchrow("""
                UPDATE payments 
                SET status = $2, 
                    transaction_id = $3,
                    subscription_id = $4,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING user_id, amount, currency, valid_until
            """, payment_id, status, transaction_id, subscription_id)
            
            if not result:
                raise ValueError(f"Payment {payment_id} not found")
            
            user_id = str(result['user_id'])
            print(f"✅ Updated payment {payment_id} status to {status}")

    async def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment details by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    id, user_id, provider, amount, currency, status,
                    transaction_id, subscription_id, valid_until,
                    created_at, updated_at
                FROM payments 
                WHERE id = $1
            """, payment_id)
            
            if not row:
                return None
            
            return {
                'id': str(row['id']),
                'user_id': str(row['user_id']),
                'provider': row['provider'],
                'amount': float(row['amount']),
                'currency': row['currency'],
                'status': row['status'],
                'transaction_id': row['transaction_id'],
                'subscription_id': row['subscription_id'],
                'valid_until': row['valid_until'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }

   
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _row_to_transaction(self, row) -> Transaction:
        """Convert database row to Transaction object"""
        return Transaction(
            id=row['id'],
            user_id=str(row['user_id']),
            amount=row['amount'],
            description=row['description'],
            category=row['category'],
            transaction_type=TransactionType(row['transaction_type']),
            original_message=row['original_message'],
            source_platform=row['source_platform'],
            merchant=row['merchant'],
            date=row['date'],
            receipt_image_url=row['receipt_image_url'],
            location=json.loads(row['location']) if row['location'] else None,
            is_recurring=row['is_recurring'],
            recurring_pattern=row['recurring_pattern'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            confidence_score=row['confidence_score'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def _row_to_reminder(self, row) -> Reminder:
        """Convert database row to Reminder object"""
        return Reminder(
            id=row['id'],
            user_id=str(row['user_id']),
            title=row['title'],
            description=row['description'],
            source_platform=row['source_platform'],
            due_datetime=row['due_datetime'],
            reminder_type=ReminderType(row['reminder_type']),
            priority=Priority(row['priority']),
            is_completed=row['is_completed'],
            is_recurring=row['is_recurring'],
            recurrence_pattern=row['recurrence_pattern'],
            notification_sent=row['notification_sent'],
            snooze_until=row['snooze_until'],
            tags=row['tags'],
            location_reminder=json.loads(row['location_reminder']) if row['location_reminder'] else None,
            attachments=json.loads(row['attachments']) if row['attachments'] else [],
            assigned_to_platforms=json.loads(row['assigned_to_platforms']) if row['assigned_to_platforms'] else [],
            created_at=row['created_at'],
            completed_at=row['completed_at'],
            updated_at=row['updated_at']
        )

