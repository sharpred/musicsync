# musicsync

Tracks which music files exist on which of your 3 Macs, and reports:

- Tracks you own that are **missing from the iMac** (but present on the Air or mini), with where they actually are.
- Tracks you own that are **missing from all 3 machines** entirely (purchased/ripped but not downloaded anywhere).

"Own" is determined by exporting your iTunes/Music library as the canonical reference — see step 4.

## How it works

One copy of this repo is cloned onto **all three Macs**. Each machine scans its own music folders into a local `snapshot.db` (artist/title/album/path, no audio data). One machine is designated **central** (recommended: Mac mini, since it's most likely to be always-on) — it pulls the other two machines' snapshots over SSH, merges everything into `library.db`, cross-checks against your exported Music library, and writes a report.

```
iMac (agent)  ──┐
MacAir (agent)──┼──(SSH pull)──> MacMini (central) ──> library.db ──> report.html / report.csv
MacMini (central, scans itself too)
```

Everything is plain files (sqlite + a Python stdlib/mutagen script) — no server process, no daemon beyond a monthly launchd timer.

## 1. Install Python 3 on all three Macs

This Mac Air and the Mac mini are on a current macOS and likely already have Python 3. Check:

```sh
python3 --version   # want 3.9 or newer
```

The **High Sierra iMac** does not ship a usable Python 3. Install one from <https://www.python.org/downloads/macos/> — but pin the version carefully: recent releases (3.13, 3.14) raise the installer's minimum macOS version to 10.15+, and will fail at runtime with a `dyld`/`____chkstk_darwin` error if you run them on 10.13. Instead, scroll to **"Looking for a specific release?"** and install **Python 3.9.13** — the last 3.9.x release with a macOS installer, built for macOS 10.9+, so it runs fine on High Sierra. Do **not** rely on Homebrew there; recent Homebrew has dropped High Sierra support.

Multiple Python versions can coexist in `/Library/Frameworks/Python.framework/Versions/`. After installing, confirm `python3 --version` reports 3.9.13 — if it still shows an older/newer stray install, use the versioned binary explicitly instead: `/Library/Frameworks/Python.framework/Versions/3.9/bin/python3.9`.

## 2. Clone this repo and install dependencies, on each machine

```sh
git clone <this-repo-url> ~/musicsync   # or copy the folder however you like
cd ~/musicsync
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

## 5. Set up SSH so the central machine can pull from the other two

On **each of the two non-central Macs** (iMac, MacAir if mini is central):
**System Settings → General → Sharing → Remote Login → On.**

On the **central machine**, generate a dedicated key and distribute it:

```sh
cd ~/musicsync
scripts/setup_ssh.sh paulryanwork@imac.local paulryan@macair.local
```

This creates `~/.ssh/musicsync_ed25519` (used only for this, no passphrase so launchd can run unattended) and copies the public key to both peers via `ssh-copy-id`, then verifies passwordless login works. Update `musicsync.toml`'s `peers` entries with the right `host`/`user`/`remote_snapshot_path` (that's `<their state_dir>/snapshot.db`, default `~/.musicsync/snapshot.db`) if you haven't already.

This is more setup than a plain shared folder, but it's the more secure option: key-based auth instead of a password-protected network share, and nothing is exposed except SSH (which you likely already use).

## 6. Try it manually once, before automating

```sh
# on iMac and MacAir (the peers -- central scans itself as part of run-central below):
python3 -m musicsync.cli scan

# then on MacMini:
python3 -m musicsync.cli run-central
```

`run-central` scans the central machine's own music first, then pulls both peers, merges, re-imports the owned library, and reports -- so the peers need their own `scan` run (and up to date) *before* you run `run-central`, but the central machine doesn't need a separate `scan` step of its own.

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

On the **central machine only**, additionally install the pull+merge+report job (runs an hour later, so both peers have finished scanning). It scans the central machine itself too, so its own scan job above is redundant but harmless to also have installed:

```sh
sed "s|__REPO_DIR__|$REPO_DIR|g" launchd/com.paulryan.musicsync.central.plist > ~/Library/LaunchAgents/com.paulryan.musicsync.central.plist
launchctl load ~/Library/LaunchAgents/com.paulryan.musicsync.central.plist
```

Both run on the 1st of the month (02:00 scan, 03:00 central), as long as the Mac is on/awake around then — if it's asleep at the scheduled time, launchd runs the job the next time it wakes rather than skipping it. Logs land in `logs/` under the repo.

To stop a job: `launchctl unload ~/Library/LaunchAgents/com.paulryan.musicsync.scan.plist`.

## Running it on demand

The monthly run is a baseline, not a limit — run any step manually whenever you want a fresh picture:

```sh
# on iMac or MacAir, whenever you've added music:
cd ~/musicsync && source .venv/bin/activate
python3 -m musicsync.cli scan

# on MacMini, whenever you want an up-to-date report:
cd ~/musicsync && source .venv/bin/activate
python3 -m musicsync.cli run-central
```

Worth doing on demand right after a CD-ripping session or a purchase, rather than waiting for the 1st.

## Reading the report

`~/.musicsync/reports/latest.html` (and `latest.csv`) on the central machine, two sections:

- **Missing from iMac** — you own it, it's on the Air or mini, but not the iMac. Shows which machine(s) have it.
- **Missing from every machine** — you own it per `Library.xml` but it isn't on any of the 3 scanned machines (e.g. a cloud purchase you never downloaded).

Matching is fuzzy (normalized artist+title, ignoring case/punctuation/"remastered"/"feat." noise) since a CD rip's tags rarely match a purchased copy's exactly. It's tuned for "roughly the same song," not byte-for-byte identity — expect the occasional false match/miss on things like live vs. studio versions of the same title.

## Re-running after changes

- Re-scan on a machine any time its music folder changes (or just wait for the daily launchd run).
- Re-export and re-copy `Library.xml` whenever you buy/rip something new.
- `python3 -m musicsync.cli run-central` on the central machine to refresh the report on demand.
