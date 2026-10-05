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

import polib
import sys

from zanata_plural_rules import ZANATA_LANG_RULES


def get_lang_rules(base_lang_code: str, full_lang_code: str):
    """Look up the ZANATA_LANG_RULES entry for a locale

    Most locales are listed only under their base language's entry
    (e.g. "en_GB" appears in ZANATA_LANG_RULES["en"]["region_code"]).
    A few region variants have their own top-level entry instead,
    used when their plural rules differ from the base language's
    (e.g. "pt_BR" has different plural rules than "pt") - that entry
    takes precedence when present.

    :param base_lang_code: language part only, e.g. "en"
    :param full_lang_code: full locale code, e.g. "en_GB"
    :returns: the matching ZANATA_LANG_RULES entry, or None if
        neither the full nor the base code is recognized
    """
    if full_lang_code in ZANATA_LANG_RULES:
        return ZANATA_LANG_RULES[full_lang_code]

    if base_lang_code in ZANATA_LANG_RULES:
        region_codes = ZANATA_LANG_RULES[base_lang_code]['region_code']
        if full_lang_code in region_codes:
            return ZANATA_LANG_RULES[base_lang_code]

    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 lang_plural_check.py <po_file_path>")
        sys.exit(1)

    po_file_path = sys.argv[1]
    po = polib.pofile(po_file_path)

    po_lang_data = po.metadata['Language']
    
    # The language code is lowercase.
    # But in some cases, for example,
    # Thai(Th) is mixed with upper case.
    # So we need to normalize the language code to lowercase.
    lang_code = po_lang_data.split('_')[0].lower()

    # If the language code contains a region code (e.g., en_US),
    # convert the language part to lowercase and region part to uppercase.
    parts = po_lang_data.split('_')
    converted_lang_code=""
    if len(parts) == 2:
        converted_lang_code = f"{parts[0].lower()}_{parts[1].upper()}"
    else:
        converted_lang_code = lang_code
    
    print(f"[INFO] Check {lang_code} validation...")
    rules = get_lang_rules(lang_code, converted_lang_code)
    if rules is None:
        print(f"[ERROR] {converted_lang_code} is invalid")
        sys.exit(1)

    print(f"[INFO] Convert {po_lang_data} to {converted_lang_code}")
    po.metadata['Language'] = converted_lang_code

    # Compare plural rules
    expected_plurals = rules['plurals']
    current_plurals = po.metadata['Plural-Forms']
    if expected_plurals != current_plurals:
        print(
            f"[INFO] Change plural rules from {current_plurals} "
            f"to {expected_plurals}"
        )
        po.metadata['Plural-Forms'] = expected_plurals

    po.save(po_file_path)
    print(f"[INFO] Saved {po_file_path} with new metadata")


if __name__ == "__main__":
    main()
