# Collatz Affine Rewrite Compass

Date: 2026-04-16

Command:

```text
.venv_test/bin/python scripts/run_collatz_affine_rewrite_compass.py
```

## What This Is

This is a search compass, not a proof artifact.

It treats the already Lean-proved family theorems as rewrite rules on affine families
of the form:

```text
n = a*t + b
```

and asks whether repeated rule composition can produce a strictly smaller affine leaf:

```text
a'*t + b'  with  a' < a  and  b' < b.
```

If so, the root family has a plausible composed descent certificate.

## Rule Inventory

The compass uses only rewrite rules justified by current Lean theorems:

```text
even1
odd2
one_mod_four
three_mod_sixteen
eleven_mod_32
twentythree_mod_32
seven_mod_128
fifteen_mod_128
fiftynine_mod_128
twoeightyseven_mod_1024
eightfifteen_mod_1024
fiveseventyfive_mod_1024
fiveeightythree_mod_1024
threefortyseven_mod_1024
threesixtyseven_mod_1024
twentyfiveeightyseven_mod_4096
sixfifteen_mod_4096
threeeightythree_mod_4096
```

Interpretation:

```text
odd2 is the generic two-step odd-to-odd affine rewrite
(a*t+b) -> ((3a/2)*t + (3b+1)/2)
when a is even and b is odd.

The other rules are the arithmetic family theorems already proved in Lean.
```

## Current Signal

On the unresolved mod-128 roots

```text
27, 31, 39, 47, 63, 71, 79, 91, 95, 103, 111, 123, 127
```

the affine rewrite search finds composed certificates for:

```text
39
79
95
123
```

and leaves unresolved:

```text
27
31
47
63
71
91
103
111
127
```

That unchanged root frontier is the main new fact.
The extra 1024 and 4096 rules are real, but they only apply after dyadic refinement of
the parent family.

## Example Certificates

```text
256*t + 39
-> odd2
384*t + 59
-> fiftynine_mod_128
243*t + 38
```

```text
256*t + 79
-> odd2
384*t + 119
-> twentythree_mod_32
324*t + 101
-> one_mod_four
243*t + 76
```

```text
256*t + 95
-> odd2
384*t + 143
-> fifteen_mod_128
243*t + 91
```

```text
256*t + 123
-> odd2
384*t + 185
-> one_mod_four
288*t + 139
-> eleven_mod_32
243*t + 118
```

## Why This Matters

This remains useful evidence that the concrete exit-family theorems behave like
a compositional rewrite system, not just isolated residue tricks.

But after adding the new refined rules, the stronger lesson is:

```text
rewrite alone is not enough
```

The likely missing object is now:

```text
a well-founded dyadic refinement + affine-family rewrite theorem
```

not just a longer list of hand-proved congruence lemmas.

## Next Use

Use this compass together with:

```text
docs/COLLATZ_AFFINE_REFINEMENT_COMPASS.md
```

The rewrite compass now tells us which parent roots still need refinement.
The refinement compass tells us how those parents branch.
