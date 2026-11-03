import unittest
from krillion.live import clean_candidates, clean_groups, current_turn, parse_candidates, parse_turn, pending_result


class LiveParsingTests(unittest.TestCase):
    def test_turn_status(self):
        self.assertEqual(parse_turn('▸ your puffer · type an answer'), 'you')
        self.assertEqual(parse_turn('▸ new category · Alice is up'), 'Alice')
        self.assertEqual(parse_turn('▸ Alice is up'), 'Alice')
        self.assertIsNone(parse_turn('▸ category cleared'))

    def test_candidates_are_separate_and_deduplicated(self):
        self.assertEqual(parse_candidates('1. Apple\n- Pear\nAPPLE\n'), ['apple', 'pear'])

    def test_filter_after_each_move(self):
        queue = clean_candidates(['Apple', 'apple!', 'PEAR', 'pear', 'plum'])
        self.assertEqual(queue, ['apple', 'pear', 'plum'])
        self.assertEqual(clean_candidates(queue, ['APPLE!', 'Pear']), ['plum'])

    def test_rejection_during_hidden_status_allows_retry(self):
        state = {'turn': '', 'input_enabled': True, 'placeholder': 'your puffer — type!',
                 'reject': '“french guiana”: no echo. keep going'}
        turn = current_turn(state)
        self.assertEqual(turn, 'you')
        self.assertEqual(pending_result('french guiana', state['reject'], turn), 'rejected')
        self.assertEqual(clean_candidates(['french guiana', 'france'], ['french guiana']), ['france'])

    def test_hidden_status_is_not_a_turn_change(self):
        self.assertIsNone(pending_result('answer', '', None))
        self.assertEqual(pending_result('answer', '', 'other player'), 'unknown')
        self.assertEqual(pending_result('answer', '“answer”: already said', None), 'repeat')

    def test_overlay_groups_remove_cross_group_and_used_duplicates(self):
        groups = {'ordinary': ['Apple', 'pear', 'PEAR'], 'specific': ['apple!', 'quince', 'plum']}
        self.assertEqual(clean_groups(groups, ['plum']), {'ordinary': ['apple', 'pear'], 'specific': ['quince']})
