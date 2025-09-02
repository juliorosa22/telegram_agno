# core/database.py - Supabase integrated version
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

    # Premium user linking (Supabase user <-> Telegram user)
    async def link_telegram_user(self, supabase_user_id: str, telegram_id: str):
        """Link a Supabase user to a Telegram user ID (insert or update)"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO premium_users (user_id, telegram_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET telegram_id = $2
                """,
                supabase_user_id, telegram_id
            )

    async def get_telegram_id_by_user(self, supabase_user_id: str) -> str | None:
        """Get Telegram user ID by Supabase user ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT telegram_id FROM premium_users WHERE user_id = $1",
                supabase_user_id
            )
            return row["telegram_id"] if row and row["telegram_id"] else None
    """Database manager integrated with Supabase Auth"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool = None
    
    async def connect(self):
        """Initialize database connection"""
        self.pool = await asyncpg.create_pool(self.database_url)
        #await self._create_tables()
        #print("✅ Database connected with Supabase Auth integration")
        print("✅ Database connected")

    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            print("✅ Database disconnected")
    
    async def _create_tables(self):
        """Create application-specific tables (users handled by Supabase)"""
        async with self.pool.acquire() as conn:
            # Create update timestamp function first
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            # Transactions table (expenses + income)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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
                COMMENT ON COLUMN transactions.user_id IS 'References auth.users.id from Supabase Auth';
                COMMENT ON COLUMN transactions.amount IS 'Transaction amount (positive values only)';
                COMMENT ON COLUMN transactions.transaction_type IS 'Type: expense or income';
                COMMENT ON COLUMN transactions.source_platform IS 'Platform where transaction was created';
                COMMENT ON COLUMN transactions.confidence_score IS 'AI parsing confidence (0.00-1.00)';
            """)
            
            # Reminders table (updated to use Supabase user_id)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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
                COMMENT ON COLUMN reminders.user_id IS 'References auth.users.id from Supabase Auth';
                COMMENT ON COLUMN reminders.reminder_type IS 'Type: task, event, deadline, habit, or general';
                COMMENT ON COLUMN reminders.priority IS 'Priority: urgent, high, medium, or low';
                COMMENT ON COLUMN reminders.source_platform IS 'Platform where reminder was created';
            """)
            
            # User activity table (simplified - no user data stored locally)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                    activity_type TEXT NOT NULL CHECK (activity_type IN ('transaction_added', 'reminder_added', 'reminder_completed', 'summary_requested', 'query', 'login', 'credit_used')),
                    platform_type TEXT CHECK (platform_type IN ('telegram', 'whatsapp', 'mobile_app', 'web_app')),
                    activity_data JSONB DEFAULT '{}' NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for user_activity
                CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity(user_id);
                CREATE INDEX IF NOT EXISTS idx_activity_type ON user_activity(activity_type);
                CREATE INDEX IF NOT EXISTS idx_activity_date ON user_activity(created_at);
                CREATE INDEX IF NOT EXISTS idx_activity_user_date ON user_activity(user_id, created_at);
                
                -- Table comment
                COMMENT ON TABLE user_activity IS 'User activity tracking for analytics and usage patterns';
            """)
            
            # Updated user settings table with freemium credits
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
                    name TEXT,
                    currency TEXT DEFAULT 'USD' NOT NULL,
                    language TEXT DEFAULT 'en' NOT NULL,
                    timezone TEXT DEFAULT 'UTC' NOT NULL,
                    is_premium BOOLEAN DEFAULT FALSE NOT NULL,
                    telegram_id TEXT UNIQUE,
                    premium_until TIMESTAMPTZ,
                    freemium_credits INTEGER DEFAULT 30 NOT NULL CHECK (freemium_credits >= 0),
                    credits_reset_date DATE DEFAULT CURRENT_DATE NOT NULL,
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
                COMMENT ON COLUMN user_settings.user_id IS 'References auth.users.id from Supabase Auth';
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
            
            # Credit usage tracking table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS credit_usage (
                    id SERIAL PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                    operation_type TEXT NOT NULL CHECK (operation_type IN ('text_message', 'receipt_processing', 'bank_statement', 'summary_request', 'ai_query')),
                    credits_used INTEGER NOT NULL CHECK (credits_used > 0),
                    credits_remaining INTEGER NOT NULL CHECK (credits_remaining >= 0),
                    is_premium_user BOOLEAN NOT NULL DEFAULT FALSE,
                    activity_data JSONB DEFAULT '{}' NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW() NOT NULL
                );
                
                -- Indexes for credit_usage
                CREATE INDEX IF NOT EXISTS idx_credit_usage_user ON credit_usage(user_id);
                CREATE INDEX IF NOT EXISTS idx_credit_usage_date ON credit_usage(created_at);
                CREATE INDEX IF NOT EXISTS idx_credit_usage_type ON credit_usage(operation_type);
                CREATE INDEX IF NOT EXISTS idx_credit_usage_user_date ON credit_usage(user_id, created_at);
                
                -- Table comment
                COMMENT ON TABLE credit_usage IS 'Track freemium credit usage for analytics and billing';
                COMMENT ON COLUMN credit_usage.operation_type IS 'Type of operation that consumed credits';
                COMMENT ON COLUMN credit_usage.credits_used IS 'Number of credits consumed by this operation';
                COMMENT ON COLUMN credit_usage.credits_remaining IS 'Credits remaining after this operation';
                COMMENT ON COLUMN credit_usage.is_premium_user IS 'Whether user was premium at time of operation';
            """)
            
            # Payments table for subscription management
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL CHECK (provider IN ('paypal', 'mercadopago')),
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
                COMMENT ON COLUMN payments.user_id IS 'References auth.users.id from Supabase Auth';
                COMMENT ON COLUMN payments.provider IS 'Payment provider: paypal or mercadopago';
                COMMENT ON COLUMN payments.amount IS 'Payment amount (positive values only)';
                COMMENT ON COLUMN payments.status IS 'Payment status: pending, success, failed, or cancelled';
                COMMENT ON COLUMN payments.transaction_id IS 'External payment provider transaction ID';
                COMMENT ON COLUMN payments.subscription_id IS 'Provider subscription ID for recurring payments';
                COMMENT ON COLUMN payments.valid_until IS 'Premium access valid until this date';
            """)
            
            # Enable Row Level Security (RLS) on all tables
            await conn.execute("""
                ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
                ALTER TABLE reminders ENABLE ROW LEVEL SECURITY;
                ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;
                ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
                ALTER TABLE credit_usage ENABLE ROW LEVEL SECURITY;
                ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
            """)
            
            # Create OPTIMIZED RLS Policies for transactions
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
            
            # Create OPTIMIZED RLS Policies for reminders
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
            
            # Create OPTIMIZED RLS Policies for user_activity
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own activity" ON user_activity;
                DROP POLICY IF EXISTS "Users can insert own activity" ON user_activity;
                
                CREATE POLICY "Users can view own activity" ON user_activity
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own activity" ON user_activity
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
            """)
            
            # Create OPTIMIZED RLS Policies for user_settings
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
            
            # Create OPTIMIZED RLS Policies for credit_usage
            await conn.execute("""
                DROP POLICY IF EXISTS "Users can view own credit usage" ON credit_usage;
                DROP POLICY IF EXISTS "Users can insert own credit usage" ON credit_usage;
                
                CREATE POLICY "Users can view own credit usage" ON credit_usage
                    FOR SELECT USING ((SELECT auth.uid()) = user_id);
                CREATE POLICY "Users can insert own credit usage" ON credit_usage
                    FOR INSERT WITH CHECK ((SELECT auth.uid()) = user_id);
            """)
            
            # Create OPTIMIZED RLS Policies for payments
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
            
            # Function to automatically update premium status based on payments
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_premium_status()
                RETURNS TRIGGER AS $$
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
                $$ LANGUAGE plpgsql;
            """)
            
            # Trigger to automatically update premium status on payment success
            await conn.execute("""
                DROP TRIGGER IF EXISTS payment_success_trigger ON payments;
                CREATE TRIGGER payment_success_trigger
                    AFTER INSERT OR UPDATE ON payments
                    FOR EACH ROW
                    EXECUTE FUNCTION update_premium_status();
            """)
            
            # Function to check and update expired premium subscriptions
            await conn.execute("""
                CREATE OR REPLACE FUNCTION check_expired_premium()
                RETURNS void AS $$
                BEGIN
                    UPDATE user_settings 
                    SET is_premium = FALSE, updated_at = NOW()
                    WHERE is_premium = TRUE 
                    AND premium_until IS NOT NULL 
                    AND premium_until < NOW();
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            # Function to reset monthly freemium credits
            await conn.execute("""
                CREATE OR REPLACE FUNCTION reset_monthly_credits()
                RETURNS INTEGER AS $$
                DECLARE
                    affected_users INTEGER;
                BEGIN
                    -- Reset credits for non-premium users whose reset date has passed
                    UPDATE user_settings 
                    SET freemium_credits = 30,
                        credits_reset_date = CURRENT_DATE,
                        updated_at = NOW()
                    WHERE is_premium = FALSE
                    AND credits_reset_date < CURRENT_DATE - INTERVAL '1 month';
                    
                    GET DIAGNOSTICS affected_users = ROW_COUNT;
                    
                    -- Log the reset operation
                    INSERT INTO user_activity (user_id, activity_type, platform_type, activity_data)
                    SELECT user_id, 'credit_reset', 'system', 
                           jsonb_build_object('reset_date', CURRENT_DATE, 'credits_reset_to', 30)
                    FROM user_settings 
                    WHERE is_premium = FALSE
                    AND credits_reset_date = CURRENT_DATE;
                    
                    RETURN affected_users;
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            # Function to consume freemium credits with proper checks
            await conn.execute("""
                CREATE OR REPLACE FUNCTION consume_freemium_credits(
                    p_user_id UUID,
                    p_operation_type TEXT,
                    p_credits_needed INTEGER,
                    p_activity_data JSONB DEFAULT '{}'
                )
                RETURNS JSONB AS $$
                DECLARE
                    current_credits INTEGER;
                    is_premium_user BOOLEAN;
                    credits_after INTEGER;
                    result JSONB;
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
                        -- Log the usage but don't consume credits
                        INSERT INTO credit_usage (user_id, operation_type, credits_used, credits_remaining, is_premium_user, activity_data)
                        VALUES (p_user_id, p_operation_type, 0, -1, true, p_activity_data);
                        
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
                    
                    -- Consume credits
                    credits_after := current_credits - p_credits_needed;
                    
                    UPDATE user_settings 
                    SET freemium_credits = credits_after,
                        updated_at = NOW()
                    WHERE user_id = p_user_id;
                    
                    -- Log the credit usage
                    INSERT INTO credit_usage (user_id, operation_type, credits_used, credits_remaining, is_premium_user, activity_data)
                    VALUES (p_user_id, p_operation_type, p_credits_needed, credits_after, false, p_activity_data);
                    
                    -- Log user activity
                    INSERT INTO user_activity (user_id, activity_type, platform_type, activity_data)
                    VALUES (p_user_id, 'credit_used', 'system', 
                            jsonb_build_object(
                                'operation_type', p_operation_type,
                                'credits_used', p_credits_needed,
                                'credits_remaining', credits_after
                            ));
                    
                    RETURN jsonb_build_object(
                        'success', true,
                        'is_premium', false,
                        'credits_used', p_credits_needed,
                        'credits_remaining', credits_after,
                        'message', 'Credits consumed successfully'
                    );
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            print("✅ Database tables created with OPTIMIZED RLS policies, triggers, freemium credits, and premium management")
    
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
            
            # Use the utility method instead of manual object creation
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
    # REMINDER OPERATIONS (Updated for Supabase)
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
            
            # Use the utility method instead of manual object creation
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
            
            success = result != "UPDATE 0"
            
            if success:
                await self._log_user_activity(
                    user_id,
                    'reminder_completed',
                    {'reminder_id': reminder_id}
                )
            
            return success
    
    async def get_reminder_summary(self, user_id: str, days: int = 30) -> ReminderSummary:
        """Get reminder summary for user"""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total counts
            total_row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_completed) as completed,
                    COUNT(*) FILTER (WHERE NOT is_completed) as pending,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime < NOW()) as overdue,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime::date = CURRENT_DATE) as due_today,
                    COUNT(*) FILTER (WHERE NOT is_completed AND due_datetime::date = CURRENT_DATE + 1) as due_tomorrow
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2
            """, user_id, cutoff_date)
            
            # Priority breakdown
            priority_rows = await conn.fetch("""
                SELECT priority, COUNT(*) as count
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY priority
            """, user_id, cutoff_date)
            
            by_priority = {row['priority']: row['count'] for row in priority_rows}
            
            # Type breakdown
            type_rows = await conn.fetch("""
                SELECT reminder_type, COUNT(*) as count
                FROM reminders 
                WHERE user_id = $1 AND created_at >= $2 AND NOT is_completed
                GROUP BY reminder_type
            """, user_id, cutoff_date)
            
            by_type = {row['reminder_type']: row['count'] for row in type_rows}
            
            return ReminderSummary(
                total_count=total_row['total'],
                completed_count=total_row['completed'],
                pending_count=total_row['pending'],
                overdue_count=total_row['overdue'],
                due_today_count=total_row['due_today'],
                due_tomorrow_count=total_row['due_tomorrow'],
                by_priority=by_priority,
                by_type=by_type,
                period_days=days
            )

    # ============================================================================
    # ACTIVITY TRACKING
    # ============================================================================
    
    async def _log_user_activity(self, user_id: str, activity_type: str, activity_data: Dict[str, Any] = None, platform_type: str = None):
        """Log user activity"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO user_activity (user_id, activity_type, platform_type, activity_data)
                    VALUES ($1, $2, $3, $4)
                """, user_id, activity_type, platform_type, json.dumps(activity_data) if activity_data else None)
                
            except Exception as e:
                print(f"❌ ACTIVITY LOG ERROR: {e}")

    async def get_user_activity_summary(self, user_id: str, days: int = 30) -> UserActivity:
        """Get user activity summary"""
        async with self.pool.acquire() as conn:
            # Get activity counts
            activity_row = await conn.fetchrow("""
                SELECT COUNT(*) as total_interactions
                FROM user_activity 
                WHERE user_id = $1 
                AND created_at >= $2
            """, user_id, datetime.now() - timedelta(days=days))
            
            # Get last activity dates
            last_transaction = await conn.fetchval("""
                SELECT MAX(created_at) FROM transactions WHERE user_id = $1
            """, user_id)
            
            last_reminder = await conn.fetchval("""
                SELECT MAX(created_at) FROM reminders WHERE user_id = $1
            """, user_id)
            
            # Get summaries
            transaction_summary = await self.get_transaction_summary(user_id, days)
            reminder_summary = await self.get_reminder_summary(user_id, days)
            
            return UserActivity(
                user_id=user_id,
                transaction_summary=transaction_summary,
                reminder_summary=reminder_summary,
                last_transaction_date=last_transaction,
                last_reminder_date=last_reminder,
                total_interactions=activity_row['total_interactions']
            )

    # ============================================================================
    # USER SETTINGS OPERATIONS
    # ============================================================================
    async def get_user_settings(self, user_id: str) -> UserSettings:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_settings WHERE user_id = $1", user_id
            )
            if row:
                return UserSettings(
                    user_id=str(row['user_id']),
                    currency=row['currency'],
                    language=row['language'],
                    timezone=row['timezone'],
                    is_premium=row['is_premium'],
                    telegram_id=row['telegram_id'],
                    premium_until=row['premium_until'],
                    last_bot_interaction=row['last_bot_interaction'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            # Return defaults if not found
            return UserSettings(user_id=user_id)

    async def save_user_settings(self, settings: UserSettings) -> UserSettings:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_settings (user_id, currency, language, timezone, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    currency = $2,
                    language = $3,
                    timezone = $4,
                    updated_at = NOW()
                """,
                settings.user_id, settings.currency, settings.language, settings.timezone
            )
            return await self.get_user_settings(settings.user_id)

    # ============================================================================
    # PAYMENT OPERATIONS
    # ============================================================================

    async def create_payment(self, user_id: str, provider: str = "paypal", amount: float = 9.99, currency: str = "USD") -> str:
        """Create a payment record and return payment ID"""
        async with self.pool.acquire() as conn:
            # Calculate valid_until date (1 month from now for premium subscription)
            from datetime import datetime, timedelta
            valid_until = datetime.now() + timedelta(days=30)
            
            result = await conn.fetchrow("""
                INSERT INTO payments (
                    user_id, provider, amount, currency, status, valid_until, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, 'pending', $5, NOW(), NOW())
                RETURNING id
            """, user_id, provider, amount, currency, valid_until)
            
            payment_id = str(result['id'])
            
            # Log activity
            await self._log_user_activity(
                user_id, 
                'payment_created', 
                {
                    'payment_id': payment_id,
                    'provider': provider,
                    'amount': amount,
                    'currency': currency
                },
                'telegram'
            )
            
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
            
            # If payment successful, update user premium status
            if status == 'success' and result['valid_until']:
                await conn.execute("""
                    INSERT INTO user_settings (user_id, is_premium, premium_until, updated_at)
                    VALUES ($1, TRUE, $2, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        is_premium = TRUE,
                        premium_until = $2,
                        updated_at = NOW()
                """, user_id, result['valid_until'])
                
                print(f"✅ Updated premium status for user {user_id} until {result['valid_until']}")
            
            # Log activity
            await self._log_user_activity(
                user_id,
                'payment_updated',
                {
                    'payment_id': payment_id,
                    'status': status,
                    'transaction_id': transaction_id,
                    'subscription_id': subscription_id,
                    'amount': float(result['amount']),
                    'currency': result['currency']
                },
                'telegram'
            )
            
            print(f"✅ Updated payment {payment_id} status to {status}")

    async def get_user_payments(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user payment history"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id, provider, amount, currency, status, 
                    transaction_id, subscription_id, valid_until,
                    created_at, updated_at
                FROM payments 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, user_id, limit)
            
            return [
                {
                    'id': str(row['id']),
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
                for row in rows
            ]

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

    async def check_and_expire_premium_subscriptions(self):
        """Check and update expired premium subscriptions (utility method)"""
        async with self.pool.acquire() as conn:
            # Update expired premium subscriptions
            result = await conn.execute("""
                UPDATE user_settings 
                SET is_premium = FALSE, updated_at = NOW()
                WHERE is_premium = TRUE 
                AND premium_until IS NOT NULL 
                AND premium_until < NOW()
            """)
            
            # Extract number of affected rows from result
            affected_rows = int(result.split()[-1]) if result and 'UPDATE' in result else 0
            
            if affected_rows > 0:
                print(f"✅ Expired {affected_rows} premium subscriptions")
            
            return affected_rows

    async def get_active_premium_users_count(self) -> int:
        """Get count of users with active premium subscriptions"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM user_settings 
                WHERE is_premium = TRUE 
                AND (premium_until IS NULL OR premium_until > NOW())
            """)
            return result or 0

    # ============================================================================
    # FREEMIUM CREDIT OPERATIONS
    # ============================================================================

    async def consume_credits(self, user_id: str, operation_type: str, credits_needed: int, activity_data: dict = None) -> dict:
        """Consume freemium credits for an operation"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT consume_freemium_credits($1, $2, $3, $4) as result
            """, user_id, operation_type, credits_needed, json.dumps(activity_data or {}))
            
            return json.loads(result['result'])

    async def get_user_credits(self, user_id: str) -> dict:
        """Get user's current credit status"""
        async with self.pool.acquire() as conn:
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
        async with self.pool.acquire() as conn:
            result = await conn.fetchval("SELECT reset_monthly_credits()")
            return result

    async def get_credit_usage_analytics(self, user_id: str, days: int = 30) -> dict:
        """Get credit usage analytics for a user"""
        async with self.pool.acquire() as conn:
            # Get usage by operation type
            usage_rows = await conn.fetch("""
                SELECT operation_type, 
                       SUM(credits_used) as total_credits,
                       COUNT(*) as operation_count
                FROM credit_usage 
                WHERE user_id = $1 
                AND created_at >= NOW() - INTERVAL '%s days'
                GROUP BY operation_type
                ORDER BY total_credits DESC
            """, user_id, days)
            
            # Get total usage
            total_row = await conn.fetchrow("""
                SELECT SUM(credits_used) as total_credits,
                       COUNT(*) as total_operations
                FROM credit_usage 
                WHERE user_id = $1 
                AND created_at >= NOW() - INTERVAL '%s days'
            """, user_id, days)
            
            return {
                "total_credits_used": total_row['total_credits'] or 0,
                "total_operations": total_row['total_operations'] or 0,
                "usage_by_type": [
                    {
                        "operation_type": row['operation_type'],
                        "credits_used": row['total_credits'],
                        "operation_count": row['operation_count']
                    }
                    for row in usage_rows
                ],
                "period_days": days
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
            transaction_type=TransactionType(row['transaction_type']),  # Convert to enum
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
            reminder_type=ReminderType(row['reminder_type']),  # Convert to enum
            priority=Priority(row['priority']),  # Convert to enum
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
    
    async def ensure_user_exists(self, telegram_id: str, user_data: dict):
        """Ensure user exists in user_settings table with Telegram data"""
        async with self.pool.acquire() as conn:
            # Check if user exists by telegram_id
            existing_user = await conn.fetchrow(
                "SELECT user_id FROM user_settings WHERE telegram_id = $1", 
                telegram_id
            )
            
            if not existing_user:
                # Create a new user_id for Telegram-only users
                import uuid
                user_id = str(uuid.uuid4())
                
                await conn.execute("""
                    INSERT INTO user_settings (
                        user_id, telegram_id, currency, language, timezone, 
                        last_bot_interaction, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW(), NOW(), NOW())
                    ON CONFLICT (telegram_id) DO UPDATE SET
                        last_bot_interaction = NOW(),
                        updated_at = NOW()
                """, 
                user_id, telegram_id, "USD", 
                user_data.get("language_code", "en")[:2], "UTC"
                )
                
                print(f"✅ Created user settings for Telegram ID: {telegram_id}")
            else:
                # Update last interaction
                await conn.execute("""
                    UPDATE user_settings 
                    SET last_bot_interaction = NOW(), updated_at = NOW()
                    WHERE telegram_id = $1
                """, telegram_id)
                
                print(f"✅ Updated user interaction for Telegram ID: {telegram_id}")

