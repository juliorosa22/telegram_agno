MESSAGES = {
    # Authentication and Registration Messages
    "welcome_authenticated": (
        "👋 *Hello {first_name}!*\n\n"
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
    ),
    "welcome_unauthenticated": (
        "👋 *Welcome to OkanFit Personal Tracker!*\n\n"
        "🤖 I'm your personal financial assistant powered by AI.\n\n"
        "🔐 To get started, please register your account:\n"
        "Type /register to create your account\n\n"
        "✨ After registration, you can:\n"
        "💰 Track expenses with natural language\n"
        "📸 Process receipt photos automatically\n"
        "⏰ Set smart reminders\n"
        "📊 Get financial insights"
    ),
    "welcome_premium": (
        "🎉 *Welcome to OkanAssist your personal assistant for tracking transactions and activities!*\n\n"
        "To unlock premium AI features, complete your payment:\n"
        "💳 [Pay with PayPal]({paypal_url})\n\n"
        "After payment, you'll have access to:\n"
        "🤖 AI-powered expense tracking\n"
        "📊 Smart financial insights\n"
        "⏰ Intelligent reminders\n"
        "📈 Advanced analytics"
    ),
    "need_register_premium": (
        "🔐 You need to register first to link premium features.\n\n"
        "Type /register to create your account, then try again."
    ),
    "telegram_already_registered": "❌ This Telegram account is already registered with email: {email}",
    "link_success": "✅ Telegram account linked to existing email! Welcome back {first_name}!",
    "link_failed": "❌ Failed to link accounts. Please contact support.",
    "registration_failed": "❌ Registration failed: {message}",
    "registration_success": "✅ Registration successful! Welcome {first_name}!\n\n💡 You can manage your account at the Supabase dashboard.",
    "registration_linking_failed": "❌ Registration failed during account linking. Please try again.",
    "user_not_registered": "User not registered. Please use /register command first.",
    "failed_retrieve_user_data": "❌ Failed to retrieve user data after linking. Please try logging in again or contact support.",  # NEW: Added missing key

    # Help and General Messages
    "help_message": """
🤖 *OkanAssist Personal Assistant - Agno Powered*

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

Just talk to me naturally - I understand! 🎉
    """,

    # Credit and Premium Messages
    "credit_warning": "\n\n💳 **Credits remaining: {credits_remaining}**",
    "credit_low": "\n🚨 Almost out of credits! Type /upgrade for unlimited usage.",
    "credits_remaining": "\n\n💳 Credits remaining: {credits_remaining}",
    "insufficient_credits": (
        "❌ **Insufficient Credits**\n\n"
        "💳 Available: {credits_available} credits\n"
        "🔧 Needed: {credits_needed} credits\n\n"
        "🎯 **Upgrade to Premium for unlimited usage!**\n"
        "💎 Premium includes:\n"
        "• ♾️ Unlimited AI processing\n"
        "• 📊 Advanced analytics\n"
        "• 🔄 Priority support\n"
        "• 📱 Cross-platform sync\n\n"
        "Type /upgrade to get premium access!"
    ),

    # NEW: Additional Error and Edge Case Messages for Better UX
    "session_expired": "⏰ Your session has expired. Please log in again with /start.",
    "data_incomplete": "⚠️ Your profile data is incomplete. Please update your details in the dashboard.",
    "service_unavailable": "🚧 Service temporarily unavailable. Please try again later.",
    "generic_error": "❌ Something went wrong. Please try again or contact support.",
    "auth_timeout": "⏳ Authentication timed out. Please try again."
}