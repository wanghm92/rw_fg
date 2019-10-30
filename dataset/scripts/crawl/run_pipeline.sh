#!/usr/bin/env bash

echo "download htmls from rotowire.com"
python grab_summaries.py

echo "parsing htmls and grabbing game stats"
python get_rotowire.py

echo "preprocessing"
python preproc.py
