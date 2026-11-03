import unittest
from krillion.store import Store


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(':memory:')

    def test_exact_question_and_mode(self):
        self.store.record('Name a fruit', 'puffer-party', 'Apple', 'accepted', 'game', 2)
        self.assertEqual(len(self.store.lookup('Name a fruit', 'puffer-party')), 1)
        self.assertEqual(self.store.lookup('Name a red fruit', 'puffer-party'), [])
        self.assertEqual(self.store.lookup('Name a fruit', 'daily'), [])

    def test_used_and_rejection(self):
        self.store.record('Q', 'puffer-party', 'Apple', 'accepted', 'game', 2)
        self.store.record('Q', 'puffer-party', 'apple', 'rejected', 'game')
        self.assertEqual(self.store.lookup('Q', 'puffer-party')[0][0]['status'], 'rejected')
        self.assertEqual(self.store.lookup('Q', 'puffer-party', ['APPLE']), [])

    def test_rarity_ranks_only_accepted_evidence(self):
        self.store.record('Q', 'puffer-party', 'common', 'accepted', 'game', rarity='schooler')
        self.store.record('Q', 'puffer-party', 'rare one', 'accepted', 'game', rarity='krillion')
        self.store.record('Q', 'puffer-party', 'unverified', 'observed', 'game', rarity='krillion')
        self.assertEqual([g[0]['answer'] for g in self.store.lookup('Q', 'puffer-party')],
                         ['rare one', 'common', 'unverified'])
        self.store.record('Q', 'puffer-party', 'rare one', 'rejected', 'game')
        self.assertEqual(self.store.lookup('Q', 'puffer-party')[0][0]['answer'], 'common')

    def test_suggestion_not_accepted_or_scored(self):
        self.store.record('Q', 'puffer-party', 'A', 'suggested', 'model')
        self.assertEqual(self.store.lookup('Q', 'puffer-party')[0][0]['status'], 'suggested')
        with self.assertRaises(ValueError):
            self.store.record('Q', 'puffer-party', 'B', 'suggested', 'model', 4)

if __name__ == '__main__':
    unittest.main()
