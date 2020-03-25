# Enrichment

## Requirements
* jsonlines
* pprint

## Python files

* `add_feat.py` - add game arena and team statistics breakdowns as described in the paper
* `extract_outline_ext.py` - updated content plan extractor with the enriched boxscore tables
* `finalize.py` - converting to formats as inputs to different models
* `run_pipeline.sh` - a convenience script that executes functions from the files above serially (in the correct order).

## Running

```
./run_pipeline.sh
```

## Input - Output

* input and output file names are clearly specified in the code