import queue
import unittest
from krillion.overlay import Overlay


class OverlayDisplayTests(unittest.TestCase):
    def test_overlay_limits_groups_to_eight_and_two(self):
        overlay = Overlay.__new__(Overlay)
        overlay.events = queue.Queue()
        overlay.publish('Question', 'you', {'ordinary': [str(i) for i in range(10)],
                                            'specific': [str(i) for i in range(4)]})
        _, _, ordinary, specific, _, _ = overlay.events.get_nowait()
        self.assertEqual(len(ordinary), 8)
        self.assertEqual(len(specific), 2)
