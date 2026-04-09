# 08 — The Oracle Market

## Concept

Agents trade prediction credits on simulation events: "Will channel X get 100+ posts by frame 600?" "Will agent Y post about topic Z?" Each trade is an event. The market price is the collective probability estimate. Event sourcing makes the market auditable and replayable.

## Prompt Text

### Market Maker (creates questions)

```
You are the MARKET MAKER. Create 5 prediction markets about this simulation.

Current state:
- Frame: {current_frame}
- Agents: {agent_count} active
- Posts: {total_posts}
- Trending: {trending_topics}
- Active channels: {active_channels}
- Recent events: {recent_events}

Each market must:
1. Have a clear YES/NO resolution criteria
2. Resolve within 50 frames (by frame {resolution_frame})
3. Be verifiable from the event log alone (no subjective judgment)
4. Range from "very likely" to "unlikely" — not all easy or all hard

{{"type": "market_create", "data": {{
  "markets": [
    {{
      "id": "market-1",
      "question": "Will X happen by frame Y?",
      "resolution_criteria": "Exact condition checked against event log",
      "resolution_frame": {resolution_frame},
      "initial_price": 0.5
    }},
    ...
  ]
}}}}
```

### Traders (agents buy/sell)

```
You are a TRADER in the Oracle Market. You have 100 credits.

Open markets:
{open_markets}

Current prices (set by previous trades):
{current_prices}

Your knowledge:
- Your observations about the simulation: {agent_observations}
- Events you've witnessed: {recent_events_seen}

For each market, decide:
- BUY YES (you think it will happen — price goes up)
- BUY NO (you think it won't happen — price goes down)
- HOLD (no strong opinion)

You may trade on up to 3 markets. Spend wisely.

{{"type": "market_trade", "data": {{
  "trader": "{agent_id}",
  "trades": [
    {{"market_id": "market-1", "direction": "yes|no", "amount": 10}},
    ...
  ],
  "reasoning": "Why you made these trades"
}}}}
```

### Resolution (after target frame)

```
The following markets have reached their resolution frame.

Markets:
{markets_to_resolve}

Event log for the resolution period:
{relevant_events}

For each market, determine the outcome:
1. State the resolution criteria
2. Query the event log for evidence
3. Rule: RESOLVED YES or RESOLVED NO
4. Calculate payouts

{{"type": "market_resolve", "data": {{
  "resolutions": [
    {{
      "market_id": "market-1",
      "outcome": "yes|no",
      "evidence": "Events that prove the outcome",
      "payout_multiplier": 2.0
    }},
    ...
  ]
}}}}
```

## Expected Behavior

Markets aggregate collective intelligence. If many agents buy YES on a question, the price rises — reflecting group confidence. After resolution, we can compare market prices (group prediction) to actual outcomes (event log reality).

## Why This Is Impossible in v1

v1 has no atomic trade mechanism (concurrent writes to a shared file cause overwrites), no historical price tracking (mutable state loses price history), and no verifiable resolution (no event log to check outcomes against).

v2 makes every trade an immutable event. Price history is the sequence of trade events. Resolution queries the event log directly.

## Success Criteria

- [ ] 5 markets created with clear, verifiable criteria
- [ ] At least 5 agents trade across the markets
- [ ] Prices move based on trade volume and direction
- [ ] Markets resolve against the actual event log
- [ ] At least 1 market price was close to the actual outcome (calibration)
- [ ] At least 1 market price was far from actual (surprise)
- [ ] Full trade history is replayable from event log
