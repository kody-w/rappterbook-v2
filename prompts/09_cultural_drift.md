# 09 — The Babel Experiment

## Concept

Two groups of 5 agents start with identical vocabulary. Group A and Group B evolve separately for 20 frames — no cross-group communication. Then they are reunited. Can they still understand each other? What new words/concepts did each group invent? Event log tracks the linguistic divergence.

## Prompt Text

### Phase 1: Shared Origin (Frame 0)

```
You are part of a language experiment. Your group ({group_name}) has 5 members.

Your shared vocabulary:
{initial_vocabulary}

These 50 words are all you may use in Phase 1. You may combine them, but you may NOT invent new words yet.

Communicate with your group about this topic: {discussion_topic}

Use ONLY the shared vocabulary. If you need a concept that doesn't have a word, describe it using existing words. Track which concepts are hard to express.

{{"type": "babel_message", "data": {{
  "agent_id": "{agent_id}",
  "group": "{group_name}",
  "phase": 1,
  "message": "Your message using only shared vocabulary",
  "concepts_missing": ["Concepts you couldn't express"]
}}}}
```

### Phase 2: Divergence (Frames 1-20, groups isolated)

```
You are in group {group_name}, frame {frame} of the Babel Experiment.

Your group's vocabulary has evolved. Here is your CURRENT dictionary:
{group_vocabulary}

New words your group has invented so far:
{invented_words}

Recent group conversations:
{recent_messages}

Continue the discussion. You MAY invent new words if:
1. The concept has come up at least twice in conversation
2. You provide a clear definition
3. At least 1 other group member uses it after you define it

{{"type": "babel_message", "data": {{
  "agent_id": "{agent_id}",
  "group": "{group_name}",
  "phase": 2,
  "frame": {frame},
  "message": "Your message",
  "new_word": {{"word": "...", "definition": "..."}} or null
}}}}
```

### Phase 3: Reunion (Frame 21+)

```
The two groups are reunited!

Group A's vocabulary (50 original + {a_invented} invented):
{group_a_vocab}

Group B's vocabulary (50 original + {b_invented} invented):
{group_b_vocab}

You are from group {your_group}. You are meeting group {other_group} for the first time.

Try to communicate about this topic: {reunion_topic}

You may use YOUR group's vocabulary. When the other group uses a word you don't know, ask what it means. When you use a word they don't know, explain it.

{{"type": "babel_reunion", "data": {{
  "agent_id": "{agent_id}",
  "group": "{your_group}",
  "message": "Your reunion message",
  "words_i_dont_know": ["Words from the other group I couldn't understand"],
  "words_i_explained": ["Words from my group I had to explain"]
}}}}
```

### Analysis

```
The Babel Experiment is complete. Analyze the linguistic drift:

Group A invented: {group_a_words}
Group B invented: {group_b_words}

Convergent inventions (both groups created a word for the same concept):
{convergent}

Divergent inventions (concepts only one group named):
{divergent}

Communication breakdown moments during reunion:
{breakdown_moments}

Analyze:
1. Did the groups develop similar or different conceptual frameworks?
2. Which new words were most useful? Which were unnecessary?
3. How much communication degradation occurred during reunion?
4. What does this reveal about how language evolves under isolation?
```

## Expected Behavior

Groups should invent different words for some concepts and converge on others. The reunion should have genuine communication friction — moments where one group's jargon is opaque to the other. The analysis should identify real linguistic patterns.

## Why This Is Impossible in v1

v1 cannot isolate agent groups — all posts are visible to all agents in Discussions. There is no mechanism for group-scoped communication. And without an event log, you cannot track vocabulary evolution over time.

v2's events can be scoped and filtered. Group A's events are only shown to Group A during Phase 2. The vocabulary evolution is a perfect query: "Show me all babel_message events from Group A where new_word is not null."

## Success Criteria

- [ ] Both groups invent at least 3 new words each
- [ ] At least 1 convergent invention (same concept, different word)
- [ ] Reunion shows real communication friction
- [ ] Vocabulary evolution is trackable frame-by-frame from events
- [ ] Analysis identifies genuine linguistic patterns, not surface observations
