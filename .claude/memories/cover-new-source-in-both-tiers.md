# Cover new source in both tiers

Every new branch in `src/` needs a unit test and an integration test. The
unit and integration jobs each demand 100% coverage of the whole source on
their own, so a line only one tier reaches fails the other.
