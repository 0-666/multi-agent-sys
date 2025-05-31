# agents/classifier_agent.py
from memory.shared_memory import global_shared_memory
from utils.llm_client import generate_text_gemini, summarize_pdf_bytes_gemini
from utils.file_parser import get_file_format, extract_text_from_pdf, parse_json_file, extract_text_from_email_file, extract_text_from_raw_email_content
import os

class ClassifierAgent:
    def __init__(self, memory=global_shared_memory):
        self.memory = memory
        self.name = "ClassifierAgent"

    def _get_content_for_intent(self, file_path: str, file_format: str, raw_content_bytes: bytes = None) -> str:
        """Extracts relevant text content for intent classification."""
        content_for_intent = ""
        if file_format == "PDF":
            if raw_content_bytes: # Prefer direct PDF processing if available and model supports it
                # For intent classification, a summary might be better than full text
                # Or, we can use Gemini's ability to process PDF directly for classification
                # Let's try a short summary for intent classification from PDF
                # content_for_intent = summarize_pdf_bytes_gemini(raw_content_bytes, "Briefly describe the type of document this is.")
                # OR, just extract text for now if summarization is too slow/costly for just intent
                content_for_intent = extract_text_from_pdf(file_path) # Fallback or primary
                if not content_for_intent and raw_content_bytes: # if PyPDF2 fails, try to send bytes (if model can take it)
                    # This part is tricky for intent classification directly.
                    # Usually, you'd give text. If sending bytes, the prompt needs to be clear.
                    print("PDF text extraction failed, attempting to use raw bytes summary (experimental for intent)")
                    # content_for_intent = summarize_pdf_bytes_gemini(raw_content_bytes, "What is the primary purpose or intent of this document? Choose from: Invoice, RFQ, Complaint, Regulation, Order, Query, General Information, Other.")
                    # For simplicity, let's stick to extracted text for intent classification.
            else:
                 content_for_intent = extract_text_from_pdf(file_path)

        elif file_format == "JSON":
            # For JSON, we might stringify it or pick key fields.
            # Stringifying the whole JSON might be too much for intent if it's large.
            # Let's use the stringified version for now, LLM can often pick up cues.
            json_data = parse_json_file(file_path)
            if json_data:
                content_for_intent = str(json_data)[:2000] # Truncate for very large JSONs
        elif file_format == "EMAIL":
            if file_path: # if it's a file
                _, _, _, body = extract_text_from_email_file(file_path)
                content_for_intent = body
            elif raw_content_bytes: # if it's raw bytes
                _, _, _, body = extract_text_from_raw_email_content(raw_content_bytes.decode('utf-8', errors='replace'))
                content_for_intent = body
        elif file_format == "TEXT": # Could be raw email body passed as text
            if file_path:
                with open(file_path, "r", encoding='utf-8') as f:
                    content_for_intent = f.read()
            elif raw_content_bytes: # if it's raw bytes for a text file
                 content_for_intent = raw_content_bytes.decode('utf-8', errors='replace')

        return content_for_intent[:4000] # Limit context for LLM

    def classify_intent(self, text_content: str, filename: str = "") -> str:
        if not text_content.strip():
            return "Unknown (No content)"

        # More robust prompt with few-shot examples or clearer instructions
        prompt = f"""
        Analyze the following text content (from file: "{filename}") and classify its primary intent.
        Choose one of the following intents:
        - Invoice (Billing statement, request for payment)
        - RFQ (Request for Quotation, inquiry about pricing for goods/services)
        - Complaint (Expression of dissatisfaction, issue report)
        - Regulation (Official rule, legal document, compliance information)
        - Order (Confirmation of a purchase, request to supply goods/services)
        - Query (A question, request for information not fitting other categories)
        - Marketing (Promotional material, newsletter, advertisement)
        - Internal Memo (Communication within an organization)
        - Resume (Curriculum Vitae, job application document)
        - Other (If none of the above clearly fit)

        Consider the overall purpose of the document.
        Provide only the intent label as your response. For example, if it's an invoice, respond with "Invoice".

        Text Content:
        ---
        {text_content[:3000]}
        ---
        Primary Intent:
        """
        # print(f"\nDEBUG: Sending to LLM for intent classification:\n{prompt}\n")
        intent = generate_text_gemini(prompt)
        # Clean up the response, sometimes LLMs add extra text
        possible_intents = ["Invoice", "RFQ", "Complaint", "Regulation", "Order", "Query", "Marketing", "Internal Memo", "Resume", "Other"]
        for pi in possible_intents:
            if pi.lower() in intent.lower():
                return pi
        return "Other" # Default if no specific intent is found

    def process(self, input_data: str, is_filepath=True):
        """
        Processes input, classifies, logs, and prepares for routing.
        input_data: Can be a filepath or raw string content (e.g., email body).
        is_filepath: True if input_data is a path, False if it's raw content.
        """
        thread_id = self.memory.generate_thread_id()
        filename = os.path.basename(input_data) if is_filepath else "raw_input"
        raw_bytes_content = None
        initial_content_for_processing = None # This will be passed to next agent

        if is_filepath:
            source_type = get_file_format(input_data)
            if not os.path.exists(input_data):
                print(f"Error: File not found at {input_data}")
                self.memory.add_log(self.name, {
                    "thread_id": thread_id, "source_filename": filename, "status": "Error",
                    "error": "File not found", "classified_format": "Unknown", "classified_intent": "Unknown"
                })
                return None, None, None # No routing

            with open(input_data, "rb") as f:
                raw_bytes_content = f.read()

            if source_type == "JSON":
                initial_content_for_processing = parse_json_file(input_data)
            elif source_type == "PDF":
                initial_content_for_processing = extract_text_from_pdf(input_data) # Text for next agent
                # Or pass raw_bytes_content if PDF agent can handle it
            elif source_type == "EMAIL": # .eml file
                sender, subject, recipients, body = extract_text_from_email_file(input_data)
                initial_content_for_processing = {
                    "sender": sender, "subject": subject,
                    "recipients": recipients, "body": body,
                    "original_format": "EMAIL_FILE"
                }
            elif source_type == "TEXT": # plain .txt file
                 with open(input_data, "r", encoding='utf-8') as f:
                    initial_content_for_processing = f.read()


        else: # Raw content (assumed to be email text for now as per prompt)
            source_type = "EMAIL" # Assume raw text is an email body
            raw_bytes_content = input_data.encode('utf-8') # Convert string to bytes
            sender, subject, recipients, body = extract_text_from_raw_email_content(input_data)
            initial_content_for_processing = {
                "sender": sender, "subject": subject,
                "recipients": recipients, "body": body,
                "original_format": "EMAIL_TEXT"
            }


        content_for_intent = self._get_content_for_intent(input_data if is_filepath else None, source_type, raw_bytes_content)
        intent = self.classify_intent(content_for_intent, filename)

        log_entry = {
            "thread_id": thread_id,
            "source": filename,
            "classified_format": source_type,
            "classified_intent": intent,
            "status": "Classified"
        }
        self.memory.add_log(self.name, log_entry)
        self.memory.update_context(thread_id, {
            "source_filename": filename,
            "classified_format": source_type,
            "classified_intent": intent,
            "initial_sender": initial_content_for_processing.get("sender") if isinstance(initial_content_for_processing, dict) else None
        })

        # Data to be routed
        routing_data = {
            "thread_id": thread_id,
            "original_filename": filename,
            "classified_format": source_type,
            "classified_intent": intent,
            "content": initial_content_for_processing, # This is the parsed content
            "raw_bytes_content": raw_bytes_content # For agents that might need original bytes (e.g. PDF agent)
        }

        # Determine target agent
        target_agent_name = None
        if source_type == "JSON":
            target_agent_name = "JSONAgent"
        elif source_type == "EMAIL" or (source_type == "TEXT" and intent not in ["Invoice", "RFQ", "Regulation"]): # TEXT could be email-like
            target_agent_name = "EmailAgent"
        elif source_type == "PDF":
            # If PDF content is an Invoice or RFQ, and we had an agent for that...
            # For now, if it's a PDF, and the intent is something an email agent might handle (e.g., Complaint, Query)
            # we can route its *text content* to the Email Agent.
            # This part needs refinement based on how deeply PDF content should be processed.
            # The prompt says "routes to correct agent". Email and JSON are the only processing agents specified.
            if intent in ["Complaint", "Query", "Order","RFQ"]: # If PDF's intent aligns with email agent's capabilities
                target_agent_name = "EmailAgent"
                # Ensure content for EmailAgent is text
                if not isinstance(routing_data["content"], str):
                    routing_data["content"] = extract_text_from_pdf(input_data) if is_filepath else ""
            else:
                print(f"Classifier: PDF with intent '{intent}' has no specific processing agent beyond classification. Logging only.")
                # No specific agent to route to based on current setup for PDF + (Invoice/RFQ/Regulation etc.)
        else:
            print(f"Classifier: No specific agent for format '{source_type}' and intent '{intent}'. Logging only.")

        return target_agent_name, routing_data, thread_id
    