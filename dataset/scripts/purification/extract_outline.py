import re, io, copy, os, sys, argparse, json, pdb, jsonlines
from tqdm import tqdm
from collections import Counter, OrderedDict
from domain_knowledge import Domain_Knowledge
knowledge_container = Domain_Knowledge()

DELIM = "￨"
UNK = 0
NA = 'N/A'
PAD_WORD = '<blank>'
UNK_WORD = '<unk>'
BOS_WORD = '<s>'
EOS_WORD = '</s>'

# ------------------------------- #
# --- very important patterns --- #
# ------------------------------- #

# a long pattern with 2-6 numbers
pattern1 = re.compile("\( (?:\d+ - \d+ FG)?(?: (?:,|\.) \d+ - \d+ 3PT)?(?: (?:,|\.) \d+ - \d+ FT)? \)")

# patterns with 1 number
pattern2 = re.compile("assist(?:ed)? on \d+")
# the + field, three_point, free, charity, floor; behind/beyond the arc/three; deep/distance/long range;
pattern3 = re.compile("\d+ percent from the \S+")

# patterns with 2 numbers
pattern4 = re.compile("\d+ (?:- )?(?:of|for|-) (?:- )?(?:\S+ )?\d+ (?:shooting )?from (?:the )?\S+")
pattern5 = re.compile("\d+ (?:- )?(?:of|for) (?:- )?(?:\S+ )?\d+ \S+")
pattern6 = re.compile("\( \d+ - \d+ \)")
pattern7 = re.compile("\d+ - \d+")

count_missing = dict.fromkeys(list(range(1, 43)), 0)

word2record = {
    8: ('board', 'REB'),
    9: ('assist', 'AST'),
    10: ('dime', 'AST'),
    11: ('minute', 'MIN'),
    12: ('percent', 'PCT'),
    13: ('steal', 'STL'),
    14: ('block', 'BLK'),
    15: ('turnover', 'TOV'),
    16: ('three_pointer', 'FG3'),
    17: ('three_point', 'FG3'),
    18: ('three', 'FG3'),
    19: ('3PT', 'FG3'),
    20: ('attempt', 'ATMP'),
    21: ('free_throw', 'FT'),
    22: ('shot', 'FG'),
    23: ('offensive', 'OREB'),
    24: ('offensively', 'OREB'),
    25: ('made', 'FG'),
    26: ('point', 'PTS'),
    27: ('rebound', 'REB'),
}
word2record = OrderedDict(word2record)

post_donts = {
    28: ('quarter', None),
    29: ('straight', None),
    30: ('starter', None),
    31: ('lead', None),
    32: ('team', None),
    33: ('content', None),
    34: ('run', None),
    35: ('tie', None),
    36: ('game', None),
    37: ('player', None),
}
post_donts = OrderedDict(post_donts)

pre_donts = {
    38: ('combined? for(?: \S+)? \d+', None),
    39: ('averag\S+(?: \S+)? \d+', None),
    40: ('\d{4} - \d{2,4}', None),
    41: ('(?:first|last) \d+ minutes?', None),
    42: ('\d+ minutes? (?:left|remaining)', None),
}

pre_donts = OrderedDict(pre_donts)

suffix2field = dict.fromkeys(['field', 'floor'])
suffix2three = dict.fromkeys(['three_point', 'beyond', 'behind', 'long', 'deep', 'downtown', '3', 'distance'])
suffix2foul = dict.fromkeys(['free_throw', 'charity', 'line', 'foul', 'stripe'])

# ----------------------------------------- #
# --- identify patterns to be processed --- #
# ----------------------------------------- #

def mark_records(sent):
    x = copy.deepcopy(sent)
    i = 1

    for idx, (k, v) in pre_donts.items():
        p = re.compile(k)
        delim = "#DELIM{}#".format(idx)
        for f in re.findall(p, x):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    for p in [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6, pattern7]:
        delim = "#DELIM{}#".format(i)
        i += 1
        for f in re.findall(p, x):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    for idx, (k, v) in (list(word2record.items()) + list(post_donts.items())):
        p = re.compile("\d+ (?:- )*{}(?:s|ed)*".format(k))
        delim = "#DELIM{}#".format(idx)
        for f in re.findall(p, x):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    return x


# ------------------------------- #
# --- very important patterns --- #
# ------------------------------- #

def _get_record(value, num2rcds, priority):
    candidates = num2rcds.get(value, None)
    if candidates is None:
        if len(priority) > 1:
            return [], False
        else:
            return None, False

    candidates = sorted(candidates, key=lambda x: len(x.split(DELIM)[2]))
    assert len(priority) > 0
    if len(candidates) == 1:
        check = False
        for p in priority:
            if p in candidates[0].split(DELIM)[-2]:
                check = True
                break

        if len(priority) > 1:
            return candidates, check
        else:
            return candidates[0], check
    else:
        results = []
        check = False
        for p in priority:
            for c in candidates:
                if p in c.split(DELIM)[2]:
                    results.append(c)
                    check = True
        if check:
            if len(priority) > 1:
                return results, True
            else:
                return results[0], True
        else:
            if len(priority) > 1:
                return [], False
            else:
                return None, False


def retrieve_record(value, num2rcds, priority):
    candidate, check = _get_record(value, num2rcds, priority)

    # discard found candidates if it's not the desired rcd_type when priority list contains only 1 unambiguous rcd_type
    # NOTE: many numbers, like percentage are rounded, so the correct number may be +-1
        # others are mistakes incidentally captured and corrected
    if len(priority) == 1 and not check:
        for v in [value - 1, value + 1]:
            candidate, check = _get_record(v, num2rcds, priority)
            if candidate is not None and check:
                value = v
                break
    return candidate, value


# ------------------------------- #
# --- very important patterns --- #
# ------------------------------- #

def get_records(phrase, num2rcds, the_other_team_records):
    # print(phrase)
    p = re.compile("#DELIM(\d+)#")
    temp = re.findall(p, phrase)
    pattern_num = int(temp[0])
    try:
        assert all([int(x) == pattern_num for x in temp])
    except:
        print("{} is misformatted".format(phrase))
        sys.exit(0)
    delim = "#DELIM{}#".format(pattern_num)
    tokens = [x for x in phrase.split(delim) if len(x) > 0]
    numbers_are_at = [i for x, i in zip(tokens, range(len(tokens))) if x.isdigit()]
    numbers = [int(x) for x in tokens if x.isdigit()]

    result = []
    if pattern_num == 1:
        true_numbers_are_at = []
        tmp = re.compile("\( (?:\d+ - \d+ (FG))?(?: (?:,|\.) \d+ - \d+ (3PT))?(?: (?:,|\.) \d+ - \d+ (FT))? \)")
        suffix = [x for x in re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0] if len(x) > 0]

        # fix typos
        if len(suffix) == 3:
            words_are_at = [i for x, i in zip(tokens, range(len(tokens))) if not x.isdigit()]
            suffix_temp = copy.deepcopy(suffix)
            if not suffix_temp[0] == 'FG':
                suffix[0] = 'FG'
                tokens[words_are_at[0]] = 'FG'
            if not suffix_temp[1] == '3PT':
                suffix[1] = '3PT'
                tokens[words_are_at[1]] = '3PT'
            if not suffix_temp[2] == 'FT':
                suffix[2] = 'FT'
                tokens[words_are_at[2]] = 'FT'

        i = 0
        for s in suffix:
            if s == 'FG':
                fgm, fga = numbers[i], numbers[i + 1]
                cp1, num1 = retrieve_record(fgm, num2rcds, priority=['FGM'])
                cp2, num2 = retrieve_record(fga, num2rcds, priority=['FGA'])
            elif s == '3PT':
                fg3m, fg3a = numbers[i], numbers[i + 1]
                cp1, num1 = retrieve_record(fg3m, num2rcds, priority=['FG3M'])
                cp2, num2 = retrieve_record(fg3a, num2rcds, priority=['FG3A'])
            elif s == 'FT':
                ftm, fta = numbers[i], numbers[i + 1]
                cp1, num1 = retrieve_record(ftm, num2rcds, priority=['FTM'])
                cp2, num2 = retrieve_record(fta, num2rcds, priority=['FTA'])
            else:
                print("*** WARNING *** other pattern found {}".format(phrase))
                print("phrase = {}".format(phrase))
                print("s = {}".format(s))
                print("suffix = {}".format(suffix))
                sys.exit(0)
            if cp1 is None or cp2 is None:
                pass
            else:
                if cp1.split(DELIM)[-2][:2] == cp2.split(DELIM)[-2][:2]:
                    true_numbers_are_at.extend(numbers_are_at[i:i + 1 + 1])
                    tokens[numbers_are_at[i]] = str(num1)
                    tokens[numbers_are_at[i + 1]] = str(num2)
                    result.extend([cp1, cp2])
                else:
                    pass
            i += 2
        numbers_are_at = true_numbers_are_at

    elif pattern_num == 2:
        cp, num = retrieve_record(numbers[0], num2rcds, priority=['AST'])
        if cp is not None:
            tokens[-1] = str(num)
            result.append(cp)

    elif pattern_num == 3:
        # the + field, three_point, free, charity, floor; behind/beyond the arc/three; deep/distance/long range;
        tmp = re.compile('\d+ percent from (\S+) (\S+)')
        suf_1, suf_2 = re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0]

        if suf_2 == '3':
            suf_2 = 'three_point'
            numbers_are_at.pop(-1)

        if suf_1 == 'the':
            if suf_2 in ['field', 'floor']:
                priority = ['FG_PCT']
            elif suf_2 == 'three_point':
                priority = ['FG3_PCT']
            elif suf_2 in ['free', 'charity']:
                priority = ['FT_PCT']
            else:
                priority = ['PCT']
        else:
            if suf_1 in ['behind', 'beyond', 'deep', 'distance', 'long']:
                priority = ['FG3_PCT']
            else:
                priority = ['PCT']
        cp, num = retrieve_record(numbers[0], num2rcds, priority=priority)
        if cp is not None:
            tokens[0] = str(num)
            result.append(cp)

    elif 4 <= pattern_num <= 7:
        if len(numbers) == 2:
            num1, num2 = numbers
        else:
            if numbers[-1] == 3:
                num1, num2, _ = numbers
                numbers_are_at.pop(-1)
            else:
                raise ValueError("*** WARNING *** phrase misformatted {}".format(phrase))

        if pattern_num == 4:
            tmp = re.compile("\d+ (?:- )?(?:of|for|-) (?:- )?(?:\S+ )?\d+ (?:shooting )?from (?:the )?(\S+)")
            suffix = re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0]
            if suffix in suffix2field or suffix in suffix2three or suffix in suffix2foul:
                if suffix in suffix2field:
                    p1 = ['FGM']
                    p2 = ['FGA']
                elif suffix in suffix2three:
                    p1 = ['FG3M']
                    p2 = ['FG3A']
                elif suffix in suffix2foul:
                    p1 = ['FTM']
                    p2 = ['FTA']
                cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
            else:
                p1 = ['FG3M', 'FGM', 'FTM']
                p2 = ['FG3A', 'FGA', 'FTA']
                temp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                temp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                cp1, cp2 = None, None
                for x in temp1:
                    for y in temp2:
                        if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1]:
                            cp1 = x
                            cp2 = y
                            break

        elif pattern_num == 5:
            tmp = re.compile("\d+ (?:- )?(?:of|for) (?:- )?(?:\S+ )?\d+ (\S+)")
            suffix = re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0]
            if suffix.startswith('sho'):  # shot/shooting
                p1 = ['FGM']
                p2 = ['FGA']
                cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
            else:
                p1 = ['FG3M', 'FGM', 'FTM']
                p2 = ['FG3A', 'FGA', 'FTA']
                temp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                temp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                cp1, cp2 = None, None
                for x in temp1:
                    for y in temp2:
                        if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1]:
                            cp1 = x
                            cp2 = y
                            break

        elif pattern_num == 6:
            cp1, num1 = retrieve_record(num1, num2rcds, priority=['TEAM-WINS'])
            cp2, num2 = retrieve_record(num2, num2rcds, priority=['TEAM-LOSSES'])
            if cp1 is None or cp2 is None:
                cp1, num1 = retrieve_record(num1, num2rcds, priority=['TEAM-LOSSES'])
                cp2, num2 = retrieve_record(num2, num2rcds, priority=['TEAM-WINS'])
                if cp1 is None or cp2 is None:
                    # if len(priority) > 1, cp1 and cp2 are lists
                    temp1, num1 = retrieve_record(num1, num2rcds, priority=['FG3M', 'FGM', 'FTM', 'REB'])
                    temp2, num2 = retrieve_record(num2, num2rcds, priority=['FG3A', 'FGA', 'FTA', 'REB'])

                    cp1, cp2 = None, None
                    for x in temp1:
                        for y in temp2:
                            if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1]:
                                cp1 = x
                                cp2 = y
                                break

        elif pattern_num == 7:
            if the_other_team_records is not None:
                cp1, num1 = retrieve_record(num1, num2rcds, priority=['TEAM-PTS'])
                cp2, num2 = retrieve_record(num2, the_other_team_records, priority=['TEAM-PTS'])
                if cp1 is None or cp2 is None:
                    cp1, num1 = retrieve_record(num1, the_other_team_records, priority=['TEAM-PTS'])
                    cp2, num2 = retrieve_record(num2, num2rcds, priority=['TEAM-PTS'])

                if cp1 is None or cp2 is None:
                    # if not found separately, combine and continue searching
                    for k, v in the_other_team_records.items():
                        if not k in num2rcds:
                            num2rcds[k] = v
                        else:
                            num2rcds[k].extend(v)
                    temp1, num1 = retrieve_record(num1, num2rcds,
                                                  priority=['TEAM-WINS', 'TEAM-PTS', 'REB', 'AST', 'FTM', 'FGM',
                                                            'FG3M'])
                    temp2, num2 = retrieve_record(num2, num2rcds,
                                                  priority=['TEAM-LOSSES', 'TEAM-PTS', 'REB', 'AST', 'FTA', 'FGA',
                                                            'FG3A'])
                    cp1, cp2 = None, None

                    for x in temp1:
                        for y in temp2:
                            if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1] or (
                                    x.split(DELIM)[2] == 'TEAM-WINS' and y.split(DELIM)[2] == 'TEAM-LOSSES'):
                                cp1 = x
                                cp2 = y
                                break
            else:
                temp1, num1 = retrieve_record(num1, num2rcds,
                                              priority=['TEAM-WINS', 'TEAM-PTS', 'REB', 'AST', 'FTM', 'FGM', 'FG3M'])
                temp2, num2 = retrieve_record(num2, num2rcds,
                                              priority=['TEAM-LOSSES', 'TEAM-PTS', 'REB', 'AST', 'FTA', 'FGA', 'FG3A'])
                cp1, cp2 = None, None

                for x in temp1:
                    for y in temp2:
                        if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1] or (
                                x.split(DELIM)[2] == 'TEAM-WINS' and y.split(DELIM)[2] == 'TEAM-LOSSES'):
                            cp1 = x
                            cp2 = y
                            break

        if cp1 is None or cp2 is None:
            pass
        else:
            _, team_1, rcd_type_1, _ = cp1.split(DELIM)
            _, team_2, rcd_type_2, _ = cp2.split(DELIM)

            if rcd_type_1.startswith('TEAM'):
                if not rcd_type_2.startswith('TEAM'):
                    pass
                else:
                    if rcd_type_1 == 'TEAM-WINS':
                        if not rcd_type_2 == 'TEAM-LOSSES':
                            pass
                        else:
                            if team_1 == team_2:
                                tokens[numbers_are_at[0]] = str(num1)
                                tokens[numbers_are_at[1]] = str(num2)
                                result = [cp1, cp2]
                            else:
                                pass

                    elif rcd_type_1 == 'TEAM-PTS':
                        if not rcd_type_2 == 'TEAM-PTS':
                            pass
                        else:
                            if not (team_1 == team_2):
                                tokens[numbers_are_at[0]] = str(num1)
                                tokens[numbers_are_at[1]] = str(num2)
                                result = [cp1, cp2]
                            else:
                                pass

                    else:
                        # enforcing a pair of digits having the same rcd_type
                        if rcd_type_1 == rcd_type_2 and team_1 != team_2:
                            tokens[numbers_are_at[0]] = str(num1)
                            tokens[numbers_are_at[1]] = str(num2)
                            result = [cp1, cp2]
                        else:
                            pass

            else:
                if cp1.split(DELIM)[-2][:2] == cp2.split(DELIM)[-2][:2]:
                    tokens[numbers_are_at[0]] = str(num1)
                    tokens[numbers_are_at[1]] = str(num2)
                    result = [cp1, cp2]
                else:
                    pass

    elif 8 <= pattern_num <= 27:
        k, v = word2record[pattern_num]
        priority = [v]
        cp, num = retrieve_record(numbers[0], num2rcds, priority=priority)
        if cp is not None:
            tokens[0] = str(num)
            result.append(cp)

    elif 28 <= pattern_num <= 42:
        pass

    else:
        print(phrase)
        print(num2rcds)
        raise ValueError("pattern_num {} is invalid".format(pattern_num))

    correct_phrase = ' '.join([x.strip() for x in tokens if len(x.strip()) > 0])

    if not len(result) > 0:
        count_missing[pattern_num] += 1

    return result, correct_phrase, numbers_are_at


# -------------- #
# --- main() --- #
# -------------- #
RCD_PER_PLAYER = 21
RCD_PER_TEAM = 15
NUM_PLAYERS = 26
NUM_TEAMS = 2

alias2team = knowledge_container.alias2team
singular_prons = knowledge_container.singular_prons
plural_prons = knowledge_container.plural_prons


def _tokenize(word):
    return ' '.join(word.split('_'))

def _any_other_player(sent):
    """
        no idea why some games have missing players
    """
    tokens = sent.strip().split()
    # only checking 2-word names for simplicity
    two_grams = [' '.join(tokens[i:i+2]) for i in range(len(tokens))]
    for name in two_grams:
        if name in knowledge_container.player_lookup:
            return True
    return False

def main(args, DATASET):
    player_not_found = 0

    BASE_DIR = os.path.join(args.dir, "new_clean/{}".format(DATASET))

    input_files = [
        "src_%s.norm.tk.txt" % DATASET,
        "tgt_%s.norm.mwe.txt" % DATASET,
        "tgt_%s.norm.filter.mwe.txt" % DATASET
    ]

    clean_src, clean_tgt, clean_tgt_filter = [os.path.join(BASE_DIR, f) for f in input_files]

    output_files = [
        "%s.trim.json" % DATASET,
        "%s_content_plan_tks.txt" % DATASET,
        "%s_content_plan_ids.txt" % DATASET,
        "%s_ptrs.txt" % DATASET,
        "tgt_%s.norm.filter.mwe.trim.txt" % DATASET,
        "tgt_%s.norm.filter.mwe.trim.full.txt" % DATASET,
        "src_%s.norm.trim.txt" % DATASET
    ]

    js_clean, cp_out_tks, cp_out_ids, ptrs_out, clean_tgt_trim, clean_tgt_trim_full, clean_src_trim = \
        [os.path.join(BASE_DIR, f) for f in output_files]

    JSON_DIR = os.path.join(args.dir, "new_jsonl")
    js = os.path.join(JSON_DIR, "{}.jsonl".format(DATASET))

    sent_count = 0
    empty_sent = 0
    output_count = 0
    with io.open(clean_src, 'r', encoding='utf-8') as fin_src, \
            io.open(clean_tgt, 'r', encoding='utf-8') as fin_tgt, \
            io.open(clean_tgt_filter, 'r', encoding='utf-8') as fin_tgt_filter, \
            jsonlines.open(js, 'r') as fin_js, \
            io.open(js_clean, 'w+', encoding='utf-8') as fout_js, \
            io.open(cp_out_tks, 'w+', encoding='utf-8') as fout_cp_tks, \
            io.open(cp_out_ids, 'w+', encoding='utf-8') as fout_cp_ids, \
            io.open(ptrs_out, 'w+', encoding='utf-8') as fout_ptr, \
            io.open(clean_tgt_trim, 'w+', encoding='utf-8') as fout_tgt, \
            io.open(clean_tgt_trim_full, 'w+', encoding='utf-8') as fout_tgt_full, \
            io.open(clean_src_trim, 'w+', encoding='utf-8') as fout_src:

        output_table = []

        original_summaries = fin_tgt.read().strip().split('\n')

        targets = fin_tgt_filter.read()
        targets = targets.strip().split('\n')

        inputs = fin_src.read()
        inputs = inputs.strip().split('\n')

        assert len(original_summaries) == len(targets) == len(inputs)

        city2team = {}
        for idx, (inp, summary, full_summary, table_original) in \
                tqdm(enumerate(zip(inputs, targets, original_summaries, fin_js.iter(type=dict, skip_invalid=True)))):
            current_sent_players = OrderedDict()
            current_sent_teams = OrderedDict()

            # ------ get record to index lookup ------ #
            rcd2idx = {}
            assert len(inp.strip().split()) == RCD_PER_PLAYER*NUM_PLAYERS + RCD_PER_TEAM*NUM_TEAMS
            for i, rcd in enumerate(inp.strip().split()):
                value, field, rcd_type, ha = rcd.split(DELIM)
                if value == 'N/A' or field == 'N/A':
                    continue
                if rcd in rcd2idx:
                    print("*** WARNING *** duplicate record at line # {}".format(i))
                rcd2idx[rcd] = str(i)

            # ------ get player and team record dictionary ------ #
            table = {"Players": {}, "Teams": {}}
            for rcd in inp.strip().split():
                value, field, rcd_type, ha = rcd.split(DELIM)
                if rcd_type.startswith("TEAM") or rcd_type.startswith('GAME'):
                    if not field in table['Teams']:
                        table['Teams'].update({field: [rcd]})
                    else:
                        table['Teams'][field].append(rcd)
                    if rcd_type == 'TEAM-CITY':
                        city2team[value] = field
                else:
                    if not field in table['Players']:
                        table['Players'].update({field: [rcd]})
                    else:
                        table['Players'][field].append(rcd)

            # ------ process each sentence ------ #
            paragraph_plan = []
            paragraph_text = []
            sentences = summary.strip().split(' . ')
            word_pos = 0
            rcd_pos = 0
            pointers = []
            for cnt, sent in enumerate(sentences):
                sent_count += 1
                pre_check_player = [x for x in sent.strip().split() if x in table['Players']]
                pre_check_team = [x for x in sent.strip().split() if
                                  x in table['Teams'] or x in city2team or x in alias2team]

                # ------ extract player/team this sentence is talking about ------ #
                this_sent_records = []
                this_game_teams = list(table['Teams'].keys())

                if len(pre_check_player) > 0:
                    # only reset when new player is mentioned in this sent
                    current_sent_players = OrderedDict()
                    for word in sent.strip().split():
                        if word in table['Players']:
                            if not word in current_sent_players:
                                current_sent_players[word] = True
                else:
                    player_found = False
                    for word in sent.strip().split():
                        if word in singular_prons:
                            player_found = True
                            # neither a new player is found nor a pronoun is referring to a previous player:
                                # no player is mentioned in this sent

                    if not player_found:
                        current_sent_players = OrderedDict()

                    elif _any_other_player(sent):
                        current_sent_players = OrderedDict()
                        player_not_found += 1

                if len(pre_check_team) > 0:
                    # only reset when new team is mentioned in this sent
                    current_sent_teams = OrderedDict()

                    for word in sent.strip().split():
                        # ------ resolve team name/city/alias ------ #
                        if word in table['Teams']:
                            team = word
                        elif word in city2team:
                            team = city2team[word]
                        elif word in alias2team:
                            team = alias2team[word]
                        else:
                            continue
                        if not team in current_sent_teams:
                            current_sent_teams[team] = True
                else:
                    # using team from previous sentence
                    team_found = False
                    for word in sent.strip().split():
                        if word in plural_prons:
                            team_found = True
                            # neither a new team is found nor a pronoun is referring to a previous team:
                                # no team is mentioned in this sent
                    if not team_found:
                        current_sent_teams = OrderedDict()

                for player in current_sent_players.keys():
                    player_records = table['Players'][player]
                    this_sent_records.extend(player_records)
                for team in current_sent_teams.keys():
                    # keep track which team is mentioned, the other one might still be useful
                    if team in this_game_teams:
                        this_game_teams.remove(team)
                    try:
                        team_records = table['Teams'][team]
                    except:
                        pdb.set_trace()

                    this_sent_records.extend(team_records)

                # only one team is mentioned, pass on the other team records in case needed
                the_other_team_records = None
                if len(this_game_teams) == 1:
                    the_other_team_records = OrderedDict()
                    for rcd in table['Teams'][this_game_teams[0]]:
                        value, field, rcd_type, ha = rcd.split(DELIM)
                        if value.isdigit():
                            value = int(value)
                            if not value in the_other_team_records:
                                the_other_team_records[value] = [rcd]
                            else:
                                the_other_team_records[value].append(rcd)

                # ------ seperate player/team/city and numbers ------ #
                num2rcds = OrderedDict()
                str2rcds = OrderedDict()
                for rcd in this_sent_records:
                    value, field, rcd_type, ha = rcd.split(DELIM)
                    if value.isdigit():
                        value = int(value)
                        if not value in num2rcds:
                            num2rcds[value] = [rcd]
                        else:
                            num2rcds[value].append(rcd)
                    else:
                        if not value in str2rcds:
                            str2rcds[value] = [rcd]
                        else:
                            str2rcds[value].append(rcd)

                this_sent_total_rcds = len(current_sent_players) * RCD_PER_PLAYER + len(
                    current_sent_teams) * RCD_PER_TEAM
                cnt = sum([len(v) for k, v in num2rcds.items()]) + sum([len(v) for k, v in str2rcds.items()])
                assert cnt == this_sent_total_rcds
                del this_sent_records
                """
                   this_game_teams: [team_names]
                   num2rcds: {num: [records]}
                   str2rcds: {player/team: [records]}
                """

                # ------ labeling stats patterns ------ #
                sent = mark_records(sent)

                phrases = []
                sentence_plan = []
                sentence_plan_numonly = []
                starting_word_pos = word_pos

                for mwe in sent.strip().split():
                    # include the player/team/city name (alias not available before feature extension)
                    if mwe in str2rcds:
                        sentence_plan.append(str2rcds[mwe][0])
                        phrases.append(mwe)
                        pointers.append(','.join(map(str, [word_pos, rcd_pos])))
                        word_pos += 1
                        rcd_pos += 1

                    elif mwe.startswith("#DELIM"):
                        records, phrase, numbers_are_at = get_records(mwe, num2rcds, the_other_team_records)
                        if len(records) > 0:
                            sentence_plan.extend(records)
                            sentence_plan_numonly.extend(records)
                            if not len(numbers_are_at) == len(records):
                                print(numbers_are_at)
                                print(records)
                                pdb.set_trace()
                            for n in numbers_are_at:
                                pointers.append(','.join(map(str, [word_pos + n, rcd_pos])))
                                rcd_pos += 1

                        phrases.append(phrase)
                        word_pos += len(phrase.split())

                    elif "#DELIM" in mwe:
                        p = re.compile('#DELIM\d+#')
                        delim = list(set(re.findall(p, mwe)))
                        if len(delim) == 1:
                            # skip the 0th word
                            delim = delim[0]
                            pieces = mwe.split(delim)
                            phrases.append(pieces[0])
                            word_pos += 1

                            mwe = delim.join(pieces[1:])
                            records, phrase, numbers_are_at = get_records(mwe, num2rcds, the_other_team_records)
                            if len(records) > 0:
                                sentence_plan.extend(records)
                                sentence_plan_numonly.extend(records)
                                if not len(numbers_are_at) == len(records):
                                    print(numbers_are_at)
                                    print(records)
                                    pdb.set_trace()
                                for n in numbers_are_at:
                                    pointers.append(','.join(map(str, [word_pos + n, rcd_pos])))
                                    rcd_pos += 1

                            phrases.append(phrase)
                            word_pos += len(phrase.split())

                        else:
                            # ignore this error case
                            for d in delim:
                                mwe = mwe.replace(d, ' ').strip()
                            phrases.append(mwe)
                            word_pos += len(mwe.split())
                    else:
                        phrases.append(mwe)
                        word_pos += 1

                # filter out sentences nothing is found for the player/team
                if len(sentence_plan_numonly) > 0:
                    paragraph_plan.extend(sentence_plan)
                    correct_sent = ' '.join(phrases)
                    paragraph_text.append(correct_sent)
                    # increment by 1 for '.' at end of sentence
                    word_pos += 1
                else:
                    word_pos = starting_word_pos
                    empty_sent += 1
                    for _ in range(len(sentence_plan)):
                        pointers.pop(-1)
                        rcd_pos -= 1

            paragraph_plan_ids = [rcd2idx[rcd] for rcd in paragraph_plan]

            if not len(paragraph_plan) == len(paragraph_plan_ids) == len(pointers):
                print(paragraph_text)
                print(len(paragraph_plan))
                print(len(paragraph_plan_ids))
                print(paragraph_plan)

                print(len(pointers))
                print(pointers)
                sys.exit(0)

            if len(paragraph_plan_ids) > 0:
                to_write = True
                paragraph_plan_ids = ' '.join(paragraph_plan_ids)
                paragraph_plan = ' '.join(paragraph_plan)
                paragraph_text = ' . '.join(paragraph_text)
                pointers = ' '.join(map(str, pointers))
                fout_src.write("{}\n".format(inp.strip()))

            else:
                print("content_plan empty at {}".format(idx))
                print(summary)
                to_write = False

            if to_write:
                output_count += 1

                output_table.append(table_original)

                fout_cp_ids.write("{}\n".format(paragraph_plan_ids))
                fout_cp_tks.write("{}\n".format(paragraph_plan))
                fout_tgt.write("{}\n".format(paragraph_text))
                fout_tgt_full.write("{}\n".format(full_summary.strip()))
                fout_ptr.write("{}\n".format(pointers))

        json.dump(output_table, fout_js)

    print("{} sentences out of {} are discarded due to empty content plan".format(empty_sent, sent_count))
    print("{} samples are retained".format(output_count))
    print("{} sentences out of {} contains players not available from the table".format(player_not_found, sent_count))
    print("count_missing = {}".format(count_missing))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='extract')
    parser.add_argument('--dir', type=str, default='../../rotowire_fg/',
                        help='directory of (src|tgt)_(train|valid|test).norm.(tk|mwe).txt files')
    args = parser.parse_args()

    for DATASET in ['train', 'valid', 'test']:
        print("Extracting content plan from {}".format(DATASET))
        main(args, DATASET)