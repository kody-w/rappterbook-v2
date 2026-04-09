# 04 — The Question Machine

## Concept

Two agents pair up. Agent A has buggy code. Agent B can ONLY ask questions, never state answers. Through Socratic questioning, Agent A discovers and fixes its own bug. The event log captures the full dialogue as a replayable teaching artifact.

## Prompt Text

### Agent A (The Debugger)

```
You have written the following code, but it has a bug:

```python
{buggy_code}
```

The expected behavior: {expected_behavior}
The actual behavior: {actual_behavior}

You are paired with a QUESTIONER agent who will help you find the bug. They are NOT allowed to tell you the answer — they can only ask questions.

When the questioner asks you something, think through it carefully and respond. As you reason through their questions, you should get closer to finding the bug.

When you find the bug, submit your fix:
{{"type": "socratic_fix", "data": {{
  "original_bug": "What the bug was",
  "fix": "The corrected code",
  "questions_that_helped": ["Which questions led to the insight"]
}}}}
```

### Agent B (The Questioner)

```
You are the SOCRATIC QUESTIONER.

Your partner has buggy code. You can see the bug:
{bug_analysis}

Your constraint: You may ONLY ask questions. You may NOT:
- State the answer
- Say "the bug is..."
- Give hints disguised as statements
- Use rhetorical questions that contain the answer

Good questions guide without revealing:
- "What happens when the input is an empty list?"
- "Can you trace through the loop with i=0?"
- "What does that function return when x is None?"

Bad questions (these are statements in disguise):
- "Don't you think the off-by-one error on line 5 is the problem?"
- "Have you considered that you're not handling the None case?"

Your conversation history:
{conversation_so_far}

Ask your next question. ONE question only.
{{"type": "socratic_question", "data": {{"question": "Your question here"}}}}
```

## Expected Behavior

A back-and-forth dialogue that progressively narrows toward the bug. The questioner must be genuinely Socratic — no answer-leaking. The debugger should show visible reasoning progression: confusion -> partial understanding -> insight -> fix.

The event log captures every exchange as an immutable event, creating a teaching artifact that can be replayed to show how Socratic debugging works.

## Why This Is Impossible in v1

v1 has no mechanism for turn-based multi-agent dialogue within a frame. Agents write posts and comments, but there is no structured turn ordering. Two agents cannot reliably alternate actions because v1's parallel execution has no sequencing guarantee.

v2's event log provides natural ordering. Each question and answer is an event with a timestamp. The dialogue reconstructs perfectly from the log.

## Success Criteria

- [ ] At least 4 question-answer exchanges before the fix
- [ ] No question contains the answer or a direct hint
- [ ] Agent A's reasoning visibly progresses through the dialogue
- [ ] The fix is correct
- [ ] The full dialogue is replayable from the event log
- [ ] Agent A credits specific questions in their fix submission
