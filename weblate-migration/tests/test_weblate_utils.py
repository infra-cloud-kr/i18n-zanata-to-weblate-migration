# Copyright (c) 2026 OpenStack Korea User Group
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0

import importlib.util
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import unittest
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / 'common' / 'weblate_utils.py'
)
SPEC = importlib.util.spec_from_file_location('weblate_utils', MODULE_PATH)
weblate_utils = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(weblate_utils)


def make_response(status_code, data):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = data
    response.text = str(data)
    return response


class WeblateUtilsReadinessTest(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            token='test-token',
            base_url='https://weblate.example/',
        )
        self.utils = weblate_utils.WeblateUtils(config)

    def _write_po(self, content):
        po_path = Path(
            f'{self.id().replace(".", "-")}-{id(content)}'
        ).with_suffix('.po')
        self.addCleanup(po_path.unlink, missing_ok=True)
        po_path.write_text(content, encoding='utf-8')
        return po_path

    def test_create_translation_returns_when_source_strings_are_ready(self):
        po_path = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "first"\nmsgstr ""\n'
        )
        state = {
            'created': False,
            'ready': False,
            'readiness_checks': 0,
        }

        def get_translation(url, headers=None, params=None,
                            allow_redirects=None):
            if not state['created']:
                return make_response(404, {'detail': 'Not found.'})

            state['readiness_checks'] += 1
            if state['readiness_checks'] == 1:
                return make_response(200, {'total': 0})

            state['ready'] = True
            return make_response(200, {'total': 1260})

        def create_translation(url, json=None, headers=None,
                               allow_redirects=None):
            state['created'] = True
            return make_response(201, {})

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=get_translation
            ),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=create_translation
            ),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            self.utils.create_translation(
                'neutron', 'master', 'releasenotes', 'fr', str(po_path)
            )

        self.assertTrue(state['ready'])

    def test_create_translation_stops_on_non_retryable_error(self):
        po_path = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "first"\nmsgstr ""\n'
        )
        state = {
            'created': False,
            'readiness_checks': 0,
        }

        def get_translation(url, headers=None, params=None,
                            allow_redirects=None):
            if not state['created']:
                return make_response(404, {'detail': 'Not found.'})

            state['readiness_checks'] += 1
            return make_response(401, {'detail': 'Unauthorized.'})

        def create_translation(url, json=None, headers=None,
                               allow_redirects=None):
            state['created'] = True
            return make_response(201, {})

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=get_translation
            ),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=create_translation
            ),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            with self.assertRaises(SystemExit):
                self.utils.create_translation(
                    'neutron', 'master', 'releasenotes', 'fr', str(po_path)
                )

        self.assertEqual(state['readiness_checks'], 1)

    def test_create_translation_waits_for_plural_slots_to_fill(self):
        po_path = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Delete Volume"\nmsgid_plural "Delete Volumes"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n'
        )
        state = {
            'created': False,
            'plural_checks': 0,
            'ready': False,
        }

        def get_translation(url, headers=None, params=None,
                            allow_redirects=None):
            if not state['created']:
                return make_response(404, {'detail': 'Not found.'})

            if url.endswith(
                    '/translations/neutron/master%252Freleasenotes/fr/'):
                return make_response(200, {
                    'total': 1,
                    'language': {'plural': {'number': 2}},
                })

            if '/units/' in url:
                state['plural_checks'] += 1
                if state['plural_checks'] == 1:
                    target = ['']
                else:
                    state['ready'] = True
                    target = ['', '']
                return make_response(200, {
                    'results': [{'target': target}],
                })

            self.fail(f'Unexpected GET: {url}')

        def create_translation(url, json=None, headers=None,
                               allow_redirects=None):
            state['created'] = True
            return make_response(201, {})

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=get_translation
            ),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=create_translation
            ),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            self.utils.create_translation(
                'neutron', 'master', 'releasenotes', 'fr', str(po_path)
            )

        self.assertTrue(state['ready'])

    def test_create_translation_waits_for_all_plural_units_across_pages(
            self):
        po_path = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Delete Volume"\nmsgid_plural "Delete Volumes"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n'
            '\nmsgid "Delete Item"\nmsgid_plural "Delete Items"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n'
        )
        page_two_url = (
            'https://weblate.example/translations/neutron/'
            'master%252Freleasenotes/fr/units/?q=has%3Aplural&page=2'
        )
        state = {
            'created': False,
            'page_two_checks': 0,
            'ready': False,
        }

        def get_translation(url, headers=None, params=None,
                            allow_redirects=None):
            if not state['created']:
                return make_response(404, {'detail': 'Not found.'})

            if url.endswith(
                    '/translations/neutron/master%252Freleasenotes/fr/'):
                return make_response(200, {
                    'total': 2,
                    'language': {'plural': {'number': 2}},
                })

            if url == page_two_url:
                state['page_two_checks'] += 1
                if state['page_two_checks'] == 1:
                    target = ['']
                else:
                    state['ready'] = True
                    target = ['', '']
                return make_response(200, {'results': [{'target': target}]})

            if '/units/' in url:
                # First page: its own unit is already full, but a
                # second page (not yet ready) still exists - a
                # correct implementation must not stop here.
                return make_response(200, {
                    'results': [{'target': ['', '']}],
                    'next': page_two_url,
                })

            self.fail(f'Unexpected GET: {url}')

        def create_translation(url, json=None, headers=None,
                               allow_redirects=None):
            state['created'] = True
            return make_response(201, {})

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=get_translation
            ),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=create_translation
            ),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            self.utils.create_translation(
                'neutron', 'master', 'releasenotes', 'fr', str(po_path)
            )

        self.assertTrue(state['ready'])
        self.assertGreaterEqual(state['page_two_checks'], 2)

    def test_create_component_returns_when_whole_pot_is_imported(self):
        pot_path = Path(self.id().replace('.', '-')).with_suffix('.pot')
        self.addCleanup(pot_path.unlink, missing_ok=True)
        pot_path.write_text(
            'msgid "first"\nmsgstr ""\n\n'
            'msgid "second"\nmsgstr ""\n',
            encoding='utf-8',
        )

        state = {
            'created': False,
            'ready': False,
            'source_checks': 0,
        }

        def get_component(url, headers=None, params=None,
                          allow_redirects=None):
            if '/components/' in url:
                return make_response(404, {'detail': 'Not found.'})
            if url.endswith('/projects/neutron/categories/'):
                return make_response(
                    200,
                    {'results': [{'name': 'master', 'id': 17}]},
                )
            if '/en_US/units/?page_size=1' in url and not url.endswith(
                    'page_size=1000'):
                state['source_checks'] += 1
                if state['source_checks'] == 1:
                    return make_response(200, {'count': 1})

                return make_response(200, {'count': 2})
            if '/en_US/units/' in url:
                state['ready'] = True
                return make_response(200, {'count': 2, 'results': [
                    {'context': '', 'source': ['first']},
                    {'context': '', 'source': ['second']},
                ], 'next': None})
            self.fail(f'Unexpected GET: {url}')

        def create_component(url, data=None, files=None, headers=None,
                             allow_redirects=None):
            state['created'] = True
            return make_response(201, {})

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', side_effect=get_component
            ),
            mock.patch.object(
                weblate_utils.requests, 'post', side_effect=create_component
            ),
            mock.patch.object(weblate_utils.time, 'sleep'),
        ):
            self.utils.create_component(
                'neutron', 'master', 'releasenotes', str(pot_path)
            )

        self.assertTrue(state['created'])
        self.assertTrue(state['ready'])


class WeblateUtilsSentenceDetailTest(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            token='test-token',
            base_url='https://weblate.example/',
        )
        self.utils = weblate_utils.WeblateUtils(config)

    def _write_po(self, content):
        po_path = Path(
            f'{self.id().replace(".", "-")}-{id(content)}'
        ).with_suffix('.po')
        self.addCleanup(po_path.unlink, missing_ok=True)
        po_path.write_text(content, encoding='utf-8')
        return po_path

    def test_check_sentence_detail_skips_never_translated_plural_entry(self):
        # Weblate's own PO export writes a single blank msgstr[0] for
        # a plural unit with no translated content on either side,
        # regardless of the language's true nplurals - this must not
        # be flagged as a mismatch (see check_sentence_detail's
        # both_fully_empty handling).
        zanata_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Batched Item"\nmsgid_plural "Batched Items"\n'
            'msgstr[0] ""\nmsgstr[1] ""\n'
        )
        weblate_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Batched Item"\nmsgid_plural "Batched Items"\n'
            'msgstr[0] ""\n'
        )

        result = self.utils.check_sentence_detail(
            'horizon', 'stable-2025.1', 'horizon-django', 'he',
            str(zanata_po), str(weblate_po),
        )

        self.assertTrue(result)

    def test_check_sentence_detail_still_flags_lost_plural_content(self):
        # A plural entry that DID have real translated content losing
        # a slot is genuine data loss (the kn-locale case this check
        # exists to catch) and must still fail, even though it hits
        # the same "index sets differ" branch as the empty case above.
        zanata_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Delete Volume"\nmsgid_plural "Delete Volumes"\n'
            'msgstr[0] "Translated singular"\n'
            'msgstr[1] "Translated plural"\n'
        )
        weblate_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
            'msgid "Delete Volume"\nmsgid_plural "Delete Volumes"\n'
            'msgstr[0] "Translated singular"\n'
        )

        result = self.utils.check_sentence_detail(
            'horizon', 'stable-2025.1', 'horizon-django', 'kn',
            str(zanata_po), str(weblate_po),
        )

        self.assertFalse(result)


class WeblateUtilsPoFormatTest(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            token='test-token',
            base_url='https://weblate.example/',
        )
        self.utils = weblate_utils.WeblateUtils(config)

    def _write_po(self, content):
        po_path = Path(
            f'{self.id().replace(".", "-")}-{id(content)}'
        ).with_suffix('.po')
        self.addCleanup(po_path.unlink, missing_ok=True)
        po_path.write_text(content, encoding='utf-8')
        return po_path

    def test_check_po_format_warns_but_does_not_fail_on_placeholder_mismatch(
        self,
    ):
        # Mirrors the real heat.po pt_BR case: the translator
        # translated the placeholder name itself ({key} -> {chave}),
        # which msgfmt --check correctly flags as a fatal format
        # error. This must surface as a warning, not fail the
        # accuracy test - see check_po_format's docstring.
        weblate_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            '#, python-brace-format\n'
            'msgid "Set header X-Container-Meta-{key}."\n'
            'msgstr "Configurar cabecalho X-Container-Meta-{chave}."\n'
        )

        result = self.utils.check_po_format(
            'heat', 'master', 'heat', 'pt_BR', str(weblate_po),
        )

        self.assertTrue(result)

    def test_check_po_format_passes_clean_file(self):
        weblate_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "Hello"\nmsgstr "Bonjour"\n'
        )

        result = self.utils.check_po_format(
            'heat', 'master', 'heat', 'fr', str(weblate_po),
        )

        self.assertTrue(result)

    def test_check_po_format_survives_non_utf8_msgfmt_stderr(self):
        # Mirrors the real barbican/zh_CN case (issue #42): msgfmt
        # wrote a non-UTF-8 byte to stderr and text=True's strict
        # decode raised UnicodeDecodeError, aborting the whole locale
        # instead of being recorded as a warning. Uses a fake msgfmt
        # placed ahead on PATH so the real subprocess/decode path
        # (not just check_po_format's own logic) is exercised.
        weblate_po = self._write_po(
            'msgid ""\nmsgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            'msgid "Hello"\nmsgstr "Ni hao"\n'
        )
        fake_bin_dir = Path(
            f'{self.id().replace(".", "-")}-fakebin'
        )
        fake_bin_dir.mkdir(exist_ok=True)
        self.addCleanup(shutil.rmtree, fake_bin_dir, ignore_errors=True)
        fake_msgfmt = fake_bin_dir / 'msgfmt'
        fake_msgfmt.write_text(
            '#!/usr/bin/env python3\n'
            'import sys\n'
            "sys.stderr.buffer.write(b'invalid multibyte: \\xe6 boom\\n')\n"
            'sys.exit(1)\n'
        )
        fake_msgfmt.chmod(0o755)

        with mock.patch.dict(
            'os.environ',
            {'PATH': f'{fake_bin_dir.resolve()}:{os.environ["PATH"]}'},
        ):
            result = self.utils.check_po_format(
                'barbican', 'master', 'barbican', 'zh_CN', str(weblate_po),
            )

        self.assertTrue(result)


class WeblateUtilsRedirectTest(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            token='test-token',
            base_url='http://weblate.example/',
        )
        self.utils = weblate_utils.WeblateUtils(config)

    def test_get_rejects_redirect_instead_of_following_it(self):
        # A 3xx here means WEBLATE_URL's scheme/host doesn't match the
        # server's canonical one - following it would let requests
        # silently resend the request against a different endpoint,
        # so this must fail loudly instead of quietly returning
        # whatever the followed response happens to be.
        response = mock.Mock()
        response.status_code = 301
        response.headers = {
            'Location': 'https://weblate.example/api/projects/',
        }

        with (
            mock.patch.object(
                weblate_utils.requests, 'get', return_value=response,
            ) as mock_get,
            self.assertRaises(SystemExit),
        ):
            self.utils._get('http://weblate.example/api/projects/')

        self.assertFalse(mock_get.call_args.kwargs['allow_redirects'])

    def test_post_rejects_redirect_instead_of_following_it(self):
        # Following this redirect is what would otherwise turn a
        # "create glossary" POST into a GET against the same URL
        # (requests demotes POST to GET on 301/302) - the real bug
        # this guard exists to catch.
        response = mock.Mock()
        response.status_code = 301
        response.headers = {
            'Location': ('https://weblate.example/api/projects/'
                         'barbican/components/'),
        }

        with (
            mock.patch.object(
                weblate_utils.requests, 'post', return_value=response,
            ) as mock_post,
            self.assertRaises(SystemExit),
        ):
            self.utils._post(
                'http://weblate.example/api/projects/barbican/components/',
                data={'name': 'glossary'},
            )

        self.assertFalse(mock_post.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
