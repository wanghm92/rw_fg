#!/usr/bin/env bash
PY3=/path/to/bin/python3
BASE=../../rotowire_fg/new_ncpcc   # /path/to/new_ncpcc
IDENTIFIER=newcc-trl

TRAIN_SRC1=$BASE/train/src_train.norm.trim.ncp.txt
TRAIN_TGT1=$BASE/train/train_content_plan_ids.ncp.txt
TRAIN_SRC2=$BASE/train/train_content_plan_tks.txt
TRAIN_TGT2=$BASE/train/tgt_train.norm.filter.mwe.trim.txt
TRAIN_PTR=$BASE/train/train_ptrs.txt

wc $TRAIN_SRC1 $TRAIN_TGT1 $TRAIN_SRC2 $TRAIN_TGT2 $TRAIN_PTR

VALID_SRC1=$BASE/valid/src_valid.norm.trim.ncp.txt
VALID_TGT1=$BASE/valid/valid_content_plan_ids.ncp.txt
VALID_SRC2=$BASE/valid/valid_content_plan_tks.txt
VALID_TGT2=$BASE/valid/tgt_valid.norm.filter.mwe.trim.txt

wc $VALID_SRC1 $VALID_TGT1 $VALID_SRC2 $VALID_TGT2

###################################################################################################
PREPRO=$BASE/pt_data/$IDENTIFIER
mkdir -p $PREPRO

OUTPUT=output_models/$IDENTIFIER
mkdir -p $OUTPUT

SUM_OUT=output_summaries/$IDENTIFIER
mkdir -p $SUM_OUT

####################################################################################################
echo "run preprocessing"
python preprocess.py -train_src1 $TRAIN_SRC1 -train_tgt1 $TRAIN_TGT1 -train_src2 $TRAIN_SRC2 -train_tgt2 $TRAIN_TGT2 -valid_src1 $VALID_SRC1 -valid_tgt1 $VALID_TGT1 -valid_src2 $VALID_SRC2 -valid_tgt2 $VALID_TGT2 -save_data $PREPRO/roto-$IDENTIFIER -src_seq_length 1000 -tgt_seq_length 1000 -dynamic_dict -train_ptr $TRAIN_PTR

####################################################################################################
echo "run training"
python train.py -data $PREPRO/roto-$IDENTIFIER -save_model $OUTPUT/roto -encoder_type1 mean -decoder_type1 pointer -enc_layers1 1 -dec_layers1 1 -encoder_type2 brnn -decoder_type2 rnn -enc_layers2 2 -dec_layers2 2 -batch_size 5 -feat_merge mlp -feat_vec_size 600 -word_vec_size 600 -rnn_size 600 -seed 1234 -epochs 30 -optim adagrad -learning_rate 0.15 -adagrad_accumulator_init 0.1 -report_every 100 -copy_attn -truncated_decoder 100 -gpuid 0 -attn_hidden 64 -reuse_copy_attn -start_decay_at 4 -learning_rate_decay 0.97 -valid_batch_size 5 -tensorboard -tensorboard_log_dir $OUTPUT/events

###################################################################################################
echo " ****** Evaluation ****** "
for EPOCH in $(seq 1 30)
do
    for MODEL1 in $(ls $OUTPUT/roto_stage1*_e$EPOCH.pt)
    do

        for MODEL2 in $(ls $OUTPUT/roto_stage2*_e$EPOCH.pt)
        do

        echo "--"
        echo $MODEL1
        echo $MODEL2

        echo "--"
        echo " ****** STAGE 1 ****** "
        echo $VALID_SRC1
        python translate.py -model $MODEL1 -src1 $VALID_SRC1 -output $SUM_OUT/roto_stage1_$IDENTIFIER.e$EPOCH.valid.txt -batch_size 10 -max_length 80 -gpu 0 -min_length 20 -stage1

        echo " ****** create_content_plan_from_index ****** "
        python create_content_plan_from_index.py $VALID_SRC1 $SUM_OUT/roto_stage1_$IDENTIFIER.e$EPOCH.valid.txt $SUM_OUT/roto_stage1_$IDENTIFIER.e$EPOCH.h5-tuples.valid.txt  $SUM_OUT/roto_stage1_inter_$IDENTIFIER.e$EPOCH.valid.txt

        echo " ****** STAGE 2 ****** "
        python translate.py -model $MODEL1 -model2 $MODEL2 -src1 $VALID_SRC1 -tgt1 $SUM_OUT/roto_stage1_$IDENTIFIER.e$EPOCH.valid.txt -src2 $SUM_OUT/roto_stage1_inter_$IDENTIFIER.e$EPOCH.valid.txt -output $SUM_OUT/roto_stage2_$IDENTIFIER.e$EPOCH.valid.txt -batch_size 10 -max_length 850 -min_length 150 -gpu 0

        echo " ****** BLEU ****** "
        perl ../evaluation/multi-bleu.perl $VALID_TGT2 < $SUM_OUT/roto_stage2_$IDENTIFIER.e$EPOCH.valid.txt

        cd ../evaluation/
        echo " ****** RG CS CO ****** "
        $PY3 evaluate.py --dataset valid --hypo $SUM_OUT/roto_stage2_$IDENTIFIER.e$EPOCH.valid.txt --plan $SUM_OUT/roto_stage1_inter_$IDENTIFIER.e$EPOCH.valid.txt
        cd ../model

        done
    done
done