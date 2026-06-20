# --- !! WINDOWS ONLY !! ---
# Requires: pip install pywin32
# Requires: Administrator privileges to run
# Requires: Windows Audit Policy for 'Object Access' -> 'File System' enabled
# Requires: Auditing (SACL) configured on specific files/folders for events to be generated

import logging
import platform
import os

# Attempt Windows-specific imports only on Windows
_PYWIN32_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import win32evtlog
        import win32evtlogutil
        import pywintypes
        import winerror
        _PYWIN32_AVAILABLE = True
    except ImportError:
        logging.error("Windows platform detected, but 'pywin32' package not found. Event log monitoring disabled.")
        logging.error("Install it using: pip install pywin32")

# --- Configuration ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants for Event ID and String Insert Indices (Verify against actual Event 4663 logs)
EVENT_ID_FILE_ACCESS = 4663
IDX_USER = 1          # Security ID (SID) or Account Name
IDX_OBJECT_NAME = 5   # File or Folder Path
IDX_PROCESS_ID = 9    # Process ID (PID) of the accessing process
IDX_PROCESS_NAME = 10 # Full Path of the accessing process executable
IDX_ACCESS_LIST = 11  # List of requested accesses (e.g., "ReadData (or ListDirectory)")

# Basic mapping for common access mask values found in the Access List string
ACCESS_TYPE_MAP = {
    "ReadData (or ListDirectory)": "Read",
    "WriteData (or AddFile)": "Write",
    "AppendData (or AddSubdirectory or CreatePipeInstance)": "Append",
    "Execute/Traverse": "Execute",
    "Delete": "Delete",
    "ReadAttributes": "Read Attributes",
    "WriteAttributes": "Write Attributes",
    "WriteEA": "Write Extended Attributes",
    "ReadEA": "Read Extended Attributes",
    "WriteAttributes": "Write Attributes",
    "ReadAttributes": "Read Attributes",
    # Add more specific mappings if needed based on observed logs
}

# --- Fetch file access events from Windows Security logs ---
def fetch_file_access_events(max_events=100):
    """
    Fetches recent file/folder access events (Event ID 4663) from the
    Windows Security Event Log.

    Args:
        max_events (int): The maximum number of matching events to return.

    Returns:
        list: A list of formatted strings describing the access events.
        Returns None if a critical error (like permissions or module import) occurs.
        Returns empty list ([]) if no matching events are found but log was read.
    """
    if not _PYWIN32_AVAILABLE:
        logging.error("Cannot fetch Windows events: pywin32 module not available.")
        return None # Indicate critical failure

    server = 'localhost'
    log_type = 'Security'
    events_data = []
    hand = None
    log_read_success = False

    try:
        logging.debug(f"Attempting to open Security Event Log on {server}...")
        hand = win32evtlog.OpenEventLog(server, log_type)
        log_read_success = True # Assume success unless exception below
        logging.debug("Security Event Log opened successfully.")

        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total_records = win32evtlog.GetNumberOfEventLogRecords(hand)
        logging.info(f"Reading Security log ({total_records} records). Looking for max {max_events} of Event ID {EVENT_ID_FILE_ACCESS}.")

        event_count = 0
        processed_count = 0
        while event_count < max_events:
            # Read a chunk of events (adjust buffer size if needed, 8192 is often reasonable)
            read_buffer = win32evtlog.ReadEventLog(hand, flags, 0, 8192)
            if not read_buffer:
                break # No more events

            for event in read_buffer:
                processed_count += 1
                # Check the Event ID
                if event.EventID == EVENT_ID_FILE_ACCESS:
                    try:
                        strings = event.StringInserts
                        # Check minimum length needed for required fields
                        if strings and len(strings) > max(IDX_USER, IDX_OBJECT_NAME, IDX_ACCESS_LIST, IDX_PROCESS_NAME):
                            user = strings[IDX_USER]
                            object_name = strings[IDX_OBJECT_NAME]
                            # Process name might be empty for kernel operations
                            process_name = strings[IDX_PROCESS_NAME] or "N/A"
                            access_list_raw = strings[IDX_ACCESS_LIST]

                            # Simplify access list
                            simplified_accesses = set() # Use set to avoid duplicates
                            for acc in access_list_raw.split('\n'):
                                clean_acc = acc.strip()
                                if clean_acc:
                                    mapped = ACCESS_TYPE_MAP.get(clean_acc, clean_acc) # Map known, else keep original
                                    simplified_accesses.add(mapped)

                            access_str = ", ".join(sorted(list(simplified_accesses))) if simplified_accesses else "Unknown Access"

                            # Format the output string
                            # Using basename for brevity on process path
                            message = (f"User: {user}, Process: {os.path.basename(process_name)}, "
                                       f"Action: {access_str}, Object: {object_name}")
                            events_data.append(message)
                            event_count += 1
                            if event_count >= max_events:
                                break # Exit inner loop
                        else:
                            logging.warning(f"Event ID {EVENT_ID_FILE_ACCESS} found (Record {event.RecordNumber}), but StringInserts format unexpected or too short ({len(strings) if strings else 'None'}). Skipping.")

                    except IndexError:
                        logging.warning(f"Event ID {EVENT_ID_FILE_ACCESS} found (Record {event.RecordNumber}), but failed to access expected StringInserts index. Skipping.")
                    except Exception as parse_err:
                         logging.error(f"Error parsing details for Event ID {EVENT_ID_FILE_ACCESS} (Record {event.RecordNumber}): {parse_err}", exc_info=True)

                # Check if max events reached after processing this event
                if event_count >= max_events:
                    break
            # End of inner loop (processing buffer)
        # End of outer loop (reading buffers)

        logging.info(f"Finished reading events. Processed approx {processed_count} records, found {event_count} matching events (ID {EVENT_ID_FILE_ACCESS}).")
        return events_data # Return list (possibly empty)

    except pywintypes.error as e:
        # Specific handling for pywin32 errors
        error_code = e.winerror
        error_msg = e.strerror
        if error_code == winerror.ERROR_ACCESS_DENIED: # Error code 5
            logging.error("Access Denied: Failed to open Security Event Log. Run the application as Administrator.")
            # Optionally inform user via different mechanism if needed
        elif error_code == winerror.ERROR_FILE_NOT_FOUND and log_type == 'Security' and not log_read_success: # Error code 2
             logging.error(f"Error: Security log not found or cannot be opened (Code {error_code}): {error_msg}. Ensure event logging service is running.")
        else:
            logging.error(f"Windows API Error accessing event logs: Code {error_code} - {error_msg}", exc_info=True)
        return None # Indicate critical error
    except Exception as e:
        logging.error(f"Unexpected error fetching Windows event logs: {e}", exc_info=True)
        return None # Indicate critical error
    finally:
        # Ensure the event log handle is closed
        if hand:
            try:
                win32evtlog.CloseEventLog(hand)
                logging.debug("Event log handle closed.")
            except Exception as close_err:
                 logging.error(f"Error closing event log handle: {close_err}")

# --- Example Usage (if run directly) ---
if __name__ == "__main__":
    # Setup basic logging JUST for this test run
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    print("Attempting to fetch file access events...")
    print("--- REQUIRES: ---")
    print("1. Running this script as Administrator.")
    print("2. Windows Audit Policy enabled: 'Audit Object Access' -> 'Audit File System' (Success and Failure).")
    print("3. Auditing (SACL) configured on specific test files/folders via Properties -> Security -> Advanced -> Auditing.")
    print("-" * 20)

    events = fetch_file_access_events(max_events=25)

    if events is None:
        print("\nCRITICAL ERROR occurred. Check log messages above (e.g., Permissions Denied).")
    elif not events:
        print("\nNo matching file access events (ID 4663) found in the Security Log.")
        print("Verify the 3 requirements listed above are correctly configured.")
    else:
        print(f"\n--- Found {len(events)} Recent File Access Events (ID 4663) ---")
        for event_str in events:
            print(f"[WinEvent] {event_str}") # Add prefix for clarity
        print("-" * 50)