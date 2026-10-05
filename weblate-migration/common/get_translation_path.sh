#!/bin/bash
# Create and setup the Weblate components.

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

function sanitize_locale {
    local locale=$1
    
    # Normalize locale code:
    # - Language code: lowercase (Th -> th, JA -> ja)
    # - Region code: uppercase (zh_tw -> zh_TW, pt_br -> pt_BR)
    
    if [[ "$locale" == *"_"* ]]; then
        # Has region code (e.g., zh_tw, pt_BR, ko_kr)
        IFS='_' read -r lang region <<< "$locale"
        # Language to lowercase, region to uppercase
        echo "${lang,,}_${region^^}"
    else
        # Single language code (e.g., Th, ja, DE)
        # Convert to lowercase
        echo "${locale,,}"
    fi
}

function get_project_package_name {
    local project=$1
    local project_package_name=""
    
    case $project in
        "designate-dashboard")
            # Remove all dashes
            # ex. designate-dashboard -> designatedashboard
            project_package_name="designatedashboard"
            ;;
        "cloudkitty-dashboard")
            # Remove all dashes
            # ex. cloudkitty-dashboard -> cloudkittydashboard
            project_package_name="cloudkittydashboard"
            ;;
        "freezer-web-ui")
            # Remove all dashes
            # ex. freezer-web-ui -> freezer_ui
            project_package_name="freezer_ui"
            ;;
        python-*)
            # OpenStack client repos are named with a "python-" prefix
            # that the importable module itself drops.
            # ex. python-novaclient -> novaclient
            project_package_name="${project#python-}"
            project_package_name="${project_package_name//[-.]/_}"
            ;;
        *)
            # oslo.cache -> oslo_cache, oslo.concurrency -> oslo_concurrency,
            # etc. - matches how these projects' actual importable module
            # name is derived (see get_modulename.py/PBR), which get_pot_path
            # below relies on to locate each component's real pot directory.
            project_package_name="${project//[-.]/_}"
    esac
    
    echo "$project_package_name"
}

function get_project_legacy_package_names {
    local project=$1

    case $project in
        "freezer-web-ui")
            # freezer-web-ui's Django module was named disaster_recovery
            # before it was renamed in commit 50b6486 (2024-12-09). Zanata
            # document IDs don't get renamed when the module is renamed in
            # git, so branches whose translations were last exported to
            # Zanata before that rename (e.g. stable/2025.1) still have
            # their documents registered under disaster_recovery.
            echo "disaster_recovery"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Find, among a project's known legacy package names, one whose pot file
# actually exists under $pot_dir - used to fall back to the pre-rename
# Zanata document path when the current package name's pot file isn't
# there (see get_project_legacy_package_names above).
#
# :param pot_filename: e.g. "django.pot", "djangojs.pot", "<component>.pot"
# :param pot_dir: directory pot files were pulled into for this run
# Echoes the matching legacy name and returns 0, or returns 1 if none
# of the project's legacy names have that pot file.
function find_legacy_pot_module_name {
    local pot_filename=$1
    local pot_dir=$2
    local legacy_name

    for legacy_name in $(get_project_legacy_package_names $PROJECT); do
        if [ -f "$pot_dir/$legacy_name/locale/$pot_filename" ]; then
            echo "$legacy_name"
            return 0
        fi
    done
    return 1
}

# Resolve which on-disk package directory actually holds a component's
# pot file: the current package name if its pot file exists, otherwise
# the first legacy name whose pot file exists (see
# find_legacy_pot_module_name), otherwise the current package name
# unchanged (so callers keep reporting "no translation file" exactly as
# before when neither exists).
function resolve_project_package_name {
    local pot_filename=$1
    local pot_dir=${2:-$HOME/$WORKSPACE_NAME/projects/$PROJECT/pot}
    local project_package_name=$(get_project_package_name $PROJECT)
    local legacy_name

    if [ -f "$pot_dir/$project_package_name/locale/$pot_filename" ]; then
        echo "$project_package_name"
        return
    fi

    legacy_name=$(find_legacy_pot_module_name "$pot_filename" "$pot_dir")
    if [ -n "$legacy_name" ]; then
        echo "$legacy_name"
        return
    fi

    echo "$project_package_name"
}

# Manuals-family projects (api-site, security-doc, openstack-manuals)
# run every book through setup_manuals() (see get_zanata_xml.sh),
# which - unlike a typical Python package's flat
# <package>/locale/<component>.pot layout - writes one pot per book
# under <book>/source/locale/<book>.pot. Most of these projects nest
# that under doc/ (setup_manuals()'s DocFolder), but security-doc has
# no doc/ directory and keeps books at the repository root, so both
# prefixes have to be checked. Detected by checking the canonical
# Zanata pot directory directly (not any base_dir a caller passed in),
# since get_po_path's only caller passes a different base_dir for the
# downloaded Weblate copy. Echoes the prefix that was actually found
# ("doc/" or "") and fails if the component isn't a manuals book at
# all.
function get_manuals_doc_prefix {
    local component=$1
    local pot_dir="$HOME/$WORKSPACE_NAME/projects/$PROJECT/pot"

    if [ -f "$pot_dir/doc/$component/source/locale/$component.pot" ]; then
        echo "doc/"
    elif [ -f "$pot_dir/$component/source/locale/$component.pot" ]; then
        echo ""
    else
        return 1
    fi
}

function get_pot_path {
    local component=$1
    local base_dir=${2:-$HOME/$WORKSPACE_NAME/projects/$PROJECT/pot}
    local module_name=""
    local project_package_name=$(get_project_package_name $PROJECT)

    case $component in
        "releasenotes")
            echo "$base_dir/releasenotes/source/locale/releasenotes.pot"
            ;;
        *-django)
            # openstack-auth-django -> openstack_auth/locale/django.pot
            module_name="${component%-django}"
            module_name="${module_name//-/_}"
            echo "$base_dir/$module_name/locale/django.pot"
            ;;
        *-djangojs)
            # openstack-auth-djangojs -> openstack_auth/locale/djangojs.pot
            module_name="${component%-djangojs}"
            module_name="${module_name//-/_}"
            echo "$base_dir/$module_name/locale/djangojs.pot"
            ;;
        "django")
            echo "$base_dir/$(resolve_project_package_name django.pot $base_dir)/locale/django.pot"
            ;;
        "djangojs")
            echo "$base_dir/$(resolve_project_package_name djangojs.pot $base_dir)/locale/djangojs.pot"
            ;;
        "doc"|doc-*)
            if [ "$PROJECT" == "training-guides" ]; then
                # setup_training_guides() (get_zanata_xml.sh) scopes
                # --srcdir directly to doc/upstream-training/source/locale,
                # the only location of this project's single Zanata
                # document ("upstream-training" - see
                # tools/buildlang.sh's DOCNAME). zanata-cli writes a
                # document's source file at <src-dir>/<document id>.pot,
                # and this document id has no "/" in it, so the pulled
                # pot ends up flat at the pot dir root instead of
                # nested under doc/source/locale/ like other
                # "doc"-component projects. Verified with a read-only
                # `zanata-cli pull --pull-type source`.
                echo "$base_dir/upstream-training.pot"
            elif [[ "$PROJECT" == "i18n" && "$component" == "doc" ]]; then
                # setup_i18n() scopes the source directory to
                # doc/source/locale. Zanata therefore pulls this document
                # flat as pot/doc.pot rather than preserving that prefix.
                # Return failure when it is absent so component creation
                # cannot turn a missing pull into a later FileNotFoundError.
                local i18n_pot_path="$base_dir/doc.pot"
                if [ ! -f "$i18n_pot_path" ]; then
                    return 1
                fi
                echo "$i18n_pot_path"
            else
                echo "$base_dir/doc/source/locale/$component.pot"
            fi
            ;;
        *)
            local doc_prefix
            if doc_prefix=$(get_manuals_doc_prefix "$component"); then
                echo "$base_dir/${doc_prefix}$component/source/locale/$component.pot"
            else
                echo "$base_dir/$(resolve_project_package_name $component.pot $base_dir)/locale/$component.pot"
            fi
            ;;
    esac
}

function get_po_path {
    local component=$1
    local locale=$2
    local base_dir=${3:-$HOME/workspace/projects/$PROJECT/translations}
    local is_weblate=${4:-false}
    local project_package_name=$(get_project_package_name $PROJECT)

    # For Weblate, normalize locale code
    if [ "$is_weblate" == "true" ]; then
        locale=$(sanitize_locale "$locale")
    fi

    case $component in
        "releasenotes")
            echo "$base_dir/releasenotes/source/locale/$locale/LC_MESSAGES/releasenotes.po"
            ;;
        *-django)
            if [ "$is_weblate" == "true" ]; then
                echo "$base_dir/$component/locale/$locale/LC_MESSAGES/django.po"
            else
                # openstack-auth-django -> openstack_auth/locale/django.pot
                module_name="${component%-django}"
                module_name="${module_name//-/_}"
                echo "$base_dir/$module_name/locale/$locale/LC_MESSAGES/django.po"
            fi
            ;;
        *-djangojs)
            if [ "$is_weblate" == "true" ]; then
                echo "$base_dir/$component/locale/$locale/LC_MESSAGES/djangojs.po"
            else
                # openstack-auth-djangojs -> openstack_auth/locale/djangojs.pot
                module_name="${component%-djangojs}"
                module_name="${module_name//-/_}"
                echo "$base_dir/$module_name/locale/$locale/LC_MESSAGES/djangojs.po"
            fi
            ;;
        "django")
            if [ "$is_weblate" == "true" ]; then
                echo "$base_dir/django/locale/$locale/LC_MESSAGES/django.po"
            else
                echo "$base_dir/$(resolve_project_package_name django.pot)/locale/$locale/LC_MESSAGES/django.po"
            fi
            ;;
        "djangojs")
            if [ "$is_weblate" == "true" ]; then
                echo "$base_dir/djangojs/locale/$locale/LC_MESSAGES/djangojs.po"
            else
                echo "$base_dir/$(resolve_project_package_name djangojs.pot)/locale/$locale/LC_MESSAGES/djangojs.po"
            fi
            ;;
        "doc"|doc-*)
            if [ "$is_weblate" == "true" ]; then
                echo "$base_dir/$component/source/locale/$locale/LC_MESSAGES/$component.po"
            else
                echo "$base_dir/doc/source/locale/$locale/LC_MESSAGES/$component.po"
            fi
            ;;
        *)
            local doc_prefix
            if doc_prefix=$(get_manuals_doc_prefix "$component"); then
                if [ "$is_weblate" == "true" ]; then
                    # Weblate's downloaded zip lays each manuals-book
                    # component out as <component>/locale/<locale>/
                    # LC_MESSAGES/<component>.po - no "source" segment
                    # (unlike the "doc"/doc-* single-pot case above,
                    # whose filemask is rooted at doc/source/locale).
                    echo "$base_dir/$component/locale/$locale/LC_MESSAGES/$component.po"
                else
                    echo "$base_dir/${doc_prefix}$component/source/locale/$locale/LC_MESSAGES/$component.po"
                fi
            else
                echo "$base_dir/$(resolve_project_package_name $component.pot)/locale/$locale/LC_MESSAGES/$component.po"
            fi
            ;;
    esac
}


function sanitize_django_component {
    local component=$1
    
    if [[ "$component" == *"-django" ]]; then
        echo "django"
    elif [[ "$component" == *"-djangojs" ]]; then
        echo "djangojs"
    else
        echo "$component"
    fi
}

function get_module_name_from_component {
    local component=$1
    
    if [[ "$component" == *"-django" || "$component" == *"-djangojs" ]]; then
        # Extract module name from component (e.g., "horizon-django" -> "horizon")
        echo "${component%-django*}" | sed 's/-/_/g'
    else
        echo "$component"
    fi
}

function extract_locale_from_path {
    local translation_path=$1

    # The locale code is always the directory immediately above
    # LC_MESSAGES, with or without a further "locale/" ancestor - most
    # components nest under .../locale/<code>/LC_MESSAGES/..., but
    # training-guides pulls flat as .../<code>/LC_MESSAGES/... (see
    # get_pot_path's training-guides case). Not requiring the literal
    # "locale/" segment covers both without changing the result for
    # the nested layout.
    echo "$translation_path" | sed 's|.*/\([^/]*\)/LC_MESSAGES/.*|\1|'
}

function get_po_file_path() {
    local component=$1
    local locale_file=$2
    local django_module_name=$3
    
    # Extract locale name from the full path
    # For paths like /path/to/locale/de/LC_MESSAGES/file.po, extract "de"
    local locale_name=$(echo "$locale_file" | sed 's|.*/locale/\([^/]*\)/LC_MESSAGES/.*|\1|')

    case $component in
        doc*)
            path="${TARGET_PROJECT_DIR}/translations/doc/source/locale/${locale_name}/LC_MESSAGES/${component}.po"
            echo "Doc PO path: $path" >&2
            echo "$path"
            ;;
        "*django"|"*djangojs"|"django"|"djangojs")
            # Django projects: use actual module name
            sanitized_component=$(sanitize_django_component $component)
            if [ -n "$django_module_name" ]; then
                path="${TARGET_PROJECT_DIR}/translations/${django_module_name}/locale/${locale_name}/LC_MESSAGES/${sanitized_component}.po"
                echo "Django PO path with module name: $path" >&2
                echo "$path"
            else
                path="${TARGET_PROJECT_DIR}/translations/${project_package_name}/locale/${locale_name}/LC_MESSAGES/${sanitized_component}.po"
                echo "Django PO path with package name: $path" >&2
                echo "$path"
            fi
            ;;
        "${PROJECT}")
            echo "${TARGET_PROJECT_DIR}/translations/${project_package_name}/locale/${locale_name}/LC_MESSAGES/${project_package_name}.po"
            ;;
        "releasenotes")
            # For releasenotes, locale_file should be the full path
            echo "${TARGET_PROJECT_DIR}/translations/releasenotes/source/locale/${locale_name}/LC_MESSAGES/${component}.po"
            ;;
        *)
            echo "${TARGET_PROJECT_DIR}/translations/${project_package_name}/locale/${locale_name}/LC_MESSAGES/${project_package_name}.po"
            ;;
    esac
}

function get_translation_path_list() {
    local component=$1
    local target_project_dir="$HOME/workspace/projects/$PROJECT/translations"
    local project_package_name=$(get_project_package_name $PROJECT)

    if [[ "$component" == "releasenotes" ]]; then
        # Special handling for releasenotes
        locale_list=($(find ${target_project_dir}/releasenotes -name "*.po" -path "*/locale/*/LC_MESSAGES/*.po" 2>/dev/null || echo ""))
    elif [[ "$PROJECT" == "i18n" && "$component" == "doc" ]]; then
        # With i18n, zanata.xml's source root is doc/source/locale while the
        # CLI is invoked with a separate --trans-dir. Zanata consequently
        # writes <locale>/LC_MESSAGES/doc.po directly below translations/.
        # Restrict this fallback to i18n/doc so conventional projects keep
        # using their existing */locale/* layout.
        locale_list=($(find "$target_project_dir" -mindepth 3 -maxdepth 3 \
            -type f -path "*/LC_MESSAGES/doc.po" 2>/dev/null | sort))
    elif [[ "$component" == "django" ]]; then
        local resolved_package_name=$(resolve_project_package_name django.pot)
        locale_list=($(find ${target_project_dir}/${resolved_package_name} -name "*.po" -path "*/locale/*/LC_MESSAGES/django.po" 2>/dev/null || echo ""))
    elif [[ "$component" == "djangojs" ]]; then
        local resolved_package_name=$(resolve_project_package_name djangojs.pot)
        locale_list=($(find ${target_project_dir}/${resolved_package_name} -name "*.po" -path "*/locale/*/LC_MESSAGES/djangojs.po" 2>/dev/null || echo ""))
    elif [[ "$component" == *"-django" || "$component" == *"-djangojs" ]]; then
        # Django components are saved as django.pot, djangojs.pot
        sanitized_component=$(sanitize_django_component $component)
        # Get the correct module name for this component
        correct_module_name=$(get_module_name_from_component $component)
        locale_list=($(find ${target_project_dir}/${correct_module_name} -name "*.po" -path "*/locale/*/LC_MESSAGES/${sanitized_component}.po" 2>/dev/null || echo ""))
    elif [[ "$PROJECT" == "training-guides" ]]; then
        # Matches get_pot_path's training-guides case: the single
        # "doc" component's po files are pulled flat as
        # translations/<locale>/LC_MESSAGES/upstream-training.po, with
        # no locale/ ancestor directory and not named doc.po.
        locale_list=($(find ${target_project_dir} -name "*.po" -path "*/LC_MESSAGES/upstream-training.po" 2>/dev/null || echo ""))
    else
        locale_list=($(find ${target_project_dir} -name "*.po" -path "*/locale/*/LC_MESSAGES/${component}.po" 2>/dev/null || echo ""))
    fi

    echo "${locale_list[@]}"
}
