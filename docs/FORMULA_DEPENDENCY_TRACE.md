# Formula Dependency Trace

## 30 formula-backed attendance cells — `samples/test1.xlsx` — Sheet `Shif (2)`

---

## Global Context

| Property | Value |
|---|---|
| Workbook | `samples/test1.xlsx` |
| Sheet | `Shif (2)` |
| Total employees | 299 |
| Total formula cells (date-indexed) | 30 |
| Total formula cells (all employee rows) | 30 (Shif 2) + 2505 (TESS-2 TERRIER, summary columns) |
| DateIndexer columns | L(12)=Day10 through col 33 (Days 10–31) |
| Non-indexed attendance columns | E(5)=Day1, F(6)=Day2, G(7)=Day3, H(8)=Day4, I(9)=Day5, J(10)=Day6, K(11)=Day7 |
| Formula patterns | 6 (M, N, O, T, U, V) × 5 employees = 30 |

---

## Pattern Identification

All 30 formula cells follow exactly 6 column patterns:

| Pattern | Column | Day | Formula | Hops | Reference target |
|---|---|---|---|---|---|
| M | M (col 13) | 11 | `=F{row}` | 1 | F(col 6) = Day 2 direct value |
| N | N (col 14) | 12 | `=G{row}` | 1 | G(col 7) = Day 3 direct value |
| O | O (col 15) | 13 | `=H{row}` | 1 | H(col 8) = Day 4 direct value |
| T | T (col 20) | 18 | `=M{row}` | 2 | M(formula) → F(Day 2 direct) |
| U | U (col 21) | 19 | `=N{row}` | 2 | N(formula) → G(Day 3 direct) |
| V | V (col 22) | 20 | `=O{row}` | 2 | O(formula) → H(Day 4 direct) |

All references are **same-row, same-employee**. No cross-employee formula references.

---

## Full Dependency Chains (All 30 Cells)

### Pattern M — Day 11 — `=F{row}` (1 hop, direct)

```
M13 = =F13  →  F13 = 'WO'  (BK447)
M24 = =F24  →  F24 = 'WO'  (MO840)
M26 = =F26  →  F26 = 'WO'  (MO274)
M38 = =F38  →  F38 = 'WO'  (SCH30)
M44 = =F44  →  F44 = 'WO'  (SCE98)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| M13 | BK447 | `=F13` | (none) | F13 | `'WO'` | YES |
| M24 | MO840 | `=F24` | (none) | F24 | `'WO'` | YES |
| M26 | MO274 | `=F26` | (none) | F26 | `'WO'` | YES |
| M38 | SCH30 | `=F38` | (none) | F38 | `'WO'` | YES |
| M44 | SCE98 | `=F44` | (none) | F44 | `'WO'` | YES |

### Pattern N — Day 12 — `=G{row}` (1 hop, direct)

```
N12 = =G12  →  G12 = 'WO'  (AQ152)
N27 = =G27  →  G27 = 'WO'  (NG595)
N34 = =G34  →  G34 = 'WO'  (RR235)
N41 = =G41  →  G41 = 'WO'  (SBI80)
N50 = =G50  →  G50 = 'WO'  (VF395)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| N12 | AQ152 | `=G12` | (none) | G12 | `'WO'` | YES |
| N27 | NG595 | `=G27` | (none) | G27 | `'WO'` | YES |
| N34 | RR235 | `=G34` | (none) | G34 | `'WO'` | YES |
| N41 | SBI80 | `=G41` | (none) | G41 | `'WO'` | YES |
| N50 | VF395 | `=G50` | (none) | G50 | `'WO'` | YES |

### Pattern O — Day 13 — `=H{row}` (1 hop, direct)

```
O8  = =H8   →  H8  = 'WO'  (KI996)
O9  = =H9   →  H9  = 'WO'  (AO824)
O19 = =H19  →  H19 = 'WO'  (LC141)
O21 = =H21  →  H21 = 'WO'  (MN457)
O43 = =H43  →  H43 = 'WO'  (SAR55)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| O8 | KI996 | `=H8` | (none) | H8 | `'WO'` | YES |
| O9 | AO824 | `=H9` | (none) | H9 | `'WO'` | YES |
| O19 | LC141 | `=H19` | (none) | H19 | `'WO'` | YES |
| O21 | MN457 | `=H21` | (none) | H21 | `'WO'` | YES |
| O43 | SAR55 | `=H43` | (none) | H43 | `'WO'` | YES |

### Pattern T — Day 18 — `=M{row}` (2 hops, chain)

```
T13 = =M13  →  M13 = =F13  →  F13 = 'WO'  (BK447)
T24 = =M24  →  M24 = =F24  →  F24 = 'WO'  (MO840)
T26 = =M26  →  M26 = =F26  →  F26 = 'WO'  (MO274)
T38 = =M38  →  M38 = =F38  →  F38 = 'WO'  (SCH30)
T44 = =M44  →  M44 = =F44  →  F44 = 'WO'  (SCE98)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| T13 | BK447 | `=M13` | M13 | F13 | `'WO'` | YES |
| T24 | MO840 | `=M24` | M24 | F24 | `'WO'` | YES |
| T26 | MO274 | `=M26` | M26 | F26 | `'WO'` | YES |
| T38 | SCH30 | `=M38` | M38 | F38 | `'WO'` | YES |
| T44 | SCE98 | `=M44` | M44 | F44 | `'WO'` | YES |

### Pattern U — Day 19 — `=N{row}` (2 hops, chain)

```
U12 = =N12  →  N12 = =G12  →  G12 = 'WO'  (AQ152)
U27 = =N27  →  N27 = =G27  →  G27 = 'WO'  (NG595)
U34 = =N34  →  N34 = =G34  →  G34 = 'WO'  (RR235)
U41 = =N41  →  N41 = =G41  →  G41 = 'WO'  (SBI80)
U50 = =N50  →  N50 = =G50  →  G50 = 'WO'  (VF395)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| U12 | AQ152 | `=N12` | N12 | G12 | `'WO'` | YES |
| U27 | NG595 | `=N27` | N27 | G27 | `'WO'` | YES |
| U34 | RR235 | `=N34` | N34 | G34 | `'WO'` | YES |
| U41 | SBI80 | `=N41` | N41 | G41 | `'WO'` | YES |
| U50 | VF395 | `=N50` | N50 | G50 | `'WO'` | YES |

### Pattern V — Day 20 — `=O{row}` (2 hops, chain)

```
V8  = =O8   →  O8  = =H8   →  H8  = 'WO'  (KI996)
V9  = =O9   →  O9  = =H9   →  H9  = 'WO'  (AO824)
V19 = =O19  →  O19 = =H19  →  H19 = 'WO'  (LC141)
V21 = =O21  →  O21 = =H21  →  H21 = 'WO'  (MN457)
V43 = =O43  →  O43 = =H43  →  H43 = 'WO'  (SAR55)
```

| Cell | Employee | Display | Intermediate | Source | Src Value | Entry? |
|------|----------|---------|-------------|--------|-----------|--------|
| V8 | KI996 | `=O8` | O8 | H8 | `'WO'` | YES |
| V9 | AO824 | `=O9` | O9 | H9 | `'WO'` | YES |
| V19 | LC141 | `=O19` | O19 | H19 | `'WO'` | YES |
| V21 | MN457 | `=O21` | O21 | H21 | `'WO'` | YES |
| V43 | SAR55 | `=O43` | O43 | H43 | `'WO'` | YES |

---

## Consolidated Dependency Map

```
Day  2 (col F):  F{row} = 'WO'  (direct value — true entry cell)
Day  3 (col G):  G{row} = 'WO'  (direct value — true entry cell)
Day  4 (col H):  H{row} = 'WO'  (direct value — true entry cell)
     ↑              ↑
     │              │
Day 11 (col M):  M{row} = =F{row}   (formula — derived)
Day 12 (col N):  N{row} = =G{row}   (formula — derived)
Day 13 (col O):  O{row} = =H{row}   (formula — derived)
     ↑              ↑
     │              │
Day 18 (col T):  T{row} = =M{row}   (formula — derived from derived)
Day 19 (col U):  U{row} = =N{row}   (formula — derived from derived)
Day 20 (col V):  V{row} = =O{row}   (formula — derived from derived)
```

**Three levels:**
- **Level 1 (Source):** F/G/H columns — direct values, true attendance entry cells
- **Level 2 (Derived):** M/N/O columns — simple formulas referencing Level 1
- **Level 3 (Double-derived):** T/U/V columns — chain formulas referencing Level 2

---

## Write Destination Analysis

### Option A: Formula Cell (display cell)

Write to M13, N12, O8, T13, etc.

| Pro | Con |
|-----|-----|
| User's value appears in the intended day column | Formula is destroyed permanently |
| Same column the DateIndexer maps to | Spreadsheet design relationship is lost |
| Simple to implement — current behavior | Data integrity violation |

### Option B: First Referenced Cell

Write to the cell the formula immediately references.

| Case | Write to | Problem |
|------|----------|---------|
| Direct (M13 → F13) | F13 | F13 is Level 1 — same as Option C |
| Chain (T13 → M13) | M13 | M13 is also a formula — would need recursion |

For chain formulas, Option B writes to another formula cell. This requires recursive resolution anyway — and the final result is the same as Option C.

### Option C: Final Non-Formula Source Cell

Write to the terminal cell after resolving the full dependency chain.

| Pro | Con |
|-----|-----|
| Preserves all formulas in the chain | Write lands on a different column than the user selected |
| A single write cascades through all dependents | Target column (F/G/H) is NOT in DateIndexer |
| Maintains spreadsheet data integrity | Requires special write path for non-indexed columns |
| Source cells ARE true attendance entry cells | Column headers are strings ('04', '05', '06') |

---

## Conclusion

**Recommended: Option C — write to the final non-formula source cell.**

Evidence:
- All 30 formula cells ultimately resolve to columns F(6)/G(7)/H(8)
- These columns contain direct values manually entered by the attendance officer
- These ARE true attendance entry cells — they are physically in the attendance grid, just not DateIndexer-indexed (row 5 values are strings, not ints)
- Writing to F13 preserves `=F13` in M13 and `=M13` in T13 — the change cascades correctly
- Option A (current behavior) destroys the formula — proven by FORMULA_COMMIT_TRACE.md
- Option B is equivalent to C for direct references and equivalent to A (with recursion) for chain references

**Tradeoff:** The user selects Day 11 via the DateIndexer which maps to column M. But Option C writes to column F (Day 2). The semantic is: "Day 11 = Day 2 = new value" — the formula relationship is preserved, and the displayed value in Day 11 changes as expected.

**Required mechanism:** The app needs to detect formula cells in the write path, resolve the dependency chain, and write to the resolved source cell even when that cell's column is not in the DateIndexer.
