import pyttsx3
import threading
import queue
import logging

class SpeechService:
    def __init__(self):
        self.queue = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 250) # ~1.5x speed
            
            while self.running:
                try:
                    # Wait for a name with a timeout so we can check if self.running changed
                    name = self.queue.get(timeout=1)
                    if name:
                        engine.say(name)
                        engine.runAndWait()
                    self.queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logging.error(f"Speech worker error: {e}")
        except Exception as e:
            logging.error(f"Speech engine initialization failed: {e}")

    def speak(self, name):
        if self.running:
            self.queue.put(name)

    def stop(self):
        self.running = False
        # No need to join a daemon thread, but we signal it to stop
