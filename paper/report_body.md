# Solving Integer Square and Rectangle Packing with SAT/SMT Encodings

## Abstract

This project studies a grid-based packing problem. Given a rectangular container and a collection of axis-aligned squares or rectangles with integer side lengths, the task is to decide whether all pieces can be placed inside the container without overlap. Packing problems are classical computationally difficult problems, and they appear in applications such as VLSI layout, manufacturing, storage allocation, cutting stock, and logistics. The focus of this project is not to design a specialized packing heuristic, but to implement a reduction from a packing instance to a SAT/SMT formula. A satisfying assignment of the formula corresponds to a valid packing, and an unsatisfiable formula means that no valid packing exists under the chosen model.

We begin with integer square packing as a baseline and then extend the tool to rectangle packing with optional 90-degree rotation. The implementation uses Z3 as the SMT solver. It supports JSON input instances, deterministic benchmark generation, runtime measurement, CSV summaries, and Matplotlib visualizations of satisfying assignments. This extension beyond squares is important because rectangle packing is closer to realistic layout and cutting applications, and it directly addresses the instructor's suggestion that extending beyond square packing would make the project more interesting.

## 1. Introduction

Packing problems ask whether a collection of objects can be placed into a bounded region without overlap. Even simple two-dimensional versions of packing are computationally difficult. Related problems such as bin packing, strip packing, and rectangular packing have been studied extensively in approximation algorithms and combinatorial optimization. These problems are also practically relevant: a chip designer wants to arrange components in a limited area, a manufacturer wants to cut parts from raw material with minimal waste, and a logistics planner wants to load objects into containers efficiently.

In this project, we consider a finite, integer-coordinate version of two-dimensional packing. The input describes a container and a list of pieces. Each piece must be placed at integer coordinates, must remain inside the container, and must not overlap with any other piece. The decision problem asks whether such a placement exists.

Our original proposal focused on square packing. After receiving feedback that extending beyond squares would be interesting, we expanded the project to support rectangles and optional rotation. This gives the final project three levels of functionality: a square-packing baseline, rectangle packing without rotation, and rectangle packing with optional 90-degree rotation. The last mode is the most interesting because the solver must decide both where each rectangle goes and whether each rectangle should be rotated.

The main purpose of the project is to show how a packing problem can be encoded as logical constraints and solved using an off-the-shelf SAT/SMT solver. We therefore emphasize the modeling choices, correctness of the encoding, formula size, and experimental behavior of the solver.

## 2. Problem Definition

The baseline problem is integer square packing. An instance consists of a square container with side length `L` and a list of square side lengths `s_1, s_2, ..., s_n`. Every number is a positive integer. A solution assigns each square `i` a lower-left coordinate `(x_i, y_i)` such that the square is completely inside the `L x L` container and no two squares overlap.

The implemented tool generalizes this baseline to rectangular containers and rectangular pieces. A rectangle instance consists of a container with width `C_W` and height `C_H`, together with pieces whose original dimensions are `(w_i, h_i)`. In the no-rotation mode, each rectangle must keep its original orientation. In the rotation mode, each rectangle may either keep its original orientation or rotate by 90 degrees, changing its effective dimensions from `(w_i, h_i)` to `(h_i, w_i)`.

The tool supports three modes:

- `squares`: every piece is a square and the container is square.
- `rectangles_no_rotation`: pieces are rectangles with fixed orientation.
- `rectangles_rotation`: each rectangle may optionally rotate by 90 degrees.

All three modes solve a decision/search problem. The solver first decides whether a feasible packing exists. If the instance is satisfiable, it also returns a concrete placement for every piece.

## 3. SAT Encoding

One direct way to reduce square packing to SAT is to enumerate every legal placement. For a square `i` with side length `s_i`, its legal placements are all integer coordinate pairs `(a, b)` such that `0 <= a <= L - s_i` and `0 <= b <= L - s_i`. Each legal placement means that the lower-left corner of square `i` is placed at `(a, b)`.

For every square `i` and every legal placement `p`, we introduce a Boolean variable `X_{i,p}`. The intended meaning is that `X_{i,p}` is true exactly when square `i` uses placement `p`.

The first set of clauses ensures that each square chooses exactly one placement. For every square, we add one at-least-one clause requiring it to choose some legal placement. We also add pairwise at-most-one clauses so that the same square cannot choose two different placements.

The second set of clauses enforces non-overlap. If placement `p` of square `i` and placement `q` of square `j` occupy at least one common grid cell, then these two placements cannot both be selected. For each such conflicting pair, we add the binary clause `not X_{i,p} or not X_{j,q}`.

This SAT formula is correct because every satisfying assignment selects exactly one legal placement for each square and never selects two overlapping placements. Therefore it gives a valid packing. Conversely, any valid packing selects one legal placement for every square and avoids all conflicting pairs, so it satisfies the formula.

The main downside of this SAT encoding is size. For square `i`, the number of legal placements is `(L - s_i + 1)^2`. Therefore the number of Boolean variables is the sum of these values over all squares. The number of exactly-one clauses and non-overlap clauses can also become large. This encoding is still polynomial in the number of enumerated placements, but it can be much larger than the SMT encoding used in our implementation.

## 4. SMT Encoding

Our implementation uses Z3's integer arithmetic interface directly. Instead of creating one Boolean variable for every possible placement, we create two integer variables for each piece: `x_i` and `y_i`. These variables represent the lower-left coordinate of piece `i`.

For a non-rotatable rectangle, the effective width and height are simply its original width and height. For a rotatable rectangle, we introduce a Boolean variable `r_i`. If `r_i` is false, the rectangle keeps its original orientation. If `r_i` is true, the rectangle is rotated by 90 degrees. In other words, the effective width is either `w_i` or `h_i`, and the effective height is the other dimension. In Z3, this is represented with conditional expressions.

The boundary constraints require every piece to stay inside the container. For each piece, we add constraints requiring `x_i >= 0`, `y_i >= 0`, `x_i + W_i <= C_W`, and `y_i + H_i <= C_H`, where `W_i` and `H_i` are the effective width and height of the piece after considering rotation.

The non-overlap constraints are added for every pair of distinct pieces. Two axis-aligned rectangles do not overlap if at least one of four cases is true: the first piece is left of the second, the second is left of the first, the first is below the second, or the second is below the first. Therefore, for each pair `i, j`, we add one disjunction containing these four alternatives.

This SMT encoding uses `2n` integer coordinate variables, up to `n` Boolean rotation variables, `4n` boundary inequalities, and `n(n-1)/2` pairwise non-overlap constraints. This is more compact than the direct SAT placement encoding, especially when the container is large.

The SMT encoding is correct for the same reason as the SAT encoding. If Z3 finds a satisfying model, the model assigns coordinates and rotation choices to all pieces. The boundary constraints guarantee that the pieces stay inside the container, and the non-overlap constraints guarantee that every pair is separated horizontally or vertically. Therefore the model gives a valid packing. Conversely, any valid packing directly defines values for all coordinate variables and rotation variables, and those values satisfy all constraints.

## 5. Preprocessing and Optimization

The solver includes a simple but useful area lower bound. If the total area of all pieces is greater than the area of the container, the instance is immediately unsatisfiable. This check avoids unnecessary solver calls for obviously impossible cases. For example, in the square baseline experiment, the total square area is 88. When the container side length is 9, the container area is 81, so the instance is unsatisfiable by area alone.

The implementation also sorts pieces by decreasing area before constructing constraints. This does not change satisfiability, but it often helps the solver reason about the largest and most restrictive pieces first.

Finally, the solver includes an optional symmetry-breaking constraint. When enabled, the largest piece is restricted to the lower-left half of the board. This is satisfiability preserving because any packing can be reflected horizontally and vertically so that the largest piece lies in that region. Symmetry breaking can reduce redundant search caused by equivalent reflected solutions.

## 6. Implementation

The project is implemented in Python using Z3 as the SMT backend. The core solver is in `src/packing_solver.py`. It defines the data structures for pieces, instances, placements, statistics, and solver results. It also builds the Z3 constraints and validates the returned model.

Input handling and deterministic instance generation are implemented in `src/instances.py`. The project supports JSON input files containing a container, a list of pieces, and solver settings such as timeout and symmetry breaking. The command `python -m src.solve_instance examples/rotation_witness.json --image results/rotation_witness.png` solves a single JSON instance and optionally writes a visualization.

The experiment runner is implemented in `src/experiments.py`. The command `python -m src.experiments --preset final` runs the full final-project experiment set, writes `results/summary.csv`, and generates PNG visualizations. The visualizations are implemented in `src/visualize.py` using Matplotlib.

The repository also includes unit tests in `tests/test_packing_solver.py`. These tests check single-piece satisfiability, area-bound unsatisfiability, rectangle non-overlap, a case where rotation changes feasibility, and JSON instance loading.

## 7. Experiments

The experiments are designed to show three things: the square-packing baseline works, the rectangle extension works, and allowing rotation can change the answer from unsatisfiable to satisfiable.

The square baseline uses the fixed square list `[5, 4, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1]`. The container side length varies from 30 down to 9. The total area of the pieces is 88. The solver finds satisfying assignments for container sizes 30, 25, 20, 15, 12, 11, and 10. For container size 9, the area lower bound proves unsatisfiability immediately because the container area is only 81.

The most important rectangle experiment compares fixed-orientation rectangle packing with rotatable rectangle packing. The container is `12 x 10`, and the same sequence of rectangles is tested with increasing numbers of pieces. For 4, 5, 6, and 7 pieces, both no-rotation and rotation modes are satisfiable. For 8 pieces, the no-rotation mode is unsatisfiable, while the rotation mode is satisfiable. This is the strongest experimental evidence that the extension beyond squares is meaningful: rotation is not just an extra variable, but can change the feasibility of an instance.

The 8-piece rectangle case also shows the cost of the extension. Without rotation, the solver reports unsatisfiable in about 0.0068 seconds. With rotation, the solver finds a satisfying assignment in about 0.2816 seconds. The rotated version is more expressive, but the solver must search over additional orientation choices.

The rotation witness gives a smaller version of the same phenomenon. Two `3 x 2` rectangles cannot both fit in a `5 x 3` container if rotation is forbidden. If rotation is allowed, one rectangle can rotate to become `2 x 3`, and the instance becomes satisfiable.

The final experiment group uses deterministic random rectangle instances. These experiments vary the number of pieces while keeping the container fixed. The results are written to `results/summary.csv`, including density, solver time, number of variables, number of assertions, and satisfiability status. These experiments help show how the solver behaves as density and instance size change.

## 8. Discussion

The experiments support the main claim of the project: SAT/SMT solvers can be used as a practical backend for solving small and medium grid-based packing instances. The SMT encoding is compact and easy to extend from squares to rectangles. Adding rotation requires only one Boolean variable per rotatable non-square rectangle and conditional expressions for effective width and height.

The project also illustrates a common tradeoff in solver-based modeling. A richer model can express more realistic constraints and solve instances that the simpler model cannot, but it may increase solver runtime. The rectangle rotation experiment demonstrates this clearly. Rotation makes the 8-piece instance satisfiable, but the solver spends more time finding the solution because it must reason about both coordinates and orientations.

The current tool is not intended to compete with highly optimized packing solvers. Its purpose is to demonstrate a clean reduction from a combinatorial geometry problem to SMT, produce valid placements, and support reproducible experiments. This matches the goal of the final project: showing how an NP-hard problem can be encoded and solved with an off-the-shelf SAT/SMT solver.

## 9. Team Contributions

Changqing Li focused on the SMT reduction, including the coordinate encoding, rotation variables, non-overlap constraints, and correctness argument.

Fei Keng focused on the Python implementation, JSON input handling, deterministic experiment generation, and visualization output.

Grant O'Connor focused on background research, experimental interpretation, and report writing, including the explanation of why packing problems are relevant to areas such as VLSI layout, manufacturing, and logistics.

## 10. Conclusion

This project demonstrates how integer packing problems can be solved through SAT/SMT encodings. We started with square packing and then extended the model to rectangle packing with optional rotation. The direct SAT encoding enumerates legal placements, while the implemented SMT encoding uses integer coordinate variables and pairwise disjunctive non-overlap constraints. For rotatable rectangles, the solver also uses Boolean rotation variables and conditional effective dimensions.

The implementation supports square packing, rectangle packing without rotation, and rectangle packing with rotation. It can read JSON instances, run deterministic experiments, output CSV summaries, and generate visualizations. The experiments show that the solver correctly handles satisfiable and unsatisfiable cases, and that rotation can change a rectangle-packing instance from unsatisfiable to satisfiable. Overall, the project shows that SMT is a natural and flexible way to model grid-based packing problems.

## References

Garey, M. R., and Johnson, D. S. *Computers and Intractability: A Guide to the Theory of NP-Completeness*. W. H. Freeman, 1979.

Coffman Jr., E. G., Garey, M. R., Johnson, D. S., and Tarjan, R. E. "Performance Bounds for Level-Oriented Two-Dimensional Packing Algorithms." *SIAM Journal on Computing*, 9(4), 808-826, 1980.

de Moura, L., and Bjorner, N. "Z3: An Efficient SMT Solver." *Tools and Algorithms for the Construction and Analysis of Systems*, 337-340, 2008.
