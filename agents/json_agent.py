# agents/json_agent.py
from memory.shared_memory import global_shared_memory
# from utils.llm_client import generate_text_gemini # If LLM is needed for complex reformatting

class JSONAgent:
    def __init__(self, memory=global_shared_memory):
        self.memory = memory
        self.name = "JSONAgent"
        # Example target schema (could be loaded from a config file)
        self.target_schema = {
            "invoice": {
                "required_fields": ["invoice_id", "customer_name", "total_amount", "issue_date", "items"],
                "item_schema": {"name": str, "quantity": int, "unit_price": float}
            },
            "rfq": {
                "required_fields": ["rfq_id", "company_name", "request_details", "submission_deadline"],
                "details_schema": {"item_description": str, "quantity_needed": int}
            }
            # Add other schemas as needed
        }

    def process(self, data_payload: dict):
        thread_id = data_payload.get("thread_id")
        original_json = data_payload.get("content")
        intent = data_payload.get("classified_intent")
        filename = data_payload.get("original_filename", "N/A")

        if not isinstance(original_json, dict):
            error_msg = "Invalid data: Expected a JSON dictionary."
            self.memory.add_log(self.name, {
                "thread_id": thread_id, "source": filename, "status": "Error",
                "error": error_msg, "details": "Input was not a dictionary"
            })
            self.memory.update_context(thread_id, {"json_agent_status": "Error", "json_agent_error": error_msg})
            return

        extracted_data = {}
        anomalies = []
        processed_successfully = False

        # Determine schema based on intent (simplified)
        schema_key = intent.lower() if intent else None
        current_schema_config = self.target_schema.get(schema_key)

        if not current_schema_config:
            anomaly_msg = f"No target schema defined for intent: {intent}. Processing as generic JSON."
            anomalies.append(anomaly_msg)
            extracted_data = original_json # Store original if no schema
            # In a real system, you might have a default extraction or use LLM to guess structure
        else:
            # Validate required fields
            missing_fields = [field for field in current_schema_config["required_fields"] if field not in original_json]
            if missing_fields:
                anomalies.append(f"Missing required fields: {', '.join(missing_fields)}")

            # Extract fields based on schema (simple extraction)
            for field in current_schema_config["required_fields"]:
                if field in original_json:
                    extracted_data[field] = original_json[field]
                # else: already handled by missing_fields

            # Example: Basic type checking for items in an invoice
            if schema_key == "invoice" and "items" in extracted_data and isinstance(extracted_data["items"], list):
                valid_items = []
                for i, item in enumerate(extracted_data["items"]):
                    if not isinstance(item, dict):
                        anomalies.append(f"Item {i+1} is not a valid object.")
                        continue
                    
                    item_valid = True
                    for key, expected_type in current_schema_config["item_schema"].items():
                        if key not in item:
                            anomalies.append(f"Item {i+1} missing field: {key}")
                            item_valid = False
                        elif not isinstance(item[key], expected_type):
                            anomalies.append(f"Item {i+1} field '{key}' has incorrect type (expected {expected_type.__name__}, got {type(item[key]).__name__})")
                            item_valid = False
                    if item_valid:
                         valid_items.append(item)
                extracted_data["items"] = valid_items # only keep valid structure items or transformed items

            # Add more specific validation/reformatting as needed
            processed_successfully = not missing_fields # Simple success condition

        log_entry = {
            "thread_id": thread_id,
            "source": filename,
            "intent": intent,
            "status": "Processed" if processed_successfully and not anomalies else "ProcessedWithAnomalies",
            "extracted_data": extracted_data,
            "anomalies": anomalies
        }
        self.memory.add_log(self.name, log_entry)
        self.memory.update_context(thread_id, {
            "json_agent_status": log_entry["status"],
            "last_extracted_json_fields": list(extracted_data.keys()),
            "json_anomalies_count": len(anomalies)
        })
        