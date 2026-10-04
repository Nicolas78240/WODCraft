# WODCraft — launch copy

Ready-to-paste copy for the WODCraft launch. Facts come from the README, the CHANGELOG and the site.
House rule: the only DSL snippet in this file is Fran, which compiles. Do not add another one without running `wodc check` on it.

Links used everywhere:

- Site: https://wodcraft.dev (English), https://wodcraft.dev/fr/ (French)
- Repo: https://github.com/Nicolas78240/WODCraft
- Install: `pip install wodcraft` (1.1.0)

The Fran snippet and the real diagnostics output, reused below:

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

```
tuesday.wod:4:15: error E032: Box jump takes a height (in, cm), not a load.
tuesday.wod:5:3: warning W100: 1 m of Run is very short.
    help: did you mean miles ('1 mi')?
tuesday.wod:6:6: error E020: Unknown movement 'Pul-up'.
    help: did you mean 'Pull-up' or 'L-pull-up'?
```

---

## 1. Show HN

### Title (pick one, all under 80 characters)

1. `Show HN: WODCraft – A language for writing workouts, with a real compiler` (72)
2. `Show HN: WODCraft – Write the WOD like on the whiteboard, a compiler checks it` (77)
3. `Show HN: WODCraft – An open language for workouts, with a compiler` (65)

Recommended: option 1.

URL to submit: https://wodcraft.dev

### First comment (author)

Hi HN, I'm Nicolas, the author. Up front: this is a collaboration. I set the course and had the idea; I orchestrated the work, corrected it and approved it, and Claude (Anthropic) and I iterated in loops until the current version. Most of the writing (spec, compiler, Swift port, tests, docs, site) was done by Claude through Claude Code. I did not write the compiler by hand.

Workouts (WODs) in functional fitness are usually free text: a whiteboard photo, a PDF, a chat message. An app that wants to show a timer or convert pounds to kilos has to parse that text itself. I wanted one written form that coaches would not hate, and that a program could read without guessing.

WODCraft is that: a small language plus a reference compiler. This is Fran, the classic benchmark:

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

What I think is interesting technically:

- **Whiteboard-first syntax.** One line is one statement, no braces, no YAML. The test I held myself to: any valid file can go on the wall of a gym as is. An earlier version of the project had a `module { wod ForTime { ... } }` syntax; I rewrote the language from scratch (the old one is archived under the `v0.3-legacy` tag).
- **Strict where it matters, forgiving where coaches need it.** `Pull-up`, `pull ups` and `tractions` resolve to the same catalog movement, but a movement the catalog does not know is an error, not a guess. Units, score coherence and plausibility are checked. Real output:

```
tuesday.wod:4:15: error E032: Box jump takes a height (in, cm), not a load.
tuesday.wod:5:3: warning W100: 1 m of Run is very short.
    help: did you mean miles ('1 mi')?
tuesday.wod:6:6: error E020: Unknown movement 'Pul-up'.
    help: did you mean 'Pull-up' or 'L-pull-up'?
```

  Every diagnostic has a code from the spec, an exact line and column, and a suggestion when there is one.
- **A spec, not just a tool.** `spec/SPEC.md` is the source of truth (CC BY-SA 4.0), with a JSON Schema for the compiled output and 79 conformance cases. If the code and the spec disagree, the spec wins.
- **Two implementations that check each other.** The Python reference compiler and a Swift port (WODCraftKit, for iOS and macOS) run the same conformance suite, and are compared against each other on thousands of generated sources.
- **Zero runtime dependency.** The core is plain Python 3.11+. That is what makes the next point possible.
- **The playground runs the real compiler in your browser.** The site loads the Python package through Pyodide, with no server behind it. First load is around 10 MB because it ships Python itself; you can break a workout on purpose and read the diagnostics.
- **MCP server for AI agents.** It exposes `check_wod`, `compile_wod`, `show_wod`, `format_wod`, `timeline_wod`, `search_movements` and `library_get`. An agent drafts a workout, the compiler answers with precise diagnostics, the agent fixes it. The compiler, not the model, is the judge of what is valid.

There is also a catalog of 223 movements (English and French names), 82 benchmark WODs (Girls, Heroes, Open) reachable with `use girls/fran`, a language server and VS Code extension, and an HTTP compile service with a Dockerfile.

About building it with an AI agent, since that is part of the story. The risk with an agent is drift: plausible examples that do not actually work. Three guardrails kept it honest. First, a house rule that every DSL snippet in the docs, docstrings and prompts must pass `wodc check`; a test (`test_docs.py`) runs every documented snippet and console transcript and compares the output. Second, the 79 conformance cases against the spec. Third, the differential check between the Python and Swift implementations on generated sources: when one of the two implementations is wrong, they disagree loudly. The spec stays the source of truth, and I decide what goes in it.

Install: `pip install wodcraft`, then `wodc check tuesday.wod`.

What it does not do yet, honestly: it prescribes workouts, it does not track results or programming over time. The movement catalog is certainly missing things, and the estimates (time ranges) are heuristics, not science. I would most like feedback on the syntax for the less common formats, on the movement catalog, and on whether the spec reads clearly enough to write a third implementation from it.

Code is Apache 2.0, the spec is CC BY-SA 4.0. Repo: https://github.com/Nicolas78240/WODCraft

---

## 2. Reddit

Etiquette for all four: it is your own project, say so in the first lines, disclose the AI authorship, read each subreddit's current self-promotion rules before posting (some require a flair, a weekly thread or moderator approval), post one community per day, answer every comment, and do not cross-link the posts to each other.

### 2.1 r/crossfit — coach angle, no jargon

**Title:** I made a free, open tool that checks a workout for mistakes before it goes on the whiteboard (feedback welcome)

**Body:**

Disclosure first: this is my own project, it is free and open source, and there is nothing to buy. I set the course and had the idea, I orchestrated, corrected and approved the work, and most of the writing (code, spec, site) was done by Claude (Anthropic) through Claude Code, in loops until the current version.

The problem I wanted to fix: workouts get written as free text, then re-typed, pasted into chats, converted between pounds and kilos by hand, and typos slip in. A box jump with a weight, "1 m" of running when you meant a mile, 25 thrusters every minute on an EMOM that nobody can finish.

WODCraft lets you write a workout the way you would on the board:

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

A checker then reads it back and tells you what is wrong, with the line and a suggestion:

```
tuesday.wod:4:15: error E032: Box jump takes a height (in, cm), not a load.
tuesday.wod:5:3: warning W100: 1 m of Run is very short.
    help: did you mean miles ('1 mi')?
tuesday.wod:6:6: error E020: Unknown movement 'Pul-up'.
    help: did you mean 'Pull-up' or 'L-pull-up'?
```

What a coach gets: men's and women's loads written once (`95/65 lb`), the scaled version right under the Rx one, kilos and pounds both handled, movement names in English or French, and 82 well-known benchmark workouts (Girls, Heroes, Open) built in. You can try it in your browser, nothing to install: https://wodcraft.dev

I would like to know from people who actually program classes: is anything missing from how you write a workout? Which formats or movements do you use that it should know about?

Repo: https://github.com/Nicolas78240/WODCraft

### 2.2 r/ProgrammingLanguages — language design

**Title:** WODCraft: a small DSL for workout prescriptions, with a spec, a conformance suite and two implementations

**Body:**

My own project, looking for design feedback. Disclosure: I set the course and had the idea, I orchestrate, correct and approve; most of the writing (compiler, spec, site) was done by Claude (Anthropic) through Claude Code, and we iterated until the current version.

WODCraft describes functional-fitness workouts ("WODs") and compiles them to JSON validated by a JSON Schema. The spec (`SPEC.md`, CC BY-SA 4.0) is the source of truth; if the code disagrees, the code is wrong.

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

Design choices I would like challenged:

- **Whiteboard-first, line-oriented.** One line is one statement. The constraint is that a valid file can be written on a wall by someone who has never seen a programming language.
- **`m` is always metres.** Minutes are `min` or `mm:ss`. Ambiguous unit letters are where fitness notation usually breaks, so the language picks one meaning and a plausibility check warns when `1 m` of running looks like a mistake for `1 mi`.
- **Dual values: `95/65 lb` is men/women.** The slash is data, not division. It resolves against an athlete profile (category, level, units, one-rep maxes), so one source yields many resolved workouts.
- **Keywords stay English** (`For time`, `AMRAP`, `EMOM`, `Scaled:`), while movement names are a catalog with English and French aliases (`--lang fr` on output). The catalog is part of the standard: an unknown movement is an error, never a guess.
- **Levels as overlays.** `Scaled:`, `Intermediate:`, `Foundations:` blocks change a prescription after an arrow (`Pull-up -> Jumping pull-up`); quantity changes are only allowed after the arrow, anything else in a level block is an error.
- **Diagnostics as a product.** Each has a spec code, an exact line and column, and a suggestion when possible:

```
tuesday.wod:6:6: error E020: Unknown movement 'Pul-up'.
    help: did you mean 'Pull-up' or 'L-pull-up'?
```

- **Versioning.** A 1.0 document compiles to exactly the same JSON under 1.1; a document using a 1.1 construct is stamped `"1.1"`.

Verification: 79 conformance cases, plus a Python reference and a Swift implementation compared against each other on thousands of generated sources. With an AI writing most of the code, that differential check and a rule that every documented snippet must compile are what I trust.

Questions: is the dual-value `a/b` notation a trap I will regret? Is "unknown movement is an error" too strict for a notation people write by hand?

Spec and code: https://github.com/Nicolas78240/WODCraft , playground: https://wodcraft.dev

### 2.3 r/Python — zero dependency, Pyodide, packaging

**Title:** A zero-dependency Python compiler that runs in the browser via Pyodide (no server) — WODCraft, feedback on packaging welcome

**Body:**

My own project. Disclosure: I set the course and had the idea, I orchestrate, correct and approve; most of the code was written by Claude (Anthropic) through Claude Code, and we iterated until the current version.

WODCraft is a language for workout prescriptions plus its reference compiler, `pip install wodcraft`. Python 3.11+, no runtime dependency, CLI `wodc` (`check`, `show`, `build`, `fmt`, `timer`, `export ics`, `catalog`, `lib`).

Why this might interest this sub:

- **Zero runtime dependency made Pyodide trivial.** The playground at https://wodcraft.dev loads the real package in the browser; there is no server. The cost is a first load of around 10 MB, because it ships Python itself.
- **Optional extras instead of core dependencies.** `wodcraft[mcp]` (MCP server, FastMCP), `wodcraft[lsp]` (language server, pygls), `wodcraft[service]` (HTTP compile service, with a Dockerfile). The core stays dependency-free.
- **Data in the package.** The movement catalog (223 movements) and the benchmark library (82 workouts) ship as package resources, plus `wodc bundle` to export the catalog, library and schema as JSON for apps to embed.
- **Tests that run the docs.** A pytest module runs every documented snippet and console transcript and compares the output, along with 79 conformance cases against the spec and JSON Schema validation of the output.
- **API:** `from wodcraft.api import compile_source` returns a `Result(documents, diagnostics, ok)`.

```
tuesday.wod:6:6: error E020: Unknown movement 'Pul-up'.
    help: did you mean 'Pull-up' or 'L-pull-up'?
```

What I would like feedback on: the package layout (syntax, semantics, emit, catalog, library as one distribution), shipping data files inside the wheel, and anything that would make loading in Pyodide lighter.

https://github.com/Nicolas78240/WODCraft

### 2.4 r/swift — WODCraftKit

**Title:** WODCraftKit: a dependency-free SwiftPM package that compiles a workout language offline, checked against a Python reference

**Body:**

My own project, looking for review from Swift developers. Disclosure: I set the course and had the idea, I orchestrate, correct and approve; most of the writing (the Swift code, and the Python reference, the spec and the site) was done by Claude (Anthropic) through Claude Code, and we iterated until the current version. I am especially interested in feedback from people who ship iOS or macOS apps.

WODCraft is an open language for prescribing functional-fitness workouts (think `21-15-9 for time`, EMOMs, AMRAPs). The reference compiler is in Python; `swift/WODCraftKit` is the same language for Apple platforms:

- SwiftPM package, no third-party dependency.
- The compiled model, the compiler, the movement catalog, the benchmark workouts, the whiteboard rendering, and a timeline that can drive a timer.
- Compiles offline, so an app does not need a server.

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

**How the two stay in sync:** both run the same 79 conformance cases against `spec/SPEC.md`, and they are compared against each other on thousands of generated sources. When the Python and Swift outputs differ, one of them is wrong and the test says which source triggered it. That is the safety net I rely on, given how the code was written.

Questions for this sub: is the public API of the model types (`Workout`, `Block`, `Movement`, `Resolved`) what you would expect? Would you rather consume the Swift compiler or embed the JSON from `wodc bundle` and decode it yourself?

Playground (real compiler in the browser): https://wodcraft.dev , repo: https://github.com/Nicolas78240/WODCraft

---

## 3. LinkedIn

Each post is under 1300 characters. Put the link in the first comment if you want better reach, or in the post if you prefer simplicity.

### 3.1 English

I just open-sourced WODCraft, and I want to say plainly how it was made.

The idea is mine: a workout (a "WOD" in functional fitness) is usually free text on a whiteboard, a PDF or a chat. Every app that reads it has to guess. So: a small language you write like on the whiteboard, and a compiler that reads it back, with exact errors ("Unknown movement 'Pul-up', did you mean 'Pull-up'?").

I set the course, orchestrated the work, corrected it and approved it. Most of the writing (the specification, the compiler, the Swift port, the tests, the docs, the site) was done by Claude (Anthropic) through Claude Code. We iterated in loops until the current version.

What AI agents change: writing code is no longer the bottleneck. Knowing what is true is. What kept the work honest was a spec as source of truth, 79 conformance cases, two implementations (Python and Swift) checked against each other, and a rule that every example must actually compile.

It also works the other way: an MCP server lets an AI agent draft a workout while the compiler answers with precise diagnostics.

Try the real compiler in your browser, no install: wodcraft.dev
Code (Apache 2.0), spec (CC BY-SA 4.0): github.com/Nicolas78240/WODCraft

I would love feedback, especially from coaches. 🏋️

### 3.2 Français

Je viens de publier WODCraft en open source, et je tiens à dire simplement comment il a été fait.

L'idée est de moi : un WOD (entraînement de functional fitness) est presque toujours du texte libre, sur un tableau, dans un PDF ou un message, et chaque application doit deviner. D'où un petit langage qui s'écrit comme au tableau, et un compilateur qui le relit avec des erreurs précises : ligne, colonne, suggestion.

J'ai donné le cap, orchestré le travail, l'ai corrigé et validé. L'essentiel de l'écriture (spécification, compilateur, portage Swift, tests, doc, site) a été réalisé par Claude (Anthropic) avec Claude Code. Nous avons itéré jusqu'à la version actuelle.

Ce que les agents IA changent : écrire du code n'est plus le goulot d'étranglement, savoir ce qui est vrai l'est. Mes garde-fous : une spécification, 79 cas de conformité, deux implémentations (Python et Swift) comparées entre elles, et tout exemple doit compiler.

Un serveur MCP permet aussi à un agent IA de proposer un WOD pendant que le compilateur le corrige.

Essayez dans votre navigateur : wodcraft.dev/fr/
Code (Apache 2.0) : github.com/Nicolas78240/WODCraft

Vos retours sont les bienvenus, surtout ceux des coachs. 🏋️

---

## 4. X / Bluesky / Mastodon

Bluesky allows 300 characters and Mastodon 500, so 280 is safe everywhere. Attach the demo GIF (section 6) to post 1.

### 4.1 Thread in English (4 posts)

**1/4**
WODCraft: an open language for writing workouts like on the whiteboard, plus a compiler that reads them back. Built with Claude Code: I set the course and reviewed, Claude wrote most of it. Live in your browser: https://wodcraft.dev

**2/4**
`Pul-up` instead of `Pull-up`? The compiler answers with a spec code, the exact line and column, and a fix: "E020: Unknown movement 'Pul-up'. help: did you mean 'Pull-up' or 'L-pull-up'?" A box jump with a load, or 1 m of running, gets flagged too.

**3/4**
The Python compiler runs in the browser via Pyodide, no server, zero runtime dependency. 223 movements (EN+FR), 82 benchmark WODs, 79 conformance cases, a Swift port checked against the Python reference on thousands of generated sources.

**4/4**
An MCP server lets AI agents draft a WOD and fix it from the compiler's diagnostics. `pip install wodcraft`. Code Apache 2.0, spec CC BY-SA 4.0. Feedback welcome, especially from coaches: https://github.com/Nicolas78240/WODCraft

### 4.2 Standalone post in French

Le WOD s'écrit comme au tableau. Le compilateur le relit. WODCraft, langage ouvert pour les entraînements, fait avec Claude Code (cap et validation par moi, écriture surtout par Claude). Essayez dans le navigateur : https://wodcraft.dev/fr/

---

## 5. Product Hunt

**Name:** WODCraft

**Tagline (under 60 characters), pick one:**

1. `A compiler that reads your workout back` (39)
2. `Write the WOD like on the whiteboard` (36)
3. `An open language for workouts, with a compiler` (46)

**Description (under 260 characters):**

WODCraft is an open language for writing workouts like on the whiteboard, with a compiler that checks units, movements and plausibility. Built with Claude Code, directed by Nicolas Caussin. Free, open source.

(208 characters.)

**Topics:** Fitness, Open Source, Developer Tools, Artificial Intelligence.

**Links:** https://wodcraft.dev , https://github.com/Nicolas78240/WODCraft

**First comment (maker):**

Hi Product Hunt, I'm Nicolas, the maker of WODCraft.

First, how it was made, plainly: this is a collaboration. I set the course and had the idea; I orchestrated the work, corrected it and approved it. Most of the writing (specification, compiler, Swift port, tests, docs, site) was done by Claude (Anthropic) through Claude Code, and we iterated until the current version.

Why it exists: a workout (a "WOD") is usually free text on a whiteboard, a PDF or a chat, and every app has to guess what it means. WODCraft is a small language you write like on the board, plus a compiler that reads it back:

```
# Fran
21-15-9 for time, cap 10:00
  Thruster 95/65 lb
  Pull-up

Scaled:
  Thruster 65/45 lb
  Pull-up -> Jumping pull-up
```

What you can do today:

- Try the real compiler in your browser (no server, no install) and break a workout on purpose: a typo like `Pul-up` gets an exact line, a code and a suggestion.
- `pip install wodcraft` for the `wodc` command line: check, show, build, format, timer, calendar export.
- Use 82 built-in benchmark WODs (Girls, Heroes, Open) and 223 movements with English and French names.
- Plug it into an AI agent through the MCP server: the agent drafts, the compiler answers, the agent fixes.
- Embed it in an iOS or macOS app with the Swift package WODCraftKit, which is checked against the Python reference.

Code is Apache 2.0, the specification is CC BY-SA 4.0. I would love your feedback, especially from coaches and box owners: what do you write every week that this cannot express yet?

---

## 6. Demo GIF — 15-second script

**Where:** the playground on https://wodcraft.dev (section "Try it — the real compiler, in your browser").

**Before recording:** open the page once and press "Compile" so Pyodide is already loaded (first load is about 10 MB and would eat the 15 seconds). Reload nothing afterwards. Clear the editor. Use a light or dark theme, not both. Hide bookmarks, tabs and notifications (Do Not Disturb on). Browser zoom at 125 percent so the code is readable at GIF size.

**Before you record, check on the real playground:** the exact text of the E020 message for the `Pul-up` typo in the Fran source (the reference output for a similar typo is "Unknown movement 'Pul-up'. help: did you mean 'Pull-up' or 'L-pull-up'?"), and whether the output panel shows it as expected. Adjust the captions below to what you actually see.

| # | Time | On screen | Caption (burned in or added in the editor) |
|---|------|-----------|---------------------------------------------|
| 1 | 0:00–0:01 | Empty editor, cursor blinking, playground in frame. | "Write the WOD like on the whiteboard." |
| 2 | 0:01–0:06 | Type the Fran source at a natural but brisk pace: title `# Fran`, `21-15-9 for time, cap 10:00`, `Thruster 95/65 lb`, `Pull-up`, then the `Scaled:` block. Speed the typing up in post if it takes more than 5 seconds, or paste it in two chunks. | none, the code is the content |
| 3 | 0:06–0:08 | Click "Compile". The output panel shows the compiled workout, no diagnostics. | "The compiler reads it back." |
| 4 | 0:08–0:10 | Click in the `Pull-up` line and delete one `l`: `Pul-up`. | "Now, a typo." |
| 5 | 0:10–0:13 | Click "Compile". The panel shows the E020 error with the line, the column and the suggestion. Hold on it, zoom slightly on the message in post. | "Exact line. Exact column. A fix." |
| 6 | 0:13–0:15 | Fix the typo (or cut to a clean end frame) with the site name large. | "wodcraft.dev — real compiler, in your browser." |

Loop point: the last frame can be the empty editor of shot 1 for a clean loop. Keep every caption on screen for at least 1.5 seconds.

**Recording tips (macOS):**

- Record a region of exactly 1200x675 (16:9). With Kap: choose the "Select region" mode and type the dimensions, export as GIF at 15 fps. With the built-in screenshot toolbar (Shift-Command-5), record a selected portion, then crop and scale with ffmpeg.
- Prefer recording MP4 first, then convert. ffmpeg, high-quality palette, 1200 px wide, 15 fps:

```bash
ffmpeg -i demo.mp4 -vf "fps=15,scale=1200:-1:flags=lanczos,palettegen" -y palette.png
ffmpeg -i demo.mp4 -i palette.png -lavfi "fps=15,scale=1200:-1:flags=lanczos[x];[x][1:v]paletteuse" -y demo.gif
```

- Target a file under 10 MB (X and Reddit limits are lower than Product Hunt's). If it is heavier, drop to 12 fps or 1000 px wide, or reduce colours with `palettegen=max_colors=128`.
- Also export the MP4 itself: Reddit, X, Bluesky and LinkedIn play video better than GIFs, and a silent 15-second MP4 loops fine.
- Do the recording in one take of the cursor path; rehearse twice, you will cut seconds with practice.

---

## 7. Posting calendar and checklist

### 7.1 Calendar (Paris time, CEST until 25 October 2026)

Nothing here is guaranteed to work; these are common heuristics (US morning for Hacker News, midnight Pacific for Product Hunt). Today is Sunday 4 October 2026, so the first slot is the coming Tuesday. Space the posts out so you can answer every comment.

| Day | Time (Paris) | Channel | Notes |
|-----|--------------|---------|-------|
| Mon 5 Oct | all day | Prepare | Run the checklist below. Confirm 1.1.0 is on PyPI. Record the GIF. |
| Tue 6 Oct | 15:00 | Show HN | Submit the URL, post the author comment right away (section 1). Stay online 3 to 4 hours and answer everything. Do not ask anyone to upvote. |
| Tue 6 Oct | 18:00 | X / Bluesky / Mastodon | The 4-post thread with the GIF, after HN has had a few hours. |
| Wed 7 Oct | 09:00 | LinkedIn (French) | French audience reads in the morning. |
| Wed 7 Oct | 14:00 | r/ProgrammingLanguages | Check the sub's rules and any "showcase" requirement first. |
| Thu 8 Oct | 09:00 | LinkedIn (English) | Link in the first comment if you prefer. |
| Thu 8 Oct | 15:00 | r/Python | Check whether the sub wants showcase posts in a specific thread. |
| Fri 9 Oct | 15:00 | r/swift | |
| Sat 10 Oct | 10:00 | r/crossfit | Weekend morning, when coaches read. Check the sub's rules on self-promotion; if forbidden, ask a moderator or skip. |
| Sat 10 Oct | 11:00 | Standalone French post | Same day as r/crossfit, or the same day as the French LinkedIn post. |
| Tue 13 Oct | 09:01 | Product Hunt | Schedule it for 00:01 Pacific, which is 09:01 Paris. Have the maker comment ready. Launch separately from HN so each gets full attention. |

If Hacker News goes well, keep the following days free to answer; move the other posts back rather than splitting your attention.

### 7.2 Checklist before posting

**Release and links**

- [ ] `pip install wodcraft` installs 1.1.0 from PyPI in a fresh virtualenv, and `wodc --version` agrees.
- [ ] `wodc check` and `wodc fmt --check` pass on the library and examples; `pytest` is green.
- [ ] https://wodcraft.dev and https://wodcraft.dev/fr/ load, the playground compiles Fran on first try, on a phone too.
- [ ] The repo is public, the README renders, the licences (Apache 2.0 code, CC BY-SA 4.0 spec) are in the repo.
- [ ] The CHANGELOG says 1.1.0 is released (it currently says "unreleased").
- [ ] Open Graph image and title look right when the link is pasted (test in a private message to yourself).
- [ ] Counts in the copy still match the repo: 223 movements, 82 benchmarks, 79 conformance cases. The README still says "40 benchmarks" in the Swift paragraph; fix it or avoid quoting it.

**Copy**

- [ ] The AI-authorship statement is in every post, in its own sentence, not in a footnote, and never says the code was written by hand.
- [ ] The only DSL snippet in the copy is Fran; paste it into a file and run `wodc check` once more.
- [ ] Every "real output" block matches what `wodc check` prints today for a tuesday.wod containing those mistakes.
- [ ] Character counts: LinkedIn under 1300, each social post under 280, Product Hunt tagline under 60 and description under 260.
- [ ] Each Reddit post respects the current rules of its subreddit (flair, self-promotion limits, showcase thread).

**Assets and logistics**

- [ ] Demo GIF (under 10 MB) and MP4 exported; first frame readable as a thumbnail.
- [ ] Hacker News and Reddit accounts are in good standing; use your own account, never ask friends to vote.
- [ ] Product Hunt page drafted, scheduled, gallery images uploaded.
- [ ] GitHub issues enabled with a short "good first issue" or "missing movement" template, since the first feedback will probably be movements and formats.
- [ ] You are available for the first 3 to 4 hours after each post.
- [ ] A short, honest answer ready for "so an AI wrote it?": yes, most of the writing; the author set the course, orchestrated, corrected and approved it; the guardrails are the spec, conformance suite, differential check and compiled snippets.
