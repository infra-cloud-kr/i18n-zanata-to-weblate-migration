# Copyright (c) 2015 Hewlett-Packard Development Company, L.P.
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

import argparse
from collections import defaultdict
import fcntl
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from typing import Callable
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
import zipfile
import polib
import requests


def sanitize_locale(locale: str) -> str:
    """Sanitize locale for standardization

    :param locale: string locale to sanitize
    :returns: string sanitized locale
    """
    # Some translations are set to invalid locale format in weblate.
    # so we need to convert them. ex) zh_Hans, zh_Hant, etc.
    if locale == "zh_Hans":
        locale = "zh_CN"
    elif locale == "zh_Hant":
        locale = "zh_TW"
    # In weblate, the language code is lowercase.
    # ex) Th -> th etc.
    if '_' in locale:
        locale_split = locale.split('_')
        locale = locale_split[0].lower() + '_' + locale_split[1]
    else:
        locale = locale.lower()
    return locale


def sanitize_slug(name: str) -> str:
    """Sanitize slug for standardization

    Replace special characters(dot, space, etc.) with hyphens.
    ex) stable/2025.02 -> stable-2025-02, zun_ui -> zun-ui etc.

    :param name: string name to sanitize
    :returns: string sanitized name
    """
    return re.sub(r'-+', '-', re.sub(r'[^a-zA-Z0-9_-]', '-', name)).strip('-')


def is_retryable_status(status_code: int) -> bool:
    """Whether a response status code is worth retrying

    Meant to be called only after the caller's own success check has
    already failed for this response. A non-4xx code reaching that
    point (e.g. upload_po_file's 200 with result=false) isn't a
    rejection, so it's worth retrying, same as a 5xx (server-side,
    usually transient) failure. 423 (Weblate could not obtain its
    internal repository lock - e.g. another write to the same
    component was still in progress) and 429 (rate limited) are also
    transient despite being in the 4xx range: the condition they
    describe is expected to clear on its own shortly. Any other 4xx
    means the server rejected this exact request, so an identical
    retry cannot succeed.

    :param status_code: HTTP status code from a Weblate API response
    :returns: True if retrying the same request may succeed later
    """
    if status_code < 400 or status_code >= 500:
        return True
    return status_code in (423, 429)


def get_component_display_name(component_name: str) -> str:
    """Get the Weblate-facing display name for a component

    The internal component identifier is a flat, hyphen-joined string
    (e.g. "horizon-django") used for slug/path construction throughout
    this pipeline. For components representing a specific Django
    module (<module>-django / <module>-djangojs), Weblate's 'name'
    field should instead read like the original Zanata document name,
    with '/' separating the module from its type (e.g.
    "horizon/django"). The slug (URL/API identifier) still comes from
    sanitize_slug() on the original hyphenated identifier and is
    unaffected by this.

    :param component_name: internal component identifier
    :returns: display name to use for Weblate's 'name' field
    """
    if component_name.endswith('-django'):
        return f'{component_name[:-len("-django")]}/django'
    if component_name.endswith('-djangojs'):
        return f'{component_name[:-len("-djangojs")]}/djangojs'
    return component_name


def get_filemask(component_name: str) -> str:
    """Get filemask for the component

    It follows the pattern that zanata uses.

    :param component_name: string name of the component
    :returns: string filemask for the component
    """
    if component_name == 'releasenotes':
        return 'source/locale/*/LC_MESSAGES/releasenotes.po'
    # In Weblate, it doesn't allow the same component name.
    # When the project has multiple horizon modules,
    # the component name is <module_name>-django/djangojs.
    # But, the filemask is same for consistency with other components.
    elif component_name == 'django' or component_name.endswith('-django'):
        return 'locale/*/LC_MESSAGES/django.po'
    elif component_name == 'djangojs' or component_name.endswith('-djangojs'):
        return 'locale/*/LC_MESSAGES/djangojs.po'
    # All of the doc components use the same filemask.
    # ex) doc, doc-install, etc.
    elif component_name.startswith('doc'):
        return f'source/locale/*/LC_MESSAGES/{component_name}.po'
    else:
        return f'locale/*/LC_MESSAGES/{component_name}.po'


def get_version_name(version: str) -> str:
    return version.replace('/', '-')


def get_pot_source_keys(pot_path: str) -> set:
    """Get the set of source string keys a POT file defines.

    A key is (msgctxt, msgid, msgid_plural), with a missing msgctxt/
    msgid_plural normalized to '' - the same parts Weblate hashes into
    a bilingual unit's id_hash (source with plural forms joined, plus
    context; see weblate.formats.base.TranslationUnit.calculate_id_hash),
    so two entries Weblate would collapse into one unit (it keeps the
    first and raises a DuplicateString alert for the rest) also collapse
    into one key here. Obsolete (#~) entries are excluded, since
    Weblate never imports them as units.

    Compared as a set rather than a count because a POT whose strings
    were replaced one-for-one keeps the same total - a count-only check
    cannot tell it apart from an unchanged one.

    :param pot_path: path to the POT file
    :returns: set of (msgctxt, msgid, msgid_plural) tuples
    """
    pot = polib.pofile(pot_path)
    return {
        (entry.msgctxt or '', entry.msgid, entry.msgid_plural or '')
        for entry in pot if not entry.obsolete
    }


def get_unit_source_key(unit: dict) -> tuple:
    """Get a Weblate API unit's source key, as get_pot_source_keys does.

    The units API returns 'source' as a list of plural forms ([msgid]
    or [msgid, msgid_plural] for a PO unit) and the msgctxt as
    'context' ('' when absent).

    :param unit: one unit object from the Weblate units API
    :returns: (msgctxt, msgid, msgid_plural) tuple
    """
    source = unit.get('source') or ['']
    if isinstance(source, str):
        source = [source]
    return (
        unit.get('context') or '',
        source[0],
        source[1] if len(source) > 1 else '',
    )


def describe_source_key_diff(expected_keys: set, actual_keys: set) -> str:
    """Summarize how a Weblate source set differs from the POT's.

    :param expected_keys: keys from get_pot_source_keys
    :param actual_keys: keys collected via get_unit_source_key
    :returns: short "missing=N, extra=M" description
    """
    return (f"missing={len(expected_keys - actual_keys)}, "
            f"extra={len(actual_keys - expected_keys)}")


# Matches printf-style placeholders, including flag/width/precision
# modifiers (%s, %d, %(name)s, %(name)3d, %.2f, ...), and str.format-
# style placeholders ({}, {0}, {name}, {name!r}, ...). The space flag
# (e.g. "% d") is deliberately excluded from the flag characters below
# - unlike '-'/'+'/'0'/'#', which rarely appear right after a literal
# '%' in ordinary prose, a bare "% " is extremely common in natural
# text (e.g. "100% done"), so including it would misdetect ordinary
# sentences as placeholders far more often than it would catch a
# genuine space-flag placeholder, which is rare in practice.
#
# The trailing conversion character is restricted to Python's actual
# %-formatting conversion types (diouxXeEfFgGcrs%) rather than any
# letter - a bare [a-zA-Z] also matches width-digits-then-letter
# sequences that happen to appear in percent-encoded URLs in source
# text (e.g. "%3A", "%5B" - neither 'A' nor 'B' is a real conversion
# type, so this whitelist stops them from being misread as
# placeholders).
_PRINTF_MODIFIERS = (
    r'[-+0#]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXeEfFgGcrs%]'
)
_PLACEHOLDER_RE = re.compile(
    r'%\([a-zA-Z_][a-zA-Z0-9_]*\)' + _PRINTF_MODIFIERS +
    r'|%' + _PRINTF_MODIFIERS +
    r'|\{[^{}]*\}'
)


def extract_placeholders(text: str) -> list:
    """Extract printf-style/str.format-style placeholder tokens from text.

    %% and {{/}} are the printf/str.format escapes for a literal '%',
    '{', '}' (e.g. "10%%s off" renders as the literal text "10%s off",
    not a %s placeholder) - replaced with a sentinel first so an
    escaped literal isn't mistaken for the start of a real placeholder.

    :param text: string to scan for placeholders
    :returns: list of placeholder substrings found, e.g. ['%s', '{name}']
    """
    if not text:
        return []
    unescaped = text.replace('%%', '\x00').replace(
        '{{', '\x00').replace('}}', '\x00')
    return _PLACEHOLDER_RE.findall(unescaped)


def load_result_events(result_jsonl_path) -> list:
    """Read a result JSON Lines log written by WeblateUtils._save_result.

    Tolerates a truncated final line (e.g. the writer process was
    killed mid-write) by skipping it with a warning instead of
    discarding every event that came before it.

    :param result_jsonl_path: Path to the result JSON Lines file.
    :returns: list of event dicts, in the order they were appended.
    """
    events = []
    if not os.path.exists(result_jsonl_path):
        return events
    with open(result_jsonl_path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(
                    f"[WARN] {result_jsonl_path}:{lineno}: not valid "
                    "JSON - skipped",
                    file=sys.stderr,
                )
    return events


def reduce_result_events(events) -> dict:
    """Fold raw check-result events into one merged entry per
    (project, category, component, locale).

    check_sentence_count and check_sentence_detail each append their
    own event for the same key; later events overwrite the fields
    they carry (mirroring the in-place dict merge the previous
    read-modify-write version of _save_result used to do) so the
    final entry for a key holds the latest value of every field
    either check has ever written for it.

    :param events: iterable of event dicts, in append order (e.g.
        from load_result_events).
    :returns: dict keyed by "project/category/component/locale",
        each value a merged entry with a derived 'status' field.
    """
    results = {}
    for event in events:
        key = (
            f"{event['project']}/{event['category']}/"
            f"{event['component']}/{event['locale']}"
        )
        entry = results.get(key, {
            'project': event['project'],
            'category': event['category'],
            'component': event['component'],
            'locale': event['locale'],
        })
        entry.update({
            k: v for k, v in event.items()
            if k not in ('project', 'category', 'component', 'locale')
        })
        results[key] = entry

    # existence_status/fuzzy_status/placeholder_status/count_status/
    # detail_status/format_status are only set by
    # check_translation_existence/check_fuzzy_untranslated/
    # check_placeholder_consistency/check_sentence_count/
    # check_sentence_detail/check_po_format respectively, when that
    # check actually runs. Deriving "pass" from count_errors/
    # detail_errors being empty would be wrong here: an entry that has
    # never had one of the six checks run against it also has an
    # empty error list for that check, which is not the same as having
    # passed it.
    #
    # A 'fail' is checked first and wins over a missing status:
    # test_accuracy() stops after check-translation-existence or
    # check-sentence-count fails and never calls the checks after it
    # for that locale, so their status stays None even though the
    # locale has conclusively failed - that must report as 'fail', not
    # 'incomplete'.
    #
    # format_status can also be 'warn' (check_po_format found a
    # msgfmt --check issue but doesn't treat it as fatal - see that
    # function's docstring). 'warn' matches neither 'fail' nor None
    # below, so it falls through to 'pass' here same as a clean
    # check - the warning itself isn't lost, aggregate_report.py's
    # _accuracy_rows() surfaces it separately via format_status.
    for entry in results.values():
        existence_status = entry.get('existence_status')
        fuzzy_status = entry.get('fuzzy_status')
        placeholder_status = entry.get('placeholder_status')
        count_status = entry.get('count_status')
        detail_status = entry.get('detail_status')
        format_status = entry.get('format_status')
        statuses = (existence_status, fuzzy_status, placeholder_status,
                    count_status, detail_status, format_status)
        if 'fail' in statuses:
            entry['status'] = 'fail'
        elif None in statuses:
            entry['status'] = 'incomplete'
        else:
            entry['status'] = 'pass'

    return results


class WeblateConfig:
    """Object that stores Weblate configuration.

    Before using this class, you need to set the
    WEBLATE_TOKEN and WEBLATE_URL
    in system environment variables.
    """
    def __init__(self):
        self.token = os.getenv('WEBLATE_TOKEN')
        self.base_url = os.getenv('WEBLATE_URL')


class WeblateUtils:
    """Utilities for managing Weblate features"""
    def __init__(self, config: WeblateConfig, result_json_path: str = None):
        self.config: WeblateConfig = config
        self.result_json_path = result_json_path
        # All of the API calls are prefixed with api/
        self.base_url = urljoin(self.config.base_url, 'api/')

    def _save_result(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        **fields,
    ) -> None:
        """Append one accuracy-check event to result_json_path.

        check_sentence_count and check_sentence_detail each call this
        with their own fields, once per process. No-op when
        result_json_path wasn't given, so JSON persistence stays
        optional for callers that only want console output.

        This deliberately only appends - it does not read the file at
        all. An earlier version read the full accumulated result set
        and rewrote it on every call so that same-key events (e.g. a
        count check and the detail check that follows it) merged into
        one record; that made total I/O grow with the square of the
        number of checks in a run (each of N calls re-read and
        rewrote up to N-1 prior entries). reduce_result_events() now
        does that merge - including the count_status/detail_status ->
        status derivation - at read time instead, from the plain
        event log this writes.

        The write is wrapped in an exclusive fcntl.flock() so that if
        multiple check-sentence-count/-detail processes ever append
        to the same result_json_path concurrently (e.g. a future
        parallelized test_accuracy/test.sh), their lines can't tear
        into each other. Without the lock, two processes' write()
        calls to the same shared file offset can interleave their
        bytes, producing a line that is neither event's JSON - unlike
        a truncated last line (see load_result_events), a torn
        interior line isn't distinguishable from valid JSON that
        happens to be malformed, so it's not safely recoverable after
        the fact and must be prevented at write time instead.
        """
        if not self.result_json_path:
            return

        event = {
            'project': project_name,
            'category': category_name,
            'component': component_name,
            'locale': locale,
            'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            **fields,
        }
        line = json.dumps(event, ensure_ascii=False, sort_keys=True) + '\n'

        result_path = Path(self.result_json_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with open(result_path, 'a', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(line)

    @property
    def _headers(self) -> dict:
        """Get headers for the request

        Create a new dict of headers on each call
        to avoid potential issues.
        This prevents issues where headers modified in one method
        could affect subsequent requests.

        :returns: A dict of headers
        """
        return {
            'Authorization': f'Token {self.config.token}',
        }

    def _with_connection_retry(
        self,
        request_fn: Callable[[], requests.Response],
        error_context: str,
        retry_count: int = 5,
        sleep_time: int = 15,
    ) -> requests.Response:
        """Call request_fn, retrying on connection-level failures.

        request_fn is called fresh on every attempt - needed because
        a file-like request body (e.g. a PO file handle or a zip
        buffer) may be partially consumed by requests before a
        connection-level failure interrupts the send, so it must be
        able to reset itself on each call (mirrors the requirement
        _post_with_retry's build_kwargs has for the same reason).

        Only a RequestException with no response attached is treated
        as connection-level (e.g. connection refused, timeout, DNS
        failure - the server never actually answered) and retried.
        One that carries a response is an HTTP error raised by the
        caller's own raise_for_status(): the server did respond and
        rejected the request, so retrying the exact same request
        cannot help - that propagates immediately, unchanged from the
        behavior before this retry was added.

        :param request_fn: no-arg callable that performs the request
            and returns its Response
        :param error_context: short description of the failed
            request, used in log messages (e.g. "Failed to get:
            <url>")
        :param retry_count: number of attempts before giving up
        :param sleep_time: seconds to sleep between attempts
        :returns: the successful response
        """
        assert retry_count >= 1, "retry_count must allow at least one attempt"
        last_exception = None
        for cnt in range(retry_count):
            try:
                return request_fn()
            except requests.exceptions.RequestException as e:
                if getattr(e, 'response', None) is not None:
                    print(f"[ERROR] {error_context}")
                    print(f"[ERROR] Exception: {e}")
                    print(f"[ERROR] Response details: {e.response.text}")
                    sys.exit(1)

                last_exception = e
                if cnt + 1 == retry_count:
                    break
                print(f"[ERROR] {error_context} (attempt {cnt + 1} "
                      f"of {retry_count}): {e}, retrying")
                time.sleep(sleep_time)

        print(f"[ERROR] {error_context}")
        print(f"[ERROR] Gave up after {retry_count} attempts: "
              f"{last_exception}")
        sys.exit(1)

    def _reject_redirect(self, response: requests.Response) -> None:
        """Raise a clear, immediate error if the server tried to redirect.

        Redirects are never followed for API calls (every request
        below passes allow_redirects=False) - a 3xx response here
        almost always means WEBLATE_URL's scheme/host doesn't match
        the server's canonical one (e.g. http:// where the server
        enforces https://). Silently following it is actively
        harmful: requests demotes POST to GET on a 301/302 redirect,
        so a "create" call turns into a read against a different
        endpoint instead of failing - the resulting confusion showed
        up as an unrelated-looking 404 in create_glossary() and an
        uncaught JSONDecodeError in upload_po_file(), both really
        this same misconfiguration.

        :param response: the response to check
        :raises: requests.exceptions.HTTPError if the response is a
            redirect (3xx)
        """
        if 300 <= response.status_code < 400:
            location = response.headers.get('Location', '<no Location header>')
            raise requests.exceptions.HTTPError(
                f"{response.status_code} redirect to {location} - not "
                "following (check WEBLATE_URL's scheme/host)",
                response=response,
            )

    def _get(self, url, params=None, raise_error=False) -> requests.Response:
        """Get query to request

        Weblate uses a RESTful API, so query parameters
        should be passed in the URL.

        Retries on connection-level failures (connection refused,
        timeout, DNS failure - see _with_connection_retry) since those
        mean the server never responded at all, not that it rejected
        the request.

        :param url: The URL to send the request to
        :param params: The parameters to send in the request
        :param raise_error: (Optional)
            If status code is over 400,
            raise an exception.
        :raises: requests.exceptions.RequestException
            If request is failed. If raise_error is True,
            this exception will be raised.
            When it's raised, the function will exit
            with status code 1.
        :returns: requests.Response
        """
        def do_get():
            response = requests.get(
                url, headers=self._headers, params=params,
                allow_redirects=False)
            self._reject_redirect(response)
            if raise_error:
                response.raise_for_status()
            return response

        return self._with_connection_retry(do_get, f"Failed to get: {url}")

    def _post(
        self,
        url: str,
        data: str = None,
        file: dict = None,
        raise_error: bool = False
    ) -> requests.Response:
        """Post query to request

        When the file is included in the request,
        the file should be passed in the file parameter.

        Retries on connection-level failures (connection refused,
        timeout, DNS failure - see _with_connection_retry) since those
        mean the server never responded at all, not that it rejected
        the request. Any file-like value in `file` is rewound to the
        start before each attempt, since requests reads it to EOF
        while sending - without this, a retry after a connection
        failure mid-send would upload a truncated or empty file.

        :param url: The URL string to send the request to
        :param data: (Optional) The data string to send in the request
        :param file: (Optional) The file dictionary to send in the request
        :param raise_error: (Optional)
            If status code is over 400,
            raise an exception.
        :raises: requests.exceptions.RequestException
            If request is failed. If raise_error is True,
            this exception will be raised.
            When it's raised, the function will exit
            with status code 1.
        :returns: requests.Response
        """
        def do_post():
            # The requests.post automatically set the Content-Type
            # depending on the post type.
            if file:
                for value in file.values():
                    fileobj = value[1] if isinstance(value, tuple) else value
                    if hasattr(fileobj, 'seek'):
                        fileobj.seek(0)
                response = requests.post(
                    url, data=data, files=file, headers=self._headers,
                    allow_redirects=False)
            else:
                response = requests.post(
                    url, json=data, headers=self._headers,
                    allow_redirects=False)

            self._reject_redirect(response)
            if raise_error:
                response.raise_for_status()

            return response

        return self._with_connection_retry(do_post, f"Failed to post: {url}")

    def _patch(self, url: str, data: dict) -> requests.Response:
        """PATCH a JSON body, retrying connection-level failures.

        See _post for the redirect and retry behavior.

        :param url: The URL string to send the request to
        :param data: The JSON-serializable body
        :returns: requests.Response
        """
        def do_patch():
            response = requests.patch(
                url, json=data, headers=self._headers,
                allow_redirects=False)
            self._reject_redirect(response)
            return response

        return self._with_connection_retry(
            do_patch, f"Failed to patch: {url}")

    def _retry_on_status(
        self,
        perform_request: Callable[[], requests.Response],
        success: Callable[[requests.Response], bool],
        action: str,
        retry_count: int = 3,
        sleep_time: int = 15,
    ) -> requests.Response:
        """Shared retry loop for a status-code-based transient failure

        Retries up to retry_count times when the response fails
        `success` but its status is retryable (see
        is_retryable_status - 5xx, 423 repository-locked, 429 rate
        limited, or any non-4xx that still didn't count as success).
        A genuine 4xx rejection, or exhausting all retries, exits the
        process - callers rely on this instead of checking a return
        value. Shared by _post_with_retry (the create/upload POSTs)
        and _get_with_retry (the existence-check GETs in
        create_component/create_translation) so the retry/status
        logic and log format only live in one place.

        :param perform_request: no-arg callable that performs one
            attempt and returns its Response - called fresh on every
            attempt, so a caller whose request body is consumed on
            send (e.g. a file-like POST body) can rebuild/re-seek it
            each time
        :param success: predicate(response) -> True if this attempt
            should be treated as successful
        :param action: short label for this operation, used in log
            and error messages (e.g. "Create component")
        :returns: the successful response
        """
        assert retry_count >= 1, "retry_count must allow at least one attempt"
        for cnt in range(retry_count):
            response = perform_request()

            if success(response):
                return response

            if not is_retryable_status(response.status_code):
                print(f"[ERROR] {action} rejected "
                      f"({response.status_code}), not retrying: "
                      f"{response.text}")
                sys.exit(1)

            if cnt + 1 == retry_count:
                break

            print(f"[ERROR] {action} attempt {cnt + 1} failed "
                  f"({response.status_code}), retrying: "
                  f"{response.text}")
            time.sleep(sleep_time)

        print(f"[ERROR] {action} failed after {retry_count} attempts "
              f"({response.status_code}): {response.text}")
        sys.exit(1)

    def _post_with_retry(
        self,
        url: str,
        success: Callable[[requests.Response], bool],
        build_kwargs: Callable[[], dict],
        action: str,
        retry_count: int = 3,
        sleep_time: int = 15,
    ) -> requests.Response:
        """POST with retry for transient failures

        See _retry_on_status for the retry/status-code semantics.

        :param url: request URL
        :param success: predicate(response) -> True if this attempt
            should be treated as successful
        :param build_kwargs: called fresh before every attempt to
            build this attempt's `data`/`file` kwargs for `_post` -
            needed because a file-like request body (e.g. a zip
            buffer) is consumed once sent, so callers must rebuild or
            re-seek it for each retry
        :param action: short label for this operation, used in log
            and error messages (e.g. "Create component")
        :returns: the successful response
        """
        return self._retry_on_status(
            perform_request=lambda: self._post(url=url, **build_kwargs()),
            success=success,
            action=action,
            retry_count=retry_count,
            sleep_time=sleep_time,
        )

    def _get_with_retry(
        self,
        url: str,
        success: Callable[[requests.Response], bool],
        action: str,
        retry_count: int = 3,
        sleep_time: int = 15,
    ) -> requests.Response:
        """GET with retry for transient failures

        See _retry_on_status for the retry/status-code semantics.
        Used for the existence-check GET in create_component()/
        create_translation(): a transient 5xx there is a normal
        Response (not a RequestException, so _get()'s own
        connection-level retry never sees it), and previously had no
        retry at all - the first non-200/404 status exited the
        process immediately.

        :param url: request URL
        :param success: predicate(response) -> True if this attempt
            should be treated as successful (e.g. status in (200,
            404), both meaningful terminal outcomes for an existence
            check rather than failures)
        :param action: short label for this operation, used in log
            and error messages (e.g. "Check component existence")
        :returns: the response from the successful attempt
        """
        return self._retry_on_status(
            perform_request=lambda: self._get(url),
            success=success,
            action=action,
            retry_count=retry_count,
            sleep_time=sleep_time,
        )

    def _wait_for_translation_source_units(
        self,
        url: str,
        locale: str,
        expected_total: int = None,
        retry_count: int = 60,
        sleep_time: int = 5,
    ) -> None:
        """Wait until Weblate has populated a translation's source units.

        A component or translation creation request can finish before
        Weblate has populated its source units. Poll the translation
        endpoint until it reports a usable total. If expected_total is
        given, the reported total must match it exactly; otherwise any
        positive total is considered ready.

        :param url: translation API URL to poll
        :param locale: locale label used in log and error messages
        :param expected_total: exact source unit count to wait for, or
            None to accept any positive count
        :param retry_count: number of status checks before giving up
        :param sleep_time: seconds to sleep between status checks
        :returns: None
        """
        assert retry_count >= 1, "retry_count must allow at least one attempt"
        last_detail = "no response"

        for cnt in range(retry_count):
            response = self._get(url)
            total = None
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    print(f"[ERROR] Invalid JSON while waiting for "
                          f"translation {locale}: {e}")
                    sys.exit(1)

                total = data.get('total') if isinstance(data, dict) else None
                if not isinstance(total, int):
                    print(f"[ERROR] Invalid translation response for "
                          f"{locale}: {response.text}")
                    sys.exit(1)

            if expected_total is None:
                is_ready = isinstance(total, int) and total > 0
            else:
                is_ready = total == expected_total
            if is_ready:
                print(f"[INFO] Translation ready: {locale} "
                      f"({total} source strings)")
                return

            if total is not None:
                last_detail = f"total={total}"
            else:
                last_detail = f"HTTP {response.status_code}: {response.text}"

            if (response.status_code not in (200, 404)
                    and not is_retryable_status(response.status_code)):
                print(f"[ERROR] Failed while waiting for translation "
                      f"{locale}: {last_detail}")
                sys.exit(1)

            if cnt + 1 < retry_count:
                print(f"[INFO] Waiting for translation: {locale} "
                      f"({last_detail})")
                time.sleep(sleep_time)

        print(f"[ERROR] Timed out waiting for translation {locale} after "
              f"{retry_count} attempts: {last_detail}")
        sys.exit(1)

    def _wait_for_translation_plural_ready(
        self,
        translation_url: str,
        locale: str,
        retry_count: int = 60,
        sleep_time: int = 5,
    ) -> None:
        """Wait until every has:plural unit has full target slots.

        Weblate populates a translation's units asynchronously (see
        _wait_for_translation_source_units), and that wait only
        checks the *number* of source units, not whether each
        plural-capable unit's target array has already reached the
        language's full plural count. A translation can have several
        plural-capable units, so this walks every page of the
        has:plural query instead of looking at a single one -
        checking only one leaves the rest free to be silently and
        permanently dropped by method='translate' if they're still
        mid-creation when the upload happens. Call only when the
        caller already knows (from the po file about to be uploaded)
        that this translation has at least one plural entry -
        otherwise a component with no plural strings would never
        find one and would spin for the entire retry budget.

        :param translation_url: translation API URL (already known to
            exist by the time this is called)
        :param locale: locale label used in log and error messages
        :param retry_count: number of status checks before giving up
        :param sleep_time: seconds to sleep between status checks
        :returns: None
        """
        assert retry_count >= 1, "retry_count must allow at least one attempt"

        response = self._get_with_retry(
            translation_url,
            success=lambda r: r.status_code == 200,
            action='Get translation for plural readiness check',
        )
        nplurals = response.json()['language']['plural']['number']
        if nplurals <= 1:
            return

        units_url = urljoin(
            translation_url, 'units/?' + urlencode({'q': 'has:plural'}))
        last_detail = "no plural unit found yet"

        for cnt in range(retry_count):
            checked = 0
            all_ready = True
            page_url = units_url

            while page_url:
                response = self._get(page_url)
                if response.status_code != 200:
                    if not is_retryable_status(response.status_code):
                        print(f"[ERROR] Failed while waiting for plural "
                              f"slots {locale}: HTTP "
                              f"{response.status_code}: {response.text}")
                        sys.exit(1)
                    last_detail = (
                        f"HTTP {response.status_code}: {response.text}")
                    all_ready = False
                    break

                data = response.json()
                for unit in data.get('results', []):
                    checked += 1
                    target_len = len(unit.get('target', []))
                    if target_len != nplurals:
                        all_ready = False
                        last_detail = (
                            f"unit {unit.get('id', '?')} has "
                            f"{target_len}/{nplurals} slots")
                        break
                if not all_ready:
                    break
                page_url = self._next_page_url(data)

            if all_ready and checked > 0:
                print(f"[INFO] Plural slots ready: {locale} "
                      f"({checked} plural unit(s), {nplurals} slots each)")
                return

            if cnt + 1 < retry_count:
                print(f"[INFO] Waiting for plural slots: {locale} "
                      f"({last_detail})")
                time.sleep(sleep_time)

        print(f"[ERROR] Timed out waiting for plural slots {locale} after "
              f"{retry_count} attempts: {last_detail}")
        sys.exit(1)

    def _component_api_path(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
    ) -> str:
        """Get the '<project>/<category>%252F<component>' API path part."""
        return (f'{sanitize_slug(project_name)}/'
                f'{sanitize_slug(category_name)}%252F'
                f'{sanitize_slug(component_name)}')

    def _next_page_url(self, data: dict):
        """Get a paginated response's next page URL on WEBLATE_URL's host.

        Weblate builds 'next' from what it thinks its own URL is, which
        behind a TLS-terminating proxy can be http:// even though the
        API is served over https:// (seen on weblate.printf.kr). Every
        request here refuses redirects (see _reject_redirect), so
        following that URL as-is fails on the 301 to https://. Only its
        path and query are kept; scheme and host come from WEBLATE_URL.

        :param data: decoded JSON body of a paginated list response
        :returns: next page URL, or None on the last page
        """
        next_url = data.get('next')
        if not next_url:
            return None
        base = urlsplit(self.base_url)
        parts = urlsplit(next_url)
        return urlunsplit(
            (base.scheme, base.netloc, parts.path, parts.query, ''))

    def _get_unit_count(self, translation_url: str):
        """Get a translation's current unit count from the units API.

        Used instead of the translation's 'total': that comes from
        cached statistics, which Weblate only recalculates once the
        whole background re-parse of a component has finished, so it
        can lag the actual units by many minutes after a source update.

        :param translation_url: translation API URL
        :returns: (unit count or None, short detail for logging); None
            when the translation isn't there yet (404) or the request
            failed transiently - exits on a non-retryable failure
        """
        response = self._get(
            urljoin(translation_url, 'units/?' + urlencode({'page_size': 1})))
        if response.status_code == 200:
            return response.json().get('count'), ''
        if (response.status_code != 404
                and not is_retryable_status(response.status_code)):
            print(f"[ERROR] Failed to count units: {translation_url}: "
                  f"HTTP {response.status_code}: {response.text}")
            sys.exit(1)
        return None, f"HTTP {response.status_code}: {response.text}"

    def _get_all_pages(self, url: str, action: str) -> list:
        """GET every page of a paginated Weblate list endpoint.

        Each page is fetched with _get_with_retry, so a transient
        failure is retried and a non-retryable one exits the process.

        :param url: first page URL (may carry its own query string)
        :param action: short label used in log and error messages
        :returns: concatenated 'results' of every page
        """
        results = []
        page_url = url
        while page_url:
            response = self._get_with_retry(
                page_url,
                success=lambda r: r.status_code == 200,
                action=action,
            )
            data = response.json()
            results.extend(data.get('results', []))
            page_url = self._next_page_url(data)
        return results

    def _get_translation_source_keys(self, translation_url: str) -> tuple:
        """Get the source key set of every unit in one translation.

        :param translation_url: translation API URL
        :returns: (set of source keys, number of units listed) - the
            two differ only if Weblate listed the same key twice
        """
        units_url = urljoin(
            translation_url, 'units/?' + urlencode({'page_size': 1000}))
        units = self._get_all_pages(units_url, 'List translation units')
        return {get_unit_source_key(unit) for unit in units}, len(units)

    def _wait_for_source_keys(
        self,
        translation_url: str,
        label: str,
        expected_keys: set,
        retry_count: int = 180,
        sleep_time: int = 5,
    ) -> None:
        """Wait until a translation's units match the POT's source set.

        Weblate (re)parses component files in a background task, so
        neither a component creation nor a source upload response
        means the new source set is visible yet. The cheap unit count
        (see _get_unit_count) is polled first; only once it equals the
        expected count is the full unit list fetched and compared as a
        set - a count match alone would also accept the old source set
        when strings were replaced one-for-one.

        :param translation_url: translation API URL to poll
        :param label: label used in log and error messages
        :param expected_keys: keys from get_pot_source_keys
        :param retry_count: number of status checks before giving up
        :param sleep_time: seconds to sleep between status checks
        :returns: None
        """
        assert retry_count >= 1, "retry_count must allow at least one attempt"
        expected_total = len(expected_keys)
        last_detail = "no response"

        for cnt in range(retry_count):
            count, count_detail = self._get_unit_count(translation_url)
            if count is None:
                last_detail = count_detail
            elif count == expected_total:
                actual_keys, unit_count = (
                    self._get_translation_source_keys(translation_url))
                if (actual_keys == expected_keys
                        and unit_count == expected_total):
                    print(f"[INFO] Source strings match POT: {label} "
                          f"({expected_total} source strings)")
                    return
                diff = describe_source_key_diff(expected_keys, actual_keys)
                last_detail = f"units={count}, {diff}"
            else:
                last_detail = f"units={count}, expected={expected_total}"

            if cnt + 1 < retry_count:
                print(f"[INFO] Waiting for source strings: {label} "
                      f"({last_detail})")
                time.sleep(sleep_time)

        print(f"[ERROR] Timed out waiting for source strings {label} after "
              f"{retry_count} attempts: {last_detail}")
        sys.exit(1)

    def _upload_component_source(
        self,
        source_translation_url: str,
        pot_path: str,
    ) -> None:
        """Replace an existing component's source strings with a POT.

        Uses Weblate's 'source' upload method on the source language
        (en_US) translation - the supported way to update a bilingual
        component's source strings. Weblate runs msgmerge with the
        uploaded POT against every language's PO file (exact matches
        keep their msgstr, plural forms and fuzzy flag; strings no
        longer in the POT become obsolete; new ones are added
        untranslated, or as a fuzzy guess when msgmerge's fuzzy
        matching finds a similar old string) and replaces the new_base
        POT, so languages added later start from the new POT too. No
        language's translations are replaced wholesale.

        The response only means the files were merged and committed -
        the database re-parse runs as a background task, so callers
        must wait for it (see _wait_for_source_keys).

        :param source_translation_url: en_US translation API URL
        :param pot_path: path to the new POT file
        """
        url = urljoin(source_translation_url, 'file/')
        print(f"[INFO] Updating source strings from POT: {pot_path}")
        with open(pot_path, 'rb') as f:
            self._post_with_retry(
                url=url,
                success=lambda r: r.status_code == 200,
                # _post()'s do_post rewinds `f` before every send.
                build_kwargs=lambda: {
                    'file': {'file': f},
                    'data': {'method': 'source'},
                },
                action='Update source strings',
            )

    def _check_translation_source(
        self,
        translation_url: str,
        expected_keys: set,
    ) -> str:
        """Compare one translation's current source set with the POT's.

        One-shot (no waiting). The full unit list is only fetched when
        the cheap unit count already equals the expected count - a
        count mismatch is enough to know the set differs.

        :param translation_url: translation API URL
        :param expected_keys: keys from get_pot_source_keys
        :returns: '' if the source set matches, otherwise a short
            description of the difference
        """
        count, count_detail = self._get_unit_count(translation_url)
        if count is None:
            return count_detail
        if count != len(expected_keys):
            return f"units={count}, expected={len(expected_keys)}"
        actual_keys, unit_count = self._get_translation_source_keys(
            translation_url)
        if actual_keys == expected_keys and unit_count == len(expected_keys):
            return ''
        return describe_source_key_diff(expected_keys, actual_keys)

    def _list_language_translation_urls(self, component_path: str) -> dict:
        """Map every non-source language code of a component to its URL.

        :param component_path: see _component_api_path
        :returns: dict of language code -> translation API URL
        """
        list_url = urljoin(
            self.base_url,
            f'components/{component_path}/translations/?'
            + urlencode({'page_size': 1000}))
        translations = self._get_all_pages(
            list_url, 'List component translations')
        return {
            t['language_code']: urljoin(
                self.base_url,
                f"translations/{component_path}/{t['language_code']}/")
            for t in translations if not t.get('is_source')
        }

    def _sync_existing_component_source(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        pot_path: str,
        expected_keys: set,
    ) -> None:
        """Bring an existing component's source strings in line with a POT.

        Every translation - en_US and each existing language - is
        checked once against the POT's source set, not just en_US:
        Weblate parses the source (POT) file before the language PO
        files, so a re-run after an interrupted or slow source update
        can find en_US already current while a language still has the
        same number of old strings. Uploading that language's PO would
        make 'translate' report the new strings as not_found and drop
        them.

        If everything matches (an idempotent re-run) nothing is sent.
        Otherwise the POT is uploaded with method=source - safe to
        repeat, since Weblate re-merges only files that still differ
        from the POT and commits/re-parses nothing when none do - and
        en_US plus each language that differed is waited on until its
        source set matches. A language whose file is already merged
        but whose database copy never catches up can't be fixed via
        this API, so the wait times out and the process exits; the
        caller then skips every PO upload for this component.
        """
        component_path = self._component_api_path(
            project_name, category_name, component_name)
        source_url = urljoin(
            self.base_url, f'translations/{component_path}/en_US/')

        mismatched = {}
        source_detail = self._check_translation_source(
            source_url, expected_keys)
        if source_detail:
            mismatched['source en_US'] = (source_url, source_detail)
        for language_code, translation_url in (
                self._list_language_translation_urls(component_path).items()):
            detail = self._check_translation_source(
                translation_url, expected_keys)
            if detail:
                mismatched[language_code] = (translation_url, detail)

        if not mismatched:
            print("[INFO] Source strings already match POT in every "
                  f"language ({len(expected_keys)} source strings)")
            return

        for label, (_, detail) in mismatched.items():
            print(f"[INFO] Source strings differ from POT: {label} "
                  f"({detail})")
        self._upload_component_source(source_url, pot_path)
        # en_US is always re-checked: the upload replaces new_base,
        # and this is a single cheap check when it already matched.
        mismatched.setdefault('source en_US', (source_url, ''))
        for label, (translation_url, _) in mismatched.items():
            self._wait_for_source_keys(translation_url, label, expected_keys)
        print("[INFO] Source strings updated: ", component_name)

    def _build_category_list(self, project_name: str) -> dict:
        """Get category list for the project

        :param project_name: The name of the project
        :returns: A dictionary of categories
            Each key is a category name and
            the value is a dictionary representing a category ID.
        """
        path = f'projects/{sanitize_slug(project_name)}/categories/'
        url = urljoin(self.base_url, path)
        response = self._get(url, raise_error=True)

        # The dictionary is set as defaultdict(dict)
        # to clearly indicate the value is a category id.
        category_dict = defaultdict(dict)
        for category in response.json()['results']:
            category_dict[category['name']] = {
                'id': category['id'],
            }
        return category_dict

    def _get_category_id(self, project_name: str, category_name: str) -> int:
        """Get category id for the project

        In weblate, referencing a category requires
        using its unique category ID.

        :param project_name: The name of the project
        :param category_name: The name of the category
        :returns: The id of the category
        """
        category_dict = self._build_category_list(project_name)
        if not category_dict.get(get_version_name(category_name)):
            print("[ERROR] Category does not exist: ", category_name)
            sys.exit(1)

        return category_dict[get_version_name(category_name)]['id']

    def create_project(self, project_name: str) -> None:
        """Create a new project

        If the project does not exist, create a new one.

        :param project_name: The name of the project
        """

        path = f'projects/{sanitize_slug(project_name)}/'
        url = urljoin(self.base_url, path)
        response = self._get(url)
        if response.status_code == 200:
            print("[INFO] Project already exists: ", project_name)
        elif response.status_code == 404:
            print("[INFO] Project does not exist: ", project_name)

            path = 'projects/'
            url = urljoin(self.base_url, path)
            data = {
                'name': project_name,
                'slug': sanitize_slug(project_name),
                'web': f'https://opendev.org/openstack/{project_name}',
            }
            _ = self._post(url=url, data=data, raise_error=True)

            print("[INFO] Project created: ", project_name)
        else:
            print("[ERROR] Failed to create project: ",
                  json.dumps(response.json()))

    def create_category(self, project_name: str, category_name: str) -> None:
        """Create a new category to specify the version.

        If the category does not exist, create a new one.

        :param project_name: The name of the project
        :param category_name: The name of the category
        """

        category_dict = self._build_category_list(project_name)
        is_exists = bool(category_dict.get(get_version_name(category_name)))
        if not is_exists:
            print("[INFO] Category does not exist: ", category_name)

            path = 'categories/'
            url = urljoin(self.base_url, path)
            data = {
                'name': get_version_name(category_name),
                'slug': sanitize_slug(category_name),
                'project': urljoin(
                    self.base_url, f'projects/{sanitize_slug(project_name)}/'),
            }
            _ = self._post(url=url, data=data, raise_error=True)

            print("[INFO] Category created: ", category_name)
        else:
            print("[INFO] Category already exists: ", category_name)

    def create_glossary(self, project_name: str) -> None:
        """Create a new glossary component

        If the glossary component does not exist, create a new one.
        In glossary component, the filemask and file_format is tbx.

        :param project_name: The name of the project
        """
        path = (f'components/{sanitize_slug(project_name)}/'
                f'glossary/')
        url = urljoin(self.base_url, path)
        response = self._get(url)
        if response.status_code == 200:
            print("[INFO] Glossary Component already exists.")
        elif response.status_code == 404:
            print("[INFO] Glossary Component does not exist")

            path = f'projects/{sanitize_slug(project_name)}/components/'
            url = urljoin(self.base_url, path)
            data = {
                'name': 'glossary',
                'slug': 'glossary',
                'file_format': 'tbx',
                'filemask': '*.tbx',
                'repo': 'local:',
                'vcs': 'local',
                'source_language': 'en_US',
                "is_glossary": True,
            }
            create_response = self._post(url=url, data=data)
            if create_response.status_code == 404:
                # The project itself isn't visible at this endpoint
                # (e.g. create-project silently no-op'd because a
                # misconfigured WEBLATE_URL turned its POST into a
                # GET on redirect). Not fatal on its own - skip the
                # glossary rather than aborting the whole project
                # migration over it.
                print("[INFO] Skipping glossary creation: "
                      f"project not found: {project_name}")
                return
            if create_response.status_code >= 400:
                print("[ERROR] Failed to create glossary: ",
                      json.dumps(create_response.json()))
                sys.exit(1)

            print("[INFO] Glossary created.")
        else:
            print("[ERROR] Failed to create glossary: ",
                  json.dumps(response.json()))
            sys.exit(1)

    def create_component(
            self,
            project_name: str,
            category_name: str,
            component_name: str,
            pot_path: str
    ) -> None:
        """Create a new component, or update an existing one's source

        If the component does not exist, create a new one from the
        POT. If it already exists (a re-run), its source strings are
        compared with the POT's as a (msgctxt, msgid, msgid_plural)
        set and, if they differ, updated in place with a 'source'
        upload - see _sync_existing_component_source. Either way this
        only returns once the source set matches the POT, and exits
        the process otherwise, so the caller never uploads
        translations against a stale source set. Retries up to 3
        times if Weblate could not obtain its internal repository lock
        (423) or rate-limited us (429) - see is_retryable_status.

        :param project_name: The name of the project
        :param category_name: The name of the category
        :param component_name: The name of the component
        :param pot_path: The path to the pot file
        """

        path = (f'components/{sanitize_slug(project_name)}/'
                f'{sanitize_slug(category_name)}%252F'
                f'{sanitize_slug(component_name)}/')
        url = urljoin(self.base_url, path)
        response = self._get_with_retry(
            url,
            success=lambda r: r.status_code in (200, 404),
            action='Check component existence',
        )

        expected_keys = get_pot_source_keys(pot_path)

        if response.status_code == 200:
            print("[INFO] Component already exists: ", component_name)
            self._sync_existing_component_source(
                project_name,
                category_name,
                component_name,
                pot_path,
                expected_keys,
            )
            return

        print("[INFO] Component does not exist: ", component_name)

        path = f'projects/{sanitize_slug(project_name)}/components/'
        url = urljoin(self.base_url, path)
        category_id = self._get_category_id(project_name, category_name)
        category_url = urljoin(
            self.base_url,
            f"categories/{category_id}/")

        # Create a zip file containing the pot file for Weblate
        # component initialization. new_base must match the arcname
        # written below exactly, since Weblate looks for that
        # filename inside the uploaded zip - for suffixed components
        # (e.g. "horizon-django", whose pot file is generated as
        # plain "django.pot") that name differs from
        # f"{component_name}.pot".
        pot_filename = os.path.basename(pot_path)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(
                zip_buf, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(pot_path, pot_filename)
        data = {
            'name': get_component_display_name(component_name),
            'slug': sanitize_slug(component_name),
            'file_format': 'po',
            'filemask': get_filemask(component_name),
            'repo': 'local:',
            'vcs': 'local',
            'source_language': 'en_US',
            'new_base': pot_filename,
            'category': category_url,
        }

        def build_kwargs():
            # _post()'s do_post rewinds every file-like value in
            # `file` before each send, so no explicit seek is needed
            # here - it covers both this loop's retries and _post()'s
            # own internal connection-level retries.
            return {
                'data': data,
                'file': {
                    'zipfile': (
                        f'{component_name}.zip',
                        zip_buf,
                        'application/zip',
                    ),
                },
            }

        self._post_with_retry(
            url=url,
            success=lambda r: r.status_code == 201,
            build_kwargs=build_kwargs,
            action='Create component',
        )
        component_path = self._component_api_path(
            project_name, category_name, component_name)
        source_url = urljoin(
            self.base_url, f'translations/{component_path}/en_US/')
        self._wait_for_source_keys(source_url, 'source en_US', expected_keys)
        print("[INFO] Component created: ", component_name)

    def create_translation(
            self,
            project_name: str,
            category_name: str,
            component_name: str,
            locale: str,
            po_path: str
    ) -> None:
        """Create a new translation

        If the translation does not exist, create a new one. Retries
        up to 3 times if Weblate could not obtain its internal
        repository lock (423) or rate-limited us (429) - see
        is_retryable_status - since those are expected to clear on
        their own shortly (e.g. another write to the same component
        was still in progress).

        _wait_for_translation_source_units() only confirms the
        translation has *some* source units - it says nothing about
        whether a plural-capable unit's target array has already been
        sized to the language's full plural count, or is still a
        shorter, not-yet-finished placeholder. Uploading against a
        not-yet-finished unit silently and permanently drops any
        plural form beyond what existed at that moment (see
        upload_po_file()'s docstring on 'translate' only filling
        existing slots). If po_path has any plural entries, this also
        waits for that to settle before returning - see
        _wait_for_translation_plural_ready().

        :param project_name: The name of the project
        :param category_name: The name of the category
        :param component_name: The name of the component
        :param locale: The locale of the translation
        :param po_path: Path to the po file about to be uploaded for
            this locale - used only to check whether it has any
            plural entries worth waiting on
        """

        locale = sanitize_locale(locale)
        po = polib.pofile(po_path)
        has_plural = any(
            entry.msgid_plural for entry in po if not entry.obsolete)

        path = (f'translations/{sanitize_slug(project_name)}/'
                f'{sanitize_slug(category_name)}%252F'
                f'{sanitize_slug(component_name)}/'
                f'{locale}/')
        translation_url = urljoin(self.base_url, path)
        response = self._get_with_retry(
            translation_url,
            success=lambda r: r.status_code in (200, 404),
            action='Check translation existence',
        )

        if response.status_code == 200:
            self._wait_for_translation_source_units(
                translation_url, locale)
            if has_plural:
                self._wait_for_translation_plural_ready(
                    translation_url, locale)
            print("[INFO] Translation already exists: ", locale)
            return

        path = (f'components/{sanitize_slug(project_name)}/'
                f'{sanitize_slug(category_name)}%252F'
                f'{sanitize_slug(component_name)}/'
                f'translations/')
        create_url = urljoin(self.base_url, path)
        data = {
            'language_code': locale,
        }

        self._post_with_retry(
            url=create_url,
            success=lambda r: r.status_code == 201,
            build_kwargs=lambda: {'data': data},
            action='Create translation',
        )
        self._wait_for_translation_source_units(translation_url, locale)
        if has_plural:
            self._wait_for_translation_plural_ready(translation_url, locale)
        print("[INFO] Translation created: ", locale)

    def _clear_fuzzy_guesses(
        self,
        translation_url: str,
        po: polib.POFile,
        locale: str,
    ) -> None:
        """Empty fuzzy Weblate strings that Zanata has no translation for.

        A source update (see _upload_component_source) runs msgmerge
        with fuzzy matching, which fills new or changed source strings
        with the translation of a similar old string, marked fuzzy -
        e.g. "29.0.0" gets "9.0.0". When Zanata has no translation for
        that string, the 'translate' upload has nothing to overwrite
        the guess with, so it would stay on Weblate although Zanata
        never had it. Only strings that are fuzzy (needs editing) with
        content on Weblate and fully empty in this Zanata PO are
        emptied; translated/approved strings are never touched, and
        strings Zanata does translate are left for the upload itself,
        which overwrites fuzzy strings.

        :param translation_url: translation API URL for this locale
        :param po: the parsed Zanata PO file about to be uploaded
        :param locale: locale label used in log messages
        """
        untranslated_keys = {
            (entry.msgctxt or '', entry.msgid, entry.msgid_plural or '')
            for entry in po if not entry.obsolete
            and not entry.msgstr
            and not any(entry.msgstr_plural.values())
        }
        if not untranslated_keys:
            return

        units_url = urljoin(
            translation_url,
            'units/?' + urlencode(
                {'q': 'state:needs-editing', 'page_size': 1000}))
        units = self._get_all_pages(units_url, 'List fuzzy units')
        to_clear = [
            unit for unit in units
            if 10 <= unit.get('state', 0) < 20
            and any(unit.get('target') or [])
            and get_unit_source_key(unit) in untranslated_keys
        ]
        for unit in to_clear:
            url = urljoin(self.base_url, f"units/{unit['id']}/")
            self._retry_on_status(
                perform_request=lambda url=url, unit=unit: self._patch(
                    url,
                    {'state': 0, 'target': [''] * len(unit['target'])},
                ),
                success=lambda r: r.status_code == 200,
                action='Clear fuzzy guess',
            )
        if to_clear:
            print(f"[INFO] Cleared {len(to_clear)} fuzzy guess(es) not "
                  f"translated in source: {locale}")

    def upload_po_file(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        po_path: str
    ) -> bool:
        """Upload a translation po file

        Uses Weblate's 'translate' upload method rather than
        'replace': every (component, locale) this is called for was
        just created empty by create_translation(), and 'translate'
        fills in translations from the uploaded file without the
        wholesale file replacement 'replace' does - appropriate for
        populating a fresh, empty translation during migration. It
        also avoids a real failure mode 'replace' hits: po files can
        legitimately contain two distinct msgids that differ only by
        trailing whitespace (e.g. the same source string used with
        and without a trailing space in different templates), which
        Weblate's id_hash treats as identical - 'replace' tries to
        insert both as separate units and hits a DB unique-constraint
        violation, while 'translate' only fills matching existing
        units and silently ignores the second one.

        Retries up to 3 times for anything other than success (200
        with result=true) or a non-retryable rejection (see
        is_retryable_status - most 4xx codes mean the server rejected
        this exact request, so an identical retry cannot help and
        those exit immediately instead of spending the retry budget).

        If po_path has no translated content at all (every entry's
        msgstr/msgstr_plural is empty - a locale Zanata never had any
        translations for, as opposed to one that lost them), Weblate's
        'translate' upload correctly finds nothing to accept and
        replies 200 with result=false and accepted=0. That is not a
        transient failure - retrying an unchanged empty file cannot
        turn it into result=true - so it would otherwise burn the
        full retry budget and get reported as a failed locale even
        though there was never anything to migrate. Detected up front
        and skipped without a request, rather than relying on
        is_retryable_status to special-case it after the fact, since
        that predicate is shared with other callers where a 200 is
        always a real success/failure signal. The caller (main()) is
        told about this via the return value, rather than this case
        being indistinguishable from a real upload - see main()'s
        exit-code mapping and create_weblate_components.sh's handling
        of it, which reports it as its own "no translation in
        source" tree leaf instead of silently folding it into the
        success count (the same reasoning create_weblate_components.sh
        already applies to a component with zero translation files).

        A related but distinct case: a locale that a *previous* run
        already fully uploaded. Re-uploading the same content makes
        Weblate correctly report result=false with accepted=0 too -
        there is nothing *new* to accept - but this time skipped
        equals the file's translated-entry count and not_found is 0,
        i.e. every translated string matched an existing unit and none
        needed changing. That combination can only mean the content
        already matches what's on Weblate (confirmed against a real
        run: a locale failing this way had a byte-identical Weblate
        translation already, from an earlier successful attempt at
        this same migration), so it's treated as success rather than
        retried - an identical retry would report the same thing every
        time. This one prints its own message but still returns True
        (unlike the empty-source case above): the translation is
        genuinely, correctly present on Weblate, so counting it as a
        real success is not misleading the way counting an empty
        upload as one would be.

        :param project_name: The name of the project
        :param category_name: The name of the category
        :param component_name: The name of the component
        :param locale: The locale of the translation
        :param po_path: The path to the po file
        :returns: True if the translation is present on Weblate
            (either just uploaded, or already there from an earlier
            run), False if po_path had no translated content and
            nothing was sent
        """

        locale = sanitize_locale(locale)
        po = polib.pofile(po_path)
        translated_count = sum(
            1 for entry in po if not entry.obsolete
            and (entry.msgstr or any(entry.msgstr_plural.values())))

        # Before the early return below: a locale with no translation
        # at all in Zanata can still have guesses to clear.
        component_path = self._component_api_path(
            project_name, category_name, component_name)
        self._clear_fuzzy_guesses(
            urljoin(self.base_url,
                    f'translations/{component_path}/{locale}/'),
            po,
            locale,
        )

        if translated_count == 0:
            print("[INFO] No translation exists in source, skipping "
                  f"upload: {component_name} {locale}")
            return False

        path = (f'translations/{sanitize_slug(project_name)}/'
                f'{sanitize_slug(category_name)}%252F'
                f'{sanitize_slug(component_name)}/'
                f'{locale}/file/')
        url = urljoin(self.base_url, path)
        print(f"[INFO] Uploading PO file: {po_path}")

        def already_up_to_date(body: dict) -> bool:
            return (
                body.get('not_found') == 0
                and body.get('accepted') == 0
                and body.get('skipped') == translated_count)

        with open(po_path, 'rb') as f:
            def build_kwargs():
                # _post()'s do_post rewinds every file-like value in
                # `file` before each send, so no explicit seek is
                # needed here - it covers both this loop's retries
                # and _post()'s own internal connection-level retries.
                return {
                    'file': {'file': f},
                    'data': {'method': 'translate', 'fuzzy': 'process'},
                }

            def upload_succeeded(r: requests.Response) -> bool:
                if r.status_code != 200:
                    return False
                body = r.json()
                return body['result'] is True or already_up_to_date(body)

            response = self._post_with_retry(
                url=url,
                success=upload_succeeded,
                build_kwargs=build_kwargs,
                action='Upload',
            )
        if response.json()['result'] is True:
            print("[INFO] Upload successful: ", component_name, locale)
        else:
            print("[INFO] Already up to date, nothing new to upload: ",
                  component_name, locale)
        return True

    def download_translation_file(
        self,
        project_name: str,
        po_path: str,
    ) -> None:
        """Download translation file from Weblate

        :param project_name: Name of the project
        :param po_path: Path to the po file to save
        """
        path = (f'projects/{sanitize_slug(project_name)}/file/')
        url = urljoin(self.base_url, path)
        response = self._get(url, raise_error=True)
        if response.status_code == 200:
            with open(po_path, 'wb') as f:
                f.write(response.content)
            print(
                "[INFO] Successfully downloaded translation "
                f"file from: {url}"
            )
            print(f"[INFO] Saved to: {po_path}")
        else:
            print(
                "[ERROR] Failed to download translation file: "
                f"{response.status_code}"
            )
            sys.exit(1)

        return None

    def check_translation_existence(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        zanata_po_path: str,
        weblate_po_path: str,
    ) -> bool:
        """Check that the Zanata and Weblate PO files actually exist.

        The accuracy-check loop iterates locales driven by which
        Zanata PO files exist locally. If a component - or just one
        locale of it - was never created in Weblate, its PO file
        never lands in the downloaded/extracted Weblate translation
        tree. Without this check, that absence only ever surfaced as
        an uncaught FileNotFoundError deep inside polib.pofile() in
        check_sentence_count, indistinguishable from any other
        unexpected parse/IO failure. This promotes that absence to
        its own explicit, recorded check, run before count/detail so
        those checks are never attempted against a file that isn't
        there.

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Name of the locale
        :param zanata_po_path: Path to the zanata po file
        :param weblate_po_path: Path to the weblate po file
        :returns: True if both files exist, False otherwise
        """
        missing = []
        if not os.path.isfile(zanata_po_path):
            missing.append(f"zanata:{zanata_po_path}")
        if not os.path.isfile(weblate_po_path):
            missing.append(f"weblate:{weblate_po_path}")

        if missing:
            error_msg = (
                "Component/locale does not exist - missing PO "
                "file(s): " + ", ".join(missing)
            )
            print(f"[ERROR] {error_msg}")
            self._save_result(
                project_name, category_name, component_name, locale,
                existence_errors=[error_msg],
                existence_status='fail',
                # None of the later checks can run this pass. Reset
                # every field they'd otherwise set explicitly so a
                # stale pass/fail left over from an earlier successful
                # run of this same key doesn't linger next to today's
                # existence failure.
                fuzzy_status=None,
                fuzzy_zanata=None,
                fuzzy_weblate=None,
                untranslated_zanata=None,
                untranslated_weblate=None,
                fuzzy_increase=None,
                untranslated_increase=None,
                fuzzy_errors=[],
                placeholder_status=None,
                placeholder_checked=None,
                placeholder_mismatches=None,
                placeholder_errors=[],
                count_status=None,
                total_zanata=None,
                total_weblate=None,
                translated_zanata=None,
                translated_weblate=None,
                count_errors=[],
                detail_status=None,
                total_entries=None,
                mismatch_count=None,
                string_mismatch_count=None,
                plural_mismatch_count=None,
                missing_count=None,
                extra_count=None,
                detail_errors=[],
                format_status=None,
                format_errors=[],
            )
            return False

        print(
            f"[INFO] ✓ Component/locale exists in both Zanata and "
            f"Weblate: {locale}"
        )
        self._save_result(
            project_name, category_name, component_name, locale,
            existence_errors=[],
            existence_status='pass',
        )
        return True

    def check_fuzzy_untranslated(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        zanata_po_path: str,
        weblate_po_path: str,
    ) -> bool:
        """Classify why the translated count changed after migration.

        check_sentence_count fails outright on any translated-count
        difference between Zanata and Weblate, without saying whether
        that difference is benign (content preserved, just re-flagged
        fuzzy for review) or a real loss (content actually emptied
        out). This runs before check_sentence_count so that
        classification - not gated by check_sentence_count's own
        pass/fail - is always recorded to help a human triage a count
        failure. It does not change check_sentence_count's own
        equality check, which stays as strict as before.

        polib.POEntry.translated() excludes both obsolete and fuzzy
        entries, and POFile.untranslated_entries() excludes both
        translated and fuzzy entries, so among the non-obsolete
        entries every entry is in exactly one of translated/fuzzy/
        untranslated - counting fuzzy and untranslated directly is
        enough to classify the change without needing the total/
        translated counts check_sentence_count already computes.

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Name of the locale
        :param zanata_po_path: Path to the zanata po file
        :param weblate_po_path: Path to the weblate po file
        :returns: True unless the untranslated count increased
            (a decrease not explained by fuzzy re-marking alone)
        """
        zanata_po = polib.pofile(zanata_po_path, encoding='utf-8')
        weblate_po = polib.pofile(weblate_po_path, encoding='utf-8')

        zanata_fuzzy = len(zanata_po.fuzzy_entries())
        weblate_fuzzy = len(weblate_po.fuzzy_entries())
        zanata_untranslated = len(zanata_po.untranslated_entries())
        weblate_untranslated = len(weblate_po.untranslated_entries())

        fuzzy_increase = weblate_fuzzy - zanata_fuzzy
        untranslated_increase = weblate_untranslated - zanata_untranslated

        errors = []
        if untranslated_increase > 0:
            error_msg = (
                f"Untranslated count increased by "
                f"{untranslated_increase} (zanata="
                f"{zanata_untranslated} -> weblate="
                f"{weblate_untranslated}) - not explained by fuzzy "
                f"re-marking alone, possible translation loss"
            )
            print(f"[ERROR] {error_msg}")
            errors.append(error_msg)

        fuzzy_ok = untranslated_increase <= 0

        if fuzzy_increase > 0:
            print(
                f"[INFO] Fuzzy count increased by {fuzzy_increase} "
                f"(zanata={zanata_fuzzy} -> weblate={weblate_fuzzy}) "
                f"- content preserved, marked fuzzy for review"
            )

        fuzzy_fields = {
            'fuzzy_zanata': zanata_fuzzy,
            'fuzzy_weblate': weblate_fuzzy,
            'untranslated_zanata': zanata_untranslated,
            'untranslated_weblate': weblate_untranslated,
            'fuzzy_increase': fuzzy_increase,
            'untranslated_increase': untranslated_increase,
            'fuzzy_errors': errors,
        }

        if not fuzzy_ok:
            self._save_result(
                project_name, category_name, component_name, locale,
                fuzzy_status='fail',
                **fuzzy_fields,
                # Placeholder/count/detail/format cannot run this
                # pass. Reset their status explicitly so a stale
                # pass/fail left over from an earlier successful run
                # of this same key doesn't linger next to today's
                # fuzzy failure.
                placeholder_status=None,
                placeholder_checked=None,
                placeholder_mismatches=None,
                placeholder_errors=[],
                count_status=None,
                total_zanata=None,
                total_weblate=None,
                translated_zanata=None,
                translated_weblate=None,
                count_errors=[],
                detail_status=None,
                total_entries=None,
                mismatch_count=None,
                string_mismatch_count=None,
                plural_mismatch_count=None,
                missing_count=None,
                extra_count=None,
                detail_errors=[],
                format_status=None,
                format_errors=[],
            )
            return False

        print(
            "[INFO] ✓ No untranslated increase "
            f"(zanata={zanata_untranslated}, "
            f"weblate={weblate_untranslated})"
        )
        self._save_result(
            project_name, category_name, component_name, locale,
            fuzzy_status='pass',
            **fuzzy_fields,
        )

        return True

    def check_placeholder_consistency(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        zanata_po_path: str,
        weblate_po_path: str,
    ) -> bool:
        """Check that printf/str.format placeholders survive migration.

        check_sentence_detail already flags whether Zanata and Weblate
        msgstr differ, but not why a difference matters. A placeholder
        (%s, %(name)s, {name}, ...) dropped or mangled during
        migration still counts as "translated", but breaks string
        formatting at runtime - a much higher-severity class of
        mismatch than a wording difference. For entries whose source
        (msgid/msgid_plural) contains at least one placeholder, this
        compares the placeholder set actually present in the Zanata
        translation against the one in the Weblate translation and
        fails if they differ, isolating that specific failure mode
        out of check_sentence_detail's generic mismatch signal.

        This deliberately compares Zanata's translation directly to
        Weblate's, not each side to the English source: gettext plural
        rules mean a language can have a different number of plural
        forms than the two (singular/plural) English source strings,
        so there is no reliable way to say which of msgid/msgid_plural
        a given translated form "should" match. Comparing Zanata to
        Weblate at the same plural index sidesteps that ambiguity
        entirely and stays consistent with this project's baseline:
        Zanata is the source of truth Weblate must match, for
        placeholders exactly as for everything else check_sentence_*
        already compares.

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Name of the locale
        :param zanata_po_path: Path to the zanata po file
        :param weblate_po_path: Path to the weblate po file
        :returns: True unless a placeholder-set mismatch was found
        """
        zanata_po = polib.pofile(zanata_po_path, encoding='utf-8')
        weblate_po = polib.pofile(weblate_po_path, encoding='utf-8')

        zanata_entries = [e for e in zanata_po if not e.obsolete]
        weblate_entries = [e for e in weblate_po if not e.obsolete]
        weblate_dict = {
            (entry.msgid, entry.msgctxt): entry for entry in weblate_entries
        }

        checked_count = 0
        errors = []

        for zanata_entry in zanata_entries:
            msgid = zanata_entry.msgid
            msgctxt = zanata_entry.msgctxt
            weblate_entry = weblate_dict.get((msgid, msgctxt))
            # A missing/extra entry is check_sentence_detail's job to
            # report, not this check's.
            if weblate_entry is None:
                continue

            has_placeholder = (
                extract_placeholders(msgid) or
                extract_placeholders(zanata_entry.msgid_plural)
            )
            if not has_placeholder:
                continue

            # Fuzzy/untranslated entries have no finished content to
            # judge placeholder-preservation on - that gap is
            # check_fuzzy_untranslated's and check_sentence_count's
            # job, not this check's.
            if not (zanata_entry.translated() and
                    weblate_entry.translated()):
                continue

            checked_count += 1

            if zanata_entry.msgid_plural:
                common_indices = sorted(
                    zanata_entry.msgstr_plural.keys() &
                    weblate_entry.msgstr_plural.keys()
                )
                if not common_indices:
                    # No overlapping plural-form index to compare at
                    # all (check_sentence_detail separately reports
                    # this as a "Plural form count mismatch"). Without
                    # this, an entry here would silently count as
                    # "checked" with zero placeholder mismatches even
                    # though none of Weblate's plural forms could
                    # actually be verified against Zanata's.
                    error_msg = (
                        f"Placeholder mismatch for msgid: '{msgid}' "
                        f"msgctxt: '{msgctxt}' - no common plural "
                        f"form indices between Zanata "
                        f"({sorted(zanata_entry.msgstr_plural.keys())}) "
                        f"and Weblate "
                        f"({sorted(weblate_entry.msgstr_plural.keys())}) "
                        f"to compare"
                    )
                    print(f"[ERROR] {error_msg}")
                    errors.append(error_msg)
                    continue
                units = [
                    (
                        f'index {index}',
                        sorted(extract_placeholders(
                            zanata_entry.msgstr_plural[index])),
                        sorted(extract_placeholders(
                            weblate_entry.msgstr_plural[index])),
                    )
                    for index in common_indices
                ]
            else:
                units = [(
                    None,
                    sorted(extract_placeholders(zanata_entry.msgstr)),
                    sorted(extract_placeholders(weblate_entry.msgstr)),
                )]

            # Compared as sorted lists, not sets, so that losing one
            # of several repeated occurrences of the same placeholder
            # (e.g. "Copied %s to %s" -> only one %s survives) is
            # still caught - a set comparison would collapse both
            # sides to {'%s'} and miss it.
            for unit_label, zanata_actual, weblate_actual in units:
                if zanata_actual == weblate_actual:
                    continue
                location = f" {unit_label}" if unit_label else ""
                error_msg = (
                    f"Placeholder mismatch for msgid: '{msgid}' "
                    f"msgctxt: '{msgctxt}'{location} - Zanata msgstr "
                    f"placeholders: {zanata_actual} - Weblate "
                    f"msgstr placeholders: {weblate_actual}"
                )
                print(f"[ERROR] {error_msg}")
                errors.append(error_msg)

        placeholder_fields = {
            'placeholder_checked': checked_count,
            'placeholder_mismatches': len(errors),
            'placeholder_errors': errors,
        }

        if errors:
            # One summary line with the total count, printed last -
            # this (not one of the per-entry lines above) is what
            # extract_status_reason() (common/pretty-printer.sh) sees,
            # since it only captures the last printed line. Without
            # this, the tree would show one arbitrary example msgid
            # instead of how many mismatches there were. See
            # failure-reason-categorization/plan.md.
            print(
                "[ERROR] Placeholder consistency check completed "
                f"with issues: mismatches={len(errors)}"
            )
            self._save_result(
                project_name, category_name, component_name, locale,
                placeholder_status='fail',
                **placeholder_fields,
                # Count/detail/format cannot run this pass. Reset
                # their status explicitly so a stale pass/fail left
                # over from an earlier successful run of this same
                # key doesn't linger next to today's placeholder
                # failure.
                count_status=None,
                total_zanata=None,
                total_weblate=None,
                translated_zanata=None,
                translated_weblate=None,
                count_errors=[],
                detail_status=None,
                total_entries=None,
                mismatch_count=None,
                string_mismatch_count=None,
                plural_mismatch_count=None,
                missing_count=None,
                extra_count=None,
                detail_errors=[],
                format_status=None,
                format_errors=[],
            )
            return False

        print(
            f"[INFO] ✓ No placeholder mismatches "
            f"({checked_count} entries with placeholders checked)"
        )
        self._save_result(
            project_name, category_name, component_name, locale,
            placeholder_status='pass',
            **placeholder_fields,
        )

        return True

    def check_sentence_count(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        zanata_po_path: str,
        weblate_po_path: str,
    ) -> bool:
        """Check the sentence count of the translation

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Name of the locale
        :param zanata_po_path: Path to the zanata po file
        :param weblate_po_path: Path to the weblate po file
        :returns: True if the sentence counts match, False otherwise
        """
        zanata_po = polib.pofile(
            zanata_po_path, encoding='utf-8')
        weblate_po = polib.pofile(
            weblate_po_path, encoding='utf-8')

        # A fresh check_sentence_count run means any detail-check
        # result recorded by a previous run is no longer known to be
        # current. Reset those fields explicitly on every branch below
        # so they don't linger stale if check_sentence_detail never
        # gets called this run (e.g. because the count check fails
        # and the caller stops before Step 2/2).
        detail_reset = {
            'detail_status': None,
            'total_entries': None,
            'mismatch_count': None,
            'string_mismatch_count': None,
            'plural_mismatch_count': None,
            'missing_count': None,
            'extra_count': None,
            'detail_errors': [],
            # Format cannot run this pass either - reset it too so a
            # stale pass/fail from an earlier successful run doesn't
            # linger next to today's count failure.
            'format_status': None,
            'format_errors': [],
        }

        # Zanata keeps the obsolete entries.
        # On the other hand, Weblate deletes them automatically.
        # Filter out obsolete entries for accurate comparison.
        zanata_active = [e for e in zanata_po if not e.obsolete]
        weblate_active = [e for e in weblate_po if not e.obsolete]
        if len(zanata_active) != len(weblate_active):
            error_msg = (
                f"Total sentence count mismatch: "
                f"{len(zanata_active)}(zanata) != "
                f"{len(weblate_active)}(weblate)"
            )
            print(f"[ERROR] {error_msg}")
            self._save_result(
                project_name, category_name, component_name, locale,
                total_zanata=len(zanata_active),
                total_weblate=len(weblate_active),
                # Explicitly clear translated_* rather than omitting
                # them, so a stale value from a previous successful
                # run of this same (project, category, component,
                # locale) doesn't linger next to a "fail" status.
                translated_zanata=None,
                translated_weblate=None,
                count_errors=[error_msg],
                count_status='fail',
                **detail_reset,
            )
            return False

        total_count = len(zanata_active)
        zanata_translated = len(
            [e for e in zanata_active if e.translated()])
        weblate_translated = len(
            [e for e in weblate_active if e.translated()])

        if zanata_translated != weblate_translated:
            error_msg = (
                f"Translated sentence count mismatch: "
                f"{zanata_translated}(zanata) != "
                f"{weblate_translated}(weblate)"
            )
            print(f"[ERROR] {error_msg}")
            self._save_result(
                project_name, category_name, component_name, locale,
                total_zanata=total_count,
                total_weblate=total_count,
                translated_zanata=zanata_translated,
                translated_weblate=weblate_translated,
                count_errors=[error_msg],
                count_status='fail',
                **detail_reset,
            )
            return False

        print(
            f"[INFO] ✓ Count matched(translated/total): "
            f"{zanata_translated}/{len(zanata_active)}"
        )
        self._save_result(
            project_name, category_name, component_name, locale,
            total_zanata=total_count,
            total_weblate=total_count,
            translated_zanata=zanata_translated,
            translated_weblate=weblate_translated,
            count_errors=[],
            count_status='pass',
            **detail_reset,
        )

        return True

    def check_sentence_detail(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        zanata_po_path: str,
        weblate_po_path: str,
    ) -> bool:
        """Check detailed translation matching and save to TestResult.

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Locale code
        :param zanata_po_path: Path to the zanata po file
        :param weblate_po_path: Path to the weblate po file
        :returns: True if the detailed comparison matched, False otherwise
        """
        zanata_po = polib.pofile(zanata_po_path, encoding='utf-8')
        weblate_po = polib.pofile(weblate_po_path, encoding='utf-8')

        # Filter out obsolete entries for accurate comparison
        zanata_entries = [e for e in zanata_po if not e.obsolete]
        weblate_entries = [e for e in weblate_po if not e.obsolete]

        # Key entries by (msgid, msgctxt) rather than msgid alone.
        # The same msgid can legitimately repeat with a different
        # msgctxt (e.g. the same source string used in two different
        # screens with different meanings). Keying on msgid alone
        # collapses those distinct entries into one another - either
        # matching two unrelated entries as if they were the same
        # (masking a real mismatch/missing entry), or comparing the
        # wrong pair and reporting a false mismatch.
        weblate_dict = {
            (entry.msgid, entry.msgctxt): entry for entry in weblate_entries
        }

        string_mismatch_count = 0
        plural_mismatch_count = 0
        missing_count = 0
        plural_empty_skipped_count = 0
        errors = []

        for zanata_entry in zanata_entries:
            msgid = zanata_entry.msgid
            msgctxt = zanata_entry.msgctxt
            key = (msgid, msgctxt)

            # Check if (msgid, msgctxt) exists in Weblate
            if key not in weblate_dict:
                error_msg = (
                    f"Missing in Weblate: msgid='{msgid}' "
                    f"msgctxt='{msgctxt}'"
                )
                print(f"[ERROR] {error_msg}")
                errors.append(error_msg)
                missing_count += 1
                continue

            weblate_entry = weblate_dict[key]

            if zanata_entry.msgid_plural:
                # Plural entries carry msgstr_plural (a dict of
                # index -> string) instead of msgstr, which stays ''
                # for them - a plain msgstr comparison silently
                # no-ops for every plural entry and never catches a
                # broken or lost plural translation. Compare index by
                # index instead.
                zanata_plurals = zanata_entry.msgstr_plural
                weblate_plurals = weblate_entry.msgstr_plural
                entry_mismatched = False

                if zanata_plurals.keys() != weblate_plurals.keys():
                    # An entry with zero real content on either side
                    # (never translated in Zanata at all) isn't a
                    # genuine indexing bug: Weblate's own PO export
                    # writes a single blank msgstr[0] for a plural
                    # unit with no translated content, regardless of
                    # the language's true nplurals, since there's
                    # nothing per-slot to preserve. Flagging that as
                    # a mismatch produces a false positive for every
                    # untranslated plural string in every locale and
                    # buries the real bug this check exists to catch
                    # - an entry that DID have content losing a slot.
                    both_fully_empty = (
                        not any(v.strip() for v in zanata_plurals.values())
                        and not any(
                            v.strip() for v in weblate_plurals.values())
                    )
                    if both_fully_empty:
                        plural_empty_skipped_count += 1
                    else:
                        error_msg = (
                            f"Plural form count mismatch for msgid: "
                            f"'{msgid}' msgctxt: '{msgctxt}' "
                            f"- Zanata indices: "
                            f"{sorted(zanata_plurals.keys())} "
                            f"- Weblate indices: "
                            f"{sorted(weblate_plurals.keys())}"
                        )
                        print(f"[ERROR] {error_msg}")
                        errors.append(error_msg)
                        entry_mismatched = True

                common_indices = (
                    zanata_plurals.keys() & weblate_plurals.keys()
                )
                for index in sorted(common_indices):
                    if zanata_plurals[index] != weblate_plurals[index]:
                        error_msg = (
                            f"Plural translation mismatch for msgid: "
                            f"'{msgid}' msgctxt: '{msgctxt}' "
                            f"index {index} "
                            f"- Zanata msgstr[{index}]: "
                            f"'{zanata_plurals[index]}' "
                            f"- Weblate msgstr[{index}]: "
                            f"'{weblate_plurals[index]}'"
                        )
                        print(f"[ERROR] {error_msg}")
                        errors.append(error_msg)
                        entry_mismatched = True

                if entry_mismatched:
                    plural_mismatch_count += 1
            # Compare msgstr from zanata and weblate
            elif zanata_entry.msgstr != weblate_entry.msgstr:
                error_msg = (
                    f"Translation mismatch for msgid: '{msgid}' "
                    f"msgctxt: '{msgctxt}' "
                    f"- Zanata msgstr: '{zanata_entry.msgstr}' "
                    f"- Weblate msgstr: '{weblate_entry.msgstr}'"
                )
                print(f"[ERROR] {error_msg}")
                errors.append(error_msg)
                string_mismatch_count += 1

        if plural_empty_skipped_count:
            # Printed here (not after the final combined status line
            # below) since extract_status_reason() only reads the
            # last printed line of a failed check-sentence-detail
            # call - this must never become that line.
            print(
                f"[INFO] Skipped {plural_empty_skipped_count} "
                f"untranslated plural entries (empty on both sides) "
                f"from the mismatch count"
            )

        # Check for entries in Weblate but not in Zanata
        zanata_keys = {(e.msgid, e.msgctxt) for e in zanata_entries}
        extra_in_weblate = [
            key for key in weblate_dict.keys()
            if key not in zanata_keys
        ]

        weblate_extra_count = len(extra_in_weblate)
        if extra_in_weblate:
            print(
                f"[ERROR] {weblate_extra_count} entries in "
                f"Weblate but not in Zanata"
            )

            # show first 5 extra entries on weblate
            for msgid, msgctxt in extra_in_weblate[:5]:
                error_msg = (
                    f"Extra msgid on weblate: '{msgid[:50]}' "
                    f"msgctxt: '{msgctxt}'"
                )
                print(f"[ERROR] {error_msg}")
                errors.append(error_msg)

        mismatch_count = string_mismatch_count + plural_mismatch_count
        detail_ok = (
            mismatch_count == 0 and missing_count == 0 and
            weblate_extra_count == 0
        )
        if detail_ok:
            print(
                f"[INFO] ✓ Sentence detail matched: "
                f"{len(zanata_entries)} entries"
            )
        else:
            # One combined line with all four counts always present
            # (never conditional) - this is the only line
            # extract_status_reason() (common/pretty-printer.sh) ever
            # sees for a failed check-sentence-detail call (it only
            # captures the last printed line), so a locale that fails
            # on more than one of these can't have one silently
            # overwrite another the way separate conditional lines
            # would. See failure-reason-categorization/plan.md.
            print(
                "[ERROR] Sentence detail check completed with issues: "
                f"string={string_mismatch_count}, "
                f"plural={plural_mismatch_count}, "
                f"missing={missing_count}, extra={weblate_extra_count}"
            )

        self._save_result(
            project_name, category_name, component_name, locale,
            total_entries=len(zanata_entries),
            mismatch_count=mismatch_count,
            string_mismatch_count=string_mismatch_count,
            plural_mismatch_count=plural_mismatch_count,
            missing_count=missing_count,
            extra_count=weblate_extra_count,
            detail_errors=errors,
            detail_status='pass' if detail_ok else 'fail',
            # Format cannot run this pass if detail failed - reset it
            # explicitly so a stale pass/fail from an earlier
            # successful run doesn't linger next to today's detail
            # failure. On success this just gets overwritten by
            # check_po_format's own call right after, so it's a no-op
            # there.
            **({} if detail_ok else {
                'format_status': None,
                'format_errors': [],
            }),
        )

        return detail_ok

    def check_po_format(
        self,
        project_name: str,
        category_name: str,
        component_name: str,
        locale: str,
        weblate_po_path: str,
    ) -> bool:
        """Check that the Weblate PO file is valid gettext PO/MO format.

        check_sentence_count/check_sentence_detail only ever compare
        whether Zanata and Weblate *agree* on content - they never
        ask whether that content is itself a syntactically valid PO
        file. An encoding or format break introduced during migration
        can leave Zanata/Weblate content looking identical while the
        Weblate PO is actually broken for a real gettext build (e.g.
        a msgid/msgstr format-specifier mismatch, or a syntax error).
        `msgfmt --check` is the same tool the real build uses to
        compile the PO, so it's a direct check of buildability rather
        than a re-implementation of gettext's own validation rules.

        A format-specifier mismatch msgfmt reports here is almost
        always a pre-existing mistranslation carried over from Zanata
        (e.g. a translator translating a placeholder name itself,
        such as "{key}" -> "{chave}") rather than something migration
        broke, so it's surfaced as a warning (format_status='warn')
        and does NOT fail the accuracy test/pipeline - only "msgfmt
        itself couldn't run at all" (not installed) is treated as a
        real failure, since that means the file was never actually
        validated.

        :param project_name: Name of the project
        :param category_name: Name of the category
        :param component_name: Name of the component
        :param locale: Name of the locale
        :param weblate_po_path: Path to the weblate po file
        :returns: True unless msgfmt itself could not be run
        """
        try:
            # errors='replace': msgfmt's stderr isn't guaranteed valid
            # UTF-8 (e.g. it can echo back a mis-encoded byte sequence
            # from the very PO content it's complaining about), and a
            # strict decode failure here would raise UnicodeDecodeError
            # and abort this locale's check entirely - defeating the
            # warn-don't-fail behavior below.
            result = subprocess.run(
                ['msgfmt', '--check', '-o', os.devnull, weblate_po_path],
                capture_output=True, text=True, errors='replace',
            )
        except FileNotFoundError:
            error_msg = (
                "msgfmt is not installed or not on PATH - cannot "
                "validate PO format"
            )
            print(f"[ERROR] {error_msg}")
            self._save_result(
                project_name, category_name, component_name, locale,
                format_errors=[error_msg],
                format_status='fail',
            )
            return False

        if result.returncode != 0:
            # msgfmt writes one diagnostic per line to stderr; warnings
            # (e.g. missing optional header fields) don't affect the
            # exit code, only fatal errors do, so a non-zero exit here
            # means a real format problem. Reported as [WARN] (not
            # [ERROR]) and format_status='warn' (not 'fail') - see the
            # docstring above for why this must not fail the run, but
            # the specific msgfmt diagnostics are still printed/saved
            # so the broken msgid/locale is easy to find and fix.
            error_lines = [
                line for line in result.stderr.splitlines() if line.strip()
            ]
            for line in error_lines:
                print(f"[WARN] msgfmt: {line}")
            print(
                f"[WARN] PO format issue found (not failing the "
                f"accuracy test): {locale}"
            )
            self._save_result(
                project_name, category_name, component_name, locale,
                format_errors=error_lines,
                format_status='warn',
            )
            return True

        print(f"[INFO] ✓ PO format valid (msgfmt --check): {locale}")
        self._save_result(
            project_name, category_name, component_name, locale,
            format_errors=[],
            format_status='pass',
        )
        return True


def setup_argument_parser():
    """Setup command line argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description='Weblate management utilities')
    subparser = parser.add_subparsers(
        dest='command', help='Available commands')
    # Create project command
    create_project_parser = subparser.add_parser(
        'create-project', help='Create a new project')
    create_project_parser.add_argument(
        '--project', required=True, help='Name of the project')
    # Create category command
    create_category_parser = subparser.add_parser(
        'create-category', help='Create a new category')
    create_category_parser.add_argument(
        '--project', required=True, help='Name of the project')
    create_category_parser.add_argument(
        '--category', required=True, help='Name of the category')
    # Create component command
    create_component_parser = subparser.add_parser(
        'create-component', help='Create a new component')
    create_component_parser.add_argument(
        '--project', required=True, help='Name of the project')
    create_component_parser.add_argument(
        '--category', required=True, help='Name of the category')
    create_component_parser.add_argument(
        '--component', required=True, help='Name of the component')
    create_component_parser.add_argument(
        '--pot-path', required=True, help='Path to the pot file')
    # Create glossary command
    create_glossary_parser = subparser.add_parser(
        'create-glossary', help='Create a new glossary')
    create_glossary_parser.add_argument(
        '--project', required=True, help='Name of the project')
    # Create translation command
    create_translation_parser = subparser.add_parser(
        'create-translation', help='Create a new translation')
    create_translation_parser.add_argument(
        '--project', required=True, help='Name of the project')
    create_translation_parser.add_argument(
        '--category', required=True, help='Name of the category')
    create_translation_parser.add_argument(
        '--component', required=True, help='Name of the component')
    create_translation_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    create_translation_parser.add_argument(
        '--po-path', required=True,
        help='Path to the po file about to be uploaded for this locale')
    # Upload PO file command
    upload_po_file_parser = subparser.add_parser(
        'upload-po-file', help='Upload a new po file')
    upload_po_file_parser.add_argument(
        '--project', required=True, help='Name of the project')
    upload_po_file_parser.add_argument(
        '--category', required=True, help='Name of the category')
    upload_po_file_parser.add_argument(
        '--component', required=True, help='Name of the component')
    upload_po_file_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    upload_po_file_parser.add_argument(
        '--po-path', required=True, help='Path to po file')
    # Download translation file command
    download_translation_file_parser = subparser.add_parser(
        'download-translation-file',
        help='Download a translation file from Weblate')
    download_translation_file_parser.add_argument(
        '--project', required=True, help='Name of the project')
    download_translation_file_parser.add_argument(
        '--po-path', required=True, help='Path to po file')
    # Check translation existence command
    check_translation_existence_parser = subparser.add_parser(
        'check-translation-existence',
        help='Check that the component/locale PO files exist')
    check_translation_existence_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_translation_existence_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_translation_existence_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_translation_existence_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_translation_existence_parser.add_argument(
        '--zanata-po-path', required=True, help='Path to the zanata po file')
    check_translation_existence_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_translation_existence_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    # Check fuzzy/untranslated command
    check_fuzzy_untranslated_parser = subparser.add_parser(
        'check-fuzzy-untranslated',
        help='Classify a translated-count change as fuzzy re-marking '
             'or possible translation loss')
    check_fuzzy_untranslated_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_fuzzy_untranslated_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_fuzzy_untranslated_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_fuzzy_untranslated_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_fuzzy_untranslated_parser.add_argument(
        '--zanata-po-path', required=True, help='Path to the zanata po file')
    check_fuzzy_untranslated_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_fuzzy_untranslated_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    # Check placeholder consistency command
    check_placeholder_consistency_parser = subparser.add_parser(
        'check-placeholder-consistency',
        help='Check that printf/str.format placeholders in the source '
             'survive translation on both sides')
    check_placeholder_consistency_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_placeholder_consistency_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_placeholder_consistency_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_placeholder_consistency_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_placeholder_consistency_parser.add_argument(
        '--zanata-po-path', required=True, help='Path to the zanata po file')
    check_placeholder_consistency_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_placeholder_consistency_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    # Check sentence count command
    check_sentence_count_parser = subparser.add_parser(
        'check-sentence-count', help='Check the sentence count of the translation')
    check_sentence_count_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_sentence_count_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_sentence_count_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_sentence_count_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_sentence_count_parser.add_argument(
        '--zanata-po-path', required=True, help='Path to the zanata po file')
    check_sentence_count_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_sentence_count_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    # Check sentence detail command
    check_sentence_detail_parser = subparser.add_parser(
        'check-sentence-detail',
        help='Check the sentence detail of the translation')
    check_sentence_detail_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_sentence_detail_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_sentence_detail_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_sentence_detail_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_sentence_detail_parser.add_argument(
        '--zanata-po-path', required=True, help='Path to zanata po')
    check_sentence_detail_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_sentence_detail_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    # Check PO format command
    check_po_format_parser = subparser.add_parser(
        'check-po-format',
        help='Check the weblate PO file is valid gettext format '
             '(msgfmt --check)')
    check_po_format_parser.add_argument(
        '--project', required=True, help='Name of the project')
    check_po_format_parser.add_argument(
        '--category', required=True, help='Name of the category')
    check_po_format_parser.add_argument(
        '--component', required=True, help='Name of the component')
    check_po_format_parser.add_argument(
        '--locale', required=True, help='Name of the locale')
    check_po_format_parser.add_argument(
        '--weblate-po-path', required=True, help='Path to weblate po')
    check_po_format_parser.add_argument(
        '--result-json', required=False,
        help='Path to result JSON Lines log (append-only)')
    return parser


def main():
    """Main entry point for the script."""
    try:
        config = WeblateConfig()

        parser = setup_argument_parser()
        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            sys.exit(1)

        # Get result JSON path from args if available
        result_json_path = getattr(args, 'result_json', None)
        utils = WeblateUtils(config, result_json_path)

        if args.command == 'create-project':
            utils.create_project(args.project)
        elif args.command == 'create-category':
            utils.create_category(args.project, args.category)
        elif args.command == 'create-component':
            utils.create_component(
                args.project, args.category, args.component, args.pot_path)
        elif args.command == 'create-glossary':
            utils.create_glossary(args.project)
        elif args.command == 'create-translation':
            utils.create_translation(
                args.project, args.category, args.component, args.locale,
                args.po_path)
        elif args.command == 'upload-po-file':
            uploaded = utils.upload_po_file(
                args.project, args.category, args.component, args.locale,
                args.po_path)
            if not uploaded:
                # Distinct from both success (0) and a real failure
                # (1) - source had no translation at all, so
                # create_weblate_components.sh can report it as its
                # own "no translation in source" tree leaf instead of
                # counting it as either.
                sys.exit(2)
        elif args.command == 'download-translation-file':
            utils.download_translation_file(
                args.project, args.po_path)
        elif args.command == 'check-translation-existence':
            passed = utils.check_translation_existence(
                args.project, args.category, args.component, args.locale,
                args.zanata_po_path, args.weblate_po_path)
            if not passed:
                sys.exit(1)
        elif args.command == 'check-fuzzy-untranslated':
            passed = utils.check_fuzzy_untranslated(
                args.project, args.category, args.component, args.locale,
                args.zanata_po_path, args.weblate_po_path)
            if not passed:
                sys.exit(1)
        elif args.command == 'check-placeholder-consistency':
            passed = utils.check_placeholder_consistency(
                args.project, args.category, args.component, args.locale,
                args.zanata_po_path, args.weblate_po_path)
            if not passed:
                sys.exit(1)
        elif args.command == 'check-sentence-count':
            passed = utils.check_sentence_count(
                args.project, args.category, args.component, args.locale,
                args.zanata_po_path, args.weblate_po_path)
            if not passed:
                sys.exit(1)

        elif args.command == 'check-sentence-detail':
            passed = utils.check_sentence_detail(
                args.project, args.category, args.component, args.locale,
                args.zanata_po_path, args.weblate_po_path)
            if not passed:
                sys.exit(1)
        elif args.command == 'check-po-format':
            passed = utils.check_po_format(
                args.project, args.category, args.component, args.locale,
                args.weblate_po_path)
            if not passed:
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to migrate: {e}")
        traceback.print_exc()
        # Without this, an uncaught exception anywhere in a subcommand
        # (network error, missing file, corrupt PO, ...) is printed
        # here and then main() returns normally, so the process still
        # exits 0 - callers like test_accuracy/test.sh and
        # migration_projects.sh that branch on exit code see a false
        # success.
        sys.exit(1)


if __name__ == "__main__":
    main()
