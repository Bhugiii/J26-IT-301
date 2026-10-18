# Survey data for traveller segmentation

`SYNTHETIC_tourist_behaviour_619.csv` is generated test data (`python -m segmentation.synthetic`).
Every row is tagged `data_source = SYNTHETIC`. It is used to build and test the pipeline and is not
evidence about real tourists.

Real responses go in this folder as CSV files downloaded from the Google Form's response sheet. Git
ignores everything here except the synthetic file and this note, so real responses are never committed.
Run the pipeline on them with `python -m segmentation.pipeline data/segmentation/<file>.csv`.
