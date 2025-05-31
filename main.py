# main.py
import argparse
import os
from agents.classifier_agent import ClassifierAgent
from agents.json_agent import JSONAgent
from agents.email_agent import EmailAgent
from memory.shared_memory import global_shared_memory

# Ensure project root is in sys.path if running from a sub-directory or for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Orchestrator:
    def __init__(self, memory):
        self.memory = memory
        self.classifier_agent = ClassifierAgent(memory)
        self.json_agent = JSONAgent(memory)
        self.email_agent = EmailAgent(memory)
        self.agents = {
            "JSONAgent": self.json_agent,
            "EmailAgent": self.email_agent
        }

    def process_input(self, input_data: str, is_filepath=True):
        print(f"\n🚀 Orchestrator: Processing {'file' if is_filepath else 'raw text'}: {input_data if is_filepath else 'Input Text Snippet'}...")

        # 1. Classifier Agent
        target_agent_name, routing_data, thread_id = self.classifier_agent.process(input_data, is_filepath=is_filepath)

        if not target_agent_name or not routing_data:
            print("Orchestrator: Classification did not result in a target agent or data. Halting.")
            return None

        print(f"Orchestrator: Classified as Format='{routing_data['classified_format']}', Intent='{routing_data['classified_intent']}'. Routing to {target_agent_name}.")

        # 2. Route to specific agent
        if target_agent_name in self.agents:
            agent_to_run = self.agents[target_agent_name]
            print(f"Orchestrator: Invoking {target_agent_name}...")
            agent_to_run.process(routing_data)
        else:
            print(f"Orchestrator: No agent named '{target_agent_name}' found or no specific processing needed beyond classification. Task logged.")

        print(f"Orchestrator: Processing complete for Thread ID: {thread_id}.")
        print("="*50)
        return thread_id



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent AI System")
    parser.add_argument("input", type=str, help="Path to the input file (PDF, JSON, TXT/EML) or raw email text if --raw is used.")
    parser.add_argument("--raw", action="store_true", help="Indicates that the input is raw text content (e.g., email body) instead of a filepath.")
    args = parser.parse_args()

    if not args.raw and not os.path.exists(args.input):
        print(f"Error: File not found at '{args.input}'")
        exit(1)

    orchestrator = Orchestrator(global_shared_memory)

    try:
        orchestrator.process_input(args.input, is_filepath=not args.raw)
    except Exception as e:
        print(f"An unexpected error occurred in the orchestrator: {e}")
        import traceback
        traceback.print_exc()
   # main.py
# ...
    finally:
        print("\n📜 Final Shared Memory Logs:")
        all_logs = global_shared_memory.get_all_logs() # Fetch logs first
        for log_entry in all_logs: # Iterate over the fetched logs
            print(log_entry)

        print("\n📦 Final Shared Context Data (sample from last thread if logs exist):")
    # for thread_id, context in global_shared_memory.context_data.items(): # Old way
    # print(f"Thread {thread_id}: {context}")

    # Example: Get logs and context for the last processed thread_id if available
        if all_logs: # Check if the fetched list of logs is not empty
            last_log_entry = all_logs[-1] # Get the last log entry from the list
            last_thread_id = last_log_entry.get("thread_id")
            if last_thread_id:
                print(f"\n🔍 Context for last thread ({last_thread_id}):")
                print(global_shared_memory.get_context(last_thread_id))
        else:
            print("No logs found to retrieve last thread context.")
    # --- Example how to test with sample files (if not using CLI args) ---
    # Create sample files first in sample_inputs/
    # orchestrator.process_input("sample_inputs/invoice_example.json")
    # orchestrator.process_input("sample_inputs/rfq_example.pdf")
    # orchestrator.process_input("sample_inputs/complaint_example.txt")
    # orchestrator.process_input("sample_inputs/order_confirmation.eml")
    # orchestrator.process_input("Subject: Urgent - System Down\n\nHi team,\nThe main server is down. We need immediate help! Regards, Bob", is_filepath=False)