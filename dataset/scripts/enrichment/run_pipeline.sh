#!/usr/bin/env bash
echo "add_feat"
python add_feat.py

echo "extract_outline_ext"
python extract_outline_ext.py

echo "finalize"
python finalize.py

for DATA in train valid test
do
    echo "copying files to new_ws2017"
    mkdir -p ../../rotowire_fg/new_ws2017_v2
    cp ../../rotowire_fg/new_extend/$DATA/$DATA.trim.ws.json ../../rotowire_fg/new_ws2017_v2/$DATA.json

    echo "copying files to new_ncpcc"
    mkdir -p ../../rotowire_fg/new_ncpcc/$DATA
    cp ../../rotowire_fg/new_extend/$DATA/*.ncp* ../../rotowire_fg/new_ncpcc/$DATA
    cp ../../rotowire_fg/new_extend/$DATA/$DATA\_content_plan_tks.txt ../../rotowire_fg/new_ncpcc/$DATA
    cp ../../rotowire_fg/new_extend/$DATA/tgt_$DATA.norm.filter.mwe.trim.txt ../../rotowire_fg/new_ncpcc/$DATA
    cp ../../rotowire_fg/new_extend/$DATA/$DATA\_ptrs.txt ../../rotowire_fg/new_ncpcc/$DATA
done

ls -l ../../rotowire_fg/new_ws2017_v2/
ls -l ../../rotowire_fg/new_ncpcc/*