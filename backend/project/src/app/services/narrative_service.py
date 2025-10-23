# import os
# import re
# from litellm import completion
# from flask import current_app
# from .database_ops import get_vendor_statistics

# def clean_narrative_text(raw_text: str) -> str:
#     """
#     Cleans model output by removing unwanted newlines, spaces, and hidden characters.
#     """
#     if not raw_text:
#         return ""
#     # Remove zero-width and non-breaking spaces
#     text = re.sub(r'[\u200B-\u200D\uFEFF]', '', raw_text)
#     # Merge characters split by newlines (e.g., 'T\nh\ni\ns' → 'This')
#     text = re.sub(r'(?<=\S)\n(?=\S)', '', text)
#     # Replace multiple newlines with a single newline
#     text = re.sub(r'\n+', '\n', text)
#     # Normalize multiple spaces
#     text = re.sub(r'[ ]{2,}', ' ', text)
#     return text.strip()

# def generate_narrative(invoice, api_key: str):
#     """
#     Generates a human-readable summary for a specific invoice using a dynamically constructed,
#     context-aware prompt and a user-provided API key.
#     """
#     try:
#         # 1. Get historical vendor data for context
#         vendor_stats = get_vendor_statistics(invoice.vendor_name, invoice.id)
        
#         # 2. Pre-format numbers
#         avg_amount_str = f'{vendor_stats.get("avg_amount", 0):.2f}'
#         max_amount_str = f'{vendor_stats.get("max_amount", 0):.2f}'
#         current_amount_str = f'{invoice.amount:.2f}'

#         # 3. Persona
#         if invoice.risk_level == "High":
#             persona = "You are a senior fraud analyst. Your task is to write an urgent but professional alert for a finance manager, highlighting the critical red flags and the potential financial exposure."
#         elif invoice.risk_level == "Medium":
#             persona = "You are an AP specialist. Your task is to write a clear and concise summary for your manager, pointing out anomalies that require a second look before approval."
#         else:
#             persona = "You are an automated compliance checker. Your task is to provide a simple, affirmative statement that the invoice has passed all checks."

#         # 4. Risk drivers
#         risk_drivers = [factor.feature_name for factor in invoice.risk_factors]
#         drivers_text = ", ".join(risk_drivers) if risk_drivers else "None identified"

#         # 5. Prompt
#         prompt = f"""
#         {persona}

#         Your narrative must be concise, professional, and directly actionable for an Accounts Payable team.

#         ---
#         📊 **Vendor Baseline for {invoice.vendor_name}**
#         - Average Invoice Amount: ${avg_amount_str}
#         - Highest Previous Invoice: ${max_amount_str}
#         - Past Issues: None on record.
#         ---

#         ---
#         📄 **Current Invoice Details**
#         - Invoice ID: {invoice.id}
#         - Vendor: {invoice.vendor_name}
#         - Amount: ${current_amount_str}
#         - Date: {invoice.invoice_date.strftime('%Y-%m-%d')}
#         - Risk Score: {invoice.risk_score}
#         - Risk Level: {invoice.risk_level}
#         - Primary Risk Drivers: {drivers_text}
#         ---

#         ### Narrative Generation Rules:
#         1. Start by stating the risk level and score.
#         2. Compare the current invoice amount to the vendor's historical baseline.
#         3. Clearly state the primary risk drivers identified.
#         4. Conclude by selecting ONE action from:
#            - [Proceed with Payment]
#            - [Verify with Originator]
#            - [Requires Managerial Approval]
#            - [Place Payment on Hold - Query Vendor]
#         ---

#         Now, generate the narrative.
#         """

#         messages = [{"role": "user", "content": prompt}]

#         response = completion(
#             model="openai/gpt-4.1", 
#             messages=messages,
#             api_key=api_key
#         )
        
#         narrative = response.choices[0].message.content
#         narrative = clean_narrative_text(narrative)

#         if narrative:
#             return narrative
#         else:
#             current_app.logger.error("litellm model returned no content.")
#             raise Exception("Failed to generate narrative; the model returned an empty response.")

#     except Exception as e:
#         current_app.logger.error(f"An unexpected error occurred while generating the narrative: {e}")
#         return f"Narrative generation failed due to an internal error. Please review invoice {invoice.id} manually."


import os
import re
from litellm import completion
from flask import current_app
from .database_ops import get_vendor_statistics

def clean_narrative_text(raw_text: str) -> str:
    """
    Cleans model output by removing unwanted newlines, spaces, and hidden characters.
    """
    if not raw_text:
        return ""
    # Remove zero-width and non-breaking spaces
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', raw_text)
    # Merge characters split by newlines (e.g., 'T\nh\ni\ns' → 'This')
    text = re.sub(r'(?<=\S)\n(?=\S)', '', text)
    # Replace multiple newlines with a single newline
    text = re.sub(r'\n+', '\n', text)
    # Normalize multiple spaces
    text = re.sub(r'[ ]{2,}', ' ', text)
    return text.strip()

def generate_narrative(invoice, api_key: str):
    """
    Generates a human-readable summary for a specific invoice using a dynamically constructed,
    context-aware prompt and a user-provided API key.
    """
    try:
        # 1. Get historical vendor data for context
        vendor_stats = get_vendor_statistics(invoice.vendor_name, invoice.id)
        
        # 2. Pre-format numbers
        avg_amount_str = f'{vendor_stats.get("avg_amount", 0):.2f}'
        max_amount_str = f'{vendor_stats.get("max_amount", 0):.2f}'
        current_amount_str = f'{invoice.amount:.2f}'
        invoice_count = vendor_stats.get("invoice_count", 0)

        # 3. Calculate variance for context
        avg_amount = vendor_stats.get("avg_amount", 0)
        variance_pct = ((invoice.amount - avg_amount) / avg_amount * 100) if avg_amount > 0 else 0

        # 4. Dynamic persona based on risk level
        if invoice.risk_level == "High":
            persona = """You are a senior fraud analyst with 15+ years of experience in financial crime detection. 
Your primary responsibility is to protect the organization from fraudulent transactions and financial losses.
Your audience is the Finance Manager who needs clear, urgent, and actionable intelligence to make immediate decisions.
Your tone should be authoritative, direct, and focused on risk mitigation."""
            
        elif invoice.risk_level == "Medium":
            persona = """You are an experienced Accounts Payable specialist with expertise in payment verification and vendor management.
Your role is to identify anomalies that could indicate errors, policy violations, or potential fraud.
Your audience is the AP Manager who reviews flagged transactions before approval.
Your tone should be professional, analytical, and focused on due diligence."""
            
        else:
            persona = """You are an automated compliance system providing routine verification confirmations.
Your role is to document that standard controls have been satisfied.
Your audience is the AP team who processes approved invoices.
Your tone should be concise, affirmative, and procedural."""

        # 5. Risk drivers with detailed context
        risk_drivers = [factor.feature_name for factor in invoice.risk_factors]
        drivers_text = ", ".join(risk_drivers) if risk_drivers else "None identified"
        
        # Create detailed risk context
        risk_context = ""
        if "amount_deviation" in drivers_text.lower():
            risk_context += f"\n  • This invoice amount deviates significantly ({variance_pct:+.1f}%) from the vendor's historical average."
        if "new_vendor" in drivers_text.lower():
            risk_context += f"\n  • This is a new or infrequent vendor with limited transaction history ({invoice_count} previous invoices)."
        if "duplicate" in drivers_text.lower():
            risk_context += "\n  • Potential duplicate payment detected based on amount, date, or invoice number similarity."
        if "unusual_timing" in drivers_text.lower():
            risk_context += "\n  • Invoice submitted outside normal business patterns for this vendor."

        # 6. Enhanced prompt with detailed instructions
        prompt = f"""
{persona}

## OBJECTIVE
Generate a professional risk assessment narrative for Invoice #{invoice.id} that enables informed decision-making by the Accounts Payable team.

═══════════════════════════════════════════════════════════════════════

## VENDOR CONTEXT: {invoice.vendor_name}

**Historical Transaction Profile:**
- Total Previous Invoices: {invoice_count}
- Average Invoice Amount: ${avg_amount_str}
- Highest Previous Invoice: ${max_amount_str}
- Payment History: {vendor_stats.get("payment_history", "No prior issues documented")}
- Vendor Relationship: {vendor_stats.get("relationship_duration", "Established vendor")}

═══════════════════════════════════════════════════════════════════════

## CURRENT INVOICE ANALYSIS

**Transaction Details:**
- Invoice ID: {invoice.id}
- Vendor Name: {invoice.vendor_name}
- Invoice Amount: ${current_amount_str}
- Invoice Date: {invoice.invoice_date.strftime('%B %d, %Y')}
- Variance from Average: {variance_pct:+.1f}%

**Risk Assessment:**
- Risk Score: {invoice.risk_score}/100
- Risk Classification: {invoice.risk_level}
- Primary Risk Indicators: {drivers_text}

**Risk Factor Details:**{risk_context if risk_context else "\n  • No specific risk patterns identified."}

═══════════════════════════════════════════════════════════════════════

## NARRATIVE GENERATION REQUIREMENTS

**Structure your response with these mandatory sections:**

1. **RISK SUMMARY** (1-2 sentences)
   - Open with the risk classification and score
   - Immediately state whether this requires attention or is routine

2. **COMPARATIVE ANALYSIS** (2-3 sentences)
   - Compare current invoice amount to vendor baseline
   - Highlight any significant deviations (>20% variance is notable, >50% is critical)
   - Reference vendor transaction history and patterns

3. **RISK DRIVERS ASSESSMENT** (2-4 sentences)
   - Explain each primary risk driver in plain business language
   - Connect drivers to potential fraud scenarios or operational issues
   - Quantify the concern level for each driver

4. **RECOMMENDED ACTION** (1 sentence + action tag)
   - Provide ONE clear, specific action directive
   - Select the most appropriate action from these options:
     
     For LOW risk: **[Proceed with Payment]**
     For MEDIUM risk with minor concerns: **[Verify with Originator]**
     For MEDIUM risk with multiple flags: **[Requires Managerial Approval]**
     For HIGH risk: **[Place Payment on Hold - Query Vendor]**

═══════════════════════════════════════════════════════════════════════

## WRITING GUIDELINES

**Tone & Style:**
- Use clear, jargon-free business language
- Be specific and factual, avoiding vague statements
- Show urgency proportional to risk level
- Use active voice and direct statements

**Formatting:**
- Write in flowing paragraphs, not bullet points
- Keep total length between 100-150 words
- End with the action directive in square brackets

**Avoid:**
- Technical jargon or machine learning terminology
- Hedging language like "possibly" or "might be"
- Repetition of data already visible in the UI
- Generic statements that could apply to any invoice

═══════════════════════════════════════════════════════════════════════

Now generate the narrative assessment following all requirements above.
"""

        messages = [{"role": "user", "content": prompt}]

        response = completion(
            model="openai/gpt-4.1", 
            messages=messages,
            api_key=api_key,
            temperature=0.3,  # Lower temperature for more consistent, focused output
            max_tokens=500
        )
        
        narrative = response.choices[0].message.content
        narrative = clean_narrative_text(narrative)

        if narrative:
            return narrative
        else:
            current_app.logger.error("litellm model returned no content.")
            raise Exception("Failed to generate narrative; the model returned an empty response.")

    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred while generating the narrative: {e}")
        return f"Narrative generation failed due to an internal error. Please review invoice {invoice.id} manually."
