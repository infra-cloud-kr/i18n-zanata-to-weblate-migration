# Copyright (c) 2026 OpenStack Korea User Group
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / 'common'
    / 'get_translation_path.sh'
)


class GetTranslationPathTest(unittest.TestCase):
    def run_get_pot_path(self, project, component, pot_dir):
        return subprocess.run(
            [
                'bash', '-c',
                'source "$1"; PROJECT="$2"; WORKSPACE_NAME=workspace; '
                'get_pot_path "$3" "$4"',
                '_', str(SCRIPT_PATH), project, component, str(pot_dir),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_get_translation_path_list(self, project, component, home_dir):
        return subprocess.run(
            [
                'bash', '-c',
                'source "$1"; PROJECT="$2"; HOME="$3"; '
                'get_translation_path_list "$4"',
                '_', str(SCRIPT_PATH), project, str(home_dir), component,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_extract_locale(self, project, translation_path):
        return subprocess.run(
            [
                'bash', '-c',
                'source "$1"; PROJECT="$2"; '
                'extract_locale_from_path "$3"',
                '_', str(SCRIPT_PATH), project, str(translation_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_i18n_doc_uses_flattened_pulled_pot_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pot_dir = Path(temp_dir) / 'pot'
            expected = pot_dir / 'doc.pot'
            expected.parent.mkdir(parents=True)
            expected.touch()

            result = self.run_get_pot_path('i18n', 'doc', pot_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(expected), result.stdout.strip())

    def test_conventional_doc_path_is_preferred(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pot_dir = Path(temp_dir) / 'pot'
            expected = pot_dir / 'doc' / 'source' / 'locale' / 'doc.pot'
            expected.parent.mkdir(parents=True)
            expected.touch()
            (pot_dir / 'other' / 'doc.pot').parent.mkdir(parents=True)
            (pot_dir / 'other' / 'doc.pot').touch()

            result = self.run_get_pot_path(
                'openstack-manuals', 'doc', pot_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(expected), result.stdout.strip())

    def test_missing_pot_path_fails_instead_of_returning_nonexistent_path(
            self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pot_dir = Path(temp_dir) / 'pot'
            pot_dir.mkdir()

            result = self.run_get_pot_path('i18n', 'doc', pot_dir)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)

    def test_ambiguous_fallback_pot_paths_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pot_dir = Path(temp_dir) / 'pot'
            for directory in ('first', 'second'):
                path = pot_dir / directory / 'doc.pot'
                path.parent.mkdir(parents=True)
                path.touch()

            result = self.run_get_pot_path('i18n', 'doc', pot_dir)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)

    def test_i18n_doc_finds_flattened_pulled_translation_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            translations_dir = (
                home_dir / 'workspace' / 'projects' / 'i18n'
                / 'translations'
            )
            expected = []
            for locale in ('ko_KR', 'fr'):
                po_path = (
                    translations_dir / locale / 'LC_MESSAGES' / 'doc.po'
                )
                po_path.parent.mkdir(parents=True)
                po_path.touch()
                expected.append(str(po_path))

            # A nested conventional-looking file must not be mixed into the
            # i18n-specific flattened layout.
            unrelated = (
                translations_dir / 'doc' / 'source' / 'locale' / 'ja'
                / 'LC_MESSAGES' / 'doc.po'
            )
            unrelated.parent.mkdir(parents=True)
            unrelated.touch()

            result = self.run_get_translation_path_list(
                'i18n', 'doc', home_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(sorted(expected), result.stdout.strip().split())

    def test_non_i18n_doc_keeps_conventional_translation_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home_dir = Path(temp_dir)
            translations_dir = (
                home_dir / 'workspace' / 'projects' / 'openstack-manuals'
                / 'translations'
            )
            expected = (
                translations_dir / 'doc' / 'source' / 'locale' / 'ja'
                / 'LC_MESSAGES' / 'doc.po'
            )
            expected.parent.mkdir(parents=True)
            expected.touch()

            result = self.run_get_translation_path_list(
                'openstack-manuals', 'doc', home_dir)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(expected), result.stdout.strip())

    def test_i18n_locale_is_extracted_from_flattened_path(self):
        path = '/tmp/translations/ko_KR/LC_MESSAGES/doc.po'

        result = self.run_extract_locale('i18n', path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('ko_KR', result.stdout.strip())

    def test_conventional_locale_extraction_is_unchanged(self):
        path = '/tmp/translations/doc/source/locale/ja/LC_MESSAGES/doc.po'

        result = self.run_extract_locale('openstack-manuals', path)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('ja', result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
