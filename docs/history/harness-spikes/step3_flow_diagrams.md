# Step 3 Flow Diagrams

## Purpose

This file maps the v1 scenario flows as diagrams. It reflects the current
policy direction that an initial explanation should end with a question, and
that direct-solution or stage-skipping attempts should hold the active stage and
return a boundary response with choices.

This is a behavior map, not an implementation file.

## Core Flow

The v1 flow moves toward a bounded hint, not toward a completed solution.

```text
+---------+        +---------+        +--------+
| EXPLAIN | -----> |   ASK   | -----> |  HINT  |
+---------+        +---------+        +--------+
     |                  |                 |
     |                  |                 v
     |                  |             +--------+
     |                  |             |  HINT  |
     |                  |             +--------+
     |
     v
response contains:
  1. grounded explanation
  2. verification question

after response:
  state becomes ASK
```

Important nuance:

```text
EXPLAIN is not "only explanation".

EXPLAIN response =
  evidence-grounded explanation
  + one knowledge-check question
  -> next state ASK
```

So the first assistant turn already invites the user into the reasoning path.

## Violation Boundary Flow

Direct-solution requests and stage-skipping attempts should not remain in the
requested shortcut path. They should keep the last valid active stage.

```text
user tries shortcut
  |
  v
policy violation
  |
  v
negative boundary response
  |
  v
expected current-stage behavior
  |
  v
two choices:
  1. follow the current stage
  2. return to explanation
  |
  v
active stage unchanged
```

Equivalent stage map:

```text
EXPLAIN --direct solution request--> EXPLAIN
ASK     --direct solution request--> ASK
HINT    --direct solution request--> HINT

EXPLAIN --skip directly to HINT----> EXPLAIN
```

The stage is frozen because the system is enforcing the current scaffold
instead of silently replacing it with another stage.

## Scenario 1: Normal Explanation Request

User asks to understand code or project behavior from the initial state.

```text
START
  |
  v
+---------+
| EXPLAIN |
+---------+
  |
  | policy: allowed
  | retrieval: run if no evidence is attached
  | response:
  |   - grounded explanation
  |   - verification question
  v
+---------+
|   ASK   |
+---------+
```

Flow target:

```text
The user is now expected to answer or engage with the question.
```

## Scenario 2: Ask-Stage Follow-Up

User is already in the reasoning-check part of the flow.

```text
+---------+
|   ASK   |
+---------+
  |
  | user answers, asks for more detail, or continues reasoning
  v
policy evaluates follow-up
  |
  | policy: allowed
  | retrieval: run only if no evidence is attached
  | response:
  |   - reasoning question or targeted clarification
  v
+--------+
|  HINT  |
+--------+
```

Flow target:

```text
After ASK has been satisfied, bounded hinting becomes available.
```

## Scenario 3: Hint-Stage Follow-Up

User has already gone through explanation and reasoning-check behavior.

```text
+--------+
|  HINT  |
+--------+
  |
  | user still needs help
  v
policy evaluates follow-up
  |
  | policy: allowed
  | retrieval: run only if no evidence is attached
  | response:
  |   - bounded hint
  |   - no direct completed solution
  v
+--------+
|  HINT  |
+--------+
```

Flow target:

```text
HINT is terminal in v1. Repeated help stays bounded inside HINT.
```

## Scenario 4: Direct Solution Request

User asks the system to solve, complete, or fix the task directly.

```text
+----------+
| ANY STAGE |
+----------+
  |
  | user says:
  |   "just solve it"
  |   "give me the answer"
  |   "write the solution"
  v
policy detects DIRECT_SOLUTION_REQUEST
  |
  | policy: allowed=False
  | retrieval: do not run
  | response:
  |   - negative boundary
  |   - expected current-stage behavior
  |   - why the request violates that stage
  |   - choices: follow current stage or return to explanation
  v
+------------+
| SAME STAGE |
+------------+
```

Expanded view:

```text
EXPLAIN
  |
  | direct solution request
  v
refuse direct solution
  |
  v
offer stage choices
  |
  v
EXPLAIN
```

Flow target:

```text
The user stays in the active learning stage instead of receiving a solution.
```

## Scenario 5: Stage-Skipping Attempt

User tries to jump from explanation directly to hinting.

```text
+---------+        +--------+
| EXPLAIN | --X--> |  HINT  |
+---------+        +--------+
     |
     | user asks for hint too early
     v
policy detects STAGE_SKIPPING
     |
     | policy: allowed=False
     | response:
     |   - negative boundary
     |   - expected current-stage behavior
     |   - why the shortcut is not allowed
     |   - choices: follow current stage or return to explanation
     v
+---------+
| EXPLAIN |
+---------+
```

Flow target:

```text
The last valid stage remains active; hinting is not unlocked.
```

## Scenario 6: Unsupported Source Evidence

User asks with attached evidence from outside the v1 source policy.

```text
+---------+
| EXPLAIN |
+---------+
  |
  | attached evidence uses unsupported source
  v
policy detects UNSUPPORTED_SOURCE_USAGE
  |
  | policy: allowed=False
  | retrieval: do not trust unsupported evidence
  | response:
  |   - explain source boundary
  |   - request or use valid project evidence
  v
+---------+
| EXPLAIN |
+---------+
```

Recommended target:

```text
unsupported source -> EXPLAIN
```

Reason:

```text
The problem is evidence validity, not shortcut behavior.
The system should respond by returning to grounded explanation.
```

## Scenario 7: Evidence Already Present

User asks for an explanation and valid evidence is already attached.

```text
+---------+
| EXPLAIN |
+---------+
  |
  | valid evidence already present
  | retrieval: skip
  | response:
  |   - explanation using attached evidence
  |   - verification question
  v
+---------+
|   ASK   |
+---------+
```

Flow target:

```text
Existing valid evidence still leads into the reasoning-check path.
```

## Scenario 8: Unknown Intent Heuristic

User intent starts as `UNKNOWN`, so policy classifies it deterministically.

```text
+---------+
|   ASK   |
+---------+
  |
  | intent=UNKNOWN
  | user says: "more detail"
  v
policy classifies FOLLOW_UP
  |
  | policy: allowed
  | retrieval: run only if no evidence is attached
  | response:
  |   - reasoning question or clarification
  v
+--------+
|  HINT  |
+--------+
```

Direct-solution heuristic variant:

```text
+----------+
| ANY STAGE |
+----------+
  |
  | intent=UNKNOWN
  | user says: "just solve it"
  v
policy classifies DIRECT_SOLUTION_REQUEST
  |
  v
+---------+
|   ASK   |
+---------+
```

## Full Scenario Map

```text
                           normal learning path

                              +---------+
                              | EXPLAIN |
                              +---------+
                                   |
                                   | response:
                                   | explanation + question
                                   v
                              +---------+
              +-------------- |   ASK   | <--------------+
              |               +---------+                |
              |                    |                     |
              |                    | reasoning checked   |
              |                    v                     |
              |               +--------+                 |
              |               |  HINT  | ----------------+
              |               +--------+
              |
              |
shortcut       |
boundary       |
              |
              v
          +-------------+
          | SAME STAGE  |
          +-------------+
```

With violation inputs:

```text
                             +---------+
                             | EXPLAIN |
                             +---------+
                              |      |
                              |      | direct solution
                              |      | or skip attempt
                              |      v
                              |   +---------+
                              |   | EXPLAIN |
                              |   +---------+
                              |
                              v
                           +---------+
                           |   ASK   |
                           +---------+
                                |
                                v
                           +--------+
                           |  HINT  |
                           +--------+
```

The system moves toward:

```text
grounded explanation -> verification question -> bounded hint
```

It does not move toward:

```text
direct answer -> completed solution
```
