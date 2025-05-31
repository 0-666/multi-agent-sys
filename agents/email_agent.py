# agents/email_agent.py
from memory.shared_memory import global_shared_memory
from utils.llm_client import generate_text_gemini
import re
import json

class EmailAgent:
    def __init__(self, memory=global_shared_memory):
        self.memory = memory
        self.name = "EmailAgent"

    def _extract_email_address(self, text_sender_field: str) -> str:
        if not text_sender_field:
            return "Unknown"
        # Regex to find email addresses
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text_sender_field)
        return match.group(0) if match else text_sender_field # Return full if no email found

    def process(self, data_payload: dict):
        thread_id = data_payload.get("thread_id")
        intent = data_payload.get("classified_intent")
        filename = data_payload.get("original_filename", "N/A")
        email_content_data = data_payload.get("content") # Could be dict from .eml or str from text/PDF

        sender = "Unknown"
        subject = "N/A"
        body = ""

        if isinstance(email_content_data, dict): # Parsed from .eml or raw text by classifier
            sender_field = email_content_data.get("sender", "Unknown Sender")
            sender = self._extract_email_address(sender_field)
            subject = email_content_data.get("subject", "No Subject")
            body = email_content_data.get("body", "")
        elif isinstance(email_content_data, str): # From PDF text or plain text file
            body = email_content_data
            # Try to get sender from shared context if available (e.g., if classifier logged it)
            context = self.memory.get_context(thread_id)
            sender_field = context.get("initial_sender", "Unknown Sender (from context)")
            sender = self._extract_email_address(sender_field)
            # Subject might not be available for plain text
        else:
            error_msg = "Invalid email content data type."
            self.memory.add_log(self.name, {
                "thread_id": thread_id, "source": filename, "status": "Error",
                "error": error_msg, "details": f"Expected dict or str, got {type(email_content_data)}"
            })
            self.memory.update_context(thread_id, {"email_agent_status": "Error", "email_agent_error": error_msg})
            return

        if not body.strip():
            error_msg = "Email body is empty."
            self.memory.add_log(self.name, {
                "thread_id": thread_id, "source": filename, "status": "Error",
                "error": error_msg, "extracted_sender": sender, "extracted_subject": subject
            })
            self.memory.update_context(thread_id, {"email_agent_status": "Error", "email_agent_error": error_msg})
            return

        # Use LLM to determine urgency and format for CRM
        prompt = f"""
        Analyze the following email content:
        Sender: {sender}
        Subject: {subject}
        Body:
        ---
        {body[:3000]}
        ---

        Based on the content, determine the following:
        1. Urgency: Classify the urgency as Low, Medium, or High.
        2. CRM Summary: Provide a concise summary (1-2 sentences) of the main point or request, suitable for a CRM system.
        3. Extracted Entities (Optional): List any key entities like names, organizations, dates, or product names mentioned.

        Format your response as a JSON object with keys "urgency", "crm_summary", and "entities" (entities can be a list of strings).
        Example:
        {{
          "urgency": "High",
          "crm_summary": "Customer is reporting a critical system outage and requires immediate assistance.",
          "entities": ["System X", "John Doe", "Main St Office"]
        }}
        """
        llm_response_str = generate_text_gemini(prompt)

        # Attempt to parse the LLM response (it should be JSON)
        crm_data = {}
        urgency = "Medium" # Default
        crm_summary = "Could not summarize."
        entities = []

        try:
            # Gemini sometimes wraps JSON in ```json ... ```
            if llm_response_str.strip().startswith("```json"):
                llm_response_str = llm_response_str.strip()[7:-3].strip()
            elif llm_response_str.strip().startswith("```"): # More generic ``` wrapper
                 llm_response_str = llm_response_str.strip()[3:-3].strip()


            parsed_llm_response = json.loads(llm_response_str)
            urgency = parsed_llm_response.get("urgency", "Medium")
            crm_summary = parsed_llm_response.get("crm_summary", "Summary not extracted.")
            entities = parsed_llm_response.get("entities", [])
            crm_data = {
                "extracted_sender": sender,
                "extracted_subject": subject,
                "intent": intent, # From classifier
                "urgency": urgency,
                "crm_summary": crm_summary,
                "extracted_entities": entities,
                "full_body_preview": body[:200] + "..." if len(body) > 200 else body
            }
            status = "Processed"
        except json.JSONDecodeError:
            status = "ProcessedWithLLMError"
            crm_summary = f"LLM response was not valid JSON. Raw: {llm_response_str}"
            crm_data = {
                "extracted_sender": sender,
                "extracted_subject": subject,
                "intent": intent,
                "urgency": "Medium", # Default
                "crm_summary": crm_summary,
                "llm_raw_response": llm_response_str,
                "full_body_preview": body[:200] + "..." if len(body) > 200 else body
            }
        except Exception as e:
            status = "ProcessedWithLLMError"
            crm_summary = f"Error processing LLM response: {e}. Raw: {llm_response_str}"
            # crm_data population as above

        log_entry = {
            "thread_id": thread_id,
            "source": filename,
            "status": status,
            "crm_formatted_data": crm_data,
        }
        self.memory.add_log(self.name, log_entry)
        self.memory.update_context(thread_id, {
            "email_agent_status": status,
            "last_extracted_email_sender": sender,
            "last_extracted_email_topic": subject, # Or use CRM summary
            "last_extracted_email_urgency": urgency
        })