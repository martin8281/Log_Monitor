import wmi
import pythoncom
import threading
import os
import time

# Win32_VolumeChangeEvent.EventType values (per Microsoft docs)
EVENT_CONFIG_CHANGED = 1
EVENT_DEVICE_ARRIVAL = 2
EVENT_DEVICE_REMOVAL = 3
EVENT_DOCKING = 4

# Load previously authorized devices (if needed, kept for future enhancements)
def load_authorized_devices():
    devices = []
    if os.path.exists('authorized_usb_devices.txt'):
        with open('authorized_usb_devices.txt', 'r') as f:
            devices = [line.strip() for line in f.readlines()]
    return devices

# Debugging: Callback function to print messages
def usb_event_callback(message):
    print(f"[USB Event] {message}")

_monitoring_active = False

def stop_usb_monitoring():
    global _monitoring_active
    _monitoring_active = False

# USB Monitoring Function
def start_usb_monitoring(callback, start_usb_file_monitor_callback):
    global _monitoring_active
    _monitoring_active = True
    def monitor_usb():
        pythoncom.CoInitialize()
        c = wmi.WMI()
        print("[INFO] USB monitoring thread started")  # Debugging print

        try:
            # Single watcher on instance CREATION of the event class itself.
            # Win32_VolumeChangeEvent fires once per volume change (insert,
            # remove, config change, docking) and tells you which one
            # happened via the EventType property. Watching for "Deletion"
            # of this transient event object (as the old code did) is
            # incorrect and causes false/duplicate "Removed" notifications.
            watcher = c.Win32_VolumeChangeEvent.watch_for(notification_type="Creation")
        except Exception as e:
            print(f"[ERROR] Failed to set up WMI watcher: {e}")
            return

        # Simple debounce in case WMI fires the same event twice in quick
        # succession (a known WMI quirk on some systems).
        last_event = None  # (drive, event_type, monotonic_time)
        debounce_seconds = 1.0

        while _monitoring_active:
            try:
                event = watcher(timeout_ms=100)
                if not event:
                    continue

                drive = event.DriveName
                event_type = event.EventType

                now = time.monotonic()
                if (
                    last_event
                    and last_event[0] == drive
                    and last_event[1] == event_type
                    and (now - last_event[2]) < debounce_seconds
                ):
                    continue  # duplicate event, ignore
                last_event = (drive, event_type, now)

                if event_type == EVENT_DEVICE_ARRIVAL:
                    callback(f"USB Inserted: {drive}")
                    start_usb_file_monitor_callback(drive)
                elif event_type == EVENT_DEVICE_REMOVAL:
                    callback(f"USB Removed: {drive}")
                elif event_type == EVENT_CONFIG_CHANGED:
                    callback(f"USB Configuration Changed: {drive}")
                elif event_type == EVENT_DOCKING:
                    callback(f"Docking Event: {drive}")
                else:
                    callback(f"Unknown Volume Event ({event_type}): {drive}")

            except wmi.x_wmi_timed_out:
                pass  # Expected timeout, continue monitoring
            except Exception as e:
                callback(f"[ERROR] USB Monitoring Error: {str(e)}")

    t = threading.Thread(target=monitor_usb, daemon=True)
    t.start()

# Debugging: Placeholder for file monitoring function
def dummy_file_monitor(drive):
    print(f"[INFO] Monitoring file activity on {drive}")

# Run USB Monitoring (For Testing)
if __name__ == "__main__":
    print("[INFO] Starting USB Monitoring...")
    start_usb_monitoring(usb_event_callback, dummy_file_monitor)

    # Keep script running
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[INFO] Stopping USB Monitoring...")