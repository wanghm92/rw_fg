# -*- coding: utf-8 -*-
from text2num import text2num
import codecs, json, sys, io, os, copy

# add all records to valid and test
CWD = os.getcwd()
DATA = sys.argv[1]
INPUT_PATH = os.path.join("rotowire_temp", DATA)
print(INPUT_PATH)
os.chdir(INPUT_PATH)

# if DATA == 'train':
#     ORACLE_IE_OUTPUT = 'roto-original-%s.h5-tuples.txt'%DATA  # oracle content plan obtained from IE tool
#     SKIMMED_IE_OUTPUT = 'roto-gold-%s.h5-tuples.txt'%DATA  # oracle content plan obtained from IE tool
# else:
ORACLE_IE_OUTPUT = 'roto-gold-%s.h5-tuples.txt'%DATA  # oracle content plan obtained from IE tool
SKIMMED_IE_OUTPUT = 'roto-skimmed-%s.h5-tuples.txt'%DATA  # oracle content plan obtained from IE tool

INTER_CONTENT_PLAN = '%s_content_plan_tks.txt'%DATA  # intermediate content plan input to second stage
SRC_FILE = 'src_%s.txt'%DATA  # src file input to first stage
TRAIN_TGT_FILE = "tgt_%s.txt"%DATA  # tgt file of second stage
CONTENT_PLAN_OUT = '%s_content_plan_ids.txt'%DATA  # content plan output of first stage

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

#special records for enabling pointing to bos and eos in first stage
def add_special_records(records):
    record = []
    record.append(UNK_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    records.append(DELIM.join(record))
    record = []
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    records.append(DELIM.join(record))
    record = []
    record.append(BOS_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    records.append(DELIM.join(record))
    record = []
    record.append(EOS_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    record.append(PAD_WORD)
    records.append(DELIM.join(record))

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

    # NOTE: pre-pending special tokens, UNK, PAD, SOS, EOS
    # add_special_records(records)

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

    return records, home_players, vis_players

def get_ents(thing):
    players = set()
    teams = set()
    cities = set()
    total_teams = set()

    teams.add(thing["vis_name"])
    teams.add(thing["vis_line"]["TEAM-NAME"])
    teams.add(thing["vis_city"] + " " + thing["vis_name"])
    teams.add(thing["vis_city"] + " " + thing["vis_line"]["TEAM-NAME"])

    total_teams.add(thing["vis_city"] + " " + thing["vis_name"])
    total_teams.add(thing["vis_city"] + " " + thing["vis_line"]["TEAM-NAME"])
    teams.add(thing["home_name"])
    teams.add(thing["home_line"]["TEAM-NAME"])
    teams.add(thing["home_city"] + " " + thing["home_name"])
    teams.add(thing["home_city"] + " " + thing["home_line"]["TEAM-NAME"])

    total_teams.add(thing["home_city"] + " " + thing["home_name"])
    total_teams.add(thing["home_city"] + " " + thing["home_line"]["TEAM-NAME"])
    # special case for this
    if thing["vis_city"] == "Los Angeles":
        teams.add("LA" + thing["vis_name"])
    if thing["home_city"] == "Los Angeles":
        teams.add("LA" + thing["home_name"])
    if thing["vis_city"] == "LA":
        teams.add("Los Angeles " + thing["vis_name"])
    if thing["home_city"] == "LA":
        teams.add("Los Angeles " + thing["home_name"])
    # sometimes team_city is different
    cities.add(thing["home_city"])
    cities.add(thing["vis_city"])
    players.update(thing["box_score"]["PLAYER_NAME"].values())
    cities.update(thing["box_score"]["TEAM_CITY"].values())
    total_players = copy.deepcopy(players)
    total_cities = copy.deepcopy(cities)
    for entset in [players, teams, cities]:
        for k in list(entset):
            pieces = k.split()
            if len(pieces) > 1:
                for piece in pieces:
                    if len(piece) > 1 and piece not in ["II", "III", "Jr.", "Jr"]:
                        entset.add(piece)

    all_ents = players | teams | cities  # union of sets

    return all_ents, players, teams, cities, total_players, total_teams, total_cities

def resolve_name(name, total_players):
    for player_name in total_players:
        if name in player_name.split():
            return player_name
    return name

def resolve_team_name(name, total_teams):
    for team_name in total_teams:
        if name in team_name.split():
            return team_name
        elif len(team_name.split())>2 \
                and ((name == " ".join(team_name.split()[1:3])) or (name == " ".join(team_name.split()[0:2]))):
            return team_name
    return name

def replace(input):
    return input.replace(" ", "_")

def create_record(value, name, record_type, homeoraway):
    record = []
    record.append(value)
    record.append(name.replace(" ", "_"))
    record.append(record_type)
    record.append(homeoraway)
    return record

# read original json file
JSON = "%s.json"%DATA  # input train.json file
with io.open(JSON, 'r',  encoding='utf-8') as f:
    trdata = json.load(f)

trdata_out = []
print("Total number of records: ")
print(type(trdata))
print(len(trdata))
x = trdata[0]
print(x.keys())
for i in x.keys():
    print(i)
    if isinstance(x[i], dict):
        y = x[i]
        print(y.keys())

output_instances = []
instance_count = 0 #exclude the first blank line of this_sample_plan
content_plan_tks = []
skimmed_inputs = []
already_have = set()
name_exists = set()
summaries = []
src_instances = []

this_sample_plan = []
curr = []
src_instance = ''
summary = ''

cnt_empty = 0
dup = 0

# -------------------------- Conversion --------------------------#
with io.open(ORACLE_IE_OUTPUT, 'r',  encoding='utf-8') as fin:
    for line in fin.readlines():
        if len(line.strip()) == 0:
            already_have = set()
            name_exists = set()

            if instance_count > 0:
                # if DATA != 'train':
                #     summaries.append(summary)
                #     src_instances.append(src_instance)
                #     if len(this_sample_plan) > 0:
                #         content_plan_tks.append(RECORD_DELIM.join(this_sample_plan))
                #     else:
                #         # use UNK for val/test set of content plan if empty
                #         content_plan_tks.append(DELIM.join([EOS_WORD, EOS_WORD, EOS_WORD, EOS_WORD]))
                #         cnt_empty += 1
                #
                # else:
                if len(this_sample_plan) > 0:
                    summaries.append(summary)
                    src_instances.append(src_instance)
                    content_plan_tks.append(RECORD_DELIM.join(this_sample_plan))
                    trdata_out.append(entry)
                    skimmed_inputs.append(curr)
                # discard samples with empty content plan
                else:
                    cnt_empty += 1

            # reset to process the next
            this_sample_plan = []
            curr = []
            src_instance = ''
            summary = ''

            # read the next
            entry = trdata[instance_count]
            records, home_players, vis_players = box_prepro(entry)
            src_instance = " ".join(records)
            all_ents, players, teams, cities, total_players, total_teams, total_cities = get_ents(entry)
            box_score = entry["box_score"]
            player_name_map = {y: x for x, y in box_score['PLAYER_NAME'].items()}
            home_line_score = entry["home_line"]
            vis_line_score = entry["vis_line"]
            summary = entry['summary']
            instance_count += 1

        else:
            curr.append(line.strip())
            args = line.split("|")
            name = args[0]
            record_type = args[2].strip()
            value = args[1]
            if not value.isdigit():
                value = text2num(value)
            else:
                value = int(value)
            if record_type.startswith("PLAYER-"):
                record_type = record_type[len("PLAYER-"):]

            name = name.replace("UNK", "").strip()
            if name == 'Los Angeles' and 'LA' in total_cities:
                name = 'LA'
            if name in total_players:
                pass
            elif name in total_teams:
                pass
            elif name in players:
                name = resolve_name(name, total_players)
            elif name == 'Los Angeles Clippers' and 'LA Clippers' in total_teams:
                name = 'LA Clippers'
            elif name in teams:
                name = resolve_team_name(name, total_teams)
            elif name in total_cities:
                name = resolve_team_name(name, total_teams)

            record_added = False
            if not (name, record_type, value) in already_have:
                if name in player_name_map and record_type in box_score \
                        and box_score[record_type][player_name_map[name]].isdigit() \
                        and int(box_score[record_type][player_name_map[name]]) == value:
                    homeoraway = ""
                    if player_name_map[name] in home_players:
                        homeoraway = "HOME"
                    elif player_name_map[name] in vis_players:
                        homeoraway = "AWAY"
                    if name not in name_exists:
                        record = create_record(box_score['FIRST_NAME'][player_name_map[name]], name, 'FIRST_NAME', homeoraway)
                        this_sample_plan.append(DELIM.join(record))
                        if box_score['SECOND_NAME'][player_name_map[name]] != NA:
                            record = create_record(box_score['SECOND_NAME'][player_name_map[name]], name, 'SECOND_NAME', homeoraway)
                            this_sample_plan.append(DELIM.join(record))
                    record = create_record(str(value), name, record_type, homeoraway)
                    this_sample_plan.append(DELIM.join(record))
                    record_added = True
                elif name.endswith(home_line_score['TEAM-NAME']) and int(home_line_score[record_type]) == value:
                    if name not in name_exists:
                        record = create_record(home_line_score['TEAM-CITY'].replace(" ", "_"),
                                               home_line_score['TEAM-NAME'].replace(" ", "_"), "TEAM-CITY", HOME)
                        this_sample_plan.append(DELIM.join(record))

                        record = create_record(home_line_score['TEAM-NAME'].replace(" ", "_"),
                                               home_line_score['TEAM-NAME'].replace(" ", "_"), "TEAM-NAME", HOME)
                        this_sample_plan.append(DELIM.join(record))

                    record = create_record(str(value), home_line_score['TEAM-NAME'].replace(" ", "_"), record_type, HOME)
                    this_sample_plan.append(DELIM.join(record))
                    record_added = True
                elif name.endswith(vis_line_score['TEAM-NAME']) and int(vis_line_score[record_type]) == value:
                    if name not in name_exists:
                        record = create_record(vis_line_score['TEAM-CITY'].replace(" ", "_"),
                                               vis_line_score['TEAM-NAME'].replace(" ", "_"), "TEAM-CITY", AWAY)
                        this_sample_plan.append(DELIM.join(record))

                        record = create_record(vis_line_score['TEAM-NAME'].replace(" ", "_"),
                                               vis_line_score['TEAM-NAME'].replace(" ", "_"), "TEAM-NAME", AWAY)
                        this_sample_plan.append(DELIM.join(record))

                    record = create_record(str(value), vis_line_score['TEAM-NAME'].replace(" ", "_"), record_type, AWAY)
                    this_sample_plan.append(DELIM.join(record))
                    record_added = True
                if record_added:
                    already_have.add((name, record_type, value))
                    name_exists.add(name)
            else:
                dup += 1

print("content plans: %d"%(instance_count))
print("empty content plans: %d"%cnt_empty)
print("duplicated records: %d"%dup)

# append last entry
# if DATA == 'train':
if len(this_sample_plan) > 0:
    content_plan_tks.append(RECORD_DELIM.join(this_sample_plan))
    summaries.append(summary)
    src_instances.append(src_instance)
    trdata_out.append(entry)
    skimmed_inputs.append(curr)
# else:
#     content_plan_tks.append(RECORD_DELIM.join(this_sample_plan))
#     summaries.append(summary)
#     src_instances.append(src_instance)

# content plans
with io.open(INTER_CONTENT_PLAN, 'w', encoding='utf-8') as fout:
    for plan in content_plan_tks:
        fout.write("%s\n" % plan)

# save summary
with io.open(TRAIN_TGT_FILE, 'w', encoding='utf-8') as fout:
    for summary in summaries:
        # summary = [word.encode("utf-8") for word in summary]
        fout.write("%s\n" % " ".join(summary))

# all input records
with io.open(SRC_FILE, 'w', encoding='utf-8') as fout:
    for src_instance in src_instances:
        fout.write("%s\n" % src_instance)
        # src_file.write("\n")

# indexing content plans
inputs = []
content_plans = []
with io.open(INTER_CONTENT_PLAN, 'r',  encoding='utf-8') as fin:
    for i, line in enumerate(fin):
        content_plans.append(line.split())
with io.open(SRC_FILE, 'r',  encoding='utf-8') as fin:
    for i, line in enumerate(fin):
        inputs.append(line.split())

content_plan_ids = []
for i, x in enumerate(inputs):
    plan = content_plans[i]
    ids = []
    for record in plan:
        try:
            ids.append(str(x.index(record)))
        except ValueError:
            ids.append('0')
    content_plan_ids.append(" ".join(ids))

with io.open(CONTENT_PLAN_OUT, 'w', encoding='utf-8') as fout:
    fout.write("\n".join(content_plan_ids))
    fout.write("\n")

# training samples with empty content plans are discarded
if len(trdata_out) > 0:
    print("saving remaining json items")
    with io.open('%s.skimmed.json'%DATA, 'w+', encoding='utf-8') as fout:
        json.dump(trdata_out, fout)

if len(skimmed_inputs) > 0:  # and DATA == 'train':
    print(len(skimmed_inputs))
    flag = True
    if os.path.isfile(SKIMMED_IE_OUTPUT):
        message = input('%s already exists, do you want to overwrite? [y/n]:'%SKIMMED_IE_OUTPUT)
        if message == 'y':
            flag = True
        else:
            flag = False

    if flag:
        with io.open(SKIMMED_IE_OUTPUT, 'w+', encoding='utf-8') as fout:
            fout.write("\n")
            for x in skimmed_inputs:
                fout.write("\n".join(x))
                fout.write("\n\n")

os.chdir(CWD)
