# CBB Dashboard v1.2.1 hotfix

Fixes a production crash on historical/challenger slates that do not contain the new V1.1.3B Champion Training Games / Champion Training Dates columns.

The v1.2 status strip used `DataFrame.get()` without a Series default.  For absent columns pandas returned a scalar `None`, and the UI then called `.notna()` on that scalar.  v1.2.1 normalizes all optional status-strip inputs to numeric Series, preserving both historical V1.1.x boards and current V1.1.3B boards.
