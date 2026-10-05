#!/bin/bash
# Get translation files(*.pot, *.po) from project repository

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

function pull_translation_files {
    cd $WORK_DIR/projects/$PROJECT/$PROJECT

    # zanata-cli's launcher passes JAVA_OPTS directly to Java. Force UTF-8
    # last so a host's missing/invalid locale (or an earlier file.encoding
    # option) cannot make the gettext translation writer replace multibyte
    # msgstr values with question marks. Preserve unrelated caller options
    # such as heap sizing.
    local zanata_java_opts="${JAVA_OPTS:+$JAVA_OPTS }-Dfile.encoding=UTF-8"

    # Pull all translation files(po, pot) from Zanata.
    # source file(*.pot) is in /pot directory.
    # translation file(*.po) is in /translations directory.
    run_tagged_quiet env LANG=C.UTF-8 LC_ALL=C.UTF-8 \
        JAVA_OPTS="$zanata_java_opts" \
        zanata-cli -B -e pull --pull-type both \
        --src-dir $WORK_DIR/projects/$PROJECT/pot \
        --trans-dir $WORK_DIR/projects/$PROJECT/translations
}
