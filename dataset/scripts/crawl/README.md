# Crawling More Games

## Python files

* grab_summaries.py - downloading raw summaries from [ROTOWIRE](https://www.rotowire.com/basketball/game-recaps.php) as htmls
* get_rotowire.py - parsing htmls and grabbing game stats
* preproc.py - contains functions prep_roto() for tokenizing, normalizing, and splitting aligned data, output train|valid|test.json
* run_pipeline.sh - a convenience script that executes functions from the files above serially (in the correct order).

## Running

```
./run_pipeline.sh
```