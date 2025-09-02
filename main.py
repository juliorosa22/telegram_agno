import sys
import asyncio
import argparse
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

def run_api():
    """Run the API service using uvicorn"""
    import uvicorn
    from api import app
    
    print("🔧 Starting API service...")
    
    # Use uvicorn.run() directly - this will create its own event loop
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

async def run_bot():
    """Run the Telegram bot service"""
    print("🤖 Starting Bot service...")
    
    try:
        from bot_handler import AgnoTelegramBot
        
        bot = AgnoTelegramBot()
        await bot.run()
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        traceback.print_exc()
        raise

def verify_environment():
    """Verify all required environment variables are set"""
    import os
    
    required_vars = [
        'TELEGRAM_BOT_TOKEN',
        'SUPABASE_URL', 
        'SUPABASE_SECRET_KEY',
        'DATABASE_URL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("💡 Make sure your .env file contains all required variables")
        return False
    
    print("✅ All required environment variables are set")
    return True

def run_both_services():
    """Run both API and Bot services using multiprocessing"""
    import multiprocessing
    import time
    
    def api_process():
        """Process function for API"""
        try:
            run_api()
        except Exception as e:
            print(f"❌ API process error: {e}")
    
    def bot_process():
        """Process function for Bot"""
        try:
            # Create new event loop for this process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_bot())
        except Exception as e:
            print(f"❌ Bot process error: {e}")
    
    print("🚀 Starting both API and Bot services...")
    
    # Start API process
    api_proc = multiprocessing.Process(target=api_process, name="API-Service")
    api_proc.start()
    
    # Give API time to start
    time.sleep(3)
    
    # Start Bot process
    bot_proc = multiprocessing.Process(target=bot_process, name="Bot-Service")
    bot_proc.start()
    
    try:
        # Wait for both processes
        api_proc.join()
        bot_proc.join()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        
        # Terminate processes gracefully
        if bot_proc.is_alive():
            bot_proc.terminate()
            bot_proc.join(timeout=5)
        
        if api_proc.is_alive():
            api_proc.terminate()
            api_proc.join(timeout=5)
        
        print("✅ Services stopped")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="OkanFit Assist AI Service")
    parser.add_argument(
        '--mode', 
        choices=['api', 'bot', 'both'], 
        default='both',
        help='Service mode: api (API only), bot (Bot only), or both (default)'
    )
    parser.add_argument(
        '--api-port',
        type=int,
        default=8000,
        help='API service port (default: 8000)'
    )
    
    args = parser.parse_args()
    
    print("🚀 Starting OkanAssist AI Services...")
    
    # Verify environment
    if not verify_environment():
        return
    
    try:
        if args.mode == 'api':
            print("🔧 Starting API service only...")
            run_api()
            
        elif args.mode == 'bot':
            print("🤖 Starting Bot service only...")
            # Run bot in the main event loop
            asyncio.run(run_bot())
            
        elif args.mode == 'both':
            run_both_services()
            
    except KeyboardInterrupt:
        print("\n🛑 Services stopped by user")
    except Exception as e:
        print(f"❌ Error starting services: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()