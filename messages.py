
MESSAGES = {
    "en": {
        "welcome_authenticated": (
            "👋 *Hello {first_name}!*\n\n"
            "How can I help you today? You can track expenses, manage reminders, and view summaries.\n\n"
            "Type /help for examples!"
        ),
        "welcome_unauthenticated": (
            "👋 *Welcome to OkanAssist Tracker!*\n\n"
            "To get started, please register your account by typing /register."
        ),
        "need_register_premium": "🔐 You need to register first. Type /register to create your account, then try again.",
        "telegram_already_registered": "❌ This Telegram account is already registered with email: {email}",
        "link_success": "✅ Telegram account linked to existing email! Welcome back {first_name}!",
        "link_failed": "❌ Failed to link accounts. Please contact support.",
        "registration_failed": "❌ Registration failed: {message}",
        "registration_success": "✅ Registration successful! Welcome {first_name}!",
        "registration_linking_failed": "❌ Registration failed during account linking. Please try again.",
        "user_not_registered": "User not registered. Please use /register command first.",
        "failed_retrieve_user_data": "❌ Failed to retrieve user data after linking. Please try logging in again or contact support.",
         "help_message": """
🤖 *OkanAssist*

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
        "credit_warning": "\n\n💳 **Credits remaining: {credits_remaining}**",
        "credit_low": "\n🚨 Almost out of credits! Type /upgrade for unlimited usage.",
        "insufficient_credits": "🚀 You've reached your credit limit. To continue, please /upgrade for unlimited access.",
        "session_expired": "⏰ Your session has expired. Please log in again with /start.",
        "generic_error": "❌ Something went wrong. Please try again or contact support.",
        "upgrade_to_premium": "🚀 *Upgrade to Premium!*\n\nClick the link below to unlock unlimited AI features.\n\n[Upgrade Now]({stripe_url})",
        "registration_html_success": ("""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Registration Successful</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        background-color: #f0f2f5;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        color: #333;
                    }}
                    .container {{
                        text-align: center;
                        background-color: #ffffff;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                        max-width: 400px;
                        width: 90%;
                    }}
                    .logo {{
                        width: 80px;
                        height: 80px;
                        margin-bottom: 20px;
                    }}
                    h1 {{
                        font-size: 24px;
                        margin-bottom: 10px;
                        color: #1c1e21;
                    }}
                    p {{
                        font-size: 16px;
                        margin-bottom: 30px;
                        line-height: 1.5;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 24px;
                        font-size: 16px;
                        font-weight: bold;
                        color: #fff;
                        background-color: #007bff;
                        border-radius: 6px;
                        text-decoration: none;
                        transition: background-color 0.3s;
                    }}
                    .button:hover {{
                        background-color: #0056b3;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <img src="{logo_url}" alt="OkanAssist Logo" class="logo">
                    <h1>Registration Confirmed!</h1>
                    <p>Your account is now active. You can return to Telegram and start tracking your finances.</p>
                    <a href="{download_url}" class="button">Download the Mobile App</a>
                </div>
            </body>
            </html>
"""),

    },
    "es": {
        "welcome_authenticated": (
            "👋 ¡*Hola {first_name}!*\n\n"
            "¿Cómo puedo ayudarte hoy? Puedes registrar gastos, gestionar recordatorios y ver resúmenes.\n\n"
            "Escribe /help para ver ejemplos."
        ),
        "welcome_unauthenticated": (
            "👋 ¡*Bienvenido a OkanAssist Tracker!*\n\n"
            "Para comenzar, por favor registra tu cuenta escribiendo /register."
        ),
        "need_register_premium": "🔐 Necesitas registrarte primero. Escribe /register para crear tu cuenta y vuelve a intentarlo.",
        "telegram_already_registered": "❌ Esta cuenta de Telegram ya está registrada con el email: {email}",
        "link_success": "✅ ¡Cuenta de Telegram vinculada a un email existente! ¡Bienvenido de nuevo {first_name}!",
        "link_failed": "❌ No se pudo vincular la cuenta. Por favor, contacta a soporte.",
        "registration_failed": "❌ El registro falló: {message}",
        "registration_success": "✅ ¡Registro completado! ¡Bienvenido {first_name}!",
        "registration_linking_failed": "❌ El registro falló durante la vinculación de la cuenta. Por favor, inténtalo de nuevo.",
        "user_not_registered": "Usuario no registrado. Por favor, usa el comando /register primero.",
        "failed_retrieve_user_data": "❌ No se pudieron recuperar los datos del usuario después de la vinculación. Por favor, inicia sesión de nuevo o contacta a soporte.",
        "help_message": "🤖 *Ayuda de OkanAssist*\n\n*💰 Gastos:* 'Gasté $25 en el almuerzo'\n*⏰ Recordatorios:* 'Recuérdame pagar las facturas mañana'\n*📊 Resumen:* /balance\n\n¡Solo háblame con naturalidad!",
        "credit_warning": "\n\n💳 **Créditos restantes: {credits_remaining}**",
        "credit_low": "\n🚨 ¡Casi sin créditos! Escribe /upgrade para uso ilimitado.",
        "insufficient_credits": "🚀 Has alcanzado tu límite de créditos. Para continuar, por favor usa /upgrade para acceso ilimitado.",
        "session_expired": "⏰ Tu sesión ha expirado. Por favor, inicia sesión de nuevo con /start.",
        "generic_error": "❌ Algo salió mal. Por favor, inténtalo de nuevo o contacta a soporte.",
        "upgrade_to_premium": "🚀 ¡*Actualiza a Premium!*\n\nHaz clic en el enlace para desbloquear funciones ilimitadas de IA.\n\n[Actualizar ahora]({stripe_url})",
        "registration_html_success": """... (HTML content translated to Spanish) ...""",
    },
    "pt": {
        "welcome_authenticated": (
            "👋 *Olá {first_name}!*\n\n"
            "Como posso te ajudar hoje? Você pode registrar despesas, gerenciar lembretes e ver resumos.\n\n"
            "Digite /help para ver exemplos."
        ),
        "welcome_unauthenticated": (
            "👋 *Bem-vindo ao OkanAssist Tracker!*\n\n"
            "Para começar, por favor, registre sua conta digitando /register."
        ),
        "need_register_premium": "🔐 Você precisa se registrar primeiro. Digite /register para criar sua conta e tente novamente.",
        "telegram_already_registered": "❌ Esta conta do Telegram já está registrada com o e-mail: {email}",
        "link_success": "✅ Conta do Telegram vinculada a um e-mail existente! Bem-vindo de volta {first_name}!",
        "link_failed": "❌ Falha ao vincular a conta. Por favor, entre em contato com o suporte.",
        "registration_failed": "❌ O registro falhou: {message}",
        "registration_success": "✅ Registro concluído! Bem-vindo {first_name}!",
        "registration_linking_failed": "❌ O registro falhou durante a vinculação da conta. Por favor, tente novamente.",
        "user_not_registered": "Usuário não registrado. Por favor, use o comando /register primeiro.",
        "failed_retrieve_user_data": "❌ Falha ao recuperar os dados do usuário após a vinculação. Por favor, faça login novamente ou contate o suporte.",
        "help_message": "🤖 *Ajuda do OkanAssist*\n\n*💰 Despesas:* 'Gastei R$25 no almoço'\n*⏰ Lembretes:* 'Lembre-me de pagar as contas amanhã'\n*📊 Resumo:* /balance\n\nÉ só falar comigo normalmente!",
        "credit_warning": "\n\n💳 **Créditos restantes: {credits_remaining}**",
        "credit_low": "\n🚨 Quase sem créditos! Digite /upgrade para uso ilimitado.",
        "insufficient_credits": "🚀 Você atingiu seu limite de créditos. Para continuar, por favor, use /upgrade para acesso ilimitado.",
        "session_expired": "⏰ Sua sessão expirou. Por favor, faça login novamente com /start.",
        "generic_error": "❌ Algo deu errado. Por favor, tente novamente ou entre em contato com o suporte.",
        "upgrade_to_premium": "🚀 *Faça o Upgrade para Premium!*\n\nClique no link abaixo para desbloquear recursos ilimitados de IA.\n\n[Fazer Upgrade Agora]({stripe_url})",
        "registration_html_success": """... (HTML content translated to Portuguese) ...""",
    }
}


def get_message(key: str, lang: str, **kwargs) -> str:
    """Gets a translated message, falling back to English."""
    lang_short = lang.split('-')[0] if lang else 'en'
    
    # Fallback to 'en' if language or key is not found
    messages = MESSAGES.get(lang_short, MESSAGES['en'])
    message_template = messages.get(key, MESSAGES['en'].get(key, "Message key not found."))
    
    return message_template.format(**kwargs)