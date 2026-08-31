"""The guardrail suite (G1-G7).

These assert that a class of behaviour is impossible, not that a case works. That is why they are
reported as their own CI check and excluded from the coverage figure: a guardrail that merely has
coverage is not a guardrail.

Invariants whose enforcement arrives in a later phase carry an xfail naming the issue, so the suite
is a complete map of Spec 10 from the start rather than growing quietly.
"""
