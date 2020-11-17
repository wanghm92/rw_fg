from __future__ import division
import re, io, copy, os, sys, argparse, json, pdb, jsonlines, shutil, jsonlines
from tqdm import tqdm
from pprint import pprint
from collections import Counter, OrderedDict
sys.path.insert(0, '../purification/')
from domain_knowledge import Domain_Knowledge
knowledge_container = Domain_Knowledge()
from pyxdameraulevenshtein import normalized_damerau_levenshtein_distance

DELIM = "￨"
UNK = 0
NA = 'N/A'
PAD_WORD = '<blank>'
UNK_WORD = '<unk>'
BOS_WORD = '<s>'
EOS_WORD = '</s>'
ncp_prefix = "<unk>￨<blank>￨<blank>￨<blank> <blank>￨<blank>￨<blank>￨<blank> <s>￨<blank>￨<blank>￨<blank> </s>￨<blank>￨<blank>￨<blank>"

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
pattern7 = re.compile("\d+ - \d+ \S+")

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
    20: ('attempt', 'ATMP'),  # not used
    21: ('free_throw', 'FT'),
    22: ('shot', 'FG'),
    23: ('offensive', 'OREB'),
    24: ('offensively', 'OREB'),
    25: ('made', 'FG'),
    26: ('point', ['PTS', 'DIFF']),
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

    for p in [pattern1, pattern2, pattern3, pattern4, pattern5, pattern6]:
        delim = "#DELIM{}#".format(i)
        i += 1
        for f in re.findall(p, x):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    for f in re.findall(pattern7, x):
        delim = "#DELIM{}#".format(i)
        i += 1
        suffix = f.split()[-1]
        # avoid sticking with pattern 6 items
        if not suffix.startswith('#'):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    for idx, (k, v) in (list(word2record.items()) + list(post_donts.items())):
        p = re.compile("\d+ (?:- )*{}(?:s|ed)*".format(k))
        delim = "#DELIM{}#".format(idx)
        i += 1
        for f in re.findall(p, x):
            rep = "{}{}{}".format(delim, delim.join(f.split()), delim)
            x = x.replace(f, rep)

    return x


# ------------------------------- #
# --- very important patterns --- #
# ------------------------------- #

def _retrieve_record(value, num2rcds, priority):
    """  get the record with the matching value, and desired record type  """
    candidates = num2rcds.get(value, None)
    # nothing found, return
    if candidates is None:
        if len(priority) > 1:
            return [], False
        else:
            return None, False

    candidates = sorted(candidates, key=lambda x: len(x.split(DELIM)[2]))
    assert len(priority) > 0
    # found one, check if it's of the desired type
    if len(candidates) == 1:
        check = False
        for p in priority:
            if p in candidates[0].split(DELIM)[2]:
                check = True
                break

        if len(priority) > 1:
            return candidates, check
        else:
            return candidates[0], check
    # found multiple, choose the one with the desired type
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
    """  legacy wrapper from outline extraction script  """
    candidate, check = _retrieve_record(value, num2rcds, priority)
    if len(priority) == 1 and not check:
        candidate = None
    return candidate, value


# ------------------------------- #
# --- very important patterns --- #
# ------------------------------- #

def get_records(phrase, num2rcds, the_other_team_records, entity, rcd_type, ha, p_or_t):
    p = re.compile("#DELIM(\d+)#")
    temp = re.findall(p, phrase)
    pattern_num = int(temp[0])
    # only one pattern is allowed in one mwe/phrase
    if not all([int(x) == pattern_num for x in temp]):
        pdb.set_trace()
        raise RuntimeError("{} is misformatted".format(phrase))

    delim = "#DELIM{}#".format(pattern_num)
    tokens = [x for x in phrase.split(delim) if len(x) > 0]
    numbers = [int(x) for x in tokens if x.isdigit()]

    result = []
    if pattern_num == 1:
        tmp = re.compile("\( (?:\d+ - \d+ (FG))?(?: (?:,|\.) \d+ - \d+ (3PT))?(?: (?:,|\.) \d+ - \d+ (FT))? \)")
        suffix = [x for x in re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0] if len(x) > 0]

        suffix2rcdtype = {
            'FG': ['FGM', 'FGA'],
            '3PT': ['FG3M', 'FG3A'],
            'FT': ['FTM', 'FTA']
        }

        # fix spelling variations
        if len(suffix) == 3:
            suffix_temp = copy.deepcopy(suffix)
            if not suffix_temp[0] == 'FG':
                suffix[0] = 'FG'
            if not suffix_temp[1] == '3PT':
                suffix[1] = '3PT'
            if not suffix_temp[2] == 'FT':
                suffix[2] = 'FT'

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

            # During original outline extraction, only retain if both are found, here we don't constrain it too much
            if cp1 is None or cp2 is None:
                # making a guess if either is not found on the entity which this record belongs to
                # rcd_types are already inferred
                if cp1 is None:
                    rcd_type = 'TEAM-'+suffix2rcdtype[s][0] if p_or_t == 'TEAM' else suffix2rcdtype[s][0]
                    cp1 = DELIM.join([str(numbers[i]), entity, rcd_type, ha])
                if cp2 is None:
                    rcd_type = 'TEAM-' + suffix2rcdtype[s][1] if p_or_t == 'TEAM' else suffix2rcdtype[s][1]
                    cp2 = DELIM.join([str(numbers[i+1]), entity, rcd_type, ha])
                result.extend([cp1, cp2])

            else:
                if cp1.split(DELIM)[-2][:2] == cp2.split(DELIM)[-2][:2]:
                    result.extend([cp1, cp2])
                else:
                    pass
            i += 2

    elif pattern_num == 2:
        cp, num = retrieve_record(numbers[0], num2rcds, priority=['AST'])
        if cp is None:
            rcd_type = 'TEAM-AST' if p_or_t == 'TEAM' else 'AST'
            cp = DELIM.join([str(num), entity, rcd_type, ha])
        result.append(cp)

    elif pattern_num == 3:
        # the + field, three_point, free, charity, floor; behind/beyond the arc/three; deep/distance/long range;
        tmp = re.compile('\d+ percent from (\S+) (\S+)')
        suf_1, suf_2 = re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0]

        if suf_2 == '3':
            suf_2 = 'three_point'

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
        if cp is None:
            rcd_type = 'TEAM-'+priority[0] if p_or_t == 'TEAM' else priority[0]
            cp = DELIM.join([str(num), entity, rcd_type, ha])

        result.append(cp)

    elif 4 <= pattern_num <= 7:
        if len(numbers) == 2:
            num1, num2 = numbers
        else:
            if numbers[-1] == 3:
                num1, num2, _ = numbers
            else:
                pdb.set_trace()
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
                p1 = ['FGM', 'FG3M', 'FTM']
                p2 = ['FGA', 'FG3A', 'FTA']
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
                p1 = ['FGM', 'FG3M', 'FTM']
                p2 = ['FGA', 'FG3A', 'FTA']
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
            p1 = ['TEAM-WINS']
            p2 = ['TEAM-LOSSES']
            cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
            cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
            if cp1 is None or cp2 is None:
                p1 = ['TEAM-LOSSES']
                p2 = ['TEAM-WINS']
                cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                if cp1 is None or cp2 is None:
                    # if len(priority) > 1, cp1 and cp2 are lists
                    p1 = ['FGM', 'FG3M', 'FTM', 'REB', 'PTS_HALF-', 'PTS_QTR-']
                    temp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                    p2 = ['FGA', 'FG3A', 'FTA', 'REB', 'PTS_HALF-', 'PTS_QTR-']
                    temp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                    cp1, cp2 = None, None
                    for x in temp1:
                        for y in temp2:
                            if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1]:
                                cp1 = x
                                cp2 = y
                                break

        elif pattern_num == 7:
            tmp = re.compile("\d+ - \d+ (\S+)")
            suffix = re.findall(tmp, ' '.join(phrase.split(delim)).strip())[0]

            suffix2rcdtype = {
                'FG': ['FGM', 'FGA'],
                '3PT': ['FG3M', 'FG3A'],
                'FT': ['FTM', 'FTA']
            }

            if suffix in suffix2rcdtype:
                p1 = [suffix2rcdtype[suffix][0]]
                p2 = [suffix2rcdtype[suffix][1]]
                cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
            else:
                if the_other_team_records is not None:
                    p1 = ['TEAM-PTS']
                    p2 = ['TEAM-PTS']
                    cp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                    cp2, num2 = retrieve_record(num2, the_other_team_records, priority=p2)
                    if cp1 is None or cp2 is None:
                        p1 = ['TEAM-PTS']
                        p2 = ['TEAM-PTS']
                        cp1, num1 = retrieve_record(num1, the_other_team_records, priority=p1)
                        cp2, num2 = retrieve_record(num2, num2rcds, priority=p2)

                    if cp1 is None or cp2 is None:
                        # if not found separately, combine and continue searching
                        for k, v in the_other_team_records.items():
                            if not k in num2rcds:
                                num2rcds[k] = v
                            else:
                                num2rcds[k].extend(v)
                        p1 = ['TEAM-WINS', 'TEAM-PTS', 'REB', 'AST', 'FTM', 'FGM', 'FG3M', 'PTS_HALF-', 'PTS_QTR-']
                        p2 = ['TEAM-LOSSES', 'TEAM-PTS', 'REB', 'AST', 'FTA', 'FGA', 'FG3A', 'PTS_HALF-', 'PTS_QTR-']
                        temp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                        temp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                        cp1, cp2 = None, None
                        for x in temp1:
                            for y in temp2:
                                if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1] or (
                                        x.split(DELIM)[2] == 'TEAM-WINS' and y.split(DELIM)[2] == 'TEAM-LOSSES'):
                                    cp1 = x
                                    cp2 = y
                                    break
                else:
                    p1 = ['TEAM-WINS', 'TEAM-PTS', 'REB', 'AST', 'FTM', 'FGM', 'FG3M', 'PTS_HALF-', 'PTS_QTR-']
                    p2 = ['TEAM-LOSSES', 'TEAM-PTS', 'REB', 'AST', 'FTA', 'FGA', 'FG3A', 'PTS_HALF-', 'PTS_QTR-']
                    temp1, num1 = retrieve_record(num1, num2rcds, priority=p1)
                    temp2, num2 = retrieve_record(num2, num2rcds, priority=p2)
                    cp1, cp2 = None, None
                    for x in temp1:
                        for y in temp2:
                            if x.split(DELIM)[2][:-1] == y.split(DELIM)[2][:-1] or (
                                    x.split(DELIM)[2] == 'TEAM-WINS' and y.split(DELIM)[2] == 'TEAM-LOSSES'):
                                cp1 = x
                                cp2 = y
                                break

        # same thing as above, increasing recall
        if cp1 is None or cp2 is None:
            rebuild = [cp1 is None, cp2 is None]
            # construct cp for this pair
            for ii, pp, nn, tt in zip(rebuild, [cp1, cp2], [num1, num2], [p1[0], p2[0]]):
                if ii:
                    rcd_type = 'TEAM-'+tt if p_or_t == 'TEAM' else tt
                    cp = DELIM.join([str(nn), entity, rcd_type, ha])
                    result.append(cp)
                else:
                    result.append(pp)

        else:
            result = [cp1, cp2]

    elif 8 <= pattern_num <= 27:
        k, v = word2record[pattern_num]
        if isinstance(v, list):
            priority = v
        else:
            priority = [v]

        cp, num = retrieve_record(numbers[0], num2rcds, priority=priority)
        if cp:
            if isinstance(cp, list):
                cp = cp[0]
        else:
            rcd_type = 'TEAM-'+priority[0] if p_or_t == 'TEAM' else priority[0]
            cp = DELIM.join([str(num), entity, rcd_type, ha])

        result.append(cp)

    elif pattern_num > 42:
        raise ValueError("pattern_num {} is invalid: mwe = {}\nnum2rcds = {}".format(pattern_num, phrase, num2rcds))

    return result


def dedup_list(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def compute_rg_cs_co(gold_outlines, hypo_outlines, inputs):
    """
        As defined in paper  https://arxiv.org/pdf/1707.08052.pdf

        RG : number and precision of identified records supported by the input table
        CS : precision and reall of identified records against outlines extracted from human-written summaries
        CO : normalized Damerau-Levenshtein Distance between identified records against outlines extracted from human-written summaries

    """
    assert len(gold_outlines) == len(hypo_outlines) == len(inputs)

    total_pred = 0
    total_gold = 0
    correct = 0
    true_positive = 0
    ndld = 0.0
    if not isinstance(gold_outlines[0], list):
        gold_outlines = [[i for i in x.strip().split() if i.split(DELIM)[0].isdigit()] for x in gold_outlines]

    for ref, hypo, inp in tqdm(zip(gold_outlines, hypo_outlines, inputs)):
        input_lookup = dict.fromkeys(inp.strip().split(), True)

        ref = dedup_list(ref)
        total_gold += len(ref)
        ref_str = ''.join([chr(1 + idx) for idx in range(len(ref))])
        ref_lookup = {i: j for i, j in zip(ref, ref_str)}

        hypo = dedup_list(hypo)
        total_pred += len(hypo)
        correct += len(set([x for x in hypo if x in input_lookup]))

        hypo_str = ''
        next_char = len(ref_str) + 1
        for h in hypo:
            if h in ref_lookup:
                true_positive += 1
                hypo_str += ref_lookup[h]
            else:
                hypo_str += chr(next_char)
                next_char += 1
        ndld += 1 - normalized_damerau_levenshtein_distance(ref_str, hypo_str)

    rg = correct/total_pred*100
    precision = true_positive/total_pred*100
    recall = true_positive/total_gold*100
    f1 = 2*precision*recall/(precision+recall)
    ndld /= len(inputs)

    metrics = OrderedDict({
        "Correct  #": correct,
        "true_positive  #": true_positive,
        "total_pred  #": total_pred,
        "total_gold  #": total_gold,
        "Relation Generation (RG) #": total_pred/len(inputs),
        "Relation Generation (RG) %Precision": rg,
        "Content Selection (CS) %Precision": precision,
        "Content Selection (CS) %Recall": recall,
        "Content Selection (CS) %F1": f1,
        "Content Ordering (CO)": ndld*100,
    })
    pprint(metrics)

# -------------- #
# --- main() --- #
# -------------- #
RCD_PER_PLAYER = 21
NUM_PLAYERS = 26
RCD_PER_TEAM = 40
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

def _choose_most_likely(this_sent_records):
    """
        arbitrarily choosing one record
    """
    rcd_types = set([rcd.split(DELIM)[-2] for rcd in this_sent_records])
    team_rcd_types = [x for x in rcd_types if x.startswith('TEAM')]
    p_or_t = None
    if len(team_rcd_types) == 0:
        p_or_t = 'PLAYER'
    elif len(team_rcd_types) == len(rcd_types):
        p_or_t = 'TEAM'

    _, entity, rcd_type, ha = this_sent_records[0].split(DELIM)
    if p_or_t is None:
        p_or_t = 'TEAM' if rcd_type.startswith('TEAM') else 'PLAYER'

    return entity, rcd_type, ha, p_or_t


def main(args):

    planner_output = None
    if args.plan is not None:
        with io.open(args.plan, 'r', encoding='utf-8') as fin:
            planner_output = fin.read().strip().split('\n')

    input_files = [
        "src_%s.norm.trim.ncp.txt" % args.dataset,
        "%s_content_plan_tks.txt" % args.dataset,
        "%s.trim.json" % args.dataset,
    ]

    BASE_DIR = os.path.join(args.path, "{}".format(args.dataset))
    gold_src, gold_plan, gold_tables = [os.path.join(BASE_DIR, f) for f in input_files]

    cp_out_hypo = "{}.cp.hypo".format(args.hypo)
    cp_out_gold = "{}.cp.gold".format(args.hypo)
    js_hypo = "{}.jsonl".format(args.hypo)

    with io.open(gold_src, 'r', encoding='utf-8') as fin_src, \
            io.open(gold_plan, 'r', encoding='utf-8') as fin_cp, \
            io.open(args.hypo, 'r', encoding='utf-8') as fin_test, \
            io.open(cp_out_hypo, 'w+', encoding='utf-8') as fout_cp_hypo, \
            io.open(cp_out_gold, 'w+', encoding='utf-8') as fout_cp_gold:

        inputs = fin_src.read().strip().split('\n')
        gold_outlines = fin_cp.read().strip().split('\n')
        hypotheses = fin_test.read().strip().split('\n')
        peaking = inputs[0]
        add_on = 0
        if peaking.startswith(ncp_prefix):
            add_on = 4

        if not len(inputs) == len(gold_outlines) == len(hypotheses):
            print("# Input tables = {}; # Gold Content Plans = {}; # Test Summaries = {}"
                  .format(len(inputs), len(gold_outlines), len(hypotheses)))
            raise RuntimeError("Inputs must have the same number of samples (1/line, aligned)")
        else:
            if planner_output is not None:
                assert len(inputs) == len(planner_output)

        hypo_outlines = []
        for idx, (inp, hypo) in tqdm(enumerate(zip(inputs, hypotheses))):
            city2team = {}
            assert len(inp.strip().split()) == RCD_PER_PLAYER*NUM_PLAYERS + RCD_PER_TEAM*NUM_TEAMS + add_on

            current_sent_players = OrderedDict()
            current_sent_teams = OrderedDict()

            # ------ get player and team record dictionary ------ #
            table = {"Players": {}, "Teams": {}}
            diff2rcds = {}
            for rcd in inp.strip().split():
                value, field, rcd_type, ha = rcd.split(DELIM)
                if rcd_type.startswith("TEAM"):
                    if not field in table['Teams']:
                        table['Teams'].update({field: [rcd]})
                    else:
                        table['Teams'][field].append(rcd)
                    if rcd_type == 'TEAM-CITY':
                        city2team[value] = field
                    # this diff is incorporated the last, no apparent pattern found, so rely on single digit matching
                    if 'DIFF' in rcd_type:
                        if not value in diff2rcds:
                            diff2rcds[value] = [rcd]
                        else:
                            diff2rcds[value].append(rcd)
                else:
                    if not field in table['Players']:
                        table['Players'].update({field: [rcd]})
                    else:
                        table['Players'][field].append(rcd)

            # ------ process each sentence ------ #
            # content plan for the whole paragraph, containing number records only
            paragraph_plan_numonly = []
            sentences = hypo.strip().split(' . ')
            for cnt, sent in enumerate(sentences):
                pre_check_player = [x for x in sent.strip().split() if x in table['Players']]
                pre_check_team = [x for x in sent.strip().split() if
                                  x in table['Teams'] or x in city2team or x in alias2team]

                # ------ extract player/team this sentence is talking about ------ #
                this_game_teams = list(table['Teams'].keys())

                player_found = False
                if len(pre_check_player) > 0:
                    player_found = True
                    # only reset when new player is mentioned in this sent
                    current_sent_players = OrderedDict()

                    for word in sent.strip().split():
                        if word in table['Players']:
                            if word not in current_sent_players:
                                current_sent_players[word] = True
                else:
                    # no player name found in this sentence, resolving pronouns
                    for word in sent.strip().split():
                        if word in singular_prons:
                            player_found = True

                    if not player_found:
                        # neither a new player is found nor a pronoun is referring to a previous player
                        # reset the lookup as we only allow coreference resolution between adjacent sentences
                        current_sent_players = OrderedDict()

                team_found = False
                if len(pre_check_team) > 0:
                    team_found = True
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
                            # continue until team word/city/alias is found and add to current_sent_teams
                            continue
                        if team not in current_sent_teams:
                            current_sent_teams[team] = True
                else:
                    # using team from previous sentence
                    for word in sent.strip().split():
                        if word in plural_prons:
                            team_found = True
                    if not team_found:
                        # neither a new team is found nor a pronoun is referring to a previous team
                        current_sent_teams = OrderedDict()

                # ------ now we know what this sentence is about, get the set of their input records ------ #
                this_sent_records = []
                for player in current_sent_players.keys():
                    player_records = table['Players'][player]
                    this_sent_records.extend(player_records)
                for team in current_sent_teams.keys():
                    # keep track which team is mentioned, the other one might still be useful
                    if team in this_game_teams:
                        this_game_teams.remove(team)
                    team_records = table['Teams'][team]
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

                # ------ separate player name/team/city/alias/arena from numbers ------ #
                num2rcds = OrderedDict()
                for rcd in this_sent_records:
                    value, field, rcd_type, ha = rcd.split(DELIM)
                    if value.isdigit():
                        value = int(value)
                        if not value in num2rcds:
                            num2rcds[value] = [rcd]
                        else:
                            num2rcds[value].append(rcd)

                # ------ labeling stats patterns ------ #
                sent = mark_records(sent)

                # make a guess for later use, in case needed
                if len(this_sent_records) > 0:
                    entity, rcd_type, ha, p_or_t = _choose_most_likely(this_sent_records)

                # ------ start looking for (player/team, number, rcd_type) triples ------ #
                sentence_plan_numonly = []
                for mwe in sent.strip().split():
                    if mwe.startswith("#DELIM"):
                        records = get_records(mwe, num2rcds, the_other_team_records, entity, rcd_type, ha, p_or_t)
                        sentence_plan_numonly.extend(records)

                    elif "#DELIM" in mwe:
                        # erroneous mwe
                        p = re.compile('#DELIM\d+#')
                        delim = list(set(re.findall(p, mwe)))
                        # skip the 0th word
                        if len(delim) == 1:
                            delim = delim[0]
                            pieces = mwe.split(delim)
                            mwe = delim.join(pieces[1:])
                            records = get_records(mwe, num2rcds, the_other_team_records, entity, rcd_type, ha, p_or_t)
                            sentence_plan_numonly.extend(records)
                        else:
                            continue
                    else:
                        guess = diff2rcds.get(mwe, [])
                        best_guess = None
                        if len(guess) >= 1:
                            # search for "first, second, third, fourth" in the sentence
                            lkt = {i: True for i in sent.strip().split()}
                            ord2rcds = {v.split(DELIM)[-2].split('-')[-1].lower(): v for v in guess}
                            for k, v in ord2rcds.items():
                                if k in lkt:
                                    best_guess = v
                        # if a record match both the value and the ordinal number, it may be talking about a quarter diff
                        if best_guess is not None:
                            sentence_plan_numonly.append(best_guess)

                # only add to the paragraph content play if this sentence is actually talking about some statistics
                # consistent with the training set, so there is no source for a model to learn to output such sentences
                if len(sentence_plan_numonly) > 0:
                    paragraph_plan_numonly.extend(sentence_plan_numonly)

            hypo_outlines.append(paragraph_plan_numonly)
            fout_cp_hypo.write("{}\n".format(' '.join(paragraph_plan_numonly)))
            otl_numonly = [x for x in gold_outlines[idx].strip().split() if x.split(DELIM)[0].isdigit()]
            fout_cp_gold.write("{}\n".format(' '.join(otl_numonly)))

            otl_numonly_tks = []
            for x in otl_numonly:
                otl_numonly_tks.extend(x.split(DELIM)[0:3])
                otl_numonly_tks.append(";")
            otl_numonly_tks.append('.')
            paragraph_plan_numonly_tks = []
            for x in paragraph_plan_numonly:
                paragraph_plan_numonly_tks.extend(x.split(DELIM)[0:3])
                paragraph_plan_numonly_tks.append(";")
            paragraph_plan_numonly_tks.append('.')
            stage1 = []
            if planner_output is not None:
                for x in planner_output[idx].strip().split():
                    if x.split(DELIM)[0].isdigit():
                        stage1.extend(x.split(DELIM)[0:3])
                        stage1.append(";")
                stage1.append('.')

        # ------ non-BLEU metrics ------ #
        print("\n *** Metrics ***\n")
        if planner_output is not None:
            planner_output = [[i for i in x.strip().split() if i.split(DELIM)[0].isdigit()] for x in planner_output]
            print("\n *** Planned vs Gold ***\n")
            compute_rg_cs_co(gold_outlines, planner_output, inputs)
            print("\n *** Extracted vs Planned ***\n")
            compute_rg_cs_co(planner_output, hypo_outlines, inputs)
        print("\n *** Extracted vs Gold ***\n")
        compute_rg_cs_co(gold_outlines, hypo_outlines, inputs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='clean')
    parser.add_argument('--path', type=str, default='../dataset/rotowire_fg/new_extend',
                        help='directory of gold files')
    parser.add_argument('--dataset', type=str, default='valid', choices=['valid', 'test'])
    parser.add_argument('--hypo', type=str, required=True,
                        help='directory of system output')
    parser.add_argument('--plan', type=str, default=None,
                        help='content plan by ncpcc stage 1')
    args = parser.parse_args()

    print("Evaluating {} set".format(args.dataset))
    main(args)