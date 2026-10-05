#!/usr/bin/env python3
"""Aggregate migration_projects.sh batch results into one status report.

Reads:
  - logs/summary.tsv, the per (project, version) run verdict that
    migration_projects.sh appends to on every run (completed_at,
    project, version, exit_code, run_id, started_at).
  - <workspace>/projects/<project>/result.jsonl, the per (project,
    category, component, locale) accuracy-check events that
    common/weblate_utils.py appends (see migration-status-tracking
    Phase 2 and Phase 5), folded into one merged entry per key by
    common.weblate_utils.reduce_result_events().
  - logs/<project>/project.<run_id>.log, to classify *where* a failed
    run stopped (clone / POT generation / Weblate component creation
    / accuracy check), by finding the last stage marker
    migration_resources.sh printed for that version before it exited
    (most stages via pretty-printer.sh's stage(), which prints
    "# <title>"; env_check is a plain "[INFO] <text>" line since it
    isn't wrapped in stage()/endstage()).

Prints a project x version x component x locale status table (or CSV)
so "how far did the migration get, and where did it fail" can be
answered without opening every logs/<project>/error.*.log by hand.
"""
import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'common'))
from weblate_utils import (  # noqa: E402
    load_result_events, reduce_result_events)

# Ordered (stage_key, marker_prefix, display_label) triples, in the
# same order migration_resources.sh prints them. classify_stage() finds
# the *last* one reached for a given version before the run's exit
# code was captured, i.e. the stage that was in progress when it died.
#
# "Clean up workspace directory" is deliberately NOT included here:
# migration_resources.sh runs cleanup unconditionally (both
# component_migration_failed and accuracy_test_failed are recorded but
# only checked *after* cleanup, right before the final exit), so
# reaching it no longer implies success - a failed accuracy test still
# prints it. Treating it as a real stage would misclassify every
# accuracy failure as "success, cleanup reached" instead of surfacing
# the actual failure.
STAGE_MARKERS = [
    ('env_check', '[INFO] Check variables',
     'Environment variable check failed'),
    ('setup', '# Setup environment and prepare workspace',
     'Environment setup failed'),
    ('clone', '# Clone ', 'Clone failed'),
    ('pot', '# Generate POT and export translations from Zanata',
     'POT generation/Zanata export failed'),
    ('weblate_component', '# Create Weblate components',
     'Weblate component creation failed'),
    ('accuracy', '# Start Accuracy Test', 'Accuracy mismatch'),
]
STAGE_LABELS = {key: label for key, _, label in STAGE_MARKERS}
UNKNOWN_STAGE = 'unknown'
STAGE_LABELS[UNKNOWN_STAGE] = 'Unknown (check log)'

# The merged entry's 'status' field (derived by
# common/weblate_utils.py reduce_result_events) can be 'pass', 'fail',
# or 'incomplete' - the latter
# meaning only one of count/detail check ran (e.g. the run was killed
# between them), which is not the same as a confirmed mismatch and
# must not be reported under the same accuracy-mismatch stage label.
ACCURACY_INCOMPLETE_LABEL = 'Accuracy check incomplete'

# check_po_format (common/weblate_utils.py) reports a msgfmt --check
# failure as format_status='warn', not 'fail' - it's almost always a
# pre-existing Zanata mistranslation, not something migration broke,
# so it must not count as an accuracy failure (see that function's
# docstring). reduce_result_events() already folds 'warn' into an
# overall 'pass' status for that reason. Without this label, that
# warning would be entirely invisible in this report (stage='-', same
# as a clean pass) even though it's exactly the kind of thing this
# report exists to surface without opening the raw log by hand.
PO_FORMAT_WARNING_LABEL = 'PO format warning (not a failure - see logs)'


def classify_stage(project_log_path, project, version):
    """Return the stage key reached last for `version` in the log.

    Only lines prefixed "<project> | <version> | " belong to this
    version's run (migration_projects.sh interleaves every version's
    output into the same per-project log file). The two fields after
    that (component, locale - "-" outside a per-locale loop) come from
    log_quiet()'s own "<component> | <locale> | " prefix
    (common/pretty-printer.sh), so the stage marker itself is only the
    third pipe-separated field after the "<project> | <version> | "
    prefix. Returns UNKNOWN_STAGE if the log is missing or no known
    marker was found.
    """
    if not project_log_path.exists():
        return UNKNOWN_STAGE

    prefix = f"{project} | {version} | "
    last_stage = None
    with open(project_log_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            if not line.startswith(prefix):
                continue
            remainder = line[len(prefix):].split(' | ', 2)
            if len(remainder) < 3:
                continue
            content = remainder[2]
            for stage_key, marker, _ in STAGE_MARKERS:
                if content.startswith(marker):
                    last_stage = stage_key
    return last_stage or UNKNOWN_STAGE


def read_summary(logs_dir):
    """Read logs/summary.tsv, keeping only the latest run per
    (project, version) since it's an append-only log across batch
    invocations and re-runs.
    """
    summary_path = Path(logs_dir) / 'summary.tsv'
    latest = {}
    if not summary_path.exists():
        return latest

    with open(summary_path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) != 6:
                print(
                    f"[WARN] {summary_path}:{lineno}: expected 6 "
                    f"tab-separated fields, got {len(parts)} - skipped",
                    file=sys.stderr,
                )
                continue
            (completed_at, project, version, exit_code, run_id,
             started_at) = parts
            try:
                exit_code = int(exit_code)
            except ValueError:
                print(
                    f"[WARN] {summary_path}:{lineno}: non-integer exit "
                    f"code '{exit_code}' - skipped",
                    file=sys.stderr,
                )
                continue
            # Later lines for the same (project, version) overwrite
            # earlier ones, so the last occurrence (most recent run)
            # wins.
            latest[(project, version)] = {
                'completed_at': completed_at,
                'started_at': started_at,
                'exit_code': exit_code,
                'run_id': run_id,
            }
    return latest


def load_result_json(workspace_dir, project):
    """Load and merge project's result.jsonl into the same
    {"project/category/component/locale": entry} shape the old
    single-file result.json used to hold, via
    common.weblate_utils.load_result_events/reduce_result_events.
    """
    path = Path(workspace_dir) / 'projects' / project / 'result.jsonl'
    try:
        return reduce_result_events(load_result_events(path))
    except OSError as e:
        print(
            f"[WARN] Failed to read {path}: {e} - "
            "treating as no accuracy data",
            file=sys.stderr,
        )
        return {}


def zanata_category(version):
    """Match migration_resources.sh's ZANATA_VERSION=${BRANCH_NAME//\\//-}.

    Zanata doesn't allow '/' in version names, so migration_resources.sh
    replaces it with '-' before using the version as the Weblate
    category/result.jsonl 'category' field. summary.tsv keeps the raw
    version (e.g. 'stable/2025.2'), so entries must be looked up by this
    normalized form, not the raw one.
    """
    return version.replace('/', '-')


def _entry_sort_key(entry):
    return (entry.get('component', ''), entry.get('locale', ''))


def _entry_in_run_window(entry, run):
    """True if `entry` (a merged result.jsonl record) was written
    during `run`.

    result.jsonl accumulates across every past run of a project, so a
    (project, category) match alone doesn't mean an entry came from
    the run being reported on - it could be a stale pass/fail left
    over from an earlier attempt at the same version. Both
    entry['checked_at'] (weblate_utils.py, '%Y-%m-%dT%H:%M:%S' local
    time) and run['started_at']/['completed_at'] (migration_projects.sh,
    same format) are naive local timestamps, so a plain string
    comparison is enough to tell whether the entry falls inside this
    run's [started_at, completed_at] window.
    """
    checked_at = entry.get('checked_at', '')
    return run['started_at'] <= checked_at <= run['completed_at']


def _accuracy_rows(project, version, entries):
    """Turn merged result.jsonl entries into report rows for one
    (project, version), with each entry's stage set only when it
    didn't pass.
    """
    rows = []
    for entry in sorted(entries, key=_entry_sort_key):
        status = entry.get('status', 'unknown')
        if status == 'pass':
            stage = (
                PO_FORMAT_WARNING_LABEL
                if entry.get('format_status') == 'warn' else '-'
            )
        elif status == 'fail':
            stage = STAGE_LABELS['accuracy']
        else:
            # 'incomplete', or any future/unexpected status value.
            stage = ACCURACY_INCOMPLETE_LABEL
        rows.append({
            'project': project, 'version': version,
            'component': entry.get('component', '-'),
            'locale': entry.get('locale', '-'),
            'status': status, 'stage': stage,
        })
    return rows


def build_report(logs_dir, workspace_dir):
    """Return a list of row dicts: project, version, component, locale,
    status, stage.
    """
    rows = []
    runs = read_summary(logs_dir)
    result_cache = {}

    for (project, version), run in sorted(runs.items()):
        if project not in result_cache:
            result_cache[project] = load_result_json(workspace_dir, project)
        result_data = result_cache[project]

        category = zanata_category(version)
        entries = [
            entry for entry in result_data.values()
            if entry.get('project') == project
            and entry.get('category') == category
            and _entry_in_run_window(entry, run)
        ]

        if run['exit_code'] == 0:
            if not entries:
                rows.append({
                    'project': project, 'version': version,
                    'component': '-', 'locale': '-',
                    'status': 'success', 'stage': '-',
                })
                continue
            rows.extend(_accuracy_rows(project, version, entries))
            continue

        # Non-zero exit code: figure out where it stopped.
        project_log_path = (
            Path(logs_dir) / project / f"project.{run['run_id']}.log"
        )
        stage_key = classify_stage(project_log_path, project, version)

        if stage_key == 'accuracy' and entries:
            # The run reached the accuracy-check stage this time, so
            # every entry for this (project, version) reflects this
            # run: test_accuracy() exits immediately on the first
            # failing locale, so entries checked before it are real
            # passes and the failing one is the reason for the
            # non-zero exit.
            rows.extend(_accuracy_rows(project, version, entries))
        else:
            # Failed before accuracy checks ever ran (or the log
            # couldn't be classified) - no component/locale to
            # attribute the failure to.
            rows.append({
                'project': project, 'version': version,
                'component': '-', 'locale': '-',
                'status': 'fail', 'stage': STAGE_LABELS[stage_key],
            })

    return rows


HEADERS = ['project', 'version', 'component', 'locale', 'status', 'stage']


def _summarize(rows):
    """Return (total, fail_count, stage_counts) shared by every output
    format, so the "N rows, M failing" / per-stage failure counts
    can't drift between print_table(), format_markdown(), etc.

    stage_counts is a list of (stage_label, count) pairs, sorted by
    count descending (most common failure stage first) - same order
    print_table has always used.
    """
    total = len(rows)
    fail_count = sum(1 for r in rows if r['status'] not in ('success', 'pass'))
    counts = {}
    for r in rows:
        if r['stage'] != '-':
            counts[r['stage']] = counts.get(r['stage'], 0) + 1
    stage_counts = sorted(counts.items(), key=lambda kv: -kv[1])
    return total, fail_count, stage_counts


def print_table(rows):
    widths = [len(h) for h in HEADERS]
    for row in rows:
        for i, h in enumerate(HEADERS):
            widths[i] = max(widths[i], len(str(row[h])))

    def fmt_row(values):
        return '  '.join(
            str(v).ljust(widths[i]) for i, v in enumerate(values))

    print(fmt_row(HEADERS))
    print('  '.join('-' * w for w in widths))
    for row in rows:
        print(fmt_row(row[h] for h in HEADERS))

    total, fail_count, stage_counts = _summarize(rows)
    print()
    print(f"{total} rows, {fail_count} failing")
    for stage, count in stage_counts:
        print(f"  {stage}: {count}")


def print_csv(rows):
    writer = csv.DictWriter(sys.stdout, fieldnames=HEADERS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)


def _md_escape(value):
    """Escape characters that would break a Markdown table row: '|'
    (mistaken for a cell boundary) and newlines (which would split one
    logical row across multiple lines). Values here only ever come
    from Zanata/Weblate project/version/component/locale names or this
    script's own status/stage labels, none of which are expected to
    contain either, but the escape is cheap insurance against a table
    silently breaking if one ever did.
    """
    return str(value).replace('|', '\\|').replace('\n', ' ')


def format_markdown(rows):
    """Render `rows` as a Markdown report: a project x version x
    component x locale status table, followed by the same "N rows, M
    failing" / per-stage summary print_table() shows (via
    _summarize()), so the console table and this Markdown version can
    never disagree - they're two renderings of the same rows list and
    the same summary computation.

    Returns the report as a single string (caller decides whether
    that goes to a file or stdout).
    """
    lines = ['# Migration Report', '']
    lines.append('| ' + ' | '.join(HEADERS) + ' |')
    lines.append('| ' + ' | '.join(['---'] * len(HEADERS)) + ' |')
    for row in rows:
        lines.append(
            '| ' + ' | '.join(_md_escape(row[h]) for h in HEADERS) + ' |')

    total, fail_count, stage_counts = _summarize(rows)
    lines.append('')
    lines.append(f"**{total} rows, {fail_count} failing**")
    if stage_counts:
        lines.append('')
        lines.append('| stage | count |')
        lines.append('| --- | --- |')
        for stage, count in stage_counts:
            lines.append(f"| {_md_escape(stage)} | {count} |")

    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Aggregate migration_projects.sh batch results into a '
            'project x version x component x locale status report.'
        )
    )
    parser.add_argument(
        '--logs-dir', default='logs',
        help="Path to migration_projects.sh's log directory "
             "(default: logs)")
    parser.add_argument(
        '--workspace', default=os.path.expanduser('~/workspace'),
        help='Path to the migration workspace root containing '
             'projects/<project>/result.jsonl (default: ~/workspace)')
    parser.add_argument(
        '--format', choices=['table', 'csv', 'markdown'], default='table',
        help='Output format written to stdout (default: table)')
    parser.add_argument(
        '--report-md', default=None,
        help='Also write the Markdown report to this path, in addition '
             'to the --format output on stdout. Renders the same rows '
             '--format does, so the two can never disagree.')
    args = parser.parse_args()

    rows = build_report(args.logs_dir, args.workspace)
    if not rows:
        print(
            f"[INFO] No runs found in {args.logs_dir}/summary.tsv",
            file=sys.stderr,
        )
        if args.report_md:
            Path(args.report_md).write_text(
                '# Migration Report\n\n'
                f"No runs found in {args.logs_dir}/summary.tsv.\n",
                encoding='utf-8',
            )
        return

    # Rendered at most once and reused for both the --report-md file
    # and (when --format markdown) stdout, rather than calling
    # format_markdown() twice and doing the row/summary rendering
    # work over again for the same rows.
    markdown_text = None
    if args.format == 'markdown' or args.report_md:
        markdown_text = format_markdown(rows)

    if args.format == 'csv':
        print_csv(rows)
    elif args.format == 'markdown':
        print(markdown_text, end='')
    else:
        print_table(rows)

    if args.report_md:
        # Match the explicit encoding='utf-8' used by every other file
        # I/O in this module (load_result_events, classify_stage),
        # rather than falling back to the platform's locale encoding
        # (ASCII under LANG=C/POSIX) the way Path.write_text() does by
        # default.
        Path(args.report_md).write_text(markdown_text, encoding='utf-8')


if __name__ == '__main__':
    main()
