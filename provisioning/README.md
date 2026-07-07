# Provisioning the shared emit daemon

OmniCursor emits events through the **shared platform emit daemon**
(`omnimarket.nodes.node_emit_daemon` — the exact same daemon and Unix-socket
wire protocol OmniClaude uses; there is no Cursor-specific transport variant).
This directory documents how the daemon gets provisioned on a Cursor host and
ships optional OS templates for durable ownership.

## How the daemon starts (three tiers)

1. **Primary — `sessionStart` ensure (automatic).** `session-start.py` fast-pings
   the daemon and, when it is down, spawns it detached via
   `.cursor/hooks/lib/daemon_ensure.py`. Never blocks the hook; degrades to a
   no-op when no suitable interpreter is configured.
2. **Fallback — first-prompt ensure (automatic).** For surfaces where
   `sessionStart` never fires (older Cursor builds, CLI), `user-prompt-submit.py`
   runs the same ensure once per conversation, on the first prompt.
3. **Optional — OS service (this directory).** A launchd agent (macOS) or
   systemd user unit (Linux) that owns the daemon independently of Cursor
   sessions. Install only if you want the daemon up at login.

All three run the same canonical command and coexist safely: the daemon exits
immediately when another instance already owns `~/.omnicursor/emit.pid`, and
the hook ensure never spawns while a live daemon answers the socket ping.

## The pinned contract (do not vary these)

| Parameter | Value | Why |
|---|---|---|
| Socket | `~/.omnicursor/emit.sock` — daemon `--socket-path` **and** hooks (`OMNICURSOR_EMIT_SOCKET`) | The two sides read *different* env vars and do not cross-read; the daemon's own default is `/tmp/onex-emit.sock`, which would silently drop 100% of events. |
| Kafka | `--kafka-bootstrap-servers localhost:19092`, **always passed** | Without it the daemon runs spool-only: ACKs every event, forwards nothing. Spool-only is a failure mode, not a degrade. |
| Registry | `<repo>/config/event_registry/omnicursor.yaml` | omnimarket bundles no omnicursor registry; every fan-out rule must declare a `tier` or the registry refuses to load. |
| Interpreter | `OMNICURSOR_DAEMON_PYTHON` → a venv with `omnimarket` installed | The bare `python3` that runs the hooks does **not** have omnimarket; hooks stay stdlib-only by design. |
| State dir | `~/.omnicursor/` (`emit.pid`, `event-spool/`, `logs/emit-daemon.log`) | One Cursor-owned home for daemon state. |

## Prerequisite (all tiers)

An interpreter with omnimarket installed, exported for the hooks:

```bash
# e.g. a dedicated venv
python3.12 -m venv ~/.omnicursor/daemon-venv
~/.omnicursor/daemon-venv/bin/pip install <omnimarket>   # per platform install docs
export OMNICURSOR_DAEMON_PYTHON="$HOME/.omnicursor/daemon-venv/bin/python"
```

Without `OMNICURSOR_DAEMON_PYTHON` (or a bundled `.venv/bin/python` that has
omnimarket), the automatic tiers degrade to a clean no-op — hooks keep working,
nothing is emitted.

## macOS — launchd user agent

```bash
sed -e "s|__DAEMON_PYTHON__|$OMNICURSOR_DAEMON_PYTHON|g" \
    -e "s|__OMNICURSOR_REPO__|$(pwd)|g" \
    provisioning/com.omnicursor.emit-daemon.plist \
    > ~/Library/LaunchAgents/com.omnicursor.emit-daemon.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.omnicursor.emit-daemon.plist
```

Remove with:

```bash
launchctl bootout gui/$(id -u)/com.omnicursor.emit-daemon
rm ~/Library/LaunchAgents/com.omnicursor.emit-daemon.plist
```

## Linux — systemd user unit

```bash
mkdir -p ~/.config/systemd/user
sed -e "s|__DAEMON_PYTHON__|$OMNICURSOR_DAEMON_PYTHON|g" \
    -e "s|__OMNICURSOR_REPO__|$(pwd)|g" \
    provisioning/omnicursor-emit-daemon.service \
    > ~/.config/systemd/user/omnicursor-emit-daemon.service
systemctl --user daemon-reload
systemctl --user enable --now omnicursor-emit-daemon.service
```

Remove with:

```bash
systemctl --user disable --now omnicursor-emit-daemon.service
rm ~/.config/systemd/user/omnicursor-emit-daemon.service
```

## Verifying

```bash
# Daemon answers the wire-protocol ping on the pinned socket:
printf '{"command":"ping"}\n' | nc -U ~/.omnicursor/emit.sock

# It was started WITH a broker (spool-only = misprovisioned):
ps -ww ax | grep node_emit_daemon | grep -- --kafka-bootstrap-servers

# Startup problems land here:
tail ~/.omnicursor/logs/emit-daemon.log
```
