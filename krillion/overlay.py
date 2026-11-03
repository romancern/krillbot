"""Small always-on-top hints window; Tk runs on the main thread."""
import asyncio
import queue
import signal
import threading
import tkinter as tk

from .live import OVERLAY_COUNTS


class Overlay:
    def __init__(self):
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.regenerate = threading.Event()
        self.autoplay = threading.Event()
        self.root = tk.Tk()
        self.root.title('Krillion hints')
        self.root.geometry('380x610')
        self.root.minsize(310, 260)
        self.root.configure(bg='#0b1729')
        self.root.attributes('-topmost', True)
        frame = tk.Frame(self.root, bg='#0b1729', padx=18, pady=14)
        frame.pack(fill='both', expand=True)
        tk.Label(frame, text='KRILLION  /  HINTS', bg='#0b1729', fg='#63daf4',
                 font=('Helvetica', 12, 'bold'), anchor='w').pack(fill='x')
        self.status = tk.Label(frame, text='Waiting for a game…', bg='#0b1729', fg='#b1c5d9',
                               font=('Helvetica', 11), anchor='w')
        self.status.pack(fill='x', pady=(10, 5))
        self.question = tk.Label(frame, text='Join a game in the browser window.', bg='#0b1729',
                                 fg='#f4f8ff', font=('Helvetica', 15, 'bold'), anchor='nw',
                                 justify='left', wraplength=340)
        self.question.pack(fill='x', pady=(2, 12))
        self.hints = tk.Label(frame, text='Suggestions will appear here.', bg='#0b1729',
                              fg='#8fe8d0', font=('Helvetica', 14), anchor='nw', justify='left', wraplength=340)
        self.hints.pack(fill='both', expand=True)
        self.mode_label = tk.Label(frame, text='HINTS MODE · You submit answers', bg='#0b1729', fg='#7890aa',
                                   font=('Helvetica', 10), anchor='w')
        self.mode_label.pack(fill='x', side='bottom')
        self.mode_button = tk.Button(frame, text='Switch to bot mode', command=self.toggle_mode)
        self.mode_button.pack(fill='x', side='bottom', pady=(2, 6))
        tk.Button(frame, text='Regenerate', command=self.regenerate.set).pack(fill='x', side='bottom', pady=(6, 8))
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(80, self.drain)

    def publish(self, question, turn, candidates, generating=False, error=None):
        groups = candidates if isinstance(candidates, dict) else {}
        self.events.put((question, turn, tuple(groups.get('ordinary', ())[:OVERLAY_COUNTS['ordinary']]), tuple(groups.get('specific', ())[:OVERLAY_COUNTS['specific']]), generating, error))

    def close(self):
        self.stop.set()
        self.root.destroy()

    def toggle_mode(self):
        if self.autoplay.is_set():
            self.autoplay.clear()
            self.mode_label.config(text='HINTS MODE · You submit answers', fg='#7890aa')
            self.mode_button.config(text='Switch to bot mode')
        else:
            self.autoplay.set()
            self.mode_label.config(text='BOT MODE · Answers submit automatically', fg='#ffcb77')
            self.mode_button.config(text='Switch to hints mode')

    def drain(self):
        latest = None
        try:
            while True:
                latest = self.events.get_nowait()
        except queue.Empty:
            pass
        if latest:
            question, turn, ordinary, specific, generating, error = latest
            status = 'YOUR TURN' if turn == 'you' else (f'{turn} is up' if turn else 'Waiting for a turn')
            self.status.config(text='NEEDS ATTENTION' if error else status, fg='#ff9e9e' if error else ('#ffcb77' if turn == 'you' else '#b1c5d9'))
            self.question.config(text=question or 'Join a game in the browser window.')
            if ordinary or specific:
                familiar = '\n'.join(f'  •  {answer}' for answer in ordinary) or '  …'
                unusual = '\n'.join(f'  •  {answer}' for answer in specific) or '  …'
                message = f'ORDINARY\n{familiar}\n\nSPECIFIC\n{unusual}'
            else:
                message = 'Generating suggestions…' if generating else 'Waiting for suggestions…'
            self.hints.config(text=error or message)
        if not self.stop.is_set():
            self.root.after(80, self.drain)


def run_overlay(args):
    from .live import run
    overlay = Overlay()

    def worker():
        try:
            asyncio.run(run(args, overlay=overlay, stop_event=overlay.stop))
            if not overlay.stop.is_set():
                overlay.publish('', None, [], error='Game window closed. Restart the bot to play again.')
        except Exception as exc:
            overlay.publish('', None, [], error=str(exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    previous = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda *_: overlay.root.after(0, overlay.close))
    try:
        overlay.root.mainloop()
    finally:
        overlay.stop.set()
        signal.signal(signal.SIGINT, previous)
        thread.join(timeout=3)
