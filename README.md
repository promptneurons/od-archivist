# Original Dissent Archivist

A PN Desktop plugin for browsing the Original Dissent forum archive (2001-2005).

## Overview

- **108,898 posts** across **16,591 threads** from **916 users**
- Full-text search via SQLite FTS
- SPARQL metadata queries via local Virtuoso
- Markdown rendering via local viewer
- Zero cloud dependencies

## Installation

### 1. Install PN Desktop
```bash
# Coming soon
```

### 2. Download the archive DLC
```bash
# SQLite database (~420MB)
curl -O https://s3.amazonaws.com/kitsap/dlc/od-2006/posts_markdown.db

# Place in plugin data directory
mv posts_markdown.db ~/.pn-desktop/plugins/od-archivist/data/
```

### 3. Load metadata into Virtuoso
```bash
# Thread metadata
curl -O https://s3.amazonaws.com/kitsap/dlc/od-2006/od-2006-threads-full.ttl
curl -T od-2006-threads-full.ttl http://localhost:8890/DAV/home/dba/rdf_sink/

# User metadata  
curl -O https://s3.amazonaws.com/kitsap/dlc/od-2006/od-2006-users.ttl
curl -T od-2006-users.ttl http://localhost:8890/DAV/home/dba/rdf_sink/
```

## Usage

### View a thread
```bash
./scripts/get-thread.py 15678
```

### View user activity
```bash
./scripts/get-user.py --name "il ragno"
./scripts/get-user.py 85
```

### Post to viewer
```bash
./scripts/get-thread.py 15678 --post-to-hastebin
# Returns viewer URL
```

## Data Sources

| Source | Description |
|--------|-------------|
| SQLite | Full post content, precomputed indexes |
| Virtuoso | Thread/user metadata for SPARQL queries |
| Wayback | Visual snapshots (linked, not stored) |

## Architecture

```
Request → SQLite query → Markdown → Hastebin → Viewer
                ↓
        Virtuoso (metadata/discovery)
```

## License

Content: Original Dissent forum archive (fair use/preservation)
Code: MIT

## Links

- [PN Desktop](https://github.com/promptneurons/pn-desktop)
- [Wayback: Original Dissent](https://web.archive.org/web/2006/http://www.originaldissent.com/)
