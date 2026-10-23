"""Offline help must remain usable with absent/older saved preferences."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ArgentumSplat'))
from argentum_splat import help_content as H


class HelpTests(unittest.TestCase):
    def test_every_topic_has_complete_text_in_both_languages(self):
        for language, pages in ((0, H.EN), (1, H.RU)):
            self.assertEqual(len(H.TOPICS[language]), len(pages))
            for topic in range(len(pages)):
                self.assertGreater(len(H.text(language, topic)), 350)
        self.assertNotEqual(H.text(0, 0), H.text(1, 0))

    def test_absent_or_invalid_saved_preferences_have_safe_fallback(self):
        for locale in (None, -1, 99, 'ru'):
            for topic in (None, -1, 99, '0'):
                self.assertEqual(H.text(locale, topic), H.EN[0])

    def test_each_language_explains_all_manual_tools_and_distinct_counts(self):
        for pages in (H.EN, H.RU):
            manual = '\n'.join(pages)
            for label in ('Gaussian Count', 'Import Quality', 'Preview Points',
                          'Initialise / Reload', 'Source Fidelity',
                          'Auto Prepare Redshift', 'Auto Frame in Empty Scene',
                          'Frame Loaded Scan', 'Set Redshift Detail Quality',
                          'Create Estimated Source Camera'):
                self.assertIn(label, manual)


if __name__ == '__main__':
    unittest.main()
