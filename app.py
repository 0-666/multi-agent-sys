# app.py (or web_app.py)
from flask import Flask, request, render_template, jsonify, redirect, url_for
import os
import tempfile # To temporarily save uploaded files

# Adjust import paths if your main orchestrator logic is in a different structure
# Assuming main.py contains the Orchestrator and it can be imported or its logic can be called
from main import Orchestrator # You might need to refactor main.py to make Orchestrator easily callable
from memory.shared_memory import global_shared_memory # Assuming this is your SQLite memory

# --- IMPORTANT REFACTORING NOTE ---
# Your main.py currently uses argparse and runs directly.
# For a web app, you'll want to be able to instantiate and call the Orchestrator
# without it trying to parse command-line args or exit.
# You might need a function in main.py or move Orchestrator to its own file
# that can be imported and used by both main.py (for CLI) and app.py (for web).

# Example: Let's assume you have a function like this or can adapt Orchestrator
# def process_input_for_web(input_data_path_or_text, is_filepath):
#     orchestrator = Orchestrator(global_shared_memory)
#     # The orchestrator.process_input should ideally return the results
#     # instead of just printing, so the web app can display them.
#     # For now, we'll rely on fetching from shared_memory after processing.
#     orchestrator.process_input(input_data_path_or_text, is_filepath=is_filepath)
#     # After processing, fetch relevant logs/context for display
#     if global_shared_memory.logs: # Assuming you fixed this to get_all_logs()
#         all_logs = global_shared_memory.get_all_logs()
#         if all_logs:
#             last_log = all_logs[-1]
#             thread_id = last_log.get("thread_id")
#             if thread_id:
#                 return {
#                     "thread_id": thread_id,
#                     "logs": global_shared_memory.get_logs_by_thread_id(thread_id),
#                     "context": global_shared_memory.get_context(thread_id)
#                 }
#     return {"error": "Processing completed, but could not retrieve specific results."}


app = Flask(__name__)
UPLOAD_FOLDER = 'uploads_temp' # Create this folder or use tempfile
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Initialize Orchestrator ---
# Best to initialize it once if possible, or ensure it's thread-safe if Flask runs multi-threaded
# For simplicity, we might re-initialize or use the global instance carefully.
# Let's assume your Orchestrator is designed to be called multiple times.
orchestrator_instance = Orchestrator(global_shared_memory) # Assuming Orchestrator can be used this way

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        results = None
        error_message = None
        thread_id_processed = None

        input_type = request.form.get('inputType')

        try:
            if input_type == 'file' and 'inputFile' in request.files:
                file = request.files['inputFile']
                if file.filename == '':
                    error_message = 'No selected file'
                if file:
                    # Save the file temporarily
                    filename = file.filename
                    temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(temp_filepath)

                    # Process the file
                    # You'll need to adapt your orchestrator to return structured results
                    # or fetch them from shared_memory using a thread_id
                    orchestrator_instance.process_input(temp_filepath, is_filepath=True)
                    
                    # Find the thread_id for the processed item
                    # This is a bit tricky if process_input doesn't return it.
                    # We might need to fetch the *latest* log.
                    all_logs_after_processing = global_shared_memory.get_all_logs()
                    if all_logs_after_processing:
                         # Find logs related to this specific filename if possible, or just take latest
                        for log in reversed(all_logs_after_processing):
                            if log.get("source_filename") == filename:
                                thread_id_processed = log.get("thread_id")
                                break
                        if not thread_id_processed: # fallback to very last one
                            thread_id_processed = all_logs_after_processing[-1].get("thread_id")


                    os.remove(temp_filepath) # Clean up temp file

            elif input_type == 'text' and 'inputText' in request.form:
                raw_text = request.form['inputText']
                if not raw_text.strip():
                    error_message = "Raw text input is empty"
                else:
                    # Process raw text
                    orchestrator_instance.process_input(raw_text, is_filepath=False)
                    all_logs_after_processing = global_shared_memory.get_all_logs()
                    if all_logs_after_processing:
                        # Assuming raw text processing creates a log with source "raw_input" or similar
                        for log in reversed(all_logs_after_processing):
                            if log.get("source_filename") == "raw_input": # Match how raw inputs are logged
                                thread_id_processed = log.get("thread_id")
                                break
                        if not thread_id_processed: # fallback
                             thread_id_processed = all_logs_after_processing[-1].get("thread_id")
            else:
                error_message = "Invalid input method or missing data."

            if thread_id_processed:
                 return redirect(url_for('show_results', thread_id=thread_id_processed))
            elif error_message:
                 return render_template('index.html', error_message=error_message, recent_logs=get_recent_logs())


        except Exception as e:
            print(f"Error during processing: {e}")
            import traceback
            traceback.print_exc()
            error_message = f"An internal error occurred: {e}"
            return render_template('index.html', error_message=error_message, recent_logs=get_recent_logs())

    return render_template('index.html', recent_logs=get_recent_logs())

@app.route('/results/<thread_id>')
def show_results(thread_id):
    thread_logs = global_shared_memory.get_logs_by_thread_id(thread_id)
    thread_context = global_shared_memory.get_context(thread_id)
    
    # Try to find specific agent outputs in logs
    classifier_log = next((log for log in thread_logs if log.get('agent_name') == 'ClassifierAgent'), None)
    json_agent_log = next((log for log in thread_logs if log.get('agent_name') == 'JSONAgent'), None)
    email_agent_log = next((log for log in thread_logs if log.get('agent_name') == 'EmailAgent'), None)

    return render_template('results.html',
                           thread_id=thread_id,
                           logs=thread_logs,
                           context=thread_context,
                           classifier_log=classifier_log,
                           json_agent_log=json_agent_log,
                           email_agent_log=email_agent_log)

@app.route('/all_logs')
def view_all_logs():
    all_logs = global_shared_memory.get_all_logs()
    return render_template('all_logs.html', logs=all_logs)

def get_recent_logs(count=5):
    all_logs = global_shared_memory.get_all_logs()
    return all_logs[-count:] # Get last 'count' logs


if __name__ == '__main__':
    app.run(debug=True) # debug=True is helpful for development