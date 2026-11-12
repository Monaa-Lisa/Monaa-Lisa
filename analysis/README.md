# Analysis

Scripts that measure the map, read only against the database. They change
nothing and are not part of the pipeline.

## evaluate_map.py

How well the 2-d map keeps what the 128-d embedding and the citations say.

```
DATABASE_URL=postgresql://user:password@host:5432/db python analysis/evaluate_map.py --json results.json
```

Needs numpy and psycopg2. The sample is drawn with a fixed seed (`--seed`),
so a run can be repeated.

Result on the dataset of November 2026 (1,224,767 papers with a map
position, published up to January 2020, all of them with an embedding in
the database; seed 7, 2,000 papers and 200,000 citing pairs sampled):

| Measurement | Map | Reference |
|---|---|---|
| 10 nearest in the embedding that are also among the 10 nearest on the map | 2.7 % | chance 0.001 % |
| the same for 30 | 4.0 % | chance 0.002 % |
| the same for 100 | 5.9 % | chance 0.008 % |
| 10 nearest in the embedding that are among the 100 nearest on the map | 15.1 % | |
| a citing pair is closer than a random pair (AUC) | 0.966 | 0.5 = chance |
| the same pairs in the embedding | 0.966 | 0.985 in the embedding |
| median map distance of a citing pair | 0.41 | 7.81 for a random pair |
| 10 nearest on the map with the same primary category | 40.9 % | chance 1.7 % |
| 10 nearest on the map with the same subject | 85.8 % | chance 38.5 % |

Reading: the map keeps the coarse structure well. Papers that cite each
other are close, nearly as reliably as in the embedding itself, and a paper's
surroundings are mostly its own subject. It does not keep the exact nearest
neighbours: of the ten most similar papers in the embedding, on average fewer
than one is also among the ten nearest on the map. Two dimensions cannot hold
the neighbourhoods of 128, so "close on the map" means "same topic area", not
"most similar paper". The application therefore takes similar papers from the
embedding where it has one.

Limits: the 768-d SPECTER2 vectors are not stored, so the reference is the
PCA reduced embedding the map was projected from. Map positions are stored
with three decimals.
