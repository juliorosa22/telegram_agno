#!/usr/bin/env python3
"""
Simple script to connect to the database and create all tables
Run this script to set up your database schema with freemium credits support
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import with absolute path
from tools.database import Database

async def setup_database():
    """Set up the database by creating all tables"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not found!")
            print("Please set DATABASE_URL in your .env file")
            return False
        
        print("🔗 Connecting to database...")
        
        # Initialize database connection
        db = Database(database_url)
        await db.connect()
        
        print("📊 Creating tables and functions...")
        
        # Create all tables, triggers, and functions
        await db._create_tables()
        
        print("Tables created")
        
        # Close connection
        await db.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

async def test_connection():
    """Test database connection without creating tables"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not found!")
            return False
        
        print("🔗 Testing database connection...")
        
        # Initialize database connection
        db = Database(database_url)
        await db.connect()
        
        print("✅ Database connection successful!")
        
        # Close connection
        await db.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def reset_database():
    """Reset database by dropping and recreating all tables"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Get database URL from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL environment variable not found!")
            return False
        
        print("⚠️  RESETTING DATABASE - This will delete ALL data!")
        confirm = input("Type 'YES' to confirm: ")
        
        if confirm != 'YES':
            print("❌ Reset cancelled")
            return False
        
        print("🔗 Connecting to database...")
        
        # Initialize database connection
        db = Database(database_url)
        await db.connect()
        
        print("🗑️  Dropping existing tables...")
        
        # Drop all tables and functions (same as the reset script)
        async with db.pool.acquire() as conn:
            # Drop all policies
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own transactions\" ON transactions;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own transactions\" ON transactions;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can update own transactions\" ON transactions;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can delete own transactions\" ON transactions;")
            
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own reminders\" ON reminders;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own reminders\" ON reminders;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can update own reminders\" ON reminders;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can delete own reminders\" ON reminders;")
            
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own activity\" ON user_activity;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own activity\" ON user_activity;")
            
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own settings\" ON user_settings;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own settings\" ON user_settings;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can update own settings\" ON user_settings;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can delete own settings\" ON user_settings;")
            
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own credit usage\" ON credit_usage;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own credit usage\" ON credit_usage;")
            
            await conn.execute("DROP POLICY IF EXISTS \"Users can view own payments\" ON payments;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can insert own payments\" ON payments;")
            await conn.execute("DROP POLICY IF EXISTS \"Users can update own payments\" ON payments;")
            
            # Drop all triggers
            await conn.execute("DROP TRIGGER IF EXISTS update_transactions_updated_at ON transactions;")
            await conn.execute("DROP TRIGGER IF EXISTS update_reminders_updated_at ON reminders;")
            await conn.execute("DROP TRIGGER IF EXISTS update_user_settings_updated_at ON user_settings;")
            await conn.execute("DROP TRIGGER IF EXISTS update_payments_updated_at ON payments;")
            await conn.execute("DROP TRIGGER IF EXISTS payment_success_trigger ON payments;")
            
            # Drop all tables
            await conn.execute("DROP TABLE IF EXISTS user_activity CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS transactions CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS reminders CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS credit_usage CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS payments CASCADE;")
            await conn.execute("DROP TABLE IF EXISTS user_settings CASCADE;")
            
            # Drop all functions
            await conn.execute("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;")
            await conn.execute("DROP FUNCTION IF EXISTS update_premium_status() CASCADE;")
            await conn.execute("DROP FUNCTION IF EXISTS check_expired_premium() CASCADE;")
            await conn.execute("DROP FUNCTION IF EXISTS reset_monthly_credits() CASCADE;")
            await conn.execute("DROP FUNCTION IF EXISTS consume_freemium_credits(UUID, TEXT, INTEGER, JSONB) CASCADE;")
        
        print("📊 Creating new tables...")
        
        # Create all tables, triggers, and functions
        await db._create_tables()
        
        print("✅ Database reset completed successfully!")
        
        # Close connection
        await db.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False

def print_help():
    """Print help information"""
    print("\n🔧 Database Setup Script")
    print("=" * 50)
    print("Available commands:")
    print("  setup    - Create all tables and functions")
    print("  test     - Test database connection")
    print("  reset    - Reset database (WARNING: deletes all data)")
    print("  help     - Show this help message")
    print("\nExamples:")
    print("  python setup_database.py setup")
    print("  python setup_database.py test")
    print("  python setup_database.py reset")
    print("\nMake sure to set DATABASE_URL in your .env file first!")

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        success = await setup_database()
        exit(0 if success else 1)
    
    elif command == "test":
        success = await test_connection()
        exit(0 if success else 1)
    
    elif command == "reset":
        success = await reset_database()
        exit(0 if success else 1)
    
    elif command in ["help", "-h", "--help"]:
        print_help()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())