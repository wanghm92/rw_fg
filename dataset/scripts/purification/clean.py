"""
This cleaning script does the following:
(1) normalize team name, city, arena, and some jargons
(2) normalize player names in input tables
(3) fix limited tokenization errors spotted along the way
"""

import re, io, copy, os, sys, argparse, json
from tqdm import tqdm
from collections import Counter, OrderedDict
from text2num import text2num

DELIM = "￨"

# ---------------------------------------------------------- #
# --- normalize team name, city, arena, and some jargons --- #
# ---------------------------------------------------------- #

threept = re.compile('3Pt|3pt|3PT|3pT')
double_word_team_names = {
    "(Trail )*Blazers": "Trail_Blazers",
    "Golden State": "Golden_State",
    "Oklahoma [cC]ity": "Oklahoma_City",
    "San Antonio": "San_Antonio",
    "Salt Lake City": "Salt_Lake_City",
    "New Orleans": "New_Orleans",
    "New York": "New_York",
    "LA|L\.A\.|Los Angeles": "Los_Angeles",
    "4Pt": "3PT",
}
double_word_team_names = OrderedDict(double_word_team_names)

arenas = {
    "American Airlines Center": "American_Airlines_Center",
    "American* *Airlines Arena": "American_Airlines_Arena",
    "Amway Center": "Amway_Center",
    "AT \& T Center": "AT_&_T_Center",
    "Air Canada (?:Center|Centre)": "Air_Canada_Centre",
    "Bankers Life Fieldhouse": "Bankers_Life_Fieldhouse",
    "(?:Barclays|Barclay 's) Center": "Barclays_Center",
    "Chesapeake (?:Energy )Arena": "Chesapeake_Energy_Arena",
    "Energy *Solutions Arena": "EnergySolutions_Arena",
    "Fed E(?:x|X) Forum Arena|FedExForum Arena": "Fed_Ex_Forum_Arena",
    "FedEx Forum": 'Fed_Ex_Forum_Arena',
    "Golden 1 Center|Golden One Center": "Golden_One_Center",
    "Madison Square Garden": "Madison_Square_Garden",
    "Mexico City Arena": "Mexico_City_Arena",
    "Moda Center": "Moda_Center",
    "(?:Oracle|ORACLE) Arena": "Oracle_Arena",
    "Pepsi Center": "Pepsi_Center",
    "Smoothie King Center": "Smoothie_King_Center",
    "Spectrum (?:Center|Arena)": "Spectrum_Center",
    "Staples Center": "Staples_Center",
    "Sleep Train Arena": "Sleep_Train_Arena",
    "Talking Stick (?:Resort )*Arena": "Talking_Stick_Resort_Arena",
    "Target Center": "Target_Center",
    "TD Center|TD Garden(?: Arena)": "TD_Garden",
    "Toyota Center|Honda Center|atToyota Center": "Toyota_Center",
    "(?:Time Warner Cable|TWC) Arena": "Time_Warner_Cable_Arena",
    "United Center": "United_Center",
    "(?:Vivint|Vivnt) Smart Home Arena": "Vivint_Smart_Home_Arena",
    "Wells Fargo (?:Center|Arena)": "Wells_Fargo_Center",
    "Verizon Center": "Verizon_Center",
    "(?:Quicken|Quciken) Loans (?:A|a)rena": "Quicken_Loans_Arena",
    "The Palace of Auburn Hills": "The_Palace_of_Auburn_Hills",
    "Phil+ips Arena": "Philips_Arena",
    "BMO Harris Bradley Center|Bradley Center": "BMO_Harris_Bradley_Center",
    "US Airways Center|U\.S\. Airways Center": "US_Airways_Center",
    "Vivint Smart Home Arena": "Vivint_Smart_Home_Arena",
}

mwes = {
    "Nation \'s Capital": "Nation_'s_Capital",
    "double figures*": "double_figures",
    "Most Valuable Player": "Most_Valuable_Player",
    "Most Improved Player": "Most_Improved_Player",
    "Defensive Player of the Year": "Defensive_Player_of_the_Year",
    "Eastern Conference": "Eastern_Conference",
    "Western Conference": "Western_Conference",
    "NBA Finals": "NBA_Finals",
}

mwes_dash = {
    "double( -)* digits*": "double_digit",
    "triple( -)* double": "triple_double",
    "double( -)* double": "double_double",
    "game - winner": "game_winner",
    "game - tying": "game_tying",
    "three( -)* point": "three_point",
    "neck - and - neck": "neck_and_neck",
    "free( -)* throw": "free_throw",
    " 3 - (point|pont|poinit) ": " three_point ",
    " 3 - (pointer|pionter|ponter)": " three_pointer",

}

others = {
    "out - scoring": "out_scoring",
    "early - season": "early_season",
    "much - needed": "much_needed",
    "league - worst": "league_worst",
    "injury - riddled": "injury_riddled",
    "hack - a - DeAndre": "hack_a_DeAndre",
    "out - rebounded": "out_rebounded",
    'P\.J\.Tucker': 'P.J. Tucker',
    'K\.J\.McDaniels': 'K.J. McDaniels',
    'K\.J\.McTroy Daniels': 'K.J. McTroyDaniels',
    '-esque': ' - esque'
}

three_pts = {
    "three - (pointer|pionter|ponter)s": "three_pointers",
    "three (pointer|pionter|ponter)s": "three_pointers",
    "three - (pointer|pionter|ponter)": "three_pointer",
}

two_pts = {
    " two - point shot": "two_point shot",
    " two - point attempt": "two_point attempt",
    " two - point range": "two_point range",
    " two - point basket": "two_point basket",
    " two - point field": "two_point field",
}

# X.X .
abbrev_names = {
    'A\.J\s*\.* ': 'AJ ',
    'C\.J\s*\.* ': 'CJ ',
    'D\.J\s*\.* ': 'DJ ',
    'J\.J\s*\.* ': 'JJ ',
    'O\.J\s*\.* ': 'OJ ',
    'P\.J\s*\.* ': 'PJ ',
    'T\.J\s*\.* ': 'TJ ',
    'K\.J\s*\.* ': 'KJ ',
    'J\.R\.* ': 'JR ',
    ' , Jr\. | Jr\. ': ' Jr ',
    'Washington( ,)* D\.*C\.*': 'Washington_DC',
    'Amare': 'Amar\'e',
    'No\.1': 'best',
    'Jan\.28': 'Jan. 28',
    'under\.500': 'under 500',
    'The Greek Freak': 'The_Greek_Freak'
}

toreplace = [double_word_team_names, arenas, mwes, mwes_dash, others, three_pts, two_pts, abbrev_names]


def fix_sent_split_error(sent):
    pattern = re.compile("(\S*[a-zA-Z]{2}\.[A-Z]{1}[a-zA-Z]{1}\S*)")
    for f in re.findall(pattern, sent):
        sent = re.sub(f, " . ".join(f.split('.')), sent)
    return sent


def collate_team_city_names(sent, player_names):
    to_replace = toreplace + [player_names]
    for d in to_replace:
        for k, v in d.items():
            sent = re.sub(re.compile(k), v, sent)
    sent = fix_sent_split_error(sent)
    sent = re.sub(threept, '3PT', sent)
    return sent


# ------------------------------ #
# --- normalize player names --- #
# ------------------------------ #

name_pattern = re.compile("(\S)\.(\S)\.(_\S+)")

def get_player_name_one(sample):
    names = []
    player_names = {}
    records = sample.strip().split()
    for rcd in records:
        _, name, _, _ = rcd.strip().split(DELIM)
        names.append(name)
    all_names = list(set(names))
    try:
        all_names.remove('N/A')
    except:
        pass

    temp = []

    for x in all_names:
        subnames = x.split('_')
        if len(subnames) == 2:
            temp.append(subnames[1])

    common_lastnames = [k for k, v in Counter(temp).most_common() if v > 1]
    common_lastnames = dict.fromkeys(common_lastnames)

    for x in all_names:
        if re.search(name_pattern, x):
            x = ''.join(re.findall(name_pattern, x)[0])
        subnames = x.split('_')
        if len(subnames) == 2:

            f, l = subnames

            if len(f.split('-')) > 1:
                f = '.'.join(f.split('-'))
            if len(l.split('-')) > 1:
                l = '.'.join(l.split('-'))

            if len(f.split('.')) > 2:
                f = "\.".join(f.split('.'))

            if not l in common_lastnames:
                # replace full or last name by one full name with _
                k = "(?:{} )?{} ".format(f, l)

            else:
                k = " ".join(subnames).strip('.')
        elif len(subnames) > 2:
            k = " ".join(subnames).strip('.')
        else:
            continue
        player_names[k] = "{} ".format(x)

    return player_names


# ------------------------------- #
# --- fix tokenization errors --- #
# ------------------------------- #

post_fixes = {
    ' - -': ' ,',
    'Jan.': 'Jan',
    'Feb.': 'Feb',
    'Mar.': 'Mar',
    'Apr.': 'Apr',
    'May.': 'May',
    'Jun.': 'Jun',
    'Jul.': 'Jul',
    'Aug.': 'Aug',
    'Sep.': 'Sep',
    'Oct.': 'Oct',
    'Nov.': 'Nov',
    'Dec.': 'Dec',
    'Jakarr JaKarr_Sampson': 'JaKarr_Sampson',
    'Steph Stephen_Curry ': 'Stephen_Curry ',
    'Steph Curry': 'Stephen_Curry',
    'Lebron LeBron_James': 'LeBron_James',
    'sideline..': ' sideline .',
    'Trail_Trail_Blazers': 'Trail_Blazers',
    'TrailTrail_Blazers': 'Trail_Blazers',
    'DeAndreDeAndre_Jordan': 'DeAndre_Jordan',
    'Kevin Durant': 'Kevin_Durant',
    'a rebound': '1 rebound',
    'an assist': '1 assist',
    'a steal': '1 steal',
    'a block': '1 block',
    'a pair of assists': '2 assists',
    'a pair of steals': '2 steals',
    'a pair of rebounds': '2 rebounds',
    'a pair of blocks': '2 blocks',
    'KJ_McTroy_Daniels': 'KJ_Daniels',
    'Dennis Schroeder': 'Dennis_Schroder',
    'Antetokonmpo': 'Antetokounmpo',
    'this 1': 'this one',
    'thethree_point': 'the three_point',
    'R.J. RJ_Hunter': 'RJ_Hunter',
    'C. J . CJ_Miles': 'CJ_Miles',
    'T. J. TJ_Warren': 'TJ_Warren',
    ' D.C. ': ' DC ',
    ' p.m. ': ' PM ',
    ' O.T. ': ' OT ',
    'KJ McTroy_Daniels': 'KJ_McDaniels',
    ' 4 - of - 7 7 ': ' 4 - of - 7 ',
    'JJ Reduce': 'JJ_Redick',

}

p1 = re.compile("\d+\.\S+|\S+\.\d+")
p2 = re.compile("([0-9]+)(F\S)")
p3 = re.compile("\d+,\d+")
p4 = re.compile("\S+,\S+")
p5 = re.compile("\d+-\d+")
p6 = re.compile("(\S+)(three_point)")
p7 = re.compile("(\S+)two_point")
full_name_cnt = 0

def fix_tokenization(s):
    global full_name_cnt
    with io.open("mwes.json", 'r', encoding='utf-8') as fmwe:
        tmp = json.load(fmwe)
        mwes = {k:v for k,v in tmp.items() if v>1}
    full_names = {' '.join(k.split('_')):k for k, _ in mwes.items()}

    clean = []

    for k, v in full_names.items():
        if k in s:
            full_name_cnt += 1
            s = s.replace(k, v)

    for w in s.split():
        if w.endswith("s’"):
            w = ' '.join([w[:-1], "'"])
        elif w.endswith("’s"):
            w = ' '.join([w[:-2], "'s"])

        if re.search(p1, w):
            components = w.split('.')
            if len(components) == 2:
                print("Original {}".format(w))
                w = ' . '.join(components)
                print("changed to {}".format(w))
            if w.endswith('..'):
                print("Original {}".format(w))
                w = '{} .'.format(components[0])
                print("changed to {}".format(w))

        if re.search(p2, w):
            print("Original {}".format(w))
            num, suffix = re.findall(p2, w)[0]
            w = ' '.join([num, suffix])
            print("changed to {}".format(w))

        # fix tokenization errors caused by commas
        if re.search(p3, w):
            print("Original {}".format(w))
            w = ''.join(w.split(','))
            print("changed to {}".format(w))

        if re.search(p4, w):
            print("Original {}".format(w))
            w = ' , '.join(w.split(','))
            print("changed to {}".format(w))

        if re.search(p5, w):
            print("Original {}".format(w))
            w = ' - '.join(w.split('-'))
            print("changed to {}".format(w))

        if re.search(p6, w):
            print("Original {}".format(w))
            pieces = re.findall(p6, w)[0]
            try:
                pieces[0] = text2num(pieces[0])
            except:
                pass
            w = ' '.join(pieces)
            print("changed to {}".format(w))

        if re.search(p7, w):
            pre = re.findall(p7, w)[0]
            print("Original {}".format(w))
            w = ' '.join([pre, 'two_point'])
            print("changed to {}".format(w))

        clean.append(w.strip())

    result = ' '.join(clean)
    for k, v in post_fixes.items():
        result = result.replace(k, v)

    return result


# --------------------------------- #
# --- input_table_normalization --- #
# --------------------------------- #

def input_table_normalization(src, fout_src):
    print("input_table_normalization ...")
    annoying_names = re.compile('\S\.\S\.?')
    with io.open(src, 'r', encoding='utf-8') as fin_src, io.open(fout_src, 'w+', encoding='utf-8') as fout:
        inputs = fin_src.read()
        inputs = inputs.strip().split('\n')

        norm_output = []
        for sample in tqdm([x for x in inputs if len(x) > 0]):
            records = sample.strip().split()

            norm_records = []
            idx = 0
            while idx < len(records):
                rcd = records[idx]
                rcd = re.sub('LA￨Clippers', 'Los_Angeles￨Clippers', rcd)
                a, ent_type, rcd_type, d = rcd.strip().split(DELIM)

                if not rcd_type.startswith('TEAM'):
                    first_name = ent_type.split('_')[0]
                    if re.search(annoying_names, first_name):
                        #                     print(ent_type)
                        first_name = first_name.replace('.', '')
                        ent_type = '_'.join([first_name] + ent_type.split('_')[1:])
                        #                     print(ent_type)

                if rcd_type == 'FIRST_NAME':
                    _, _, x, _ = records[idx + 1].strip().split(DELIM)
                    assert x == 'SECOND_NAME'
                    temp = DELIM.join([ent_type, ent_type, 'PLAYER_NAME', d])
                    idx += 2
                elif rcd_type == 'TO':
                    temp = DELIM.join([a, ent_type, 'TOV', d])
                    idx += 1
                else:
                    idx += 1
                    temp = DELIM.join([a, ent_type, rcd_type, d])
                norm_records.append(temp)
            norm_output.append(' '.join(norm_records))

        for s in norm_output:
            fout.write("{}\n".format(s))
        print("Done")


# ---------------- #
# --- cleaning --- #
# ---------------- #
def int_value(input):
    is_number = False
    try:
        value = int(input)
        is_number = True
    except ValueError:
        pass

    if not is_number:
        value = text2num(input)
    return value


def run_clean(tgt, fout_tgt_tk, fout_tgt_mwe):
    print("run_clean ...")
    with io.open(src, 'r', encoding='utf-8') as fin_src, \
            io.open(tgt, 'r', encoding='utf-8') as fin_tgt, \
            io.open(fout_tgt_tk, 'w+', encoding='utf-8') as fout_tk, \
            io.open(fout_tgt_mwe, 'w+',encoding='utf-8') as fout_mwe:

        targets = fin_tgt.read()
        targets = targets.strip().split('\n')

        inputs = fin_src.read()
        inputs = inputs.strip().split('\n')

        vocab = []
        for s in targets:
            vocab.extend(s.split())
        print("original vocab = {}".format(len(Counter(vocab).most_common())))

        print(len(inputs))
        print(len(targets))

        targets_cleaned = []
        for i, t in tqdm(zip(inputs, targets)):
            player_names = get_player_name_one(i)
            t = collate_team_city_names(t, player_names)
            targets_cleaned.append(t)

        all_num_dataset = []
        for sent in tqdm(targets_cleaned):
            all_num_tks = []
            tokens = sent.split()
            for idx, t in enumerate(tokens):
                # if not (t == "three" and annoying_number_word(tokens, idx)):
                try:
                    t = int_value(t)
                except:
                    pass
                if type(t) == int:
                    t = "{}".format(t)
                all_num_tks.append(t)
            all_num_dataset.append(" ".join(all_num_tks))

        for s in all_num_dataset:
            s = fix_tokenization(s)
            fout_mwe.write("{}\n".format(s))
            s = ' '.join(s.split('_'))
            fout_tk.write("{}\n".format(s))

        vocab = []
        for s in all_num_dataset:
            vocab.extend(s.split())
        print("cleaned vocab = {}".format(len(Counter(vocab).most_common())))
        print("*** full_name_cnt = {}".format(full_name_cnt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='clean')
    parser.add_argument('--dir', type=str, default='../../rotowire_fg',
                        help='directory of (src|tgt)_(train|valid|test).txt files')
    args = parser.parse_args()

    for dataset in ['train', 'valid', 'test']:
        BASE_DIR = os.path.join(args.dir, "new_clean/{}".format(dataset))

        print("dataset: {}".format(dataset))
        input_files = [
            "src_{}.txt".format(dataset),
            "tgt_{}.txt".format(dataset),
        ]

        src, tgt = [os.path.join(BASE_DIR, f) for f in input_files]

        output_files = [
            "src_{}.norm.tk.txt".format(dataset),
            "tgt_{}.norm.tk.txt".format(dataset),
            "tgt_{}.norm.mwe.txt".format(dataset)
        ]

        fout_src, fout_tgt_tk, fout_tgt_mwe = [os.path.join(BASE_DIR, f) for f in output_files]

        input_table_normalization(src, fout_src)
        run_clean(tgt, fout_tgt_tk, fout_tgt_mwe)