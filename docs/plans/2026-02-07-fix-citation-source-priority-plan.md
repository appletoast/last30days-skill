---
title: "fix: Citation source priority — elevate Reddit/X, tone down web credit"
type: fix
date: 2026-02-07
---

# fix: Citation source priority — elevate Reddit/X, tone down web credit

## Problem

The tool's magic is Reddit + X research with real engagement data, but the output makes it look like a web search wrapper. In the Kanye West test, 5/5 inline citations credited web sources (Rolling Stone, Billboard, etc.) while X's 29 posts got one vague mention. Users see a wall of "per Rolling Stone" and think "I could have Googled this."

**Root causes in SKILL.md:**

1. The GOOD citation example is `"per Rolling Stone"` — a web source! This models the wrong behavior.
2. No explicit "prefer @handles and r/subreddits" citation priority rule
3. The stats box shows `🌐 Web: 30+ pages` which visually dominates
4. The "What I learned" section has no instruction to lead with Reddit/X voices

## Proposed Solution — 4 SKILL.md changes

### Change 1: Add explicit citation priority rule

In the CITATION RULE section (~line 195), add a priority order:

```
CITATION PRIORITY (most to least preferred):
1. @handles from X — "per @handle" (these prove the tool's unique value)
2. r/subreddits from Reddit — "per r/subreddit"
3. Web sources — ONLY when Reddit/X don't cover that specific fact

The tool's value is surfacing what PEOPLE are saying, not what journalists wrote.
When both a web article and an X post cover the same fact, cite the X post.
```

### Change 2: Fix the GOOD/BAD citation examples

Current GOOD example teaches web citation:
```
GOOD: "His album BULLY is set for March 20 via Gamma, per Rolling Stone."
```

Replace with Reddit/X-first examples:
```
BAD: "His album is set for March 20 (per Rolling Stone; Billboard; Complex)."
GOOD: "His album BULLY drops March 20 — fans on X are split on the tracklist, per @honest30bgfan_"
GOOD: "Ye's apology got massive traction on r/hiphopheads with 2K+ upvotes"
OK (web only when needed): "The Hellwatt Festival runs July 4-18 at RCF Arena, per Billboard"
```

### Change 3: Reframe stats box — downplay web prominence

Current template gives web equal billing:
```
├─ 🌐 Web: {N} pages │ {domain1}, {domain2}, {domain3}
```

Change to something that positions web as supplementary:
```
├─ 🌐 Web: {N} pages (supplementary)
```

Remove the domain list from the stats tree — it makes web look like the main source. The domains already got credit in any inline citations where they were used.

### Change 4: Add "lead with voices" instruction in synthesis

In the "What I learned" template section, add:

```
**Lead with people, not publications.** Start each topic with what Reddit/X
users are saying/feeling, then add web context if needed. The user came here
for the conversation, not the press release.
```

## Files to Change

- `SKILL.md` — 4 edits (citation priority, examples, stats template, synthesis instruction)

## Acceptance Criteria

- [x] Citation examples model @handle and r/subreddit format, not web domains
- [x] Explicit priority rule: X > Reddit > Web for citations
- [x] Stats box positions web as "supplementary"
- [x] Synthesis instructions say to lead with people/voices
- [x] No changes to the Python script or actual research quality
- [x] Synced to `~/.claude/skills/last30days/SKILL.md`

## What This Does NOT Change

- The actual research still runs Reddit + X + WebSearch in parallel
- WebSearch results still inform the synthesis (they're great for facts)
- The quality of the output stays the same — this is purely about attribution framing
- The Judge Agent still weights Reddit/X higher internally

## Why This Works

It's a presentation fix, not a data fix. The research already prioritizes Reddit/X internally (Judge Agent rules). The problem is the citation instructions then undo that by modeling web citations. By flipping the citation examples and adding a priority rule, the agent will naturally attribute facts to @handles and r/subreddits first, making the output feel like "I talked to the internet for you" rather than "I Googled this for you."
