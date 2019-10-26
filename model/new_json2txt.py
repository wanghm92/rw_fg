# -*- coding: utf-8 -*-
import codecs, json, sys, io, os, copy, argparse
from tqdm import tqdm

parser = argparse.ArgumentParser(description='pointer generator model')
parser.add_argument('--input', type=str, required=True, help='path to train/valid/test.json files')
parser.add_argument('--output', type=str, required=True, help='path to txt format files')
args = parser.parse_args()

os.makedirs(args.output, exist_ok=True)

RECORD_DELIM = " "
DELIM = u"￨"
NUM_PLAYERS = 13

HOME = "HOME"
AWAY = "AWAY"

PAD_WORD = '<blank>'
UNK_WORD = '<unk>'
UNK = 0
BOS_WORD = '<s>'
EOS_WORD = '</s>'
NA = 'N/A'

bs_keys = ["PLAYER-START_POSITION", "PLAYER-MIN", "PLAYER-PTS",
     "PLAYER-FGM", "PLAYER-FGA", "PLAYER-FG_PCT", "PLAYER-FG3M", "PLAYER-FG3A",
     "PLAYER-FG3_PCT", "PLAYER-FTM", "PLAYER-FTA", "PLAYER-FT_PCT", "PLAYER-OREB",
     "PLAYER-DREB", "PLAYER-REB", "PLAYER-AST", "PLAYER-TO", "PLAYER-STL", "PLAYER-BLK",
     "PLAYER-PF", "PLAYER-FIRST_NAME", "PLAYER-SECOND_NAME"]

ls_keys = ["TEAM-PTS_QTR1", "TEAM-PTS_QTR2", "TEAM-PTS_QTR3", "TEAM-PTS_QTR4",
    "TEAM-PTS", "TEAM-FG_PCT", "TEAM-FG3_PCT", "TEAM-FT_PCT", "TEAM-REB",
    "TEAM-AST", "TEAM-TOV", "TEAM-WINS", "TEAM-LOSSES", "TEAM-CITY", "TEAM-NAME"]

def get_player_idxs(entry):
    nplayers = 0
    home_players, vis_players = [], []
    for k, v in entry["box_score"]["PTS"].items():
        nplayers += 1

    num_home, num_vis = 0, 0
    for i in range(nplayers):
        player_city = entry["box_score"]["TEAM_CITY"][str(i)]
        if player_city == entry["home_city"]:
            if len(home_players) < NUM_PLAYERS:
                home_players.append(str(i))
                num_home += 1
        else:
            if len(vis_players) < NUM_PLAYERS:
                vis_players.append(str(i))
                num_vis += 1

    if entry["home_city"] == entry["vis_city"] and entry["home_city"] == "Los Angeles":
        home_players, vis_players = [], []
        num_home, num_vis = 0, 0
        for i in range(nplayers):
            if len(vis_players) < NUM_PLAYERS:
                vis_players.append(str(i))
                num_vis += 1
            elif len(home_players) < NUM_PLAYERS:
                home_players.append(str(i))
                num_home += 1

    return home_players, vis_players

def box_prepro(entry):
    # an entry contains 9 items: home_name, box_score, home_city, vis_name, summary, vis_line, vis_city, day, home_line
    records = []

    home_players, vis_players = get_player_idxs(entry)
    for ii, player_list in enumerate([home_players, vis_players]):
        for j in range(NUM_PLAYERS):
            player_key = player_list[j] if j < len(player_list) else None
            player_name = entry["box_score"]['PLAYER_NAME'][player_key] if player_key is not None else NA
            for k, key in enumerate(bs_keys):
                rulkey = key.split('-')[1]
                val = entry["box_score"][rulkey][player_key] if player_key is not None else NA
                record = []
                record.append(val.replace(" ", "_"))
                record.append(player_name.replace(" ","_"))
                record.append(rulkey)
                record.append(HOME if ii == 0 else AWAY)
                records.append(DELIM.join(record))

    for k, key in enumerate(ls_keys):
        record = []
        record.append(entry["home_line"][key].replace(" ","_"))
        record.append(entry["home_line"]["TEAM-NAME"].replace(" ","_"))
        record.append(key)
        record.append(HOME)
        records.append(DELIM.join(record))
    for k, key in enumerate(ls_keys):
        record = []
        record.append(entry["vis_line"][key].replace(" ","_"))
        record.append(entry["vis_line"]["TEAM-NAME"].replace(" ","_"))
        record.append(key)
        record.append(AWAY)
        records.append(DELIM.join(record))

    return records

summaries, src_instances = [], []

for DATA in ['train', 'valid', 'test']:
    with codecs.open(os.path.join(args.input, "{}.json".format(DATA)), 'r', encoding='utf-8') as fin:
        dataset = json.load(fin)
        for entry in tqdm(dataset):
            records = box_prepro(entry)
            summaries.append(entry['summary'])
            src_instances.append(records)

    # save summary
    with io.open(os.path.join(args.output, 'tgt_{}.txt'.format(DATA)), 'w', encoding='utf-8') as fout:
        for summary in summaries:
            fout.write("{}\n".format(" ".join(summary)))

    # save records
    with io.open(os.path.join(args.output, 'src_{}.txt'.format(DATA)), 'w', encoding='utf-8') as fout:
        for s in src_instances:
            fout.write("{}\n".format(" ".join(s)))