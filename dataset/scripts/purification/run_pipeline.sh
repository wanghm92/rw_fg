#!/usr/bin/env bash
echo "json2txt"
python json2txt.py

echo "clean"
python clean.py

echo "filter"
for DATA in train valid test
do
    python pre_filter.py --dataset $DATA
done

echo "content plan and trim"
python extract_outline.py