import os
import tempfile
import threading
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from krillion.live import run


class OverlayLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlay_filters_used_answers_and_never_writes(self):
        snapshots = []

        class Hints:
            regenerate = threading.Event()
            autoplay = threading.Event()
            def publish(self, question, turn, candidates, generating=False, error=None):
                snapshots.append((question, turn, {k: list(v) for k, v in candidates.items()}))

        class Page:
            count = 0
            def is_closed(self):
                self.count += 1
                return self.count > 7
            def locator(self, *args):
                raise AssertionError('Overlay must never write to the game')

        page = Page()
        @asynccontextmanager
        async def open_page(args):
            yield page

        async def state(_):
            answer = [] if page.count < 4 else [{'text': 'apple', 'own': False, 'rarity': None}]
            return {'question': 'Name a fruit', 'category': 'CATEGORY 1', 'turn': '▸ your puffer · type an answer',
                    'placeholder': 'your puffer — type!', 'input_enabled': True, 'reject': '', 'answers': answer}

        async def generate(*_, **kwargs):
            return {'ordinary': ['apple', 'pear'], 'specific': ['quince']}, 0.1

        class Client:
            def __init__(self, **kwargs): pass
            async def close(self): pass

        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), \
             patch('krillion.live.open_game_page', open_page), \
             patch('krillion.live.read_page', state), \
             patch('krillion.live.generate', generate), \
             patch('openai.AsyncOpenAI', Client):
            args = SimpleNamespace(observe=False, overlay=True, model_timeout=1, model='test',
                                   db=os.path.join(directory, 'test.sqlite3'), poll=0.001)
            await run(args, overlay=Hints())
        self.assertTrue(any(answers == {'ordinary': ['apple', 'pear'], 'specific': ['quince']} for _, _, answers in snapshots))
        self.assertEqual(snapshots[-1][2], {'ordinary': ['pear'], 'specific': ['quince']})

    async def test_regenerate_replaces_hints_and_excludes_previous(self):
        calls, snapshots = [], []
        class Hints:
            regenerate = threading.Event()
            autoplay = threading.Event()
            def publish(self, question, turn, candidates, generating=False, error=None):
                snapshots.append({k: list(v) for k, v in candidates.items()})
                if candidates.get('ordinary') == ['apple']:
                    self.regenerate.set()
        hints = Hints()
        class Page:
            count = 0
            def is_closed(self):
                self.count += 1
                return self.count > 10
            def locator(self, *args):
                raise AssertionError('Overlay must not submit')
        page = Page()
        @asynccontextmanager
        async def open_page(args):
            yield page
        async def state(_):
            return {'question': 'Name a fruit', 'category': 'CATEGORY 1', 'turn': '▸ player is up',
                    'placeholder': 'player is up…', 'input_enabled': True, 'reject': '', 'answers': []}
        async def generate(client, model, question, used, overlay=False):
            calls.append(set(used))
            return ({'ordinary': ['apple'], 'specific': ['quince']} if len(calls) == 1 else
                    {'ordinary': ['pear'], 'specific': ['persimmon']}), 0.1
        class Client:
            def __init__(self, **kwargs): pass
            async def close(self): pass
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), \
             patch('krillion.live.open_game_page', open_page), \
             patch('krillion.live.read_page', state), \
             patch('krillion.live.generate', generate), \
             patch('openai.AsyncOpenAI', Client):
            args = SimpleNamespace(observe=False, overlay=True, model_timeout=1, model='test',
                                   db=os.path.join(directory, 'test.sqlite3'), poll=0.001)
            await run(args, overlay=hints)
        self.assertEqual(len(calls), 2)
        self.assertTrue({'apple', 'quince'}.issubset(calls[1]))
        self.assertEqual(snapshots[-1], {'ordinary': ['pear'], 'specific': ['persimmon']})

    async def test_switch_to_bot_mode_submits_on_own_turn(self):
        submissions = []
        class Hints:
            regenerate = threading.Event()
            autoplay = threading.Event()
            def publish(self, question, turn, candidates, generating=False, error=None):
                if candidates['specific']:
                    self.autoplay.set()
        class Field:
            value = ''
            async def fill(self, text): self.value = text
            async def press(self, key): submissions.append((self.value, key))
        class Page:
            count = 0
            field = Field()
            def is_closed(self):
                self.count += 1
                return self.count > 8
            def locator(self, *args): return self.field
        page = Page()
        @asynccontextmanager
        async def open_page(args): yield page
        async def state(_):
            return {'question': 'Name a fruit', 'category': 'CATEGORY 1', 'turn': '▸ your puffer · type an answer',
                    'placeholder': 'your puffer — type!', 'input_enabled': True, 'reject': '', 'answers': []}
        async def generate(*_, **kwargs):
            return {'ordinary': ['apple'], 'specific': ['quince']}, 0.1
        class Client:
            def __init__(self, **kwargs): pass
            async def close(self): pass
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {'OPENAI_API_KEY': 'test'}), \
             patch('krillion.live.open_game_page', open_page), \
             patch('krillion.live.read_page', state), \
             patch('krillion.live.generate', generate), \
             patch('openai.AsyncOpenAI', Client):
            args = SimpleNamespace(observe=False, overlay=True, model_timeout=1, model='test',
                                   db=os.path.join(directory, 'test.sqlite3'), poll=0.001)
            await run(args, overlay=Hints())
        self.assertEqual(submissions, [('quince', 'Enter')])
