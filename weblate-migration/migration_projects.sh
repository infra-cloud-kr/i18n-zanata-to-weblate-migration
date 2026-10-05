#!/bin/bash

LIST_FILE="$1"
VERSION_FILE="${2:-version.txt}"

# Provides colorize()/RED/GREEN/YELLOW/NC/IS_TTY. Sourced here (in
# this process) rather than relying on migration_resources.sh's copy,
# because IS_TTY must reflect *this* process's own stdout -
# migration_resources.sh is invoked below as `"$MIGRATION_SCRIPT" ... |
# while read line; do ... done`, so its stdout is always a pipe, even
# during an interactive batch run at a real terminal. Sourced before
# the usage/argument checks below too, so those also print with the
# "[ERROR]" tag every other error in this pipeline uses (see README's
# log format) instead of a bare "Error: ...".
source "$(dirname "$0")/common/pretty-printer.sh"

# Check the usage of the script
if [ $# -eq 0 ]; then
    echo "Usage: $0 <list_file> [version_file]"
    echo "Example: $0 list.txt"
    echo "Example: $0 list.txt version.txt"
    exit 1
fi

if [ ! -f "$LIST_FILE" ]; then
    colorize "$RED" "[ERROR] File '$LIST_FILE' does not exist."
    exit 1
fi

if [ ! -f "$VERSION_FILE" ]; then
    colorize "$RED" "[ERROR] File '$VERSION_FILE' does not exist."
    exit 1
fi

MIGRATION_SCRIPT="$(dirname "$0")/migration_resources.sh"
MIGRATION_WORKSPACE_NAME="${MIGRATION_WORKSPACE_NAME:-workspace}"

if [ ! -f "$MIGRATION_SCRIPT" ]; then
    colorize "$RED" "[ERROR] migration_resources.sh file does not exist in '$MIGRATION_SCRIPT'."
    exit 1
fi

# Colorize and print $1 (a tree_line()/tree_line_update() payload,
# marker already stripped) by the status symbol it contains - shared
# by the TREE_MARKER and TREE_UPDATE_MARKER branches below so the two
# don't drift out of sync with each other.
print_tree_content() {
    local tree_content="$1"
    if [[ "$tree_content" == *"✗"* ]]; then
        colorize "$RED" "$tree_content"
    elif [[ "$tree_content" == *"⏳"* ]]; then
        colorize "$YELLOW" "$tree_content"
    elif [[ "$tree_content" == *"✓"* ]]; then
        colorize "$GREEN" "$tree_content"
    else
        # A plain informational line (e.g. the "Next 5 stages: ..."
        # roadmap) with no status symbol of its own - print as-is,
        # neither red/yellow/green nor forced green by default like a
        # real success line would be.
        echo "$tree_content"
    fi
}

# Check the execution permission of the script
if [ ! -x "$MIGRATION_SCRIPT" ]; then
    colorize "$YELLOW" "Warning: migration_resources.sh does not have execution permission. Granting execution permission."
    chmod +x "$MIGRATION_SCRIPT"
fi

# Root directory for all log output, referenced in the startup banner
# below. Other log paths in this script (mkdir -p logs, SUMMARY_LOG,
# per-project log/error files, aggregate_report.py's --logs-dir) keep
# using the literal "logs" directly rather than $LOG_DIR - this
# variable exists only so the banner doesn't print an empty value.
LOG_DIR="logs"

# Make logs directory
mkdir -p logs

# Per (project, version) verdict, one line per run, appended across
# batch invocations. aggregate_report.py reads this as the source of
# truth for success/failure instead of re-deriving it from raw logs.
# Columns: completed_at, project, version, exit_code, run_id, started_at
SUMMARY_LOG="logs/summary.tsv"

# Count non-empty (post-trim) lines in a file, using the exact same
# blank-line test the main loops below use ([[ -z "${line// }" ]]) so
# this count always matches the number of iterations the loops will
# actually perform.
count_valid_lines() {
    local file="$1"
    local count=0
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ -z "${line// }" ]]; then
            continue
        fi
        count=$((count + 1))
    done < "$file"
    echo "$count"
}

# Precompute the total number of (project, version) pairs so the
# progress percentage has a known denominator from the very first
# item, instead of only being derivable after the batch finishes.
project_count=$(count_valid_lines "$LIST_FILE")
version_count=$(count_valid_lines "$VERSION_FILE")
total_pairs=$((project_count * version_count))
# Defensive fallback: this should be unreachable in practice (the
# main loops below can only iterate if total_pairs > 0), but avoids a
# division by zero if that invariant is ever violated.
if [ "$total_pairs" -eq 0 ]; then
    total_pairs=1
fi

# Convert a whole number of seconds into a short duration string for
# the ETA display.
format_duration() {
    local total_seconds=$1
    local hours=$((total_seconds / 3600))
    local minutes=$(((total_seconds % 3600) / 60))
    local seconds=$((total_seconds % 60))

    if [ "$hours" -gt 0 ]; then
        echo "${hours}h ${minutes}m"
    elif [ "$minutes" -gt 0 ]; then
        echo "${minutes}m ${seconds}s"
    else
        echo "${seconds}s"
    fi
}

echo "=== Migration starts ==="
echo "Project file: $LIST_FILE"
echo "Version file: $VERSION_FILE"
echo "Log directory: $LOG_DIR"
echo "====================="

total_count=0
# Cumulative wall-clock time (seconds) spent on items completed so
# far in this run, and how many items that covers. Used to compute
# the average per-item time for the ETA estimate below.
total_elapsed=0
completed_items=0

while IFS= read -r project || [ -n "$project" ]; do
    if [[ -z "${project// }" ]]; then
        continue
    fi

    # Trim before creating the log directory - otherwise a leading/
    # trailing space in list.txt makes this word-split into the wrong
    # path, and every later log write for this project silently goes
    # missing (aggregate_report.py then can't classify its failures).
    project=$(echo "$project" | xargs)
    mkdir -p "logs/$project"

    # Generate timestamp for error log filename. Includes the date (not
    # just HH:MM:SS) since this value is also used as summary.tsv's
    # run_id, which aggregate_report.py relies on to find the exact
    # log file for a run - two runs of the same project at the same
    # wall-clock second on different days must not collide.
    TIMESTAMP=$(date +%Y%m%d%H%M%S)

    # Iterate over the versions
    while IFS= read -r version || [ -n "$version" ]; do
        # Skip empty lines or lines with only whitespace
        if [[ -z "${version// }" ]]; then
            continue
        fi
        
        # Remove leading and trailing whitespace
        version=$(echo "$version" | xargs)
        
        ((total_count++))

        percent=$((total_count * 100 / total_pairs))
        if [ "$completed_items" -gt 0 ]; then
            avg_seconds=$((total_elapsed / completed_items))
            remaining_items=$((total_pairs - total_count + 1))
            eta_seconds=$((avg_seconds * remaining_items))
            eta_display="Estimated time remaining: $(format_duration "$eta_seconds")"
        else
            # No item has finished yet in this run, so there's no
            # average processing time to base an estimate on.
            eta_display="Estimated time remaining: calculating..."
        fi
        echo "[$total_count/$total_pairs] (${percent}%) Processing: '$project' (version: $version) ($eta_display)"
        # Tree root (phase 2): replaces the old "=== Project: X ==="
        # header - one root line per (project, version), closed below
        # once migration_exit_code is known.
        colorize "$YELLOW" "$project / $version  ⏳ In progress"
        item_start_epoch=$(date +%s)

        # path for log files
        LOG_FILE="logs/$project/project.${TIMESTAMP}.log"
        ERROR_LOG="logs/$project/error.${TIMESTAMP}.log"

        # Recorded alongside the verdict below so aggregate_report.py
        # can tell which result.jsonl entries (timestamped by
        # weblate_utils.py's check_sentence_count/detail) were
        # actually produced by *this* run, instead of trusting stale
        # entries left over from an earlier run of the same
        # (project, version).
        run_started_at=$(date '+%Y-%m-%dT%H:%M:%S')

        # run migration.sh and save the log to the log file
        #
        # NOTE: We deliberately do not wrap this pipeline in an
        # `if ... ; then` check. The exit status of a pipeline is the
        # exit status of its *last* command (the `while` loop here),
        # which almost always exits 0 regardless of whether
        # MIGRATION_SCRIPT failed. PIPESTATUS[0] captures the actual
        # exit code of MIGRATION_SCRIPT, and must be read immediately
        # after the pipeline, before any other command runs.
        # Tracks whether the most recent line actually printed to the
        # console was specifically a "⏳ ... In progress" tree_line() - the
        # only thing a following tree_line_update() is ever meant to
        # overwrite. Reset to 0 by every other console-visible line
        # (any other TREE_MARKER content, or the fallback echo branch);
        # left alone by QUIET_MARKER lines, since those never touch
        # the console at all. Without this, a future change that adds
        # any visible line between a stage's tree_line("⏳ ...") and
        # its tree_line_update("✓ ...") would make the cursor-up+clear
        # below silently overwrite that unrelated line instead of the
        # intended progress line - this makes that failure mode
        # degrade to "prints a new line" instead of "corrupts the
        # screen".
        last_line_was_tree_start=0
        # Buffers a TREE_UPDATE_MARKER line when stdout isn't a live
        # terminal (see the IS_TTY branch below) - create_weblate_components.sh/
        # test.sh now call tree_line_update() once per locale (a live
        # progress counter), not just once per component, so printing
        # every one as its own line here would flood a component with
        # many locales instead of collapsing to the single done/failed
        # line they're meant to end on. Flushed by flush_pending_tree_update
        # right before anything else needs to reach the console, and
        # once more after the loop for whatever update was still
        # pending when the stream closed.
        pending_tree_update=""
        flush_pending_tree_update() {
            if [ -n "$pending_tree_update" ]; then
                print_tree_content "$pending_tree_update"
                pending_tree_update=""
            fi
        }
        "$MIGRATION_SCRIPT" "$project" "$version" "$MIGRATION_WORKSPACE_NAME" 2>&1 | {
        while IFS= read -r line || [ -n "$line" ]; do
            # create_weblate_components.sh/test.sh/every other stage now
            # tag each line with one of three markers instead of always
            # being both logged and echoed the same way - see
            # TREE_MARKER/TREE_UPDATE_MARKER/QUIET_MARKER in
            # common/pretty-printer.sh for the full protocol. Lines
            # carrying no marker (there should be none left in normal
            # operation - every stage now routes through
            # log_quiet()/run_tagged_quiet()/tree_line(), or a
            # still-visible fatal-error tagged_colorize()) fall through
            # to the phase-1 behavior unchanged: tagged, logged, and
            # echoed - a safety net, not the expected path.
            if [[ "$line" == "${TREE_UPDATE_MARKER}"* ]]; then
                tree_content="${line#$TREE_UPDATE_MARKER}"
                if [ "$IS_TTY" -eq 1 ]; then
                    if [ "$last_line_was_tree_start" -eq 1 ]; then
                        # Cursor up one line + clear it, so this prints
                        # on top of the "⏳ ... In progress" line
                        # tree_line_update() is meant to replace,
                        # instead of appending a new one. Skipped if
                        # the adjacency invariant doesn't hold (see
                        # last_line_was_tree_start's own comment).
                        printf '\033[1A\033[2K'
                    fi
                    print_tree_content "$tree_content"
                else
                    # Meaningless (and stream-corrupting) to move the
                    # cursor when stdout isn't a real terminal - buffer
                    # instead of printing immediately, so a long chain
                    # of per-locale updates collapses to just its final
                    # state (see pending_tree_update's comment above).
                    pending_tree_update="$tree_content"
                fi
                # A done/failed update line is itself never a valid
                # "start" to overwrite again - see the ⏳-only check
                # in the TREE_MARKER branch below for why this isn't
                # just "=1".
                if [[ "$tree_content" == *"⏳"* ]]; then
                    last_line_was_tree_start=1
                else
                    last_line_was_tree_start=0
                fi
                continue
            fi
            if [[ "$line" == "${TREE_MARKER}"* ]]; then
                flush_pending_tree_update
                tree_content="${line#$TREE_MARKER}"
                print_tree_content "$tree_content"
                if [[ "$tree_content" == *"⏳"* ]]; then
                    last_line_was_tree_start=1
                else
                    last_line_was_tree_start=0
                fi
                continue
            fi
            if [[ "$line" == "${QUIET_MARKER}"* ]]; then
                line="${line#$QUIET_MARKER}"
                plain_line="$project | $version | $line"
                echo "$plain_line" >> "$LOG_FILE"
                if [[ "$line" == *" | [ERROR]"* ]]; then
                    echo "$plain_line" >> "$ERROR_LOG"
                fi
                continue
            fi

            last_line_was_tree_start=0
            flush_pending_tree_update
            plain_line="$project | $version | $line"
            # Log file writes must always stay plain text - never
            # colorize this, or error.*.log/project.*.log end up with
            # raw ANSI escape bytes in them, which breaks grep and the
            # README's `version | message` log format. (This replaces
            # the previous `tee -a "$LOG_FILE"`, which piped the same
            # string to both the file and stdout at once and so had no
            # way to make the two diverge.)
            echo "$plain_line" >> "$LOG_FILE"
            # migration_resources.sh's own [ERROR]/[Failed] lines
            # arrive here as plain text regardless of whether *it* was
            # run at a real terminal, because its stdout is always a
            # pipe in this context (see the IS_TTY comment on the
            # `source pretty-printer.sh` line above) - so it's safe to
            # colorize purely by matching the tag text. Since phase-1
            # log tagging, every line from migration_resources.sh's
            # log()/colorize()/run_tagged() (common/pretty-printer.sh)
            # is prefixed "component | locale | ", so the [ERROR]/
            # [Failed] tag itself no longer starts the line - match it
            # right after that prefix's trailing " | " instead of
            # anchoring at the start of the line.
            if [[ "$line" == *" | [ERROR]"* || "$line" == *" | [Failed]"* ]]; then
                colorize "$RED" "$plain_line"
            else
                echo "$plain_line"
            fi
            # save the error line to the error log file
            if [[ "$line" == *" | [ERROR]"* ]]; then
                echo "$plain_line" >> "$ERROR_LOG"
            fi
        done
        # Whatever update was still buffered when the stream closed
        # (e.g. the very last locale's progress line, if nothing else
        # printed after it) would otherwise never reach the console at
        # all on a non-TTY run.
        flush_pending_tree_update
        }
        migration_exit_code=${PIPESTATUS[0]}

        # Tree root, closed (phase 2) - replaces the old bare Success/
        # Failed summary line. Kept as its own colorize() call (not a
        # QUIET_MARKER/TREE_MARKER line from the child) since it's
        # this process's own project/version-level verdict, derived
        # from $migration_exit_code which only this process has.
        if [ "$migration_exit_code" -eq 0 ]; then
            colorize "$GREEN" "$project / $version  ✓ SUCCESS"
        else
            colorize "$RED" "$project / $version  ✗ FAILED (exit code: $migration_exit_code)"
        fi
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
            "$(date '+%Y-%m-%dT%H:%M:%S')" "$project" "$version" \
            "$migration_exit_code" "$TIMESTAMP" "$run_started_at" \
            >> "$SUMMARY_LOG"
        sleep 15

        # Roll this item's wall-clock time (migration run + the fixed
        # sleep above, since every remaining item pays that same cost)
        # into the running average used for the next item's ETA.
        item_end_epoch=$(date +%s)
        total_elapsed=$((total_elapsed + item_end_epoch - item_start_epoch))
        completed_items=$((completed_items + 1))

        echo "---"
    done < "$VERSION_FILE"
    
done < "$LIST_FILE"

echo "====================="
echo "=== Migration completed ==="
