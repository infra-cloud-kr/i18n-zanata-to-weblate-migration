#!/bin/bash
# Get zanata.xml from project repository

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

WORK_DIR="$HOME/$WORKSPACE_NAME"
CLONED_PROJECT_DIR="$WORK_DIR/projects/$PROJECT/$PROJECT"

function clone_project() {

    cd $WORK_DIR/projects/$PROJECT
    if [ ! -d "$WORK_DIR/$PROJECT" ]; then
        run_tagged_quiet git clone https://opendev.org/openstack/$PROJECT

        # If the cloned project directory is empty, remove and get errors.
        if [ -z "$(ls -A $CLONED_PROJECT_DIR)" ]; then
            rm -rf $CLONED_PROJECT_DIR
            log_quiet "[ERROR] Failed to clone $PROJECT project"
            FATAL_REASON="git clone failed ($PROJECT)"
            return 1
        else
            log_quiet "[INFO] $PROJECT: Cloned successfully"
        fi
    fi

    # If ZANATA_VERSION is master, we don't need to checkout.
    if [ "$BRANCH_NAME" != "master" ]; then
        cd $CLONED_PROJECT_DIR
        if ! run_tagged_quiet git checkout $BRANCH_NAME; then
            log_quiet "[ERROR] Failed to checkout $BRANCH_NAME version"
            FATAL_REASON="git checkout failed ($BRANCH_NAME)"
            return 1
        fi
        cd - > /dev/null
    fi
    log_quiet "[INFO] $PROJECT: Checked out $BRANCH_NAME version"
    cd - > /dev/null

    return 0
}

# setup_* functions are referenced from openstack-zuul-jobs project.
# - openstack-zuul-jobs/roles/prepare-zanata-client/files/common_translation_update.sh

# Setup a project for Zanata. This is used by both Python and Django projects.
# syntax: setup_project <project> <zanata_version>
function setup_project {
    # Exclude all dot-files, particuarly for things such such as .tox
    # and .venv
    local exclude='.*/**'

    if ! run_tagged_quiet python3 $SCRIPTSDIR/02-prepare-translations/create_zanata_xml.py \
        -p $PROJECT -v $ZANATA_VERSION --srcdir . --txdir . \
        -r '**/*.pot' '{path}/{locale_with_underscore}/LC_MESSAGES/{filename}.po' \
        -e "$exclude" -f $CLONED_PROJECT_DIR/zanata.xml; then

        log "[ERROR] Failed to create zanata.xml for $PROJECT: $(extract_status_reason "$LAST_TAGGED_LINE")"
        exit 1
    fi
    log_quiet "[INFO] zanata.xml created successfully for $PROJECT"
}

# Setup project manuals projects (api-site, openstack-manuals,
# security-guide) for Zanata
function setup_manuals {
    # doc-tools-check-languages.conf lives at the root of the cloned
    # project and is sourced by relative path below, so CWD must be
    # $CLONED_PROJECT_DIR here - clone_project() does not leave us
    # there (it cd's back to the caller's original directory when it
    # finishes).
    cd "$CLONED_PROJECT_DIR"

    # Fill in associative array SPECIAL_BOOKS
    declare -A SPECIAL_BOOKS
    source doc-tools-check-languages.conf

    # Most manuals projects (api-site, openstack-manuals) keep every
    # book directly under doc/, both on disk and as recorded by
    # Zanata. security-doc is the exception: its books (security-guide,
    # security-notes, ...) live directly at the repository root, with
    # no doc/ directory at all. Detect which layout this clone
    # actually has instead of assuming doc/ - ZanataDocFolder is left
    # empty (not ".") for the root case since it feeds directly into
    # the "**/<ZanataDocFolder>/<DOCNAME>/..." rule pattern below,
    # where a literal "./" segment would not match zanata-cli's glob.
    if [ -d doc ]; then
        DocFolder=doc
        ZanataDocFolder=doc
    else
        DocFolder=.
        ZanataDocFolder=
    fi

    # Grab all of the rules for the documents we care about
    ZANATA_RULES=

    # List of directories to skip.

    # All manuals have a source/common subdirectory that is a symlink
    # to doc/common in openstack-manuals. We have to exclude this
    # source/common directory everywhere, only doc/common gets
    # translated.
    EXCLUDE='.*/**,**/source/common/**'

    # Generate pot one by one
    for FILE in ${DocFolder}/*; do
        # Skip non-directories
        if [ ! -d $FILE ]; then
            continue
        fi
        DOCNAME=${FILE#${DocFolder}/}
        # Ignore directories that will not get translated
        if [[ "$DOCNAME" =~ ^(www|tools|generated|publish-docs)$ ]]; then
            continue
        fi
        IS_RST=0
        if [ ${SPECIAL_BOOKS["${DOCNAME}"]+_} ] ; then
            case "${SPECIAL_BOOKS["${DOCNAME}"]}" in
                RST)
                    IS_RST=1
                    ;;
                skip)
                    EXCLUDE="$EXCLUDE,${DocFolder}/${DOCNAME}/**"
                    continue
                    ;;
            esac
        fi
        if [ ${IS_RST} -eq 1 ] ; then
            # The pattern (this rule's first field) must start with **/
            # so it still matches once pull_translation_files overrides
            # --src-dir to an absolute path: zanata-cli's translation
            # file resolver glob-matches this pattern against
            # <--src-dir>/<document id>, and a plain relative pattern
            # never matches an absolute path (wrong segment count), so
            # it silently falls back to gettext's default trans-file
            # layout ({path}/{locale_with_underscore}.po - no
            # LC_MESSAGES, no filename) instead of the layout below.
            ZANATA_RULES="$ZANATA_RULES -r **/${ZanataDocFolder:+$ZanataDocFolder/}${DOCNAME}/source/locale/${DOCNAME}.pot \
                ${DocFolder}/${DOCNAME}/source/locale/{locale_with_underscore}/LC_MESSAGES/${DOCNAME}.po"
        else
            if [ -f ${DocFolder}/${DOCNAME}/locale/${DOCNAME}.pot ]; then
                ZANATA_RULES="$ZANATA_RULES -r **/${ZanataDocFolder:+$ZanataDocFolder/}${DOCNAME}/locale/${DOCNAME}.pot \
                    ${DocFolder}/${DOCNAME}/locale/{locale_with_underscore}.po"
            fi
        fi
    done

    # Project setup and updating POT files for release notes.
    if [[ $PROJECT == "openstack-manuals" ]] && [[ $ZANATA_VERSION == "master" ]]; then
        ZANATA_RULES="$ZANATA_RULES -r **/releasenotes/source/locale/releasenotes.pot \
            releasenotes/source/locale/{locale_with_underscore}/LC_MESSAGES/releasenotes.po"
    fi

    if ! run_tagged_quiet python3 $SCRIPTSDIR/02-prepare-translations/create_zanata_xml.py \
        -p $PROJECT -v $ZANATA_VERSION --srcdir . --txdir . \
        $ZANATA_RULES -e "$EXCLUDE" \
        -f $WORK_DIR/projects/$PROJECT/$PROJECT/zanata.xml; then
        log "[ERROR] Failed to create zanata.xml for $PROJECT: $(extract_status_reason "$LAST_TAGGED_LINE")"
        exit 1
    fi
    log_quiet "[INFO] zanata.xml created successfully for $PROJECT"
    cd - > /dev/null
}

# Setup a training-guides project for Zanata
function setup_training_guides {
    if ! run_tagged_quiet python3 $SCRIPTSDIR/02-prepare-translations/create_zanata_xml.py \
        -p $PROJECT -v $ZANATA_VERSION \
        --srcdir doc/upstream-training/source/locale \
        --txdir doc/upstream-training/source/locale \
        -f $CLONED_PROJECT_DIR/zanata.xml; then
        log "[ERROR] Failed to create zanata.xml for $PROJECT: $(extract_status_reason "$LAST_TAGGED_LINE")"
        exit 1
    fi
    log_quiet "[INFO] zanata.xml created successfully for $PROJECT"
}

# Setup a i18n project for Zanata
function setup_i18n {
    if ! run_tagged_quiet python3 $SCRIPTSDIR/02-prepare-translations/create_zanata_xml.py \
        -p $PROJECT -v $ZANATA_VERSION \
        --srcdir doc/source/locale \
        --txdir doc/source/locale \
        -f $CLONED_PROJECT_DIR/zanata.xml; then
        log "[ERROR] Failed to create zanata.xml for $PROJECT: $(extract_status_reason "$LAST_TAGGED_LINE")"
        exit 1
    fi
    log_quiet "[INFO] zanata.xml created successfully for $PROJECT"
}

# Setup a ReactJS project for Zanata
function setup_reactjs_project {
    local exclude='node_modules/**'

    if ! run_tagged_quiet python3 $SCRIPTSDIR/02-prepare-translations/create_zanata_xml.py \
        -p $PROJECT -v $ZANATA_VERSION --srcdir . --txdir . \
        -r '**/*.pot' '{path}/{locale}.po' \
        -e "$exclude" \
        -f $CLONED_PROJECT_DIR/zanata.xml; then
        log "[ERROR] Failed to create zanata.xml for $PROJECT: $(extract_status_reason "$LAST_TAGGED_LINE")"
        exit 1
    fi
    log_quiet "[INFO] zanata.xml created successfully for $PROJECT"
}
