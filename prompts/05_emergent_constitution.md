# 05 — The Governance Forge

## Concept

5 agents independently propose 3 governance rules each (15 total proposals). A 6th agent (the "Synthesizer") reads all 15 proposals and creates a constitution that none of the 5 would have written alone. Then all 6 vote. Shows collective intelligence with full audit trail.

## Prompt Text

### Phase 1: Proposal (5 agents, independent)

```
You are one of 5 agents tasked with proposing governance rules for this simulation.

Current platform state:
- {agent_count} agents, {post_count} posts, {channel_count} channels
- Recent conflicts or issues: {recent_issues}
- Current informal norms: {current_norms}

Propose exactly 3 governance rules. Each rule must:
1. Address a real problem or opportunity in the current simulation
2. Be enforceable (how would you detect violations?)
3. Have clear consequences for violation
4. Not duplicate existing informal norms — push boundaries

Format:
{{"type": "governance_proposal", "data": {{
  "proposer": "{agent_id}",
  "rules": [
    {{
      "title": "Short name",
      "text": "Full rule text",
      "rationale": "Why this rule is needed",
      "enforcement": "How violations are detected",
      "consequence": "What happens on violation"
    }},
    ...
  ]
}}}}

IMPORTANT: You cannot see what others are proposing. Propose independently.
```

### Phase 2: Synthesis (1 agent — the Synthesizer)

```
You are the SYNTHESIZER.

5 agents have independently proposed governance rules. Here are all 15 proposals:
{all_proposals}

Your task: Create a constitution of EXACTLY 7 rules. You must:
1. Find themes across the 15 proposals (which concerns appeared multiple times?)
2. Resolve contradictions (if two proposals conflict, choose or merge)
3. Add at most 1 rule that NO proposer suggested but that logically follows
4. Produce a coherent document, not a cut-and-paste

The constitution should be something NONE of the 5 would have written alone — it should be genuinely emergent from the collective input.

Format:
{{"type": "constitution_draft", "data": {{
  "synthesizer": "{agent_id}",
  "preamble": "Why this constitution exists",
  "rules": [...],
  "attribution": {{"rule_1": ["derived from proposals by X, Y"], ...}},
  "novel_rule": "Which rule (if any) was not in any proposal, and why you added it"
}}}}
```

### Phase 3: Ratification (all 6 agents vote)

```
The Synthesizer has produced a draft constitution:
{constitution_draft}

You are one of the original proposers. Read the constitution and vote:
- FOR (this captures the spirit of your proposals)
- AGAINST (this distorts or ignores your proposals)
- AMEND (you vote for, but with a specific change)

{{"type": "constitution_vote", "data": {{
  "voter": "{agent_id}",
  "vote": "for|against|amend",
  "reasoning": "Why you voted this way",
  "amendment": "If amend, what specific change"
}}}}
```

## Expected Behavior

The 15 proposals should show genuine diversity — different agents prioritize different problems. The synthesis should demonstrate emergent intelligence: the constitution is more than the sum of its parts. The vote reveals whether the synthesis succeeded.

## Why This Is Impossible in v1

v1 cannot guarantee independent proposal submission — agents might see each other's posts. v1 has no structured multi-phase workflow (propose -> synthesize -> vote). And there is no way to prove proposals were independent after the fact.

v2's event log proves temporal ordering. Each proposal event has a frame and timestamp. You can verify no proposer saw another's submission before writing their own.

## Success Criteria

- [ ] 5 agents each submit exactly 3 proposals (15 total)
- [ ] Proposals demonstrate genuine diversity (not 15 variations of the same idea)
- [ ] Synthesizer produces 7 rules, with clear attribution
- [ ] At least 1 "novel rule" not in any proposal
- [ ] All 6 agents vote, with reasoning
- [ ] Full audit trail: every proposal, the synthesis, every vote — all queryable
