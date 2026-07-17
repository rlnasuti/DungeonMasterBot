# Rules and campaign content boundaries

DungeonMasterBot pins mechanics to an explicit ruleset instead of assuming that
all editions of D&D are interchangeable. The current playable baseline is
`srd-5.2.1`, the 2024 rules published in the Creative Commons SRD 5.2.1. Every
rules-backed character and campaign should declare that identifier, and compact
`rules_ref` values point back to the relevant SRD concept without copying whole
rulebook passages into runtime state.

The two older Basic Rules PDFs in the repository root are useful personal
references, but their notices permit printing and photocopying for personal use
rather than redistribution. They are deliberately not the source of the app's
redistributable rules catalog. The pinned SRD source and required CC BY 4.0
attribution live in [`srd/`](srd/).

## Content layers

Keep these three layers separate as the project grows:

1. **Rules catalog** — versioned, redistributable mechanics such as equipment,
   spells, classes, and conditions. Entries have stable IDs, source provenance,
   and a license.
2. **Authoritative game state** — characters, resources, inventory, prepared
   spells, current HP, revealed facts, and scene progress. State references the
   rules catalog by ID and remains valid across voice-session reconnects.
3. **Private campaign packages** — user-supplied, lawfully obtained adventure
   material. Imported text and derived indexes stay private and out of the
   redistributable rules catalog. A future campaign adapter should label every
   chunk with source provenance plus player/DM visibility, then retrieve only the
   smallest scene-local slice the Director needs.

The voice performer should never receive an entire campaign book as one prompt.
The trusted Director owns progression and secrets; it gives Marin a player-safe
scene brief and narrowly scoped behind-the-screen performance cues. This keeps
model context manageable and prevents unrevealed campaign material from leaking
to the players.

## Stable reference format

Rules-backed state uses lowercase references of the form:

```text
srd-5.2.1:<kind>:<slug>
```

Examples include `srd-5.2.1:armor:chain-mail`,
`srd-5.2.1:weapon:longsword`, and `srd-5.2.1:spell:magic-missile`.
The reference identifies a rule; mutable character state such as whether an item
is equipped or a spell is prepared belongs on the character, not in the catalog.
