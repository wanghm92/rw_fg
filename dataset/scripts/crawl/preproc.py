import re
import json, sys, os, codecs, pdb, jsonlines
from nltk import word_tokenize
import copy
from tqdm import tqdm
from pprint import pprint
from random import shuffle

num_patt = re.compile('([+-]?\d+(?:\.\d+)?)')


def to_int(matchobj):
    num = int(round(float(matchobj.group(0)),0)) # rounds to nearest integer
    return str(num)


# functions below do the following:
# - tokenizes and separates hyphens from summaries
# - maps everything to an integer; pcts are in [0, 100]

def prep_tokes(thing):
    out = copy.deepcopy(thing)
    # remove all newline stuff
    summ = thing['summary'].replace(u'\xa0', ' ')
    summ = summ.replace('\\n', ' ').replace('\r', ' ')
    summ = re.sub("<[^>]*>", " ", summ)
    # replace all numbers with rounded integers
    summ = num_patt.sub(to_int, summ)
    tokes = word_tokenize(summ)
    # replace hyphens
    newtokes = []
    [newtokes.append(toke) if toke[0].isupper() or '-' not in toke
      else newtokes.extend(toke.replace('-', " - ").split()) for toke in tokes]
    out['summary'] = newtokes
    return out


def prep_nums(thing):
    # do box scores
    out = copy.deepcopy(thing)
    for k, d in thing['box_score'].items():
        if "PCT" in k:
            for idx, pct in d.items():
                if pct is not None:
                    out['box_score'][k][idx] = str(int(round(float(pct)*100, 0)))
                else:
                    out['box_score'][k][idx] = "N/A"
        elif k == "MIN":
            for idx, time in d.items():
                if time is not None:
                    mins, seconds = None, None
                    try:
                        mins, seconds = time.split(':') # these are actually probably minutes and seconds
                    except AttributeError as ex: # sometimes these are integers i guess
                        mins, seconds = time, 0
                    frac_mins = float(mins) + float(seconds)/60
                    out['box_score'][k][idx] = str(int(round(frac_mins, 0)))
                else:
                    out['box_score'][k][idx] = "N/A"
        else: # everything else assumed to be integral
            for idx, num in d.items():
                # see if we can make it a number
                if num is not None and num != "":
                    try:
                        fnum = float(num)
                        out['box_score'][k][idx] = str(int(round(fnum, 0)))
                    except ValueError:
                        pass
                else:
                    out['box_score'][k][idx] = "N/A"

    # do line scores
    linekeys = ['home_line', 'vis_line']
    for lk in linekeys:
        for k in thing[lk].keys():
            v = thing[lk][k]
            if "PCT" in k and v is not None:
                out[lk][k] = str(int(round(float(v)*100, 0)))
            elif k == "TEAM_WINS_LOSSES" and v is not None:
                wins, losses = v.split('-')
                out[lk]['WINS'] = wins
                out[lk]['LOSSES'] = losses
                del out[lk][k]
            elif v is not None:
                try:
                    fnum = float(v)
                    out[lk][k] = str(int(round(fnum, 0)))
                except ValueError:
                    pass

    return out


def add_player_names(thing):
    # will leave off any third name nonsense
    out = copy.deepcopy(thing)
    out['box_score']['FIRST_NAME'] = {}
    out['box_score']['SECOND_NAME'] = {}
    for k, v in thing['box_score']['PLAYER_NAME'].items():
        names = v.split()
        out['box_score']['FIRST_NAME'][k] = names[0]
        out['box_score']['SECOND_NAME'][k] = names[1] if len(names) > 1 else "N/A"
    return out


def add_team_names(thing):
    out = copy.deepcopy(thing)
    out['home_line']['CITY'] = thing['home_city']
    out['home_line']['NAME'] = thing['home_name']
    out['vis_line']['CITY'] = thing['vis_city']
    out['vis_line']['NAME'] = thing['vis_name']
    return out


def get_or_save_split_keys(all_ids):
    key_file = "outputs/split_keys.json"
    if os.path.exists(key_file):
        print("{} already exists, loading from it".format(key_file))
        with open(key_file, 'r') as fin:
            split_keys = json.load(fin)
    else:
        shuffle(all_ids)
        total = len(all_ids)
        nval, ntest = total*3//20, total*3//20  # 7:1.5:1.5 split
        ntrain = total - nval - ntest
        split_keys = {
            'train_keys': all_ids[:ntrain],
            'val_keys': all_ids[ntrain:ntrain + nval],
            'test_keys': all_ids[ntrain + nval:]
        }
        with open(key_file, 'w') as fout:
            json.dump(split_keys, fout)

    print("train :{}, dev: {}, test: {}".format(len(split_keys['train_keys']), len(split_keys['val_keys']), len(split_keys['test_keys'])))

    return split_keys

def prep_roto():
    data_out = []
    all_ids = []
    with jsonlines.open("outputs/aligned.jsonl", "r") as reader:
        for thing in tqdm(reader.iter(type=dict, skip_invalid=True)):
            game_id = thing['game_id']
            all_ids.append(game_id)

    split_keys = get_or_save_split_keys(all_ids)

    with jsonlines.open("outputs/aligned.jsonl", "r") as reader:
        for thing in tqdm(reader.iter(type=dict, skip_invalid=True)):
            thing = prep_nums(thing)
            thing = prep_tokes(thing)
            thing = add_player_names(thing)
            thing = add_team_names(thing)
            # rename home and away linescore keys so they don't conflict
            linekeys = ['home_line', 'vis_line']
            out = copy.deepcopy(thing)
            for lk in linekeys:
                for k in thing[lk].keys():
                    v = thing[lk][k]
                    if k == 'TO':
                        new_key = "TEAM-TOV"
                    else:
                        new_key = "TEAM-" + k
                    out[lk][new_key] = v
                    del out[lk][k]
            data_out.append(out)

    train, val, test = [], [], []
    for thing in data_out:
        # get the key
        key = thing['game_id']
        if key in split_keys['test_keys']:
            test.append(thing)
        elif key in split_keys['val_keys']:
            val.append(thing)
        else:
            train.append(thing)

    # finally write everything
    try:
        os.makedirs("outputs/rotowire_json")
    except OSError as ex:
        if "File exists" in ex:
            print(ex)
        else:
            raise ex

    print("saving train ...")
    with codecs.open("train.json", "w+", "utf-8") as f:
        json.dump(train, f)
    print("saving valid ...")
    with codecs.open("valid.json", "w+", "utf-8") as f:
        json.dump(val, f)
    print("saving test ...")
    with codecs.open("test.json", "w+", "utf-8") as f:
        json.dump(test, f)

if __name__ == "__main__":
    print('prep_roto')
    prep_roto()