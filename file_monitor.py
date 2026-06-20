import os
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time # Import time for potential sleep/timeout

# --- Configuration ---
# Logging setup is often done in main.py or app_gui.py
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- State Management (Module Scope) ---
_monitored_folders = set() # Folders configured via GUI/file
_observers = []          # List to hold active observer {'observer': obj, 'path': str, 'is_usb': bool}
_callback_func = None    # Thread-safe callback function provided by the GUI
_usb_drive_paths = set() # Keep track of paths monitored specifically because they are USB

# --- Event Handler ---
class FileActivityEventHandler(FileSystemEventHandler):
    """Handles filesystem events and calls the provided callback."""
    def __init__(self, callback, base_path, is_usb=False):
        super().__init__()
        self._callback = callback
        self._base_path = base_path
        self._is_usb = is_usb
        logging.debug(f"EventHandler initialized for {'USB' if is_usb else 'Folder'}: {base_path}")

    def _log_event(self, event_type: str, src_path: str, dest_path: str = None):
        """Formats and sends event messages via the callback."""
        location_tag = "[USB]" if self._is_usb else "[Folder]"
        # Create a user-friendly message
        if dest_path: # Move/Rename event
            message = f"{location_tag} {event_type}: {src_path} -> {dest_path}"
        else: # Create/Delete/Modify event
            message = f"{location_tag} {event_type}: {src_path}"

        if self._callback:
            try:
                # The callback (GUI's schedule_update) handles thread safety
                self._callback(message)
            except Exception as e:
                logging.error(f"Error executing callback for event {event_type} on {src_path}: {e}", exc_info=True)
        else:
             logging.warning(f"No callback configured! Discarding event: {message}")

    def on_created(self, event):
        # Ignore directory creation events? Often noisy.
        # if not event.is_directory:
        logging.debug(f"Event detected (created): {event.src_path} (is_dir={event.is_directory})")
        self._log_event("Created", event.src_path)

    def on_deleted(self, event):
        # if not event.is_directory:
        logging.debug(f"Event detected (deleted): {event.src_path} (is_dir={event.is_directory})")
        self._log_event("Deleted", event.src_path)

    def on_modified(self, event):
        # Modify events can be frequent; ignore for directories if desired.
        if not event.is_directory:
            logging.debug(f"Event detected (modified): {event.src_path} (is_dir={event.is_directory})")
            self._log_event("Modified", event.src_path)

    def on_moved(self, event):
        # Moved includes renaming.
        # if not event.is_directory:
        logging.debug(f"Event detected (moved): {event.src_path} -> {event.dest_path} (is_dir={event.is_directory})")
        self._log_event("Moved/Renamed", event.src_path, event.dest_path)


# --- Folder Management Functions (Called by GUI) ---
def add_monitored_folder(folder_path: str) -> bool:
    """Adds a folder path to the set of folders to be monitored."""
    folder_path = os.path.normpath(folder_path) # Normalize path
    if not os.path.isdir(folder_path):
        logging.error(f"Cannot add '{folder_path}': Not a valid directory.")
        return False
    if folder_path not in _monitored_folders:
        _monitored_folders.add(folder_path)
        logging.info(f"Folder added to monitoring list: {folder_path}")
        return True
    else:
        logging.warning(f"Folder already in monitoring list: {folder_path}")
        return False # Indicate it wasn't newly added

def remove_monitored_folder(folder_path: str) -> bool:
    """Removes a folder path from the set of folders to be monitored."""
    folder_path = os.path.normpath(folder_path) # Normalize path
    if folder_path in _monitored_folders:
        _monitored_folders.discard(folder_path)
        logging.info(f"Folder marked for removal from monitoring list: {folder_path}")
        # Actual stopping happens in stop_file_monitoring or restart logic
        return True
    else:
        logging.warning(f"Folder not found in monitoring list for removal: {folder_path}")
        return False # Indicate it wasn't found

def get_monitored_folders() -> list:
    """Returns a sorted list of currently configured monitored folders."""
    return sorted(list(_monitored_folders))

# --- Monitoring Control Functions ---

def _start_observer_for_path(path: str, callback, is_usb: bool):
    """Internal function to create, start, and store an observer for a path."""
    global _observers # Modifying global list
    path = os.path.normpath(path)

    # Prevent duplicates - check if path is already being observed
    if any(obs_info['path'] == path for obs_info in _observers):
         logging.warning(f"Attempted to start duplicate observer for path: {path}")
         return None

    if not os.path.isdir(path):
        logging.error(f"Cannot start observer: Path is not a valid directory: {path}")
        if callback: callback(f"[Error] Cannot monitor invalid path: {path}")
        return None

    try:
        event_handler = FileActivityEventHandler(callback, path, is_usb=is_usb)
        observer = Observer()
        # Watchdog might have issues with root drives (e.g., 'C:\') without subdirs
        # Use recursive=True cautiously on very large/deep drives.
        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        # Store observer along with its path info
        obs_info = {'observer': observer, 'path': path, 'is_usb': is_usb}
        _observers.append(obs_info)
        logging.info(f"Observer started successfully for {'USB' if is_usb else 'Folder'}: {path}")
        if callback: callback(f"[{'USB' if is_usb else 'Folder'}] Started monitoring: {path}")
        return observer
    except OSError as e:
        # Common issue: permissions, network path issues
        logging.error(f"OS Error starting observer for {path}: {e}", exc_info=True)
        if callback: callback(f"[Error] OS Error monitoring {path}: {e}")
    except Exception as e:
        logging.error(f"Failed to start observer for {path}: {e}", exc_info=True)
        if callback: callback(f"[Error] Failed to monitor {path}: {e}")
    return None


def start_file_monitoring(callback):
    """Starts monitoring all folders in _monitored_folders."""
    global _callback_func
    if not callable(callback):
        logging.error("start_file_monitoring: Invalid callback function provided.")
        raise ValueError("Callback function must be callable.")

    _callback_func = callback # Store for reuse (e.g., by start_usb_file_monitor)

    if _observers:
        logging.warning("Monitoring start requested, but observers already exist. Stopping first.")
        stop_file_monitoring() # Ensure clean state

    logging.info(f"Starting monitoring for configured folders: {_monitored_folders}")
    if not _monitored_folders:
         logging.warning("No folders configured for monitoring.")
         callback("[Info] No folders configured to monitor.")
         return # Don't start if nothing to monitor

    started_count = 0
    for folder in list(_monitored_folders): # Iterate a copy
        if _start_observer_for_path(folder, callback, is_usb=False):
            started_count += 1

    logging.info(f"File monitoring initialization complete. Started {started_count} observers.")


def start_usb_file_monitor(drive_path, callback):
    """Starts monitoring a specific path identified as a USB drive."""
    global _callback_func
    drive_path = os.path.normpath(drive_path)

    # Ensure we have a valid callback
    if not callable(callback):
         if not callable(_callback_func):
              logging.error("Cannot start USB monitor: No valid callback function available.")
              return
         else:
              callback = _callback_func # Use the stored callback if none provided
    elif not _callback_func:
         _callback_func = callback # Store the provided callback

    logging.info(f"Request to start monitoring USB path: {drive_path}")
    if drive_path not in _usb_drive_paths:
        if _start_observer_for_path(drive_path, callback, is_usb=True):
            _usb_drive_paths.add(drive_path) # Track USB paths being monitored
    else:
        logging.warning(f"USB path already being monitored: {drive_path}")


def stop_file_monitoring():
    """Stops ALL active file system observers (folders and USBs)."""
    global _observers, _usb_drive_paths, _callback_func
    if not _observers:
        logging.info("Stop monitoring requested, but no observers were active.")
        return

    logging.info(f"Stopping {len(_observers)} observers...")
    stopped_count = 0
    # Iterate over a copy because we might modify list implicitly if stopping fails? Safer.
    # Observers list structure: {'observer': obj, 'path': str, 'is_usb': bool}
    observers_to_stop = list(_observers)
    _observers.clear() # Clear global list immediately

    for obs_info in observers_to_stop:
        obs = obs_info['observer']
        path = obs_info['path']
        try:
            if obs.is_alive():
                obs.stop()
                # Wait for the thread to terminate, with a timeout
                obs.join(timeout=2.0)
                if obs.is_alive():
                    logging.warning(f"Observer thread for path '{path}' did not stop gracefully after 2 seconds.")
                    # Force stop might not be possible/safe depending on watchdog version/OS
                else:
                    logging.info(f"Observer stopped for: {path}")
                    stopped_count += 1
            else:
                logging.warning(f"Observer for path '{path}' was already stopped or not alive.")
                # Consider it stopped if not alive
                stopped_count += 1
        except Exception as e:
            logging.error(f"Error stopping observer for path '{path}': {e}", exc_info=True)

    if stopped_count != len(observers_to_stop):
         logging.warning(f"Attempted to stop {len(observers_to_stop)} observers, but only {stopped_count} confirmed stopped.")

    # Clear USB tracking and callback reference
    _usb_drive_paths.clear()
    # _callback_func = None # Keep callback? Or clear? Depends if start can happen without GUI interaction. Let's clear.
    _callback_func = None

    logging.info("All monitoring stop routines finished.")
    # Send a final message via callback? Only if callback still exists? Risky.


# --- Export Functions ---

def export_monitored_paths(file_path: str):
    """Exports the list of folders configured for monitoring."""
    logging.info(f"Exporting monitored folders configuration to: {file_path}")
    folders = get_monitored_folders() # Get current list
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Monitored Folders Configuration\n")
            if not folders:
                f.write("# (No folders currently configured)\n")
            else:
                for folder in folders:
                    f.write(f"{folder}\n")
        logging.info(f"Successfully exported {len(folders)} monitored folder paths to: {file_path}")
    except IOError as e:
        logging.error(f"Failed to export monitored paths to {file_path}: {e}")
        raise # Re-raise for the caller (GUI) to handle

def export_activity_log(activity_data: list, file_path: str):
    """Exports the provided activity log data (list of strings) to a file."""
    if not isinstance(activity_data, list):
        logging.error(f"Export failed: activity_data is not a list (Type: {type(activity_data)}).")
        raise TypeError("activity_data must be a list of strings")

    log_count = len(activity_data)
    logging.info(f"Attempting to export {log_count} activity log entries to: {file_path}")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            # Basic Header
            from datetime import datetime
            f.write(f"--- File & USB Activity Log ---\n")
            f.write(f"Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Entries: {log_count}\n")
            f.write(f"{'-'*30}\n\n")

            # Write each entry
            for entry in activity_data:
                f.write(f"{str(entry)}\n") # Ensure it's a string

        logging.info(f"Successfully exported {log_count} activity log entries to: {file_path}")
    except IOError as e:
        logging.error(f"IOError exporting activity log to {file_path}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error exporting activity log to {file_path}: {e}", exc_info=True)
        raise