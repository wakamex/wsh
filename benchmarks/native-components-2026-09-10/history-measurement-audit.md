# Repeated-search fixture reset

The first real-editor timing run left the prior result equal to the query after exhausting unique matches. Subsequent samples resumed that exhausted search instead of starting another full search. Those numbers are retained as `invalid-cached-summary.json` and excluded. The capture widget now clears the prior-result marker after clearing the buffer, so every measured sequence starts a fresh search. The same reset applies to both owners outside their measured navigation work. Repeat correctness before the corrected timing run.
