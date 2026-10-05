#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Script to delete all languages registered in Weblate
"""

import argparse
import json
import requests
from typing import Dict
from typing import List
from urllib.parse import urlparse
from urllib.parse import urlunparse
from weblate_utils import IniConfig
from weblate_utils import WeblateRestService


class WeblateLanguageDeleter:
    def __init__(self, ini_path: str):
        config = IniConfig(ini_path)
        self.svc = WeblateRestService(config)
        self.base_url = self.svc.url.rstrip('/')
        self.headers = self.svc.headers
        self.verify = self.svc.verify
        self.session = requests.Session()

    def get_all_languages(self) -> List[Dict]:
        all_languages = []
        url = f"{self.base_url}/api/languages/"

        try:
            while url:
                print(f"[DEBUG] GET {url}")
                response = self.session.get(
                    url,
                    headers=self.headers,
                    verify=self.verify
                )
                response.raise_for_status()

                data = response.json()
                results = data.get('results', [])
                all_languages.extend(results)

                # Check for next page URL. The server may advertise a
                # different host (e.g. a default/placeholder SITE_DOMAIN),
                # so always rewrite scheme+host to the one we actually
                # connected to and keep only the path/query it provided.
                next_url = data.get('next')
                if next_url:
                    parsed_next = urlparse(next_url)
                    parsed_base = urlparse(self.base_url)
                    url = urlunparse(parsed_next._replace(
                        scheme=parsed_base.scheme,
                        netloc=parsed_base.netloc,
                    ))
                else:
                    url = None

            print(f"Collected a total of {len(all_languages)} languages.")
            return all_languages
        except requests.exceptions.RequestException as e:
            print(f"Error occurred while retrieving language information: {e}")
            return all_languages

    def delete_language(self, language_code: str) -> bool:
        url = f"{self.base_url}/api/languages/{language_code}/"

        try:
            r = requests.delete(url, headers=self.headers, verify=self.verify)
            if r.status_code in (204, 200):
                print(f"Deleted: {language_code}")
                return True
            else:
                print(f"Failed ({r.status_code}): {r.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"Error occurred while deleting language: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response body: {e.response.text}")
            return False

    def delete_all_languages(self, dry_run: bool = True,
                             exclude_languages: List[str] = None) -> Dict:
        if exclude_languages is None:
            exclude_languages = []

        print("Weblate Language Deletion Started\n")

        # Retrieve currently registered languages
        print("Retrieving currently registered languages")
        languages = self.get_all_languages()

        if not languages:
            print("No languages found to delete")
            return {
                'total': 0,
                'deleted': 0,
                'skipped': 0,
                'failed': 0
            }

        print(f"Total {len(languages)} languages are registered.\n")

        # Filter languages for deletion
        languages_to_delete = []
        languages_to_skip = []

        for lang in languages:
            code = lang.get('code', '')
            name = lang.get('name', 'N/A')

            if code in exclude_languages:
                languages_to_skip.append((code, name))
            else:
                languages_to_delete.append((code, name))

        print(f"Languages to delete: {len(languages_to_delete)}")
        print(f"Excluded languages: {len(languages_to_skip)}")

        if languages_to_skip:
            print("Excluded languages:")
            for code, name in languages_to_skip:
                print(f"  - {code}: {name}")
        print()

        # Execute deletion
        print("Executing language deletion")
        deleted_count = 0
        failed_count = 0

        for code, name in languages_to_delete:
            print(f"Processing: {code} ({name})")

            if dry_run:
                print("[Dry Run] Deletion simulation")
                deleted_count += 1
            else:
                if self.delete_language(code):
                    print("Deletion successful")
                    deleted_count += 1
                else:
                    print("Deletion failed")
                    failed_count += 1

        # Summary
        print("\nDeletion Completed")
        print(f"Total languages: {len(languages)}")
        print(f"Deleted: {deleted_count}")
        print(f"Skipped: {len(languages_to_skip)}")
        print(f"Failed: {failed_count}")
        print(f"Dry run: {dry_run}")

        return {
            'total': len(languages),
            'deleted': deleted_count,
            'skipped': len(languages_to_skip),
            'failed': failed_count
        }

    def backup_languages(self, filename: str = "weblate_language_backup.json"):
        print(f"Backing up language information: {filename}")

        languages = self.get_all_languages()

        if languages:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(languages, f, indent=2, ensure_ascii=False)
            print(f"✓ Backup completed: {len(languages)} languages")
        else:
            print("No languages available for backup.")


def main():
    parser = argparse.ArgumentParser(
        description="Weblate language deletion via weblate_utils"
    )
    parser.add_argument(
        "--ini",
        default="weblate.ini",
        help="Path to weblate.ini (default: weblate.ini)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform actual deletion (default: dry run)"
    )
    args = parser.parse_args()

    print("Weblate Language Deletion Tool\n")
    print(f"Mode: {'Actual deletion' if args.apply else 'Dry run'}")

    # Create Weblate language deleter object
    deleter = WeblateLanguageDeleter(args.ini)

    # Test connection
    print("Testing connection to Weblate server")
    try:
        languages = deleter.get_all_languages()
        print(f"Connection successful: {len(languages)} languages found")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # Preview languages to delete
    languages = deleter.get_all_languages()

    if languages:
        print("Currently registered languages:")
        for lang in languages[:10]:
            code = lang.get('code', 'N/A')
            name = lang.get('name', 'N/A')
            print(f"  - {code}: {name}")
    else:
        print("No registered languages found.")

    deleter.delete_all_languages(
        dry_run=not args.apply
    )

    # Final summary
    if args.apply:
        print("\n Deletion completed")
    else:
        print("\n Dry run completed. Use --apply option for actual deletion")


if __name__ == "__main__":
    main()
