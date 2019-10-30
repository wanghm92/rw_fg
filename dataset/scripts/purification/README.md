# Purification

## Requirements
* jsonlines
* pprint

## Python files

* json2txt.py - convert the original json (converted to jsonl for convenience) format datasets into onmt-py input formats
* clean.py - entity name (team name, city, arena, player names) normalization, fix limited tokenization errors
* pre_filter.py - discards about 12% (#words) contents without numerical facts
* extract_outline.py - use regex to extract content plans from summaries
* domain_knowledge.py - contains many shared string constants in the NBA domain
* run_pipeline.sh - a convenience script that executes functions from the files above serially (in the correct order).

## Running

```
./run_pipeline.sh
```

## Input - Output

* input: `new_jsonl/(train|valid|test).jsonl`
* json2txt.py --> `new_clean/(src|tgt)_(train|valid|test).txt`
* clean.py --> `new_clean/(src|tgt)_(train|valid|test).norm.(tk|mwe).txt`
* pre_filter.py --> `new_clean/(src|tgt)_(train|valid|test).norm.filter.(tk|mwe).txt`
* extract_outline.py -->
        `(train|valid|test).trim.json`
        `(train|valid|test)_content_plan_tks.txt`
        `(train|valid|test)_content_plan_ids.txt`
        `(train|valid|test)_ptrs.txt`
        `tgt_(train|valid|test).norm.filter.mwe.trim.txt`
        `tgt_(train|valid|test).norm.filter.mwe.trim.full.txt`
        `src_(train|valid|test).norm.trim.txt`