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
    / '02-prepare-translations'
    / 'get_translations.sh'
)


class GetTranslationsTest(unittest.TestCase):
    def test_zanata_pull_forces_utf8_and_preserves_existing_java_opts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = (
                Path(temp_dir) / 'workspace' / 'projects' / 'i18n' / 'i18n'
            )
            project_dir.mkdir(parents=True)

            result = subprocess.run(
                [
                    'bash', '-c',
                    'HOME="$2"; WORKSPACE_NAME=workspace; PROJECT=i18n; '
                    'JAVA_OPTS="-Xmx256m -Dfile.encoding=US-ASCII"; '
                    'run_tagged_quiet() { printf "<%s>\\n" "$@"; }; '
                    'source "$1"; pull_translation_files',
                    '_', str(SCRIPT_PATH), temp_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        arguments = result.stdout.splitlines()
        self.assertEqual('<env>', arguments[0])
        self.assertIn('<LANG=C.UTF-8>', arguments)
        self.assertIn('<LC_ALL=C.UTF-8>', arguments)
        self.assertIn(
            '<JAVA_OPTS=-Xmx256m -Dfile.encoding=US-ASCII '
            '-Dfile.encoding=UTF-8>',
            arguments,
        )
        self.assertIn('<zanata-cli>', arguments)


if __name__ == '__main__':
    unittest.main()
