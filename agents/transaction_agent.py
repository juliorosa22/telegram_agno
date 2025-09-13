from agno.agent import Agent
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import asyncio  # <-- 1. IMPORT ASYNCIO
from agno.models.groq import Groq
# Fix: Use package imports from __init__.py
from tools import Transaction, TransactionType

class TransactionAgent:
    """Specialized agent for handling financial transactions"""
    
    def __init__(self, supabase_client):
        self.supabase_client = supabase_client
        
        # Define simplified categories
        self.expense_categories = ["Essentials", "Food & Dining", "Transportation", "Shopping", "Entertainment", "Utilities", "Healthcare", "Travel", "Education", "Home"]
        self.income_categories = ["Salary", "Freelance", "Business", "Investment", "Gift", "Refund", "Rental", "Other Income"]
        
        # Build category strings for agent instructions
        expense_cats = ", ".join(self.expense_categories)
        income_cats = ", ".join(self.income_categories)
        
        # Initialize Groq agent for text processing (cost-effective)
        self.text_agent = Agent(
            name="TextTransactionProcessor",
            model=Groq(id="llama-3.3-70b-versatile", temperature=0.2),  # Ultra-fast, very low cost for text
            instructions=f"""
            You are a financial transaction processor specialized in extracting transaction data from text messages.
            
            EXPENSE CATEGORIES (use exactly one of these):
            {expense_cats}
            
            INCOME CATEGORIES (use exactly one of these):
            {income_cats}
            
            Extract from text messages:
            - Amount (convert to positive number)
            - Description (clean, concise)
            - Transaction type (expense or income)
            - Category (choose from the appropriate list above)
            - Merchant (if mentioned)
            
            IMPORTANT: Category MUST be exactly one from the predefined lists.
            If unsure, use "Shopping" for expenses or "Other Income" for income.
            
            Always return valid JSON format only, no explanations.
            """
        )
        
        # Initialize Gemini agent for vision processing (receipt/image analysis)
        self.vision_agent = Agent(
            name="VisionTransactionProcessor",
            model="gemini-1.5-flash", #TODO adjust properly # Cost-effective with vision capabilities
            instructions=f"""
            You are a receipt and document processor that extracts financial data from images and PDFs.
            
            EXPENSE CATEGORIES (use exactly one of these):
            {expense_cats}
            
            For receipt images, extract:
            - Total amount (the final amount paid)
            - Merchant/store name
            - Date of transaction
            - Category (choose from: {self.expense_categories})
            - Any notable items
            
            For bank statements, extract:
            - All transactions with amounts, descriptions, and dates
            - Categorize each transaction appropriately
            
            IMPORTANT: Category MUST be exactly one from the predefined expense categories.
            If unsure, use "Shopping" as default.
            
            Always return valid JSON format only, no explanations.
            """
        )
    
    async def process_message(self, user_id: str, message: str) -> str:
        """Process a text message for transaction data using Groq"""
        try:
            # Use Groq for fast, cheap text processing
            extraction_prompt = f"""
You are a precise financial data extractor. Your task is to analyze the user's message and extract transaction details into a strict JSON format.

**Step-by-Step Thought Process:**
1.  **Identify Intent:** First, determine if the message describes an **expense** (money going out) or an **income** (money coming in).
    *   **Expense Keywords:** Look for words like 'spent', 'paid', 'bought', 'cost', 'charged', 'bill'. If no keywords are present, most transactions are expenses by default (e.g., "uber ride $25").
    *   **Income Keywords:** Look for words like 'earned', 'received', 'got paid', 'salary', 'bonus', 'refund', 'deposit','freelance'.
2.  **Select Category List:** Based on the intent, select the appropriate category list.
    *   **Expense Categories:** {self.expense_categories}
    *   **Income Categories:** {self.income_categories}
3.  **Extract Data:** Pull all required fields and strictly adhere to the output format.

**User Message:** "{message}"

**Rules & Output Format:**
- Return ONLY a valid JSON object. No explanations or surrounding text.
- The `transaction_type` MUST be either "expense" or "income".
- The `category` MUST be one of the exact strings from the chosen list.
- If you are unsure of the category, use "Shopping" for expenses or "Other Income" for income.
- If no clear transaction is found, return `{{"transaction_found": false}}`.

**Examples:**
- User: "just paid 20 bucks for my spotify sub" -> {{"amount": 20.00, "description": "Spotify subscription", "transaction_type": "expense", "category": "Entertainment", "merchant": "Spotify", "confidence": 0.95}}
- User: "got a $50 refund from amazon" -> {{"amount": 50.00, "description": "Refund from Amazon", "transaction_type": "income", "category": "Refund", "merchant": "Amazon", "confidence": 0.9}}
- User: "salary deposit $3000" -> {{"amount": 3000.00, "description": "Salary deposit", "transaction_type": "income", "category": "Salary", "merchant": null, "confidence": 1.0}}

**JSON Output:**
```json
{{
  "amount": <number>,
  "description": "<string>",
  "transaction_type": "<'expense' or 'income'>",
  "category": "<string from lists>",
  "merchant": "<string or null>",
  "confidence": <number from 0.0 to 1.0>,
  "transaction_found": true
}}
            """
            
            # --- 2. APPLY THE FIX HERE ---
            response_obj = await asyncio.to_thread(self.text_agent.run, extraction_prompt)
            response = str(response_obj)
            
            # Enhanced JSON parsing for Groq responses
            try:
                # Clean response to extract JSON
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
            except:
                # Fallback parsing if JSON isn't returned
                data = self._fallback_parse(message)
            
            if not data.get("transaction_found", True):
                return "🤔 I couldn't find transaction information in your message. Try something like 'Spent $25 on groceries' or 'Received $500 salary'."
            
            # Validate and fix category
            validated_category = self._validate_category(data["category"], data["transaction_type"])
            data["category"] = validated_category
            print("Extracted data:", data)
            # Create and save transaction
            transaction = Transaction(
                user_id=user_id,
                amount=abs(float(data["amount"])),
                description=data["description"],
                category=data["category"],
                transaction_type=TransactionType(data["transaction_type"]),
                original_message=message,
                source_platform="telegram",
                merchant=data.get("merchant"),
                confidence_score=data.get("confidence", 0.85),
                tags=[]
            )
            
            # Save to database
            saved_transaction = await self.supabase_client.database.save_transaction(transaction)
            
            # Generate response
            emoji = "💸" if data["transaction_type"] == "expense" else "💰"
            return (
                f"{emoji} *Transaction recorded!*\n\n"
                f"📝 *Description:* {data['description']}\n"
                f"💵 *Amount:* ${data['amount']:.2f}\n"
                f"📂 *Category:* {data['category']}\n"
                f"📊 *Type:* {data['transaction_type'].title()}\n"
                f"🚀 *Processed by:* Groq Llama 3.1 70B"
            )
            
        except Exception as e:
            print(f"❌ Error processing transaction message: {e}")
            return "❌ Sorry, I couldn't process that transaction. Please try again with a clearer format."
    
    async def process_receipt_image(self, user_id: str, image_path: str) -> str:
        """Process receipt image using Gemini vision capabilities"""
        try:
            # Use Gemini vision to extract receipt data
            extraction_prompt = f"""
            Analyze this receipt image and extract transaction details.
            
            Available categories: {self.expense_categories}
            
            Extract:
            - Total amount (the final amount paid)
            - Merchant/store name
            - Date of transaction
            - Category (choose from: {self.expense_categories})
            - Any notable items
            
            Rules:
            - Category MUST be exactly one from the list above
            - If unsure, use "Shopping"
            
            Return ONLY a JSON object with the extracted data, no explanation:
            """
            
            response = await self.vision_agent.run(
                extraction_prompt,
                images=[image_path]
            )
            
            # Parse the response
            try:
                # Clean response to extract JSON
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    data = json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
            except:
                # Fallback if JSON parsing fails
                return "📸 Receipt processed, but I had trouble extracting the data. Please manually enter the transaction."
            
            # Validate category
            validated_category = self._validate_category(data.get("category", "Shopping"), "expense")
            
            # Create transaction from receipt data
            transaction = Transaction(
                user_id=user_id,
                amount=abs(float(data.get("amount", 0))),
                description=f"Purchase at {data.get('merchant', 'Store')}",
                category=validated_category,
                transaction_type=TransactionType.EXPENSE,
                original_message="Receipt upload",
                source_platform="telegram",
                merchant=data.get("merchant"),
                confidence_score=0.90,
                tags=["receipt"],
                receipt_image_url=image_path  # Store the path
            )
            
            # Save to database
            saved_transaction = await self.supabase_client.database.save_transaction(transaction)
            
            return (
                f"📸 *Receipt processed successfully!*\n\n"
                f"🏪 *Merchant:* {data.get('merchant', 'Unknown')}\n"
                f"💵 *Amount:* ${data.get('amount', 0):.2f}\n"
                f"📂 *Category:* {validated_category}\n"
                f"📅 *Date:* {data.get('date', 'Today')}\n\n"
                f"Transaction automatically saved! ✅\n"
                f"🔍 *Processed by:* Gemini 1.5 Flash Vision"
            )
            
        except Exception as e:
            print(f"❌ Error processing receipt image: {e}")
            return "❌ Sorry, I couldn't process that receipt image. Please try again or enter the transaction manually."
    
    async def process_bank_statement(self, user_id: str, pdf_path: str) -> str:
        """Process bank statement PDF using Gemini"""
        try:
            # Use Gemini to extract multiple transactions from PDF
            extraction_prompt = f"""
            Analyze this bank statement PDF and extract all transactions.
            
            Available EXPENSE categories: {self.expense_categories}
            Available INCOME categories: {self.income_categories}
            
            For each transaction, extract:
            - Amount (positive for income, expenses should be marked clearly)
            - Description
            - Date
            - Transaction type (income or expense)
            - Category (choose from appropriate list above)
            
            Rules:
            - Category MUST be from the appropriate list
            - Use "Shopping" for unclear expenses, "Other Income" for unclear income
            
            Return ONLY a JSON array of transactions, no explanation:
            """
            
            response = await self.vision_agent.run(
                extraction_prompt,
                files=[pdf_path]
            )
            
            # Parse transactions
            try:
                # Clean response to extract JSON array
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    transactions_data = json.loads(json_str)
                else:
                    # Try to find JSON object instead
                    json_start = response.find('{')
                    json_end = response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = response[json_start:json_end]
                        single_transaction = json.loads(json_str)
                        transactions_data = [single_transaction]
                    else:
                        raise ValueError("No JSON found in response")
            except:
                return "📄 PDF processed, but I had trouble extracting transaction data. Please check the file format."
            
            # Save each transaction
            saved_count = 0
            for trans_data in transactions_data:
                try:
                    # Validate category
                    validated_category = self._validate_category(
                        trans_data.get("category", "Shopping"), 
                        trans_data.get("transaction_type", "expense")
                    )
                    
                    transaction = Transaction(
                        user_id=user_id,
                        amount=abs(float(trans_data.get("amount", 0))),
                        description=trans_data.get("description", "Bank transaction"),
                        category=validated_category,
                        transaction_type=TransactionType(trans_data.get("transaction_type", "expense")),
                        original_message="Bank statement import",
                        source_platform="telegram",
                        confidence_score=0.85,
                        tags=["bank_import"]
                    )
                    
                    await self.supabase_client.database.save_transaction(transaction)
                    saved_count += 1
                except Exception as e:
                    print(f"❌ Error saving transaction: {e}")
                    continue
            
            return (
                f"📄 *Bank statement processed!*\n\n"
                f"✅ *{saved_count} transactions imported*\n"
                f"📊 *Ready for analysis*\n\n"
                f"Use /balance to see your updated summary!\n"
                f"🔍 *Processed by:* Gemini 1.5 Flash"
            )
            
        except Exception as e:
            print(f"❌ Error processing bank statement: {e}")
            return "❌ Sorry, I couldn't process that bank statement. Please ensure it's a valid PDF with transaction data."
    
    async def get_summary(self, user_id: str, days: int = 30) -> str:
        """Generate financial summary using Groq for insights"""
        try:
            # Get summary data from database
            summary = await self.supabase_client.database.get_transaction_summary(user_id, days)
            
            # Use Groq for fast insights generation
            insights_prompt = f"""
            Analyze this financial summary and provide brief insights:
            
            - Total Income: ${summary.total_income:.2f}
            - Total Expenses: ${summary.total_expenses:.2f}
            - Income Transactions: {summary.income_count}
            - Expense Transactions: {summary.expense_count}
            - Top Categories: {summary.expense_categories}
            
            Provide 2-3 brief insights about spending patterns and financial health.
            Keep it concise and encouraging.
            """
            
            insights = await self.text_agent.run(insights_prompt)
            
            # Calculate net flow
            net_flow = summary.total_income - summary.total_expenses
            flow_emoji = "📈" if net_flow > 0 else "📉" if net_flow < 0 else "📊"
            
            # Build summary message
            message = f"""
{flow_emoji} *Financial Summary (Last {days} days)*

💰 *Income:* ${summary.total_income:,.2f} ({summary.income_count} transactions)
💸 *Expenses:* ${summary.total_expenses:,.2f} ({summary.expense_count} transactions)
📊 *Net Flow:* ${net_flow:,.2f}

*Top Expense Categories:*
"""
            
            for cat in summary.expense_categories[:3]:
                message += f"• {cat['category']}: ${cat['total']:,.2f}\n"
            
            message += f"\n*AI Insights:*\n{insights}\n\n🚀 *Analysis by:* Groq Llama 3.1 70B"
            
            return message
            
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            return "❌ Sorry, I couldn't generate your financial summary right now. Please try again later."
    
    def _validate_category(self, category: str, transaction_type: str) -> str:
        """Validate category against predefined lists"""
        if transaction_type == "expense":
            if category in self.expense_categories:
                return category
            # Default for invalid expense categories
            return "Shopping"
        else:  # income
            if category in self.income_categories:
                return category
            # Default for invalid income categories
            return "Other Income"
    
    def _fallback_parse(self, message: str) -> Dict[str, Any]:
        """Fallback parsing when Agno doesn't return JSON"""
        # Extract amount
        amount_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', message)
        if not amount_match:
            return {"transaction_found": False}
        
        amount = float(amount_match.group(1).replace(',', ''))
        
        # Determine transaction type
        expense_words = ['spent', 'paid', 'bought', 'cost', 'expense']
        income_words = ['earned', 'received', 'income', 'salary', 'bonus']
        
        message_lower = message.lower()
        if any(word in message_lower for word in expense_words):
            transaction_type = "expense"
            category = "Shopping"  # Default expense category
        elif any(word in message_lower for word in income_words):
            transaction_type = "income"
            category = "Other Income"  # Default income category
        else:
            # Default based on context clues
            transaction_type = "expense"  # Most common
            category = "Shopping"
        
        # Clean description
        description = re.sub(r'\$?[\d,]+\.?\d*', '', message).strip()
        description = re.sub(r'\b(spent|paid|bought|for|on|at)\b', '', description, flags=re.IGNORECASE).strip()
        
        if not description:
            description = f"Transaction for ${amount:.2f}"
        
        return {
            "amount": amount,
            "description": description,
            "transaction_type": transaction_type,
            "category": category,
            "merchant": None,
            "confidence": 0.7
        }