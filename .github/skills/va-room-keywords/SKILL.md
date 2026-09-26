---
name: va-room-keywords
description: Set up and troubleshoot room assignment using .va/room_keywords.json and folder/filename heuristics.
argument-hint: "root=<property folder> rooms you want"
---

# Room Keywords Setup

Use when rooms are mis-assigned or when starting a new property.

## Procedure
1) Generate a starter file:
- `python -m videoassistant.cli init-rooms --root <ROOT>`

2) Edit `<ROOT>/.va/room_keywords.json`:
- Add rooms you care about.
- Add multiple keywords per room (singular/plural, abbreviations).

3) Improve reliability:
- Prefer room subfolders OR include room keywords in filenames.

## Common pitfalls
- Similar keywords (e.g., "bath" vs "bed") → use more specific tokens.
- Mixed casing/spacing → add variants.

## Success criteria
- `selects.csv` has correct `room` values for the majority of clips.