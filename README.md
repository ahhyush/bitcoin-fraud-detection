# Fraudulent Bitcoin transaction detection

BT4012 Kaggle competition (`bt-4012-competition-2026`): classify transactions of the
Elliptic Bitcoin graph as illicit (`1`) or licit (`0`). Each node is a transaction, each
edge a payment flow. Graded on ROC AUC.

Everything is in one notebook, [`e1113794.ipynb`](e1113794.ipynb): data checks, feature
selection, graph features, the models, validation, and the code that writes the two
submission files selected for the final private leaderboard.

| submission | public AUC | private AUC | notebook |
| --- | --- | --- | --- |
| `selftrain_wide_3649_stepquantile.csv` (top pick) | 0.95832 | 0.95986 | section 8 |
| `robust_struct_pu_refined.csv` (second pick) | 0.95031 | — | section 7 |

The notebook regenerates both CSVs into `submissions/` (the folder is created if it is
missing). On the machine used for the submissions they matched the uploaded files to about
1e-16.

## Data

Not included. Download the four files from the competition's Data tab and put them in
`data/raw/` (the folder is in the repository, empty):

```
data/raw/train.csv
data/raw/test.csv
data/raw/txs_edgelist.csv
data/raw/sample_submission.csv
```

| file | rows | contents |
| --- | --- | --- |
| `train.csv` | 141,772 | `txId`, `time_step`, `feat_1..feat_165`, `label` (missing for unknown transactions) |
| `test.csv` | 15,329 | `index`, `txId`, `time_step`, `feat_1..feat_165` |
| `txs_edgelist.csv` | 234,355 | directed edges `txId1 -> txId2` |
| `sample_submission.csv` | 15,329 | `index,target` |

Alternatively, with Kaggle credentials in `.env` (copy `.env.example`; `pip install kaggle`):
`python scripts/kaggle_data.py download`.

## Run

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash scripts/fix_openmp.sh        # macOS only, see below

.venv/bin/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 e1113794.ipynb
```

or open `e1113794.ipynb` in VS Code or JupyterLab and run all cells. Run it from the
repository root so that `data/raw/` resolves. The full run takes
about 12 minutes on a laptop (4 LightGBM threads); it writes
`submissions/robust_struct_pu_refined.csv` and `submissions/selftrain_wide_3649_stepquantile.csv`.

`scripts/fix_openmp.sh` is only for macOS machines without a system OpenMP runtime
(`brew install libomp` makes it unnecessary): LightGBM's wheel cannot find one, so the script
points it at the copy scikit-learn already bundles. Re-run it after reinstalling lightgbm.

Results match the uploaded CSVs to about 1e-16 with the pinned versions in
`requirements.txt` (Python 3.11, lightgbm 4.5.0, scikit-learn 1.5.2) and the fixed seeds in
the notebook. Other versions or thread counts can change the last digits, and with them the
order of a few tied rows.

## Contents of the notebook

1. Load and check the four files.
2. What the data look like: label shares, the edge-list-only transactions, graph structure.
3. Feature selection: 165 features to 97 (near-duplicates and drifting features dropped, time-like features kept).
4. Graph features: neighbour counts and eight structural features from the edge list.
5. The models: supervised LightGBM, a positive-unlabelled LightGBM, a graph smoother over the test predictions.
6. Validation: seven time-ordered windows, with the one illicit pattern that dominates the plain score removed.
7. Model A, the robust submission.
8. Model B, the top submission: a drift filter for steps 43-49, a score shift that grows with the time step, and three rounds of self-training.
9. Leaderboard evidence for each step of model B.

## Notes

- The submission is keyed on `test.csv`'s `index` column, not `txId`.
- Test time steps (36-49) come after train (1-35), so validation holds out late train steps
  and never splits at random.
- Edges only join transactions of the same time step, so no test transaction has a labelled
  neighbour; the graph is used for features of the neighbourhood and to smooth predictions.
- Steps 43-49 cannot be validated (validation ends at step 35), so the later parts of model B
  were chosen on the public leaderboard; section 9 says which gains that covers.
