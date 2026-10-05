#!/bin/bash
# Migration script to create Weblate components and translations

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

PROJECT=$1
BRANCH_NAME=${2:-"master"}
WORKSPACE_NAME=${3:-"workspace"}

# Replace /'s in branch names with -'s because Zanata doesn't
# allow /'s in version names.
ZANATA_VERSION=${BRANCH_NAME//\//-}

# List the components to be handled
COMPONENTS=()

SCRIPTSDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $SCRIPTSDIR/01-setup-env/setup.sh
source $SCRIPTSDIR/02-prepare-translations/get_zanata_xml.sh
source $SCRIPTSDIR/02-prepare-translations/get_translations.sh
source $SCRIPTSDIR/03-prepare-component-name/get_project_component_name.sh
source $SCRIPTSDIR/04-prepare-weblate-components/create_weblate_components.sh
source $SCRIPTSDIR/05-test-accuracy/test.sh
source $SCRIPTSDIR/common/pretty-printer.sh

# We need a UTF-8 locale for Zanata's Java client and the PO-processing
# helpers. Ubuntu installations do not necessarily generate en_US.UTF-8;
# when that locale is missing, Java 8 silently falls back to ASCII and
# replaces each non-ASCII byte in translated PO msgstr values with "?".
# C.UTF-8 is provided by glibc without requiring a generated language locale.
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# All opendev.org projects this script clones are public - a git clone
# should never legitimately need credentials. Without this, a typo'd
# or missing project name makes opendev.org's Gitea return 401 (it
# can't tell "doesn't exist" from "private, no access" and asks git to
# authenticate to check), and git blocks forever on a username prompt
# with no TTY behind it. Disabling terminal prompts turns that hang
# into an immediate, clearly logged clone failure instead.
export GIT_TERMINAL_PROMPT=0

# You should set WEBLATE_URL and WEBLATE_TOKEN
# system environment variables.
log_quiet "[INFO] Check variables"
if [ -z "$WEBLATE_URL" ] || [ "$WEBLATE_URL" == "<weblate_url>" ]; then
    tagged_colorize "$RED" "[ERROR] WEBLATE_URL is not set"
    exit 1
fi
if [ -z "$WEBLATE_TOKEN" ] || [ "$WEBLATE_TOKEN" == "<weblate_token>" ]; then
    tagged_colorize "$RED" "[ERROR] WEBLATE_TOKEN is not set"
    exit 1
fi
log_quiet "[INFO] WEBLATE_URL and WEBLATE_TOKEN are set"

# Printed once so a long silent stretch during a slow stage (e.g. pip
# installs, a big git clone) doesn't read as the run having hung -
# without this, all a person sees between "⏳ In progress" and the next
# status line is nothing, with no way to tell "still working" from
# "stuck". No status symbol of its own, so it renders uncolored (see
# migration_projects.sh's tree dispatch).
tree_line "Next 5 stages: Setup environment → Clone → Generate POT → Create components → Accuracy test"

stage "Setup environment and prepare workspace"
tree_line "⏳ Setting up environment..."
if ! setup_env_and_prepare_workspace "$PROJECT"; then
    tagged_colorize "$RED" "[ERROR] Failed to setup environment and prepare workspace: $FATAL_REASON"
    exit 1
fi
endstage
tree_line_update "✓ Environment setup complete"

stage "Clone $PROJECT project"
tree_line "⏳ Cloning..."
if ! clone_project "$PROJECT" "$ZANATA_VERSION"; then
    tagged_colorize "$RED" "[ERROR] Failed to clone $PROJECT project: $FATAL_REASON"
    exit 1
fi
endstage
tree_line_update "✓ Clone complete"

# Every project setup below pulls from Zanata before component discovery.
# Do not let a failed pull fall through to a misleading "POT generation
# complete" message and a later FileNotFoundError during component creation.
function pull_translation_files_or_exit {
    if ! pull_translation_files; then
        tagged_colorize "$RED" "[ERROR] Failed to export translations from Zanata"
        exit 1
    fi
}

# NOTE: POT generation (setup_*, which writes zanata.xml) and the Zanata
# export (pull_translation_files) are kept in a single stage here rather
# than split into two, because get_django_component_names/
# get_doc_component_names (used by the default `*` branch below) detect
# components by checking for .pot files that pull_translation_files
# writes - they only exist *after* the Zanata pull runs. Splitting this
# into separate top-level stages would require either reordering the
# pull ahead of POT-based component detection (breaking it for the
# default branch) or duplicating stage/endstage inside all seven case
# arms; both are out of scope for this consistency-only change. See
# phase-1 result doc for details.
stage "Generate POT and export translations from Zanata"
tree_line "⏳ Generating POT..."
case $PROJECT in
    api-site)
        setup_manuals
        pull_translation_files_or_exit
        COMPONENTS+=("api-quick-start")
        COMPONENTS+=("firstapp")
        ;;
    
    security-doc)
        setup_manuals
        pull_translation_files_or_exit
        COMPONENTS+=("security-guide")
        ;;
    openstack-manuals)
        setup_manuals
        pull_translation_files_or_exit
        # Per-book components, matching doc-tools-check-languages.conf's
        # SPECIAL_BOOKS (RST books under doc/) plus releasenotes, which
        # setup_manuals() always adds separately for this project.
        COMPONENTS+=("api-quick-start")
        COMPONENTS+=("common")
        COMPONENTS+=("glossary")
        COMPONENTS+=("image-guide")
        COMPONENTS+=("install-guide")
        COMPONENTS+=("releasenotes")
        ;;
    i18n)
        setup_i18n
        pull_translation_files_or_exit
        COMPONENTS+=("doc")
        ;;
    training-guides)
        setup_training_guides
        pull_translation_files_or_exit
        COMPONENTS+=("doc")
        ;;
    tripleo-ui)
        setup_reactjs_project
        pull_translation_files_or_exit
        COMPONENTS+=("i18n")
        ;;
    *)
        setup_project
        pull_translation_files_or_exit
        
        COMPONENTS+=($(get_python_component_names))
        COMPONENTS+=($(get_django_component_names))
        COMPONENTS+=($(get_doc_component_names))
        ;;
esac

# In bash script, it did not handle duplication.
# So we need to delete duplicated components.
if [ ${#COMPONENTS[@]} -eq 0 ]; then
    fail "No components to process"
    exit 1
fi

# An optional, whitespace-separated allow-list is useful for focused
# migration tests without changing the project's normal component discovery.
# Example: MIGRATION_COMPONENTS="horizon-django" ./migration_resources.sh ...
if [ -n "${MIGRATION_COMPONENTS:-}" ]; then
    FILTERED_COMPONENTS=()
    for component in "${COMPONENTS[@]}"; do
        for requested_component in $MIGRATION_COMPONENTS; do
            if [ "$component" = "$requested_component" ]; then
                FILTERED_COMPONENTS+=("$component")
                break
            fi
        done
    done
    COMPONENTS=("${FILTERED_COMPONENTS[@]}")

    if [ ${#COMPONENTS[@]} -eq 0 ]; then
        fail "None of the requested components were found: $MIGRATION_COMPONENTS"
        exit 1
    fi
fi
log_quiet "[INFO] Components to migrate: ${COMPONENTS[*]}"
endstage
tree_line_update "✓ POT generation complete (${#COMPONENTS[@]} components: ${COMPONENTS[*]})"

stage "Create Weblate components"
# Kept as a flag rather than exiting immediately: a partial failure
# here (one bad component/locale) should not skip the accuracy test
# or workspace cleanup for everything that *did* succeed. The final
# exit code below still reflects the failure.
component_migration_failed=0
if ! create_weblate_components; then
    tagged_colorize "$RED" "[ERROR] One or more components/locales failed to migrate"
    component_migration_failed=1
fi
endstage

stage "Start Accuracy Test"
# Same reasoning as component_migration_failed above: one locale's
# check failing should not skip cleanup or hide the results of every
# other locale/component that passed.
accuracy_test_failed=0
if ! test_accuracy; then
    tagged_colorize "$RED" "[ERROR] One or more components/locales failed accuracy testing"
    accuracy_test_failed=1
fi
endstage

# Clean
log_quiet "[INFO] Clean up workspace directory"
# Not remove the project repository for reuse.
# TODO: Create code for cleanup all projects.
# pot/translations live under projects/$PROJECT/, not directly under
# projects/ - without $PROJECT here, these deleted a path that never
# existed, so pot/po files from earlier versions/branches of the same
# project silently carried over into the next run's component
# discovery and uploads.
rm -rf $HOME/$WORKSPACE_NAME/projects/$PROJECT/pot
rm -rf $HOME/$WORKSPACE_NAME/projects/$PROJECT/translations

if [ "$component_migration_failed" -eq 1 ] || [ "$accuracy_test_failed" -eq 1 ]; then
    exit 1
fi
exit 0
