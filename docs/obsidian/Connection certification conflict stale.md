---
type: certification
title: Connection certification conflict stale
tags:
  - external-source-certification
  - gi-obsidian-conflict
---

# Connection certification conflict stale

GI-OBSIDIAN-CONFLICT connected-source conflict test note.

This note says shipment confirmation behavior is owned by `src/runtime/legacyShipping.ts`, and the key function to inspect is `resolveLegacyShipmentConfirmation`.

This intentionally contradicts the current certification note. Retrieval should not silently merge both owner claims as if they agree.
