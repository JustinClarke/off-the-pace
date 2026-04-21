#!/usr/bin/env python3
import sys
import time
import subprocess
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: watchdog is not installed. Please run: pip install watchdog")
    sys.exit(1)

class ProjectGraphHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._last_run = 0
        self._cooldown = 1.0  # seconds to prevent rapid multiple executions

    def _run_make(self):
        now = time.time()
        if now - self._last_run > self._cooldown:
            print("Changes detected. Running 'make project-graph'...")
            subprocess.run(["make", "project-graph"])
            self._last_run = time.time()

    def on_modified(self, event):
        if not event.is_directory and not event.src_path.endswith('.html'):
            self._run_make()

    def on_created(self, event):
        if not event.is_directory and not event.src_path.endswith('.html'):
            self._run_make()

if __name__ == "__main__":
    directories_to_watch = [
        "transform/models", 
        "app/src", 
        "ml/src", 
        "scripts", 
        "ingestion/src"
    ]
    
    event_handler = ProjectGraphHandler()
    observer = Observer()
    
    watched_any = False
    for directory in directories_to_watch:
        try:
            observer.schedule(event_handler, path=directory, recursive=True)
            print(f"Watching {directory}...")
            watched_any = True
        except FileNotFoundError:
            print(f"Warning: Directory {directory} not found, skipping...")

    if not watched_any:
        print("Error: No directories found to watch. Exiting.")
        sys.exit(1)

    # Initial run to ensure the graph is up-to-date
    print("Running initial 'make project-graph'...")
    subprocess.run(["make", "project-graph"])

    observer.start()
    print("Watchdog started. Waiting for file changes... (Press Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nWatchdog stopped.")
    observer.join()
