# Assuming app_gui.py contains the FileActivityApp class
import logging
import tkinter as tk
from tkinter import messagebox # Explicit import for messagebox is good practice
from app_gui import FileActivityApp # Make sure filename matches
import sys # For sys.exit
import os # <-- IMPORT ADDED HERE

# --- Configure Root Logger ---
# Configure once at the entry point of the application
log_filename = "app_monitor.log"
logging.basicConfig(
    level=logging.INFO,  # Or DEBUG for more verbose output
    format='%(asctime)s [%(levelname)-8s] %(threadName)s - %(message)s (%(module)s:%(lineno)d)',
    handlers=[
        logging.FileHandler(log_filename, mode='w'), # Overwrite log each time, or use 'a' to append
        logging.StreamHandler(sys.stdout) # Log to console as well
    ]
)

def run_application():
    """Initializes and runs the Tkinter application."""
    root = None
    app = None
    try:
        logging.info("Application starting up...")
        logging.info(f"Current working directory: {os.getcwd()}") # Now 'os' is defined

        root = tk.Tk()
        # Optional: Set minimum window size
        root.minsize(800, 500)

        # Instantiate the main application GUI class
        logging.debug("Initializing FileActivityApp...")
        app = FileActivityApp(root)
        logging.debug("FileActivityApp initialized.")

        # Start the Tkinter event loop (blocks until window is closed)
        logging.info("Starting Tkinter main loop...")
        root.mainloop()
        logging.info("Tkinter main loop finished.")

    except ImportError as e:
         logging.critical(f"Failed to import required module: {e}. Please ensure all dependencies (tkinter, watchdog, wmi, pywin32) are installed and core files (app_gui.py, etc.) exist.", exc_info=True)
         # Try to show a basic messagebox if tkinter itself was imported
         try:
             tk_error_root = tk.Tk()
             tk_error_root.withdraw()
             messagebox.showerror("Fatal Error - Missing Module", f"Failed to import required module:\n{e}\n\nSee '{log_filename}' for details.\nPlease ensure dependencies are installed.")
             tk_error_root.destroy()
         except Exception:
             print(f"\nFATAL ERROR: Failed to import required module: {e}\n") # Fallback print
         sys.exit(1) # Exit with error code
    except Exception as e:
        logging.critical(f"An unexpected critical error occurred during application startup or runtime: {e}", exc_info=True)
        # Try to show error if GUI framework is available
        try:
             tk_error_root = tk.Tk()
             tk_error_root.withdraw()
             messagebox.showerror("Fatal Application Error", f"An unexpected error occurred:\n{e}\n\nSee '{log_filename}' for details.")
             tk_error_root.destroy()
        except Exception:
             print(f"\nFATAL ERROR: {e}\nCheck '{log_filename}' for details.\n")
        sys.exit(1) # Exit with error code
    finally:
        # This block will execute even if errors occurred (unless sys.exit was called)
        # Perform any final cleanup if necessary (though most is handled in on_closing)
        logging.info("Application shutdown sequence completed.")

if __name__ == "__main__":
    # Standard entry point guard
    run_application()