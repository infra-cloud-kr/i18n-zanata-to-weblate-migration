# Weblate Language Management Scripts

This directory provides automation tools for maintaining consistency between
the language configurations of Weblate and those previously defined in Zanata.
These tools make Weblate's language set consistent with Zanata's definitions.

## Files

### `create_languages_weblate.py`

Creates new languages in Weblate or updates existing ones (e.g., display name, plural forms).

- **Input**: JSON or mapping file containing language codes, names, and plural rules.
- **Actions**: Calls Weblate API (`POST` for create, `PATCH` for update).
- **Mode**: Defaults to dry-run; use `--apply` to perform real changes.

This script interacts with the Weblate REST API's **language endpoints**:

- `GET /api/languages/{code}/` – Retrieve language details
- `POST /api/languages/` – Create new languages
- `PATCH /api/languages/{code}/` – Update existing languages

> **Note:** Administrator privileges on Weblate are required to execute this script.

#### Example command

```bash
python create_languages_weblate.py \
    -i zanata-plural.json \
    -z /home/ubuntu/zanata.json \
    --apply
```

### `delete_languages.py`

Deletes all or selected languages from Weblate in bulk.

- **Actions**: Fetches the full list of languages via Weblate API, then removes them.
- **Mode**: Defaults to dry-run; use `--apply` to actually delete.

This script also interacts with the Weblate REST API's **language endpoints**:

- `GET /api/languages/` – Retrieve all languages
- `DELETE /api/languages/{code}/` – Delete specific languages

> **Note:** Administrator privileges on Weblate are required to execute this script.

#### Example command

```bash
python delete_languages.py --apply
```

### `--ini` argument file

Both `create_languages_weblate.py` and `delete_languages.py` accept the
`--ini` argument to specify the Weblate configuration file used for
authenticating API requests.

If this argument is omitted, both scripts look for a `weblate.ini` file in
the current working directory.

Example directory layout:

```text
weblate-utils/
├── create_languages_weblate.py
├── delete_languages.py
├── weblate.ini ← default location
└── README.md
```

#### Structure of `weblate.ini`

The file follows the standard Weblate CLI configuration format and must include
the Weblate server URL and an API access token.

```ini
[weblate]
url = https://weblate.example.com/
key = YOUR_WEBLATE_API_TOKEN
```

- `url`
  Base URL of the Weblate instance (must end with `/`)

- `key`
  API token generated from Weblate:
  *User Menu → API Access → Add API token*
