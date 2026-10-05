#!/bin/bash
# Get component names from project modules.

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

source $SCRIPTSDIR/common/get_translation_path.sh

PROJECT_DIR=$HOME/$WORKSPACE_NAME/projects/$PROJECT/$PROJECT
POT_DIR=$HOME/$WORKSPACE_NAME/projects/$PROJECT/pot

# List of the projects that have doc component.
DOC_TARGETS=('contributor-guide'
             'horizon'
             'openstack-ansible'
             'operations-guide',
             'swift')

function get_python_component_names {
    local components=()
    local module_names
    local python_module_names

    module_names=$(python3 $SCRIPTSDIR/03-prepare-component-name/get_modulename.py -p $PROJECT -t python -f setup.cfg)
    python_module_names=($module_names)

    if [ -n "$module_names" ]; then
        # Not every module has translatable content of its own (e.g.
        # oslo.concurrency, oslo.cache: only releasenotes.pot exists,
        # no <module>/locale/<module>.pot) - only add the module as a
        # component when its pot file actually exists, matching the
        # pattern already used below for releasenotes and in
        # get_django_component_names/get_doc_component_names.
        for modulename in "${python_module_names[@]}"; do
            if [ -f "$POT_DIR/$modulename/locale/$modulename.pot" ]; then
                components+=("$modulename")
            fi
        done

        if [ -f $PROJECT_DIR/releasenotes/source/conf.py ] && \
           [ -f $POT_DIR/releasenotes/source/locale/releasenotes.pot ]; then
            components+=("releasenotes")
        fi
    fi

    echo "${components[@]}"
}

function get_django_component_names {
    local components=()
    local module_names
    local django_module_names
    local is_multiple
    local dest_modulename
    local module_name_hyphenated

    module_names=$(python3 $SCRIPTSDIR/03-prepare-component-name/get_modulename.py -p $PROJECT -t django -f setup.cfg)
    
    # Convert array for proper counting
    # In Weblate, we can't use multiple components name in a project.
    # If it has multiple Django modules, we set name <module_name>-django/djangojs
    # to identify the module in weblate. 
    # e.g. horizon-django, openstack-dashboard-django
    django_module_names=($module_names)

    if [ ${#django_module_names[@]} -ge 2 ]; then
        is_multiple=true
    else
        is_multiple=false
    fi

    if [ -n "$module_names" ]; then
        if [[ -f $PROJECT_DIR/releasenotes/source/conf.py ]] && \
           [[ -f $POT_DIR/releasenotes/source/locale/releasenotes.pot ]]; then
            components+=("releasenotes")
        fi

        # Check if the project has multiple Django modules
        # If it has, we set name <module_name>-django/djangojs
        for modulename in ${django_module_names[@]}; do
            # For single-module projects, also accept a legacy package
            # name whose pot file exists (see
            # get_project_legacy_package_names) - a Zanata document
            # registered under the project's pre-rename name (e.g.
            # freezer-web-ui's old disaster_recovery) won't ever show up
            # under the current module name, but is_multiple==false
            # means there's only one Django component ("django")
            # either way, so the legacy pot still identifies it.
            if [ -f "$POT_DIR/$modulename/locale/django.pot" ] || \
               { [ "$is_multiple" == "false" ] && \
                 [ -n "$(find_legacy_pot_module_name django.pot $POT_DIR)" ]; }; then
                dest_modulename="django"
                if [ "$is_multiple" == "true" ]; then
                    # The module name basically use _ as separator.
                    # In weblate, we need to use -.
                    module_name_hyphenated=$(echo "$modulename" | sed 's/_/-/g')
                    dest_modulename="${module_name_hyphenated}-django"
                fi

                components+=("$dest_modulename")
            fi

            if [ -f "$POT_DIR/$modulename/locale/djangojs.pot" ] || \
               { [ "$is_multiple" == "false" ] && \
                 [ -n "$(find_legacy_pot_module_name djangojs.pot $POT_DIR)" ]; }; then
                dest_modulename="djangojs"
                if [ "$is_multiple" == "true" ]; then
                    module_name_hyphenated=$(echo "$modulename" | sed 's/_/-/g')
                    dest_modulename="${module_name_hyphenated}-djangojs"
                fi
                components+=("$dest_modulename")
            fi
        done
    fi

    echo "${components[@]}"
}

function get_doc_component_names {
    local components=()
    local doc_component_name

    if [[ -f $PROJECT_DIR/doc/source/conf.py ]]; then
        # Check if the project is in the DOC_TARGETS list.
        if [[ ${DOC_TARGETS[*]} =~ "$PROJECT" ]]; then
            if [[ -f $POT_DIR/doc/source/locale/doc.pot ]]; then
                components+=("doc")
            fi

            for doc_pot_file in $POT_DIR/doc/source/locale/doc-*.pot; do
                if [[ -f "$doc_pot_file" ]]; then
                    doc_component_name=$(basename "$doc_pot_file" .pot)
                    components+=("$doc_component_name")
                fi
            done
        fi
    fi

    echo "${components[@]}"
}
