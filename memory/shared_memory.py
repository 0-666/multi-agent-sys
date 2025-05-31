# memory/shared_memory.py
import sqlite3
import datetime
import uuid
import json
import threading # For thread-local data if you want to optimize connection reuse per thread

DB_NAME = "shared_memory.db"

class SharedMemory:
    def __init__(self, db_name=DB_NAME):
        self.db_name = db_name
        self._create_tables_if_not_exist() # Create tables once at init

    def _get_db_connection(self):
        """Creates a new database connection."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute_query(self, query, params=(), commit=False, fetch_one=False, fetch_all=False):
        conn = self._get_db_connection() # Get a new connection for each query
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                conn.commit()
            
            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()
            return result
        except sqlite3.Error as e:
            print(f"SQLite error: {e} Query: {query} Params: {params}")
            return None
        finally:
            if conn:
                conn.close() # Always close the connection

    def _create_tables_if_not_exist(self):
        """Create database tables if they don't exist, using a temporary connection."""
        # This method is called once at startup, so a temporary connection is fine.
        # Or, it could be called within _execute_query with a check, but that's less efficient.
        create_logs_table_query = """
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            source_filename TEXT,
            log_details TEXT
        );
        """
        create_context_table_query = """
        CREATE TABLE IF NOT EXISTS shared_context (
            thread_id TEXT PRIMARY KEY,
            last_updated TEXT NOT NULL,
            context_data TEXT
        );
        """
        # Use _execute_query to ensure table creation also uses its own connection
        self._execute_query(create_logs_table_query, commit=True)
        self._execute_query(create_context_table_query, commit=True)


    # ... your add_log, get_logs_by_thread_id, get_all_logs, _format_log_row,
    # update_context, get_context, generate_thread_id methods remain mostly the same,
    # as they all rely on _execute_query which now handles its own connection.

    # Remove __del__ if connections are managed per query.
    # def __del__(self):
    #     pass # No global connection to close
    def add_log(self, agent_name: str, log_details: dict):
        thread_id = log_details.get("thread_id", self.generate_thread_id()) # Ensure thread_id
        source_filename = log_details.get("source", log_details.get("source_filename"))
        
        # Prepare log_details to be stored as JSON, exclude fields already columns
        storable_details = {k: v for k, v in log_details.items() if k not in ['thread_id', 'source', 'source_filename']}

        query = """
        INSERT INTO agent_logs (timestamp, agent_name, thread_id, source_filename, log_details)
        VALUES (?, ?, ?, ?, ?);
        """
        params = (
            datetime.datetime.now().isoformat(),
            agent_name,
            thread_id,
            source_filename,
            json.dumps(storable_details) # Serialize the rest of log_details
        )
        self._execute_query(query, params, commit=True)
        print(f"MEMORY_LOG (SQLite): Agent: {agent_name}, Thread: {thread_id}, Details: {storable_details.get('status', '')}")


    def get_logs_by_thread_id(self, thread_id: str) -> list:
        query = "SELECT * FROM agent_logs WHERE thread_id = ? ORDER BY timestamp ASC;"
        rows = self._execute_query(query, (thread_id,), fetch_all=True)
        if rows:
            return [self._format_log_row(row) for row in rows]
        return []

    def get_all_logs(self) -> list:
        query = "SELECT * FROM agent_logs ORDER BY timestamp ASC;"
        rows = self._execute_query(query, fetch_all=True)
        if rows:
            return [self._format_log_row(row) for row in rows]
        return []

    def _format_log_row(self, row: sqlite3.Row) -> dict:
        """Converts a SQLite row from agent_logs to a dictionary, parsing JSON."""
        log_entry = dict(row)
        if log_entry.get('log_details'):
            try:
                parsed_details = json.loads(log_entry['log_details'])
                log_entry.update(parsed_details) # Merge parsed details
                # del log_entry['log_details'] # Optional: remove the raw JSON string
            except json.JSONDecodeError:
                print(f"Warning: Could not parse log_details JSON for log ID {log_entry.get('id')}")
        return log_entry


    def update_context(self, thread_id: str, data_to_update: dict):
        current_context = self.get_context(thread_id) # Fetch existing context
        current_context.update(data_to_update)       # Merge new data

        query = """
        INSERT OR REPLACE INTO shared_context (thread_id, last_updated, context_data)
        VALUES (?, ?, ?);
        """
        params = (
            thread_id,
            datetime.datetime.now().isoformat(),
            json.dumps(current_context) # Serialize the entire context
        )
        self._execute_query(query, params, commit=True)
        # self.add_log("SharedMemory", {"action": "context_updated", "thread_id": thread_id, "updated_keys": list(data_to_update.keys())}) # This will now also go to DB

    def get_context(self, thread_id: str) -> dict:
        query = "SELECT context_data FROM shared_context WHERE thread_id = ?;"
        row = self._execute_query(query, (thread_id,), fetch_one=True)
        if row and row['context_data']:
            try:
                return json.loads(row['context_data'])
            except json.JSONDecodeError:
                print(f"Warning: Could not parse context_data JSON for thread_id {thread_id}")
                return {}
        return {}

    def generate_thread_id(self) -> str:
        return str(uuid.uuid4())

    # Optional: Destructor to ensure connection is closed when object is garbage collected
    def __del__(self):
        self._close()

# Global instance
# This will now create/connect to shared_memory.db when first imported/used
global_shared_memory = SharedMemory()