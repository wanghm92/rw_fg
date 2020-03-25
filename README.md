This repository contains the dataset and code for the [INLG 2019](https://www.inlg2019.com/) paper [Revisiting Challenges in Data-to-Text Generation with Fact Grounding](https://www.aclweb.org/anthology/W19-8639/)

:handshake:Please kindly cite this work if it helps your research:

    @inproceedings{wang-2019-revisiting,
    title = "Revisiting Challenges in Data-to-Text Generation with Fact Grounding",
    author = "Wang, Hongmin",
    booktitle = "Proceedings of the 12th International Conference on Natural Language Generation",
    month = oct # "{--}" # nov,
    year = "2019",
    address = "Tokyo, Japan",
    publisher = "Association for Computational Linguistics",
    url = "https://www.aclweb.org/anthology/W19-8639",
    doi = "10.18653/v1/W19-8639",
    pages = "311--322"}

## Get the dataset

- :ok_hand:The `dataset/scripts` contains the scripts to prepare the dataset from stratch.
    - The `crawl`, `purification` and `enrichment` directories have respective `README.md` files inside to describe their functionalities.

- :+1:**Download** from [rotowire_fg](https://drive.google.com/drive/folders/19hV_VegpJ8oZ0Qcnk72cd8AJlx2HfaBD?usp=sharing) and place the 3 folders under `dataset/`
    - The final purified, enriched and enlarged dataset are included in `new_ncpcc` without having to execute the scripts.


## Run the model
:point_right:Please go to the `README` in under `model`

## Run Evaluation Script
:point_right:Refer to [this line](https://github.com/wanghm92/rw_fg/blob/aed53780855dfc165cc46e191e77f6d83479a5a3/model/run.sh#L69) in the `model/run.sh`