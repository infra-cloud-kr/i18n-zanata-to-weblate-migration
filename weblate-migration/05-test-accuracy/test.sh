source $SCRIPTSDIR/common/get_translation_path.sh

TEST_DIR=$HOME/$WORKSPACE_NAME/projects/$PROJECT/test
RESULT_JSON=$HOME/$WORKSPACE_NAME/projects/$PROJECT/result.jsonl

function test_accuracy {
    # Set when any single locale's checks fail, so one bad locale is
    # logged and skipped instead of aborting every remaining
    # locale/component via `exit` (mirrors create_weblate_components.sh).
    local had_failure=0

    # No component/locale is known yet for the project-level download
    # below - reset in case an earlier (project, version) run in the
    # same process left these set (see create_weblate_components.sh).
    CURRENT_COMPONENT="-"
    CURRENT_LOCALE="-"

    if [ ! -d "$TEST_DIR" ]; then
        log_quiet "[INFO] TEST_DIR does not exist. Create new one."
        mkdir -p $TEST_DIR
    fi

    cd $TEST_DIR
    # Download translation file from Weblate
    run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py download-translation-file \
        --project $PROJECT \
        --po-path $TEST_DIR/$PROJECT.zip
    run_tagged_quiet unzip -o $PROJECT.zip
    rm -f $PROJECT.zip

    tree_line "⏳ Running accuracy test..."

    local total_components=${#COMPONENTS[@]}
    local component_index=0

    for component in "${COMPONENTS[@]}"; do
        CURRENT_COMPONENT="$component"
        component_index=$((component_index + 1))
        local component_connector="├─"
        if [ "$component_index" -eq "$total_components" ]; then
            component_connector="└─"
        fi
        local child_prefix="│  "
        if [ "$component_connector" == "└─" ]; then
            child_prefix="   "
        fi

        # Get translation path list as an array
        local translation_path_array=($(get_translation_path_list $component))
        local total_locales=${#translation_path_array[@]}
        local success_count=0
        # One rendered "<locale>  <failed step>  <status reason>" entry
        # per failed locale, printed as this component's tree children
        # once the loop below finishes - mirrors
        # create_weblate_components.sh's failed_locale_lines.
        local failed_locale_lines=()
        # Locales where check-po-format found a msgfmt --check issue
        # but, per check_po_format()'s docstring (common/weblate_utils.py),
        # that's reported as a warning rather than a failure - it
        # still exits 0 and counts toward success_count below, so
        # without this it would be entirely invisible in the live
        # console tree (QUIET_MARKER lines like its [WARN] output
        # never reach migration_projects.sh's console - see
        # pretty-printer.sh). Same idea as create_weblate_components.sh's
        # no_translation_locale_lines: a real outcome that's neither a
        # plain success nor a failure gets its own tree leaf category.
        local warned_locale_lines=()

        # See create_weblate_components.sh's identical progress-line
        # pair for why this is a fresh tree_line() only the first time
        # (nothing to update yet) and tree_line_update() after every
        # locale's outcome from here on.
        if [ "$total_locales" -gt 0 ]; then
            tree_line "$(component_progress_text "$component_connector" "$component" 0 "$total_locales" 0)"
        fi

        for translation_path in "${translation_path_array[@]}"; do
            local locale=$(extract_locale_from_path $translation_path)
            CURRENT_LOCALE="$locale"

            # The downloaded/extracted directory tree mirrors Weblate's
            # own project slug (see sanitize_slug() in
            # common/weblate_utils.py, used when the project/component
            # were created and when the export was downloaded), where
            # a project name like "oslo.cache" becomes "oslo-cache" -
            # dots (and other characters Weblate slugs don't allow)
            # are replaced with -. $PROJECT itself is never sanitized,
            # so without this, a dotted project name would look for
            # its PO files under the raw (never-created) $PROJECT
            # directory and always report every locale as missing.
            local version_dir=${ZANATA_VERSION//./-}
            local project_slug=${PROJECT//./-}
            local weblate_po_path=$(get_po_path $component $locale $TEST_DIR/$project_slug/$version_dir true)

            log_quiet "[INFO] Step 1/6: Check the component/locale existence..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-translation-existence \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --zanata-po-path $translation_path \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "existence" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            # Runs before the sentence count check (which fails
            # outright on any translated-count difference) so this
            # classification - fuzzy re-marking vs possible real loss
            # - is always recorded to help triage that failure.
            log_quiet "[INFO] Step 2/6: Check fuzzy/untranslated counts..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-fuzzy-untranslated \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --zanata-po-path $translation_path \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "fuzzy-untranslated" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            # Runs before the sentence count/detail checks (which stop
            # the batch on the first content difference) so a
            # placeholder regression is always classified and recorded
            # even if those later checks fail on the same entries.
            log_quiet "[INFO] Step 3/6: Check placeholder consistency..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-placeholder-consistency \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --zanata-po-path $translation_path \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "placeholder" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            log_quiet "[INFO] Step 4/6: Check the sentence count..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-sentence-count \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --zanata-po-path $translation_path \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "sentence-count" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            log_quiet "[INFO] Step 5/6: Check the sentence detail..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-sentence-detail \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --zanata-po-path $translation_path \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "sentence-detail" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            log_quiet "[INFO] Step 6/6: Check the PO format (msgfmt --check)..."
            if ! run_tagged_quiet python3 -u $SCRIPTSDIR/common/weblate_utils.py check-po-format \
                --project $PROJECT \
                --category $ZANATA_VERSION \
                --component $component \
                --locale $locale \
                --weblate-po-path $weblate_po_path \
                --result-json $RESULT_JSON
            then
                had_failure=1
                failed_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "po-format" "$(extract_status_reason "$LAST_TAGGED_LINE")")")
                CURRENT_LOCALE="-"
                update_component_progress
                continue
            fi

            # check-po-format exits 0 here even when it found a
            # (non-fatal-to-the-pipeline) msgfmt --check issue - its
            # last printed line in that case is always "[WARN] PO
            # format issue found ...", which run_tagged_quiet falls
            # back to as LAST_TAGGED_LINE (no "[ERROR] ... (<code>)"
            # summary line to prefer instead), so this check is
            # reliable without needing check-po-format's exit code to
            # change.
            if [[ "$LAST_TAGGED_LINE" == *"PO format issue found"* ]]; then
                warned_locale_lines+=("$(printf '%-8s%-24s%s' "$locale" "po-format" "msgfmt --check warning (not fatal, see logs)")")
            fi

            success_count=$((success_count + 1))
            CURRENT_LOCALE="-"
            update_component_progress
        done

        # See create_weblate_components.sh's identical check for why
        # "0/0" gets its own neutral symbol instead of a plain ✓.
        local component_symbol="✓"
        if [ "$total_locales" -eq 0 ]; then
            component_symbol="○"
        elif [ "${#failed_locale_lines[@]}" -gt 0 ]; then
            component_symbol="✗"
        fi
        if [ "$total_locales" -eq 0 ]; then
            tree_line "$(printf '%s %s %-28s (no translation file to test)' "$component_connector" "$component_symbol" "$component")"
        else
            tree_line_update "$(printf '%s %s %-28s %d/%d' "$component_connector" "$component_symbol" "$component" "$success_count" "$total_locales")"
        fi

        local failed_count=${#failed_locale_lines[@]}
        local warned_count=${#warned_locale_lines[@]}
        local leaf_total=$((failed_count + warned_count))
        local locale_index=0
        for entry in "${failed_locale_lines[@]}"; do
            locale_index=$((locale_index + 1))
            local locale_connector="├─"
            if [ "$locale_index" -eq "$leaf_total" ]; then
                locale_connector="└─"
            fi
            tree_line "$(printf '%s%s ✗ %s' "$child_prefix" "$locale_connector" "$entry")"
        done
        # Neutral (uncolored - migration_projects.sh's tree color
        # dispatch only colors lines containing ✗/⏳/✓) marker, not ✗:
        # these locales passed (they count toward success_count above)
        # but msgfmt --check found something worth a human looking at.
        # Same reasoning as create_weblate_components.sh's "○
        # no translation in source" leaves.
        for entry in "${warned_locale_lines[@]}"; do
            locale_index=$((locale_index + 1))
            local locale_connector="├─"
            if [ "$locale_index" -eq "$leaf_total" ]; then
                locale_connector="└─"
            fi
            tree_line "$(printf '%s%s ⚠ %s' "$child_prefix" "$locale_connector" "$entry")"
        done
        CURRENT_COMPONENT="-"
    done

    cd - > /dev/null

    if [ "$had_failure" -eq 1 ]; then
        return 1
    fi
}