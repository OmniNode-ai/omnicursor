# Checkout development configuration

`hooks.json` is a development shim for the seven scripts in `../hooks/scripts/`.
It uses workspace-relative commands. `settings.json` is project configuration.
Neither file is part of the installed payload.

Disable the installed OmniCursor plugin while using this shim. To test the plugin,
reinstall the copy and use a foreign workspace without OmniCursor project hooks.
The two sources are tested independently; there is no automatic deduplication.

[Development modes and trade-offs](../docs/QUICKSTART.md#development-hook-source)
· [Canonical plugin hooks](../hooks/hooks.json)
