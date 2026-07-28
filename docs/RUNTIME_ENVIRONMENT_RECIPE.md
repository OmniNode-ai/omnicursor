# C3 runtime environment recipe

Reproducible bring-up for the **local runtime-proof environment**: the omnicursor
`compose.yaml` stack plus a host-side ONEX kernel (`onex-runtime`) with the
omniintelligence domain plugin active, able to consume
`onex.cmd.omniintelligence.cursor-hook-event.v1` end-to-end.

This is the environment behind the C3 receipt
([PR #12 comment](https://github.com/OmniNode-ai/omnicursor/pull/12#issuecomment-5098283862)).
Every non-obvious step below was learned the hard way; the Troubleshooting table maps
each failure signature to its fix. Tracked under the OMN-14749 parity epic.

## Topology

- **Containers** (from `compose.yaml`): Redpanda (`:19092` external Kafka listener,
  `:19644` admin), Postgres 16 (`:5436`), Valkey (`:16379`), and the three
  intelligence services (`:18091`–`:18093` health).
- **Host process**: the ONEX kernel (`onex-runtime` = `omnibase_infra.runtime.kernel:main`),
  run from a sibling `omniintelligence` checkout's venv, with cwd inside a sibling
  `omnibase_infra` checkout.

Dev credentials referenced below are the public compose defaults, not secrets.

## 1. Compose stack

```bash
# .env next to compose.yaml (gitignored)
REDPANDA_MEMORY=6G          # default 1G caps Redpanda at 256 partitions; kernel needs ~1080
OMNIINTELLIGENCE_REF=dev    # ref the intelligence images build from

docker compose up -d
```

One-time Redpanda core-cap raise (persists in the data volume):

```bash
docker exec <redpanda-container> rpk cluster config set topic_partitions_per_shard 4000
```

Both limits must be raised. The memory cap fails topic creation with
`Refusing to create N partitions ... would exceed memory limit`; the per-shard core cap
(default 1000 with `--smp 1`) fails it with a core-limit error. The kernel creates
~180 topics × 6 partitions.

## 2. Database migrations

The kernel's DB-ownership handshake (B1) requires `db_metadata` with
`owner_service = omniintelligence`, and the schema-fingerprint check (B2) requires the
full schema. Apply all of `deployment/database/migrations/*.sql` from omniintelligence
(32 files at time of writing) against the `omniintelligence` database on `:5436`,
in filename order.

Ordering caveat from omniintelligence's CLAUDE.md: `omnibase_infra` migrations own
`idempotency_records` and must run before first kernel boot, or B2 auto-stamps a
fingerprint that excludes the table and every later boot fails with
`SchemaFingerprintMismatchError`.

## 3. Kernel venv

```bash
cd ~/omninode/omniintelligence
uv sync --frozen            # dev lock pins compatible omnibase_infra/omnimarket

# REQUIRED after every uv sync — sync restores the entry points and re-breaks boot:
.venv/bin/python -m omnibase_infra.runtime.strip_runtime_entry_points \
  --allowed-distribution omnibase-infra --group onex.nodes --group onex.node_package
```

The strip is needed because omniintelligence and omnimarket ship function-style
`handler_routing` contracts that the pinned infra's class-only auto-wiring cannot load
(`CLASS_NOT_FOUND (HANDLER_LOADER_011)` at boot).

## 4. Contracts dir

The kernel needs `ONEX_CONTRACTS_DIR` containing `runtime/runtime_config.yaml`:

```yaml
# $ONEX_CONTRACTS_DIR/runtime/runtime_config.yaml
name: omniintelligence
```

Without it boot fails with `RuntimeHostProcess requires 'service_name'`. Keep this
directory somewhere persistent (not `/tmp`).

## 5. Kernel launch

```bash
cd ~/omninode/omnibase_infra   # cwd REQUIRED: kernel reads a repo-relative handler
                               # contract (src/omnibase_infra/contracts/handlers/db/...)
KAFKA_BOOTSTRAP_SERVERS=localhost:19092 \
KAFKA_BROKER_ALLOWLIST=localhost: \
KAFKA_TIMEOUT_SECONDS=120 \
OMNIINTELLIGENCE_DB_URL=postgresql://postgres:<dev-password>@localhost:5436/omniintelligence \
ONEX_CONTRACTS_DIR=<contracts-dir> \
ONEX_LOG_LEVEL=INFO ONEX_ENVIRONMENT=local \
setsid nohup ~/omninode/omniintelligence/.venv/bin/onex-runtime \
  > ~/.omnicursor/kernel.log 2>&1 < /dev/null &
```

`OMNIINTELLIGENCE_DB_URL` is the activation gate for `PluginIntelligence` — unset, the
kernel boots "successfully" with no intelligence consumers at all. `setsid` detaches the
kernel from the launching session so terminal/session teardown cannot reap it (a systemd
user unit is the better long-term supervisor).

## 6. Verify

```bash
# Plugin actually activated (this line is the go/no-go):
grep "plugins activated" ~/.omnicursor/kernel.log     # want "1/5 plugins activated"

# Hook-event consumer joined (takes ~10-20 min; groups are named <group>.__t.<topic>):
docker exec <redpanda-container> rpk group list | grep "cursor-hook-event"
# want state Stable, group omniintelligence-hooks.__t.onex.cmd.omniintelligence.cursor-hook-event.v1
```

Wire format for publishing proof events: the **bare six-key canonical dict** from
`.cursor/hooks/lib/canonical_event.py::build_cursor_event()` — not an
`ModelEventEnvelope` wrapper (envelope keys get merged into the payload consumer-side
and rejected as `extra_forbidden`). `session_id` must be a UUID for the
`agent_actions` persistence path. Confirm delivery from the producer's delivery
report (partition/offset), never from a bare `flush()` returning.

## Troubleshooting

| Signature | Cause | Fix |
|---|---|---|
| Kafka/Postgres clients: TCP connects but `Disconnected: connection reset by peer (APIVERSION_QUERY)` / connect timeout, while in-container checks pass | Stale Docker Desktop (WSL2) host->container port-forward after long idle/sleep | `docker restart` the affected container, re-verify with a real protocol handshake, then restart the kernel |
| Kernel log: `0/5 plugins activated`, `Failed to initialize Intelligence plugin` | DB unreachable **at boot** (activation is boot-only, never retried) | Verify Postgres from the host first, then restart the kernel |
| `CLASS_NOT_FOUND (HANDLER_LOADER_011)` at boot | `uv sync` restored the stripped entry points | Re-run the strip command (step 3) |
| `RuntimeHostProcess requires 'service_name'` | Missing `runtime/runtime_config.yaml` under `ONEX_CONTRACTS_DIR` | Step 4 |
| `Contract file not found: src/omnibase_infra/contracts/...` | Kernel cwd is not the omnibase_infra repo root | Step 5 cwd requirement |
| `Refusing to create N partitions` / core-limit error | Redpanda memory/per-shard caps | Step 1 (both raises) |
| Kernel silently gone after a session/terminal closed | Kernel was parented to the session's process tree | Launch with `setsid` (step 5) |
| `pgrep -f onex-runtime` says alive when it is not | Matches the checking shell's own command line | Use a self-escaping pattern, e.g. `pgrep -f "onex-runtim[e]"` |
| Consumer group `omniintelligence-hooks` (bare, no `.__t.` suffix) looks Dead | Legacy artifact; real per-topic groups are `<group>.__t.<topic>` | Check the suffixed group |
