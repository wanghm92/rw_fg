"""
    This script discards about 12% (#words) contents without numerical facts
"""

import re, io, copy, os, sys, argparse, pdb
from tqdm import tqdm
from collections import Counter, OrderedDict
from pprint import pprint
from domain_knowledge import Domain_Knowledge
knowledge_container = Domain_Knowledge()
DELIM = "￨"

parser = argparse.ArgumentParser(description='filter')
parser.add_argument('--dir', type=str, default='../../rotowire_fg',
                    help='directory of (src|tgt)_(train|valid|test).norm.(tk|mwe).txt files')
parser.add_argument('--dataset', type=str, required=True, help='train, valid test')
args = parser.parse_args()
DATASET = args.dataset
BASE_DIR = os.path.join(args.dir, "new_clean/{}".format(DATASET))

input_files = [
    "src_%s.norm.tk.txt" % DATASET,
    "tgt_%s.norm.tk.txt" % DATASET,
    "tgt_%s.norm.mwe.txt" % DATASET
]

fin_src_tk, fin_tgt_tk, fin_tgt_mwe = [os.path.join(BASE_DIR, f) for f in input_files]

output_files = [
    "tgt_%s.norm.filter.tk.txt" % DATASET,
    "tgt_%s.norm.filter.mwe.txt" % DATASET
]

fout_tgt_tk, fout_tgt_mwe = [os.path.join(BASE_DIR, f) for f in output_files]


# ----------------------------------------------- #
# --- Filtering sentences without any numbers --- #
# ----------------------------------------------- #

nums = re.compile('[0-9]+')
temp_dir = os.path.join(BASE_DIR, "temp")
os.makedirs(temp_dir, exist_ok=True)
tmpf = os.path.join(temp_dir, "noNumbers.txt")
out = []
total = 0
discard = 0
discard_words = 0

with io.open(fin_tgt_mwe, 'r', encoding='utf-8') as fin, io.open(tmpf, 'w+', encoding='utf-8') as fout:
    dataset = fin.read()
    dataset = dataset.strip().split('\n')
    for paragraph in dataset:
        remaining = []
        sents = [x.strip() for x in paragraph.split(' . ')]
        for s in sents:
            total += 1
            if not re.search(nums, s):
                out.append(s)
                continue
            remaining.append(s)
        remaining = ' . '.join(remaining)
        fout.write("{}\n".format(remaining))

words = sum([len(x.split()) for x in out])
print("{} sentences out of {} sentences are discarded".format(len(out), total))
print("Some discarded sentences:")
for x in out[:10]:
    print(x)
discard += len(out)
discard_words += words


# --------------------------------------------------------------------- #
# --- Filtering sentences talking about facts regarding other teams --- #
# --------------------------------------------------------------------- #

contain_other_teams = []
contain_other_cities = []
alias2team = knowledge_container.alias2team

with io.open(fin_src_tk, 'r', encoding='utf-8') as fin_src, \
        io.open(tmpf, 'r', encoding='utf-8') as fin_tgt, \
        io.open("{}.noOtherTeams.txt".format(tmpf[:-4]), 'w+', encoding='utf-8') as fout:

    targets = fin_tgt.read()
    targets = targets.strip().split('\n')

    inputs = fin_src.read()
    inputs = inputs.strip().split('\n')

    team_names = []
    city_names = []
    for sample in inputs:
        for rcd in sample.split():
            a, b, c, d = rcd.strip().split(DELIM)
            if 'TEAM' in c:
                team_names.append(b)
            if c == 'TEAM-CITY':
                city_names.append(a)
    team_vocab = Counter(team_names)
    city_vocab = Counter(city_names)

    print("team_vocab {}:".format(len(team_vocab)))
    pprint(team_vocab)
    print("city_vocab {}:".format(len(city_vocab)))
    pprint(city_vocab)

    assert len(inputs) == len(targets)
    for inp, para in tqdm(zip(inputs, targets)):
        remaining = []

        # ------ get what this summary paragraph is taking about: team + city ------ #
        thisteams = {}
        thiscities = {}
        thisinputs = inp.split()
        thisinputs.reverse()
        for rcd in thisinputs:
            a, b, c, d = rcd.strip().split(DELIM)
            if 'TEAM' in c:
                if not b in thisteams:
                    thisteams[b] = True
            if c == 'TEAM-CITY':
                if not b in thiscities:
                    thiscities[a] = True
            if len(thisteams.items()) == 2 and len(thiscities) == 2:
                break

        # ------ filter out sentences talking about team/city other than this pair ------ #
        sents = [x.strip() for x in para.split(' . ')]
        for s in sents:
            flag = False
            # check every single word
            for tk in s.split():
                # resolve team alias
                if tk in alias2team:
                    tk = alias2team[tk]
                if tk in team_vocab and not tk in thisteams:
                    contain_other_teams.append(s)
                    flag = True
                if tk in city_vocab and not tk in thiscities:
                    contain_other_cities.append(s)
                    flag = True
                if flag:
                    break
            if not flag:
                remaining.append(s)
        remaining = ' . '.join(remaining)
        fout.write("{}\n".format(remaining))

l1 = len(contain_other_teams)
words = sum([len(x.split()) for x in contain_other_teams])
print("{} sentences with {} words out of {} sentences are discarded".format(l1, words, total))
print("Some discarded sentences:")
print(contain_other_teams[-10:])
l2 = len(contain_other_cities)
words = sum([len(x.split()) for x in contain_other_cities])
print("{} sentences with {} words out of {} sentences are discarded".format(l2, words, total))
print("Some discarded sentences:")
print(contain_other_cities[-10:])
print("{} + {} = {} sentences are discarded".format(l1, l2, l1 + l2))

discard += l1+l2
discard_words += words


# --------------------------------------------------------------------- #
# --- Filtering sentences talking about facts regarding other teams --- #
# --------------------------------------------------------------------- #

def get_player_name_one(sample):
    names = []
    records = sample.strip().split()
    for rcd in records:
        _, name, _, _ = rcd.strip().split(DELIM)
        names.append(name)
    all_names = list(set(names))
    try:
        all_names.remove('N/A')
    except:
        pass

    return all_names


def contain_number(s):
    return any([x.isdigit() for x in s.strip().split()])


# ----------------------------------- #
# --- Remaining bulk of filtering --- #
# ----------------------------------- #

# ------ mask these (unwanted) numbers then check if anymore left: no, discard ------ #
years = re.compile(' [0-9]{4} - [0-9]{2} ')
months = re.compile('(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d+')
other_stats = re.compile(' [0-9]+ (?:games*|days*|man|men|ties*|lead|teams*|starters*|contests) ')
averages = re.compile(' averag[eing]* [0-9]+ ')
per_sth = re.compile(' [0-9]+ per ')
ordinal = re.compile(' [0-9]+th ')
homestead = re.compile(' [0-9] - game homestead')

num_patterns = [years, months, other_stats, averages, per_sth, ordinal, homestead]

# ------ sentences talking about these topics: discard ------ #
streak = re.compile('(?:win[ing]*|los[ing]*|hot|a|the|\'s|) streak')
seconds = re.compile('[0-9]+ seconds ')
will_next = re.compile(' [Nn]ext | previous | will | \'ll ')
on_the_road = re.compile('on the road')
straight = re.compile('straight (?:games*|seasons*) ')
last_games = re.compile('[0-9]+ of(?: \S+)* last [0-9]+ games*')
division = re.compile('\S+ Division')
filter_patterns = [seconds, streak, will_next, on_the_road, straight, last_games, division]

nums = re.compile('[0-9]+')
days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
weekdays = re.compile('|'.join(days))

out = []
with io.open(fin_src_tk, 'r', encoding='utf-8') as fin_src, \
        io.open("{}.noOtherTeams.txt".format(tmpf[:-4]), 'r', encoding='utf-8') as fin_tgt, \
        io.open(fout_tgt_tk, 'w+', encoding='utf-8') as fout_tk, \
        io.open(fout_tgt_mwe, 'w+', encoding='utf-8') as fout_mwe:

    targets = fin_tgt.read()
    targets = targets.strip().split('\n')
    inputs = fin_src.read()
    inputs = inputs.strip().split('\n')

    print(len(inputs))
    print(len(targets))

    for inp, para in tqdm(zip(inputs, targets)):

        player_names = get_player_name_one(inp)
        thisgameplayers = dict.fromkeys(player_names, True)

        remaining = []
        thisteams = {}
        thiscities = {}
        thisinputs = inp.split()
        thisinputs.reverse()
        for rcd in thisinputs:
            a, b, c, d = rcd.strip().split(DELIM)
            if 'TEAM' in c:
                if not b in thisteams:
                    thisteams[b] = True
            if c == 'TEAM-CITY':
                if not b in thiscities:
                    thiscities[a] = True
            if len(thisteams.items()) == 2 and len(thiscities) == 2:
                break

        thisgame = list(thisteams.keys()) + list(thiscities.keys())
        sents = [x.strip() for x in para.split(' . ') if len(x.strip()) > 0]
        oneteam = re.compile('(?:{}) \( [0-9]+ - [0-9]+ \)'.format('|'.join(thisgame)))

        # do not filter the 1st sentence
        remaining.append(sents[0])

        # loop through
        day_of_week = re.findall(weekdays, sents[0])
        for idx, s in enumerate(sents[1:]):
            temp = copy.deepcopy(s)
            if len(re.findall(oneteam, temp)) == 1:
                temp = re.sub(oneteam, ' dummystring ', temp)
                # after filtering out team stats, if no other number left, this sentence is talking about some fact of team not available from table
                if not contain_number(temp):
                    out.append(s)
                    continue

            # mask out number patterns not interested in
            for p in num_patterns:
                temp = re.sub(p, ' dummystring ', temp)

            # discard if no numbers in sentence after masking out unwanted ones
            if not contain_number(temp):
                out.append(s)
                continue

            # discard sentences with unwanted topics, see above
            tofilter = [re.search(x, temp) is not None for x in filter_patterns]
            if any(tofilter):
                out.append(s)
                continue

            # if we know which day_of_week this game was played, discard any other sentences mentioning other days of week
            if len(day_of_week) > 0:
                thisday = day_of_week[0]
                otherdays = [x for x in days if x != thisday]
                tmp_pattern = re.compile('|'.join(otherdays))
                if re.search(tmp_pattern, temp):
                    out.append(s)
                    continue

            remaining.append(s)

        remaining = ' . '.join([x.strip() for x in remaining if len(x.strip()) > 0])
        remaining = remaining.replace('..', '.')
        if remaining.endswith('.'):
            remaining = remaining[:-1].strip()
        fout_mwe.write("{} .\n".format(remaining))
        remaining = ' '.join(remaining.split('_'))
        fout_tk.write("{} .\n".format(remaining))

print("{} sentences with {} words out of {} sentences are discarded".format(len(out), words, total))
print("Some discarded sentences:")
print(out[-10:])
discard += len(out)
discard_words += words
print("[TOTAl] {} sentences with {} words out of {} sentences are discarded".format(discard, discard_words, total))


