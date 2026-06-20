# --- !! WINDOWS ONLY !! ---
# Requires: pip install pywin32
# Requires: Administrator privileges to run
# Requires: Windows Audit Policy for 'Object Access' -> 'File System' enabled
# Requires: Auditing (SACL) configured on specific files/folders for events to be generated

import logging
import platform
import os
from datetime import datetime

# Attempt Windows-specific imports only on Windows
_PYWIN32_AVAILABLE = False
if platform.system() == "Windows":
    try:
        import win32evtlog
        import win32evtlogutil # Potentially useful for message formatting later
        import pywintypes
        import winerror
        _PYWIN32_AVAILABLE = True
    except ImportError:
        # Log error if on Windows but missing module
        logging.error("Windows platform detected, but 'pywin32' package not found. This script requires it.")
        logging.error("Install it using: pip install pywin32")
        # Consider raising an exception or exiting if the module is critical for the script's purpose
        # raise ImportError("pywin32 not found, cannot proceed.")


# --- Configuration ---
# Basic logging setup (can be overridden if called by another script with existing setup)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Default log file name for export
DEFAULT_EXPORT_FILE = "file_access_log_export.txt"

# Constants based on the original code's usage (Verify indices against actual Event 4663 logs)
EVENT_ID_FILE_ACCESS = 4663
IDX_USER = 1          # Security ID (SID) or Account Name
IDX_OBJECT_NAME = 5   # File or Folder Path
# Index 8 usually holds the raw ACCESS MASK (e.g., 0x120089). It's less readable than Index 11 (AccessList).
IDX_ACCESS_MASK_RAW = 8

# --- Read file access events function ---
def read_file_access_events(max_events=50):
    """
    Reads recent file/folder access events (Event ID 4663) from the
    Windows Security Event Log.

    Args:
        max_events (int): The maximum number of matching events to retrieve.

    Returns:
        list: A list of dictionaries, each representing an event.
        Returns None if a critical error (like permissions or module import) occurs.
        Returns empty list ([]) if no matching events are found but log was read.

    Prerequisites:
        - Must be run as Administrator.
        - pywin32 module must be installed.
        - Windows Audit Policy for 'File System' object access must be enabled.
        - Auditing (SACL) must be configured on specific target files/folders.
    """
    if not _PYWIN32_AVAILABLE:
        logging.error("Cannot read Windows events: pywin32 module not available.")
        return None # Indicate critical failure

    server = 'localhost'
    log_type = 'Security'
    events_list = []
    hand = None
    log_read_success = False

    try:
        logging.debug(f"Attempting to open Security Event Log on {server}...")
        hand = win32evtlog.OpenEventLog(server, log_type)
        log_read_success = True
        logging.debug("Security Event Log opened successfully.")

        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        total_records = win32evtlog.GetNumberOfEventLogRecords(hand)
        logging.info(f"Reading Security log ({total_records} records). Looking for max {max_events} of Event ID {EVENT_ID_FILE_ACCESS}.")

        event_count = 0
        processed_count = 0
        while event_count < max_events:
            # Read events in batches (API handles underlying buffering)
            events_batch = win32evtlog.ReadEventLog(hand, flags, 0)
            if not events_batch:
                break # No more events

            for event in events_batch:
                processed_count += 1
                if event.EventID == EVENT_ID_FILE_ACCESS:
                    try:
                        # Safely access StringInserts and check length
                        strings = event.StringInserts
                        if strings and len(strings) > max(IDX_USER, IDX_OBJECT_NAME, IDX_ACCESS_MASK_RAW):
                            user = strings[IDX_USER]
                            object_name = strings[IDX_OBJECT_NAME]
                            # Get raw access mask (less readable than AccessList at index 11)
                            access_mask = strings[IDX_ACCESS_MASK_RAW]
                            time_generated = event.TimeGenerated.Format('%Y-%m-%d %H:%M:%S') # More standard format

                            event_data = {
                                "TimeGenerated": time_generated,
                                "User": user,
                                "ObjectName": object_name,
                                # Renamed for clarity vs. the AccessList in the other module
                                "AccessMaskRaw": access_mask
                            }
                            events_list.append(event_data)
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
            # End of inner loop (processing batch)
        # End of outer loop (reading batches)

        logging.info(f"Finished reading events. Processed approx {processed_count} records, found {event_count} matching events (ID {EVENT_ID_FILE_ACCESS}).")
        return events_list # Return list (possibly empty)

    except pywintypes.error as e:
        error_code = getattr(e, 'winerror', None)
        error_msg = getattr(e, 'strerror', str(e))
        if error_code == winerror.ERROR_ACCESS_DENIED:
            logging.error("Access Denied opening Security Event Log. Run as Administrator.")
        elif error_code == winerror.ERROR_FILE_NOT_FOUND and not log_read_success:
             logging.error(f"Security log not found or cannot be opened (Code {error_code}): {error_msg}.")
        else:
            logging.error(f"Windows API Error accessing event logs: Code {error_code} - {error_msg}", exc_info=True)
        return None # Indicate critical error
    except Exception as e:
        logging.error(f"Unexpected error reading event logs: {e}", exc_info=True)
        return None # Indicate critical error
    finally:
        if hand:
            try:
                win32evtlog.CloseEventLog(hand)
                logging.debug("Event log handle closed.")
            except Exception as close_err:
                 logging.error(f"Error closing event log handle: {close_err}")


# --- Export function ---
def export_events_to_file(events_list, filename=DEFAULT_EXPORT_FILE):
    """
    Exports a list of event dictionaries (from read_file_access_events)
    to a specified file, overwriting it.

    Args:
        events_list (list): The list of event dictionaries to export.
        filename (str): The path to the output file.

    Returns:
        bool: True if export was successful or no events to export, False otherwise.
    """
    if not isinstance(events_list, list):
        logging.error(f"Export failed: Input 'events_list' is not a list (Type: {type(events_list)}).")
        return False

    if not events_list:
        logging.info(f"No events provided to export to {filename}.")
        # Optionally create an empty file or just do nothing
        # Let's just return True as there was no error, just no data.
        return True

    logging.info(f"Exporting {len(events_list)} events to {filename}...")
    try:
        with open(filename, "w", encoding='utf-8') as f:
            # Write a simple header
            f.write(f"--- Windows File Access Log Export (Event ID {EVENT_ID_FILE_ACCESS}) ---\n")
            f.write(f"Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Found {len(events_list)} relevant events.\n")
            f.write("-" * 30 + "\n\n")

            # Write event data
            for log_entry in events_list:
                f.write(f"Time:   {log_entry.get('TimeGenerated', 'N/A')}\n")
                f.write(f"User:   {log_entry.get('User', 'N/A')}\n")
                f.write(f"File:   {log_entry.get('ObjectName', 'N/A')}\n")
                # Note: This 'Access' is the raw mask from Index 8
                f.write(f"Access: {log_entry.get('AccessMaskRaw', 'N/A')}\n")
                f.write("---\n")
        logging.info(f"Successfully wrote {len(events_list)} events to {filename}")
        return True
    except IOError as e:
        logging.error(f"Failed to write events to log file {filename}: {e}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during log export: {e}", exc_info=True)
        return False


# --- Example Usage (if run directly) ---
if __name__ == "__main__":
    print("--- Standalone File Access Log Exporter ---")
    print("This script reads recent file access events (ID 4663) from the")
    print("Windows Security Log and exports them to a file.")
    print("\n--- REQUIRES: ---")
    print("1. Running this script as Administrator.")
    print("2. pywin32 installed (`pip install pywin32`).")
    print("3. Windows Audit Policy enabled: 'Audit Object Access' -> 'Audit File System'.")
    print("4. Auditing (SACL) configured on specific test files/folders.")
    print("-" * 20)

    # Read events
    event_data_list = read_file_access_events(max_events=50) # Read last 50 matching

    # Export if reading was successful (even if list is empty)
    if event_data_list is not None:
        print(f"\nRead {len(event_data_list)} events. Attempting export...")
        success = export_events_to_file(event_data_list, filename="direct_export_file_access.log")
        if success:
            if event_data_list:
                print(f"Export successful to 'direct_export_file_access.log'.")
            else:
                 print("Export successful (no matching events found to write).")
                 print("Check Audit Policy and SACL configuration if you expected events.")
        else:
            print("Export failed. Check error messages above.")
    else:
        print("\nFailed to read events (Critical Error). Export cancelled.")
        print("Check error messages above (e.g., for permissions issues).")