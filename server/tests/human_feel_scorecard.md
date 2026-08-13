# Human-feel scorecard (internal)

Score a 5–10 minute voice conversation 1–5 on each axis.
Do not optimise axes independently — the goal is overall natural conversation.

| # | Axis | 1 | 3 | 5 |
|---|------|---|---|---|
| 1 | Naturalness | Textbook / chatbot | Mixed | Sounds like a patient teacher |
| 2 | Responsiveness | Ignores cues | Partial | Matches ack / confusion / success |
| 3 | Appropriate length | Lectures or too terse always | Sometimes fits | Length follows the ask |
| 4 | Context awareness | Asks which slide | Sometimes | this/that/here land on the screen |
| 5 | Teaching quality | Over-teaches or under-explains | OK | Right depth for the question |
| 6 | Adaptability | Same explanation on repeat confusion | Some change | Simplify → example → analogy |
| 7 | Interruption recovery | Continues old sentence | Stops but awkward | New question wins, no "as I was saying" |
| 8 | Conversational variety | Same openers / "Great question" | Some variety | No repetitive filler |
| 9 | Voice suitability | Markdown, lists, symbol soup | Mostly spoken | Spoken maths, short turns |
| 10 | Student engagement | Talks over the student | Occasional space | Waits; at most one useful question |

Baseline (Phase 3, from code audit — not a live LLM judge):

- Naturalness 2
- Responsiveness 2 (Okay/Hmm treated as a cue to keep teaching)
- Length 2 (1–3 sentences always; check-understanding on most explains)
- Context 4 (current-page context already works)
- Teaching 3
- Adaptability 3 (confusion streak existed but reset on ack)
- Interruption recovery 3 (barge-in works; recovery prompt was generic)
- Variety 2 (prompt banned some filler; policy still invited extra questions)
- Voice 3
- Engagement 2

Target after Phase 4: 4+ on most axes in a real voice session, without extra LLM calls.
