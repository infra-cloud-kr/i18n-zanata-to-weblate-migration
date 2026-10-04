# Copyright (c) 2026 OpenStack Korea User Group
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

"""Regression tests for create_component's source string handling.

A re-run against an existing component used to only wait for the
source string *count* to equal the new POT's, without ever sending
the new POT - so any source change made the wait time out, and the
shell then skipped every PO upload for that component.
"""

from collections import defaultdict
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.parse import urlsplit
import zipfile

import polib


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / 'common' / 'weblate_utils.py'
)
SPEC = importlib.util.spec_from_file_location('weblate_utils', MODULE_PATH)
weblate_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(weblate_utils)

SCRIPTSDIR = Path(__file__).resolve().parents[1]

BASE_URL = 'https://weblate.example/api/'
COMPONENT_PATH = 'neutron/master%252Freleasenotes'


def make_response(status_code, data):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = str(data)
    return response


def pot_text(*entries):
    """Build POT content; each entry is a msgid or (msgctxt, msgid)."""
    blocks = ['msgid ""\nmsgstr ""\n'
              '"Content-Type: text/plain; charset=UTF-8\\n"\n']
    for entry in entries:
        if isinstance(entry, tuple):
            ctxt, msgid = entry
            blocks.append(f'msgctxt "{ctxt}"\nmsgid "{msgid}"\nmsgstr ""\n')
        else:
            blocks.append(f'msgid "{entry}"\nmsgstr ""\n')
    return '\n'.join(blocks)


def keys_of(content):
    return {
        (e.msgctxt or '', e.msgid, e.msgid_plural or '')
        for e in polib.pofile(content) if not e.obsolete
    }


class FakeWeblate:
    """Just enough of the Weblate API for create_component.

    Uploaded POTs (the component creation zip and method=source
    uploads) are parsed for real, and - like Weblate's background
    perform_load task - each translation only shows the new source
    set after it has been polled `reparse_polls` times.

    `files` (what's on disk) is tracked apart from `visible` (what the
    API reports). Like Weblate's handle_source(), a source upload only
    re-merges and re-parses languages whose file still differs from
    the POT - a language whose file is current but whose database copy
    is stale is left alone.
    """

    def __init__(self, existing_pot=None, languages=(), reparse_polls=1,
                 source_upload_statuses=(200,), page_size=2):
        self.exists = existing_pot is not None
        keys = keys_of(existing_pot) if self.exists else None
        # language code -> currently visible source key set
        self.visible = {}
        if self.exists:
            self.visible['en_US'] = set(keys)
            for lang in languages:
                self.visible[lang] = set(keys)
        # language code -> source key set of the file on disk
        self.files = {lang: set(k) for lang, k in self.visible.items()}
        # language code -> [new key set, polls left before visible]
        self.pending = {}
        self.reparse_polls = reparse_polls
        self.source_upload_statuses = list(source_upload_statuses)
        self.page_size = page_size
        self.posts = []
        self.unit_fetches = defaultdict(int)

    # -- helpers ------------------------------------------------------
    def _schedule(self, keys, langs):
        for lang in langs:
            self.pending[lang] = [set(keys), self.reparse_polls]

    def _units_page(self, lang, page):
        keys = sorted(self.visible[lang])
        start = (page - 1) * self.page_size
        chunk = keys[start:start + self.page_size]
        results = [
            {'context': ctxt,
             'source': [msgid, plural] if plural else [msgid]}
            for ctxt, msgid, plural in chunk
        ]
        next_url = None
        if start + self.page_size < len(keys):
            next_url = (f'{BASE_URL}translations/{COMPONENT_PATH}/{lang}/'
                        f'units/?page={page + 1}')
        return {'results': results, 'next': next_url}

    # -- requests.get / requests.post replacements ----------------------
    def get(self, url, headers=None, params=None, allow_redirects=None):
        parts = urlsplit(url)
        path = parts.path[len('/api/'):]
        query = parts.query

        if path == f'components/{COMPONENT_PATH}/':
            return make_response(200 if self.exists else 404, {})
        if path == 'projects/neutron/categories/':
            return make_response(
                200, {'results': [{'name': 'master', 'id': 17}]})
        if path == f'components/{COMPONENT_PATH}/translations/':
            return make_response(200, {'results': [
                {'language_code': lang, 'is_source': lang == 'en_US'}
                for lang in self.visible
            ], 'next': None})

        prefix = f'translations/{COMPONENT_PATH}/'
        if path.startswith(prefix):
            rest = path[len(prefix):].strip('/').split('/')
            lang = rest[0]
            if len(rest) == 1:
                if lang in self.pending:
                    self.pending[lang][1] -= 1
                    if self.pending[lang][1] <= 0:
                        self.visible[lang] = self.pending.pop(lang)[0]
                if lang not in self.visible:
                    return make_response(404, {'detail': 'Not found.'})
                return make_response(
                    200, {'total': len(self.visible[lang])})
            if rest[1:] == ['units']:
                self.unit_fetches[lang] += 1
                page = 1
                if query.startswith('page='):
                    page = int(query[len('page='):])
                return make_response(200, self._units_page(lang, page))

        raise AssertionError(f'Unexpected GET: {url}')

    def post(self, url, data=None, json=None, files=None, headers=None,
             allow_redirects=None):
        path = urlsplit(url).path[len('/api/'):]
        self.posts.append((path, data))

        if path == 'projects/neutron/components/':
            with zipfile.ZipFile(files['zipfile'][1]) as zip_file:
                content = zip_file.read(data['new_base']).decode('utf-8')
            self.exists = True
            self.files['en_US'] = keys_of(content)
            self._schedule(keys_of(content), ['en_US'])
            return make_response(201, {})

        if path == f'translations/{COMPONENT_PATH}/en_US/file/':
            assert data == {'method': 'source'}, data
            status = self.source_upload_statuses.pop(0)
            if status != 200:
                return make_response(status, {'detail': 'rejected'})
            keys = keys_of(files['file'].read().decode('utf-8'))
            changed = [lang for lang in self.visible
                       if self.files.get(lang) != keys]
            for lang in changed:
                self.files[lang] = set(keys)
            self._schedule(keys, changed)
            return make_response(200, {'result': True})

        raise AssertionError(f'Unexpected POST: {url}')


class CreateComponentSourceSyncTest(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            token='test-token', base_url='https://weblate.example/')
        self.utils = weblate_utils.WeblateUtils(config)
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_dir = Path(temp_dir.name)

    def write_pot(self, content):
        pot_path = self.temp_dir / 'releasenotes.pot'
        pot_path.write_text(content, encoding='utf-8')
        return str(pot_path)

    def run_create_component(self, fake, pot_path):
        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=fake.get),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=fake.post),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            self.utils.create_component(
                'neutron', 'master', 'releasenotes', pot_path)

    def source_uploads(self, fake):
        return [p for p, _ in fake.posts if p.endswith('/en_US/file/')]

    def test_new_component_waits_for_whole_source_set(self):
        pot = pot_text('first', 'second', ('ctx', 'third'))
        fake = FakeWeblate(reparse_polls=3)

        self.run_create_component(fake, self.write_pot(pot))

        self.assertEqual(['projects/neutron/components/'],
                         [p for p, _ in fake.posts])
        self.assertEqual(keys_of(pot), fake.visible['en_US'])

    def test_unchanged_source_rerun_sends_nothing(self):
        pot = pot_text('first', 'second')
        fake = FakeWeblate(existing_pot=pot, languages=['fr', 'ko_KR'])

        self.run_create_component(fake, self.write_pot(pot))

        self.assertEqual([], fake.posts)
        # Each language's set is checked exactly once, no polling.
        self.assertEqual(1, fake.unit_fetches['fr'])
        self.assertEqual(1, fake.unit_fetches['ko_KR'])

    def test_added_source_string_is_uploaded_to_existing_component(self):
        old = pot_text('first', 'second')
        new = pot_text('first', 'second', 'third')
        fake = FakeWeblate(existing_pot=old, languages=['fr'],
                           reparse_polls=2)

        self.run_create_component(fake, self.write_pot(new))

        self.assertEqual([f'translations/{COMPONENT_PATH}/en_US/file/'],
                         self.source_uploads(fake))
        self.assertEqual(keys_of(new), fake.visible['en_US'])
        self.assertEqual(keys_of(new), fake.visible['fr'])

    def test_same_count_replacement_is_detected_and_waited_for(self):
        # Same total before and after - the case a count-only check
        # can neither detect nor wait for.
        old = pot_text('first', 'second', 'old third')
        new = pot_text('first', 'second', ('ctx', 'new third'))
        fake = FakeWeblate(existing_pot=old, languages=['fr'],
                           reparse_polls=3)

        self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(1, len(self.source_uploads(fake)))
        self.assertEqual(keys_of(new), fake.visible['fr'])
        # 'fr' reported the matching total while still holding the old
        # set, so its units had to be compared more than once.
        self.assertGreater(fake.unit_fetches['fr'], 1)

    def lagging_locale_fake(self, old, new, **kwargs):
        """en_US already has the new POT, 'fr' the same number of old
        strings - a re-run after an interrupted or slow source update.
        """
        fake = FakeWeblate(existing_pot=new, languages=['fr'], **kwargs)
        fake.visible['fr'] = keys_of(old)
        fake.files['fr'] = keys_of(old)
        return fake

    def test_rerun_resyncs_locale_left_behind_by_partial_update(self):
        # The file merge itself never reached 'fr': re-sending the
        # source update fixes it.
        old = pot_text('first', 'old')
        new = pot_text('first', 'new')
        fake = self.lagging_locale_fake(old, new, reparse_polls=2)

        self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(1, len(self.source_uploads(fake)))
        self.assertEqual(keys_of(new), fake.visible['fr'])
        self.assertEqual(keys_of(new), fake.visible['en_US'])

    def test_rerun_waits_for_locale_still_reparsing(self):
        # 'fr' file already merged, database catching up late: the
        # re-sent upload changes nothing, the wait lets it finish.
        old = pot_text('first', 'old')
        new = pot_text('first', 'new')
        fake = self.lagging_locale_fake(old, new)
        fake.files['fr'] = keys_of(new)
        fake.pending['fr'] = [keys_of(new), 4]

        self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(keys_of(new), fake.visible['fr'])
        self.assertGreater(fake.unit_fetches['fr'], 1)

    def test_rerun_fails_when_locale_never_catches_up(self):
        # 'fr' file already merged but its database copy never
        # re-parses: must fail (so no PO upload follows), and the
        # source update must not be re-sent over and over.
        old = pot_text('first', 'old')
        new = pot_text('first', 'new')
        fake = self.lagging_locale_fake(old, new)
        fake.files['fr'] = keys_of(new)

        with self.assertRaises(SystemExit) as raised:
            self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(1, raised.exception.code)
        self.assertEqual(1, len(self.source_uploads(fake)))
        self.assertEqual(keys_of(old), fake.visible['fr'])
        # Only en_US's file endpoint was ever written.
        self.assertEqual(
            [f'translations/{COMPONENT_PATH}/en_US/file/'],
            [p for p, _ in fake.posts])

    def test_only_source_language_is_written(self):
        # Existing translations must only ever be merged by Weblate's
        # own msgmerge (method=source on en_US) - never replaced by
        # an upload to a language's file endpoint.
        old = pot_text('first', 'second')
        new = pot_text('first', 'changed')
        fake = FakeWeblate(existing_pot=old, languages=['fr', 'ja'])

        self.run_create_component(fake, self.write_pot(new))

        self.assertTrue(fake.posts)
        for path, data in fake.posts:
            self.assertEqual(f'translations/{COMPONENT_PATH}/en_US/file/',
                             path)
            self.assertEqual({'method': 'source'}, data)

    def test_transient_source_upload_failure_is_retried(self):
        old = pot_text('first')
        new = pot_text('first', 'second')
        fake = FakeWeblate(existing_pot=old, languages=['fr'],
                           source_upload_statuses=(423, 200))

        self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(2, len(self.source_uploads(fake)))
        self.assertEqual(keys_of(new), fake.visible['fr'])

    def test_rejected_source_upload_exits_without_changes(self):
        old = pot_text('first')
        new = pot_text('first', 'second')
        fake = FakeWeblate(existing_pot=old, languages=['fr'],
                           source_upload_statuses=(400,))

        with self.assertRaises(SystemExit) as raised:
            self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(1, raised.exception.code)
        self.assertEqual(1, len(self.source_uploads(fake)))
        self.assertEqual(keys_of(old), fake.visible['fr'])

    def test_language_that_never_catches_up_fails(self):
        old = pot_text('first', 'old')
        new = pot_text('first', 'new')
        fake = FakeWeblate(existing_pot=old, languages=['fr'],
                           reparse_polls=10 ** 6)

        with self.assertRaises(SystemExit) as raised:
            self.run_create_component(fake, self.write_pot(new))

        self.assertEqual(1, raised.exception.code)


class SourceKeyTest(unittest.TestCase):
    def test_pot_and_unit_keys_agree(self):
        content = (
            pot_text('plain', ('menu', 'Open')) +
            '\nmsgid "%d volume"\nmsgid_plural "%d volumes"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n'
            '\n#~ msgid "gone"\n#~ msgstr ""\n'
        )
        with tempfile.NamedTemporaryFile(
                'w', suffix='.pot', delete=False) as f:
            f.write(content)
        self.addCleanup(Path(f.name).unlink)

        pot_keys = weblate_utils.get_pot_source_keys(f.name)
        unit_keys = {
            weblate_utils.get_unit_source_key(unit) for unit in [
                {'context': '', 'source': ['plain']},
                {'context': 'menu', 'source': ['Open']},
                {'context': '', 'source': ['%d volume', '%d volumes']},
            ]
        }

        self.assertEqual(unit_keys, pot_keys)


@unittest.skipUnless(shutil.which('msgmerge'), 'msgmerge not installed')
class WeblateSourceMergeTest(unittest.TestCase):
    """What a method=source upload does to an existing language file.

    Weblate 5.x's handle_source() runs `msgmerge --previous <po> <pot>`
    (BilingualUpdateMixin.get_msgmerge_args, without the msgmerge
    add-on) on every language file. This pins down the preservation
    behavior the migration relies on.
    """

    def test_existing_translations_survive_source_update(self):
        po = (
            'msgid ""\nmsgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "kept"\nmsgstr "conservé"\n\n'
            '#, fuzzy\nmsgid "kept fuzzy"\nmsgstr "à revoir"\n\n'
            'msgid "%d volume"\nmsgid_plural "%d volumes"\n'
            'msgstr[0] "%d volume"\nmsgstr[1] "%d volumes"\n\n'
            'msgid "removed string"\nmsgstr "supprimé"\n'
        )
        pot = (
            'msgid ""\nmsgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "kept"\nmsgstr ""\n\n'
            'msgid "kept fuzzy"\nmsgstr ""\n\n'
            'msgid "%d volume"\nmsgid_plural "%d volumes"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n\n'
            'msgid "brand new"\nmsgstr ""\n'
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            po_path = Path(temp_dir) / 'fr.po'
            pot_path = Path(temp_dir) / 'new.pot'
            out_path = Path(temp_dir) / 'out.po'
            po_path.write_text(po, encoding='utf-8')
            pot_path.write_text(pot, encoding='utf-8')
            subprocess.run(
                ['msgmerge', '--previous', '--output-file', str(out_path),
                 str(po_path), str(pot_path)],
                check=True, capture_output=True,
            )
            merged = polib.pofile(str(out_path))

        active = {e.msgid: e for e in merged if not e.obsolete}
        self.assertEqual({'kept', 'kept fuzzy', '%d volume', 'brand new'},
                         set(active))
        self.assertEqual('conservé', active['kept'].msgstr)
        self.assertNotIn('fuzzy', active['kept'].flags)
        self.assertEqual('à revoir', active['kept fuzzy'].msgstr)
        self.assertIn('fuzzy', active['kept fuzzy'].flags)
        self.assertEqual({0: '%d volume', 1: '%d volumes'},
                         active['%d volume'].msgstr_plural)
        self.assertEqual('', active['brand new'].msgstr)
        # Removed strings are kept as obsolete, which Weblate ignores.
        self.assertIn('removed string',
                      {e.msgid for e in merged if e.obsolete})


class CreateWeblateComponentsShellTest(unittest.TestCase):
    """create_weblate_components.sh must not upload PO files for a
    component whose create-component step (including the source
    update) failed, and must still process the other components."""

    def test_failed_component_skips_po_upload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / 'calls.log'
            script = r'''
                source "$SCRIPTSDIR/04-prepare-weblate-components/$SCRIPT"
                get_pot_path() { echo "/pot/$1.pot"; }
                get_translation_path_list() { echo "/po/$1/fr.po"; }
                extract_locale_from_path() { echo fr; }
                tree_line() { :; }
                tree_line_update() { :; }
                log_quiet() { :; }
                tagged_colorize() { :; }
                component_progress_text() { :; }
                update_component_progress() { :; }
                extract_status_reason() { echo "$1"; }
                sleep() { :; }
                run_tagged_quiet() { LAST_TAGGED_LINE="x"; "$@"; }
                python3() {
                    echo "$*" >> "$CALL_LOG"
                    case "$*" in
                        *create-component*--component\ cinder\ *) return 1 ;;
                    esac
                    return 0
                }
                PROJECT=cinder
                ZANATA_VERSION=master
                WORKSPACE_NAME=workspace
                COMPONENTS=(cinder releasenotes)
                create_weblate_components
            '''
            result = subprocess.run(
                ['bash', '-c', script],
                env={
                    'PATH': '/usr/bin:/bin',
                    'HOME': temp_dir,
                    'SCRIPTSDIR': str(SCRIPTSDIR),
                    'CALL_LOG': str(log_path),
                    'SCRIPT': 'create_weblate_components.sh',
                },
                capture_output=True, text=True,
            )
            calls = log_path.read_text().splitlines()

        self.assertEqual(1, result.returncode, result.stderr)
        uploads = [c for c in calls if 'upload-po-file' in c]
        self.assertEqual(1, len(uploads), calls)
        self.assertIn('--component releasenotes', uploads[0])
        self.assertFalse(
            [c for c in calls if 'create-translation' in c
             and '--component cinder ' in c])


if __name__ == '__main__':
    unittest.main()
