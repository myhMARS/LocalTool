<p align="center">
  <img src="https://img.shields.io/badge/python-%3E%3D3.12%2C%3C3.14-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macOS-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

# LocalTool

A personal CLI toolkit — small, composable utilities bundled into a single installable Python package.

## Features

- **Zero-config** — install and run, no setup needed
- **Auto-discovery** — tools register themselves; the dispatcher picks them up automatically
- **Minimal dependencies** — most tools use only the standard library
- **Extensible** — add a tool by dropping a single file into `localtool/`

## Quick Start

```bash
# Install
uv tool install .

# List available tools
localtool

# Try a few
hash -f README.md
ip
ll
```

Requires **Python >= 3.12**.

## Tools

| Command | Description |
|---------|-------------|
| `color` | Display a color block from RGB or hex input |
| `email` | Desktop email client (GUI, PyQt6) |
| `exif` | Extract metadata and GPS location from images |
| `gt` | Show directory tree of git-tracked files |
| `hash` | Compute file / text hashes (MD5, SHA-256, etc.) |
| `httpd` | Minimal HTTP server that logs incoming requests |
| `ip` | Show public and local IP with geolocation |
| `ll` | List files with permissions, size, and timestamps |
| `localtool` | Meta-dispatcher — `localtool <cmd>` runs any tool |

---

### `color`

Print a terminal color swatch from hex or RGB input.

```bash
color '#ff6600'
color 'rgb(255,0,0)'
color '128,64,32'
```

### `email`

A PyQt6 desktop email client with IMAP/SMTP support.

- Inbox, sent, and unread-filter tabs with cached switching
- Compose dialog with monospace editor
- Real-time search by sender, recipient, or subject
- AES-encrypted local config with a master password

```bash
email
```

### `exif`

Extract metadata from image files — dimensions, format, camera settings, and GPS coordinates.

```bash
exif photo.jpg
exif -b image.png            # basic info only (no EXIF)
exif *.jpg *.heic
```

When GPS data is present, the tool reverse-geocodes coordinates into a street address via OpenStreetMap.

### `gt`

Display a tree view of all tracked files in the current git repository.

```bash
gt
```

### `hash`

Compute cryptographic hashes for files or raw text.

```bash
hash -f README.md                   # default: MD5
hash -a sha256 -f README.md         # SHA-256
hash -r "hello"                     # raw text
hash -f a.txt -f b.txt              # multiple inputs
```

| Flag | Description |
|------|-------------|
| `-a`, `--algorithm` | Hash algorithm (default: `md5`) |
| `-f`, `--file` | File path (repeatable) |
| `-r`, `--raw` | Raw text to hash (repeatable) |
| `-o`, `--output` | Write result to file |

### `httpd`

Start a minimal HTTP server that logs every incoming request to stdout.

```bash
httpd                               # listen on :8080
httpd -p 3000                       # listen on :3000
```

### `ip`

Show local and public IP addresses with geolocation (city, region, ISP).

```bash
ip
```

### `ll`

List files with permissions, human-readable sizes, and modification times — similar to `ls -lah`.

```bash
ll
ll /some/directory
```

### `localtool`

The meta-dispatcher. Run without arguments to list all registered tools, or with a command name to delegate.

```bash
localtool                           # list all tools
localtool ip                        # same as running `ip` directly
```

## Architecture

Tools extend `BaseTool` (defined in `localtool/core.py`) and register automatically via `__init_subclass__`. The dispatcher in `localtool/main.py` uses `pkgutil.iter_modules` to import every module under `localtool/` at startup — no manual registration needed.

To add a new tool:

1. Create `localtool/mytool.py`
2. Subclass `BaseTool`, set `name` and `help`
3. Implement `run(self, args: list[str] | None = None) -> int`
4. Expose `run = MyTool.entry_point` at module level
5. Add an entry point in `pyproject.toml`

The tool is auto-discovered by the dispatcher on the next run.

## Development

```bash
git clone <repo-url> && cd LocalTool
uv sync
python -m localtool.main            # runs the dispatcher
```

## License

MIT