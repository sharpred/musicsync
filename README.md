# musicsync

Tracks which music files exist on which of your Macs, and reports:

- Tracks you own that are **missing from the iMac** (but present on another machine), with where they actually are -- plus a ready-to-import `.m3u8` playlist of exactly those tracks (see "Playlists" below).
- Tracks you own that are **missing from every machine** entirely (purchased/ripped but not downloaded anywhere).
- If you run Plex, gaps between your **Mac collection and your Plex library** (see "Syncing a Plex server" below).

Works with any number of machines — add more any time by adding another `[[peers]]` block (see "Adding another machine" below).

"Own" is determined by exporting your iTunes/Music library as the canonical reference — see step 4.

## How it works

One copy of this repo is cloned onto **every machine**. Each machine scans its own music folders into a local `snapshot.db` (artist/title/album/path, no audio data). One machine is designated **central** (recommended: Mac mini, since it's most likely to be always-on) — it pulls every other machine's snapshot over SSH, merges everything into `library.db`, cross-checks against your exported Music library, and writes a report.

```
iMac (agent)   ──┐
MacAir (agent) ──┼──(SSH pull)──────> MacMini (central) ──> library.db ──> report.html / report.csv
MacPro (agent) ──┘                          ^
Plex (minisforum.local) ────(HTTP API)──────┘
MacMini (central, scans itself too)
```

Everything is plain files (sqlite + a Python stdlib/mutagen script) — no server process, no daemon beyond a monthly launchd timer.

### Two separate folders — don't confuse them

- **The repo (this code)** can live *anywhere* on each machine — wherever you cloned or copied it. This README writes `~/musicsync` in commands purely as a short example path; your actual clone might be at `/Users/paulryan/Documents/projects.nosync/python/musicsync`, or anywhere else, and it doesn't need to match on every machine. Wherever you see `cd ~/musicsync` below, substitute wherever you actually put it on that machine.
- **`~/.musicsync`** (note the leading dot — a different, unrelated path) is created *automatically* and holds only generated artifacts: `snapshot.db`, pulled peer snapshots, the merged `library.db`, the `Library.xml` you copy in, and the `reports/` folder. It never contains code, and you shouldn't need to touch it directly. It's configurable via `state_dir` in `musicsync.toml` if you want it somewhere else, but the default is fine for almost everyone.

## 1. Install Python 3 on all three Macs

This Mac Air and the Mac mini are on a current macOS and likely already have Python 3. Check:

```sh
python3 --version   # want 3.9 or newer
```

The **High Sierra iMac** does not ship a usable Python 3. Install one from <https://www.python.org/downloads/macos/> — but pin the version carefully: recent releases (3.13, 3.14) raise the installer's minimum macOS version to 10.15+, and will fail at runtime with a `dyld`/`____chkstk_darwin` error if you run them on 10.13. Instead, scroll to **"Looking for a specific release?"** and install **Python 3.9.13** — the last 3.9.x release with a macOS installer, built for macOS 10.9+, so it runs fine on High Sierra. Do **not** rely on Homebrew there; recent Homebrew has dropped High Sierra support.

Multiple Python versions can coexist in `/Library/Frameworks/Python.framework/Versions/`. After installing, confirm `python3 --version` reports 3.9.13 — if it still shows an older/newer stray install, use the versioned binary explicitly instead: `/Library/Frameworks/Python.framework/Versions/3.9/bin/python3.9`.

## 2. Clone this repo and install dependencies, on each machine

```sh
git clone <this-repo-url> ~/musicsync   # pick any path/location you like -- ~/musicsync is just this README's example
cd ~/musicsync                          # cd into wherever you actually put it, every time you see this below
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

(`tomli` in requirements.txt is only installed on Python < 3.11, where `tomllib` isn't in the stdlib yet — e.g. the iMac if it ends up on Python 3.9/3.10.)

## 3. Configure each machine

```sh
cp config.example.toml musicsync.toml
```

Edit `musicsync.toml` **on each machine separately** (it's gitignored — never committed, since paths differ per machine):

- **iMac** (user `paulryanwork`): `host_label = "iMac"`, `role = "agent"`, `music_roots` pointing at `~/Music/iTunes/iTunes Media/Music` (the iTunes location — that's what's still running on High Sierra).
- **MacAir**: `host_label = "MacAir"`, `role = "agent"`, `music_roots` for whatever's local here.
- **MacMini**: `host_label = "MacMini"`, `role = "central"`, plus the `peers` list and `owned_library_xml` (see step 4).

All three should set `primary_host = "iMac"` — that's what "missing from iMac" is measured against.

## 4. Export your library as the "what I own" reference

On **whichever Mac has your fullest library view** (probably the iMac) — this is **iTunes** on High Sierra, or **Music.app** on newer macOS. Same menu, same underlying XML format either way:

**(iTunes or Music.app) → File → Library → Export Library...** → save as `Library.xml`.

Important: this must be **Export Library**, not **Export Playlist** on the "Purchased" smart list. Export Playlist writes an `.m3u8` of local file paths — any purchased track you haven't downloaded has no local path, so it's silently dropped. Export Library writes one entry per track with Name/Artist/Album *regardless* of download status, which is what lets this tool detect "owned but not downloaded anywhere."

Copy that `Library.xml` to the central machine (MacMini) at the path set in `owned_library_xml` in its `musicsync.toml` (default: `~/.musicsync/Library.xml`).

Re-export and re-copy this periodically as your library/purchases change.

## 5. Set up SSH so the central machine can pull from every peer

On **each non-central Mac**:
**System Settings → General → Sharing → Remote Login → On.**

On the **central machine**, generate a dedicated key and distribute it to every peer in one go:

```sh
cd ~/musicsync
scripts/setup_ssh.sh paulryanwork@imac.local paulryan@macair.local
```

This creates `~/.ssh/musicsync_ed25519` (used only for this, no passphrase so launchd can run unattended) and copies the public key to each peer listed via `ssh-copy-id`, then verifies passwordless login works. Update `musicsync.toml`'s `peers` entries with the right `host`/`user`/`remote_snapshot_path` (that's `<their state_dir>/snapshot.db`, default `~/.musicsync/snapshot.db`) if you haven't already.

This is more setup than a plain shared folder, but it's the more secure option: key-based auth instead of a password-protected network share, and nothing is exposed except SSH (which you likely already use).

## 6. Try it manually once, before automating

```sh
# on every peer machine (central scans itself as part of run-central below):
python3 -m musicsync.cli scan

# then on the central machine:
python3 -m musicsync.cli run-central
```

`run-central` scans the central machine's own music first, then pulls every peer, merges, re-imports the owned library, and reports -- so each peer needs its own `scan` run (and up to date) *before* you run `run-central`, but the central machine doesn't need a separate `scan` step of its own.

Open `~/.musicsync/reports/latest.html` on the mini in a browser. Check the counts look sane before moving on to scheduling.

## 7. Automate with launchd (monthly)

On **every** machine, install the monthly scan job:

```sh
cd ~/musicsync
mkdir -p logs
REPO_DIR="$(pwd)"
sed "s|__REPO_DIR__|$REPO_DIR|g" launchd/com.paulryan.musicsync.scan.plist > ~/Library/LaunchAgents/com.paulryan.musicsync.scan.plist
launchctl load ~/Library/LaunchAgents/com.paulryan.musicsync.scan.plist
```

On the **central machine only**, additionally install the pull+merge+report job (runs an hour later, so every peer has finished scanning). It scans the central machine itself too, so its own scan job above is redundant but harmless to also have installed:

```sh
sed "s|__REPO_DIR__|$REPO_DIR|g" launchd/com.paulryan.musicsync.central.plist > ~/Library/LaunchAgents/com.paulryan.musicsync.central.plist
launchctl load ~/Library/LaunchAgents/com.paulryan.musicsync.central.plist
```

Both run on the 1st of the month (02:00 scan, 03:00 central), as long as the Mac is on/awake around then — if it's asleep at the scheduled time, launchd runs the job the next time it wakes rather than skipping it. Logs land in `logs/` under the repo.

To stop a job: `launchctl unload ~/Library/LaunchAgents/com.paulryan.musicsync.scan.plist`.

## Running it on demand

The monthly run is a baseline, not a limit — run any step manually whenever you want a fresh picture:

```sh
# on any peer machine, whenever you've added music:
cd ~/musicsync && source .venv/bin/activate
python3 -m musicsync.cli scan

# on the central machine, whenever you want an up-to-date report:
cd ~/musicsync && source .venv/bin/activate
python3 -m musicsync.cli run-central
```

Worth doing on demand right after a CD-ripping session or a purchase, rather than waiting for the 1st.

## Reading the report

`~/.musicsync/reports/latest.html` (and `latest.csv`) on the central machine, two sections:

- **Missing from iMac** — you own it, it's on another machine, but not the iMac. Shows which machine(s) have it.
- **Missing from every machine** — you own it per `Library.xml` but it isn't on any scanned machine (e.g. a cloud purchase you never downloaded).
- **On your Macs but not in Plex** / **In Plex but not on any Mac** — only shown if `[plex]` is configured. A direct gap check between your Mac collection and your Plex library, independent of `Library.xml` (so it also catches things never added to your iTunes/Music library at all).

Matching is fuzzy (normalized artist+title, ignoring case/punctuation/"remastered"/"feat." noise) since a CD rip's tags rarely match a purchased copy's exactly. It's tuned for "roughly the same song," not byte-for-byte identity — expect the occasional false match/miss on things like live vs. studio versions of the same title. One specific thing it now corrects for: CD rips sourced from CDDB/Gracenote sometimes embed the track number right into the title tag ("02 Baltimore" instead of "Baltimore") -- that's stripped before matching, title-only (never from artist names, so numeric artists like "3 Doors Down" are untouched).

## Diagnosing a false missing/present result

If the report says a track is missing and you know it isn't (or vice versa), run this on the central machine to see exactly what's stored for it:

```sh
python3 -m musicsync.cli debug-track "Baltimore"
```

This prints every `owned` row and every `files` row whose artist/title/album contains that text, each with its computed `track_key`. If a track should match but doesn't, the `track_key` values will differ -- compare the raw `artist`/`title` fields above them to see which one disagrees (a stray word, a tag that's blank on one side, a track-number prefix, etc.). No matches under "files rows" at all usually means that machine's `scan` never covered the file -- check its `music_roots`.

## Playlists of what's missing from the iMac

`python3 -m musicsync.cli playlists` (also runs automatically as part of `run-central`) writes a real, importable `.m3u8` playlist for every "missing from iMac" track -- one file per source machine, at `~/.musicsync/playlists/missing_from_iMac__<host>.m3u8` on the central machine.

This only covers tracks that are **missing from iMac but present somewhere else** -- a playlist can only point at a file that actually exists, so there's nothing to generate for "missing from every machine" (no file anywhere = nothing to link to; keep using the CSV/HTML list for those, to search/re-download manually). Plex is excluded from playlist generation for the same reason: those paths live on the Plex server's filesystem, which doesn't run Music.app/iTunes.

To use one: copy the relevant `.m3u8` file to the machine named in its filename (it's useless anywhere else, since the paths inside are only valid on that machine), then on that machine open **Music.app/iTunes → File → Library → Import Playlist...** and pick it. You'll get a playlist of exactly the tracks the iMac is missing, ready to select and copy across.

## Syncing a Plex server

If you run Plex (e.g. on a Minisforum mini-PC or any other non-Mac box), musicsync can pull its music library in too — via Plex's own HTTP API, not an installed agent, since that box likely isn't macOS and may have no Python/SSH set up at all. Once configured, Plex just becomes another host: it folds into "missing from iMac"/"missing everywhere" (a track in Plex is no longer "missing everywhere"), plus you get the dedicated Mac-vs-Plex gap section above.

1. **Find your Plex token.** Sign into the Plex web app, open any track's "Get Info" → "View XML" link, and copy the `X-Plex-Token=...` value from the URL. (Plex's support site has a walkthrough: search "Finding an authentication token X-Plex-Token".)
2. **On the central machine's `musicsync.toml`**, add:
   ```toml
   [plex]
   base_url = "http://minisforum.local:32400"
   token = "YOUR_PLEX_TOKEN"
   library_section = "Music"   # must match your music library's name in Plex
   host_label = "Plex"
   ```
3. Run `python3 -m musicsync.cli import-plex` on its own to test it, or just `run-central` to include it in the full pipeline. You should see `Imported N tracks from Plex (...)`.

No change needed on the Plex box itself — the central machine just needs network access to it on port 32400 (the default Plex port).

## Adding another machine

There's no limit on how many machines this tracks — `peers` in the central `musicsync.toml` is just a list, and every entry gets pulled, merged, and reported on. To add one:

1. **On the new machine**: install Python 3, clone/copy this repo, `pip install -r requirements.txt`, turn on Remote Login (System Settings → General → Sharing), and create its own `musicsync.toml` from `config.example.toml` — `role = "agent"`, a `host_label` not already used by another machine, and its `music_roots`.
2. **On the central machine**: distribute the existing SSH key to the new machine (reuses the key already at `~/.ssh/musicsync_ed25519` rather than generating a new one):
   ```sh
   scripts/setup_ssh.sh newuser@newmachine.local
   ```
3. **On the central machine's `musicsync.toml`**: add a `[[peers]]` block for it (there's a commented-out template at the bottom of `config.example.toml`).
4. Run `python3 -m musicsync.cli scan` on the new machine, then `python3 -m musicsync.cli run-central` on the central machine to confirm it shows up in the merged report.
5. If you want it on the monthly schedule too, install the scan launchd job on it (step 7).

## Re-running after changes

- Re-scan on a machine any time its music folder changes (or just wait for the daily launchd run).
- Re-export and re-copy `Library.xml` whenever you buy/rip something new.
- `python3 -m musicsync.cli run-central` on the central machine to refresh the report on demand.
