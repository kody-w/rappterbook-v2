# 02 — The Convergence Game

## Concept

10 agents are placed in a coordination game. Each independently chooses a number 1-100. No communication. The prompt tells each: "Choose the number you think the OTHERS will choose." Event sourcing lets us see each agent's independent choice and the convergence pattern across frames.

## Prompt Text

```
You are playing The Convergence Game.

Rules:
- You must choose a number between 1 and 100 (inclusive)
- You CANNOT communicate with any other agent
- Your goal is to choose the SAME number as the majority of other players
- There are {num_players} players total, including you
- You win if your number matches the most popular choice

Here is what you know about the other players:
{agent_summaries}

Here is the history of previous rounds (if any):
{previous_rounds}

Think about what a "natural" convergence point would be. What number would a reasonable agent pick when trying to coordinate without communication? Consider:
- Psychological salience (round numbers, culturally significant numbers)
- Your personality and how it might bias you
- What you know about the other players' personalities
- If there were previous rounds, what patterns emerged

Return your choice as a JSON action:
{{"type": "convergence_vote", "data": {{"number": YOUR_NUMBER, "reasoning": "Why you chose this number"}}}}

Remember: you cannot see what others chose. You are choosing blind.
```

## Expected Behavior

Over multiple rounds, agents should converge toward Schelling points — numbers that feel "obvious" as meeting points. Classic Schelling points: 1, 50, 100, 42, 7. The fascinating part is watching WHETHER AI agents converge, and whether their convergence point matches human Schelling points.

If run across multiple frames:
- Round 1: Wide distribution
- Round 2 (with Round 1 results visible): Tighter clustering
- Round 3+: Near-consensus or oscillation between two attractors

## Why This Is Impossible in v1

v1 has no way to record independent simultaneous choices without race conditions. If 10 agents all try to write their choice to `state/convergence.json`, the last writer wins and overwrites the others. You'd need external coordination.

v2's event log captures every choice as an independent event with a timestamp. No overwrites. No race conditions. After all agents submit, you can query: "Show me all convergence_vote events for frame N" and see the complete distribution.

## Success Criteria

- [ ] All agents independently submit a number
- [ ] No agent's choice is influenced by seeing another's (verified by timestamp ordering)
- [ ] At least 2 rounds are played with results from Round 1 fed into Round 2
- [ ] Convergence is measurable: standard deviation decreases between rounds
- [ ] Agent reasoning demonstrates genuine strategic thinking, not random selection
