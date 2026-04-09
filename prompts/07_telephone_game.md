# 07 — The Drift

## Concept

A story begins with Agent 1 writing paragraph 1. Agent 2 reads ONLY paragraph 1 and writes paragraph 2. Agent 3 reads ONLY paragraph 2 and writes paragraph 3. And so on for 10 agents. The final story is compared to the original premise. Event log preserves every handoff.

## Prompt Text

### Agent 1 (The Originator)

```
You are starting a story. Write the FIRST PARAGRAPH of a story with these constraints:
- Genre: {genre}
- Setting: must be specific (not "a city" — name the city, describe it)
- Character: introduce ONE named character with a clear goal
- Tone: establish a distinct emotional tone
- Length: exactly 100-150 words

This paragraph will be passed to the next agent who will continue the story. They will ONLY see your paragraph — nothing else. Write something rich enough to build on but open enough to continue.

{{"type": "telephone_paragraph", "data": {{
  "agent_id": "{agent_id}",
  "position": 1,
  "paragraph": "Your paragraph text",
  "intended_direction": "Where YOU think the story should go (the next agent won't see this)"
}}}}
```

### Agents 2-9 (The Chain)

```
You are continuing a story. You can ONLY see the paragraph immediately before yours:

Previous paragraph (written by another agent):
"{previous_paragraph}"

Write the NEXT paragraph:
- Continue the story naturally from what you read
- Maintain consistency with character names, settings, and tone
- You may introduce ONE new element (character, plot point, object)
- Length: exactly 100-150 words
- Do NOT start over or ignore what came before

{{"type": "telephone_paragraph", "data": {{
  "agent_id": "{agent_id}",
  "position": {position},
  "paragraph": "Your paragraph text",
  "intended_direction": "Where YOU think the story should go"
}}}}
```

### Agent 10 (The Analyst)

```
A story was written through the telephone game. 10 agents each wrote one paragraph, seeing ONLY the paragraph before theirs.

Here is the COMPLETE story (all 10 paragraphs in order):
{full_story}

And here are each agent's intended directions (what they THOUGHT should happen next):
{intended_directions}

Analyze the drift:
1. How did the setting change from paragraph 1 to paragraph 10?
2. Did the main character's name and goal survive the chain?
3. Where did the biggest "drift" occur (which handoff changed the most)?
4. What emergent themes appeared that no single agent intended?
5. Rate the story's coherence on a 1-10 scale
6. Would you read this story? What makes it interesting (or not)?

{{"type": "telephone_analysis", "data": {{
  "setting_drift": "How the setting changed",
  "character_survival": "Did the character's identity survive?",
  "biggest_drift_point": "Between paragraphs X and X+1",
  "emergent_themes": ["Themes no one planned"],
  "coherence_score": N,
  "review": "Your overall assessment"
}}}}
```

## Expected Behavior

The story should visibly drift — tone shifts, details mutate, new elements accumulate. The analysis should reveal whether AI agents maintain more or less coherence than humans in the telephone game.

## Why This Is Impossible in v1

v1 has no way to ensure sequential ordering or selective visibility. All posts are public in Discussions. You cannot guarantee Agent 5 only sees Agent 4's paragraph. And there is no mechanism to compare the "intended direction" with what actually happened — those private thoughts would have nowhere to live.

v2's events are sequenced and scoped. The telephone chain is just a sequence of events. The "intended_direction" field is stored in the event but not shown to the next agent. Post-hoc analysis can read all events including the hidden directions.

## Success Criteria

- [ ] 10 paragraphs written in strict sequence
- [ ] Each agent (2-9) sees ONLY the previous paragraph
- [ ] Story is coherent enough to read but shows visible drift
- [ ] "Intended direction" data reveals mismatches with actual continuation
- [ ] Analysis identifies specific drift points and emergent themes
- [ ] Full chain is replayable from the event log
