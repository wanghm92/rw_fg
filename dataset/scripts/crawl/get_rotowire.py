from __future__ import absolute_import, division, print_function, unicode_literals
import re, datetime, json, sys, os, codecs, requests, pdb, jsonlines, shutil
import numpy as np
import pandas as pd
from tqdm import tqdm
from pprint import pprint
from bs4 import BeautifulSoup
from nba_api.stats.endpoints import BoxScoreTraditionalV2, BoxScoreSummaryV2

# from nba_api.stats.static import teams
# nba_teams = teams.get_teams()

# gamefinder = leaguegamefinder.LeagueGameFinder()
# all_nba_games = gamefinder.get_data_frames()[0]
print("loading all nba games ...")
all_games = pd.read_pickle("all_games.pkl")

pattern = re.compile('([\S\s]+) at ([\S\s]+)')
months2num = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}
line_keys = ["TEAM_WINS_LOSSES", "PTS_QTR1", "PTS_QTR2", "PTS_QTR3", "PTS_QTR4", "PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "AST", "REB", "TO"]
box_keys = ["TEAM_CITY", "START_POSITION", "PLAYER_NAME", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF", "PTS"]


def _get_box(player_stats):
    headers = player_stats['headers']
    data = player_stats['data']
    box_key_lookup = dict.fromkeys(box_keys, True)

    box_score = {k: {"0": v} for k, v in zip(headers, data[0]) if k in box_key_lookup}
    for idx, player in enumerate(data[1:]):
        for k, v in zip(headers, player):
            if k in box_key_lookup:
                box_score[k].update({str(idx+1): v})

    assert set(box_score.keys()) == set(box_keys)

    return box_score


def _trim_line(thing):
    out = {}
    for k, v in thing.items():
        if k in line_keys:
            out[k] = v
    try:
        assert set(out.keys()) == set(line_keys)
    except AssertionError:
        print(sorted(out.keys()))
        print(sorted(line_keys))
        sys.exit(1)

    return out


def get_stats(player_stats, id2line, home_id, away_id):
    home_line = _trim_line(id2line[home_id])
    vis_line = _trim_line(id2line[away_id])
    box_score = _get_box(player_stats)
    return home_line, vis_line, box_score


def get_home_away(team_stats, home, away):
    name_idx = team_stats['headers'].index('TEAM_NAME')
    city_idx = team_stats['headers'].index('TEAM_CITY')
    id_idx = team_stats['headers'].index('TEAM_ID')

    team0, team1 = team_stats['data'][0][name_idx], team_stats['data'][1][name_idx]
    city0, city1 = team_stats['data'][0][city_idx], team_stats['data'][1][city_idx]
    id0, id1 = team_stats['data'][0][id_idx], team_stats['data'][1][id_idx]

    if team0 in home:
        home_name = team0
        home_city = city0
        home_id = id0
        assert team1 in away
        away_name = team1
        away_city = city1
        away_id = id1
    else:
        away_name = team0
        away_city = city0
        away_id = id0
        assert team1 in home
        home_name = team1
        home_city = city1
        home_id = id1

    return home_name, away_name, home_city, away_city, home_id, away_id


def _get_id2line(team_stats):
    """
        team_stats: {
            'headers':[],
            'data': [[],[]]  # two teams, don't know which is home/away
        }
    """
    headers = team_stats['headers']
    id_loc = headers.index('TEAM_ID')

    data0 = team_stats['data'][0]
    data1 = team_stats['data'][1]

    try:
        assert len(headers) == len(data0) == len(data1)
    except AssertionError:
        print(
            "WARNING: line scores of the two teams are incomplete: \nheaders (#={}) = {}\ndata0 (#={}): \n{}\ndata1 (#={}): \n{}".format(
                headers, len(headers), data0, len(data0), data1, len(data1)))
        return None

    id2line = {
        data0[id_loc]: {k: v for k, v in zip(headers, data0)},
        data1[id_loc]: {k: v for k, v in zip(headers, data1)},
    }

    return id2line


def merge_line_scores(team_stats_1, team_stats_2):

    id2line_1 = _get_id2line(team_stats_1)
    id2line_2 = _get_id2line(team_stats_2)

    if id2line_1 is None or id2line_2 is None:
        return None
    else:
        # add info from id2line_2 to id2line_1
        for team_id, line in id2line_2.items():
            for k, v in line.items():
                # if exists, cross check to be consistent
                if k in id2line_1[team_id]:
                    try:
                        assert id2line_1[team_id][k] == v
                    except AssertionError:
                        print("WARNING: the two line scores mismatch: \nteam_stats_1: \n{}\nteam_stats_2: \n{}".format(
                            team_stats_1, team_stats_2))
                # add stats from 2 to 1
                else:
                    id2line_1[team_id][k] = v
        return id2line_1


def get_games_from_htmls():
    in_dir = "outputs/rotowire_raw"
    mv_dir = "outputs/rotowire_done"

    dup = 0
    discard = 0
    total = 0
    game_lkt = {}

    writer = jsonlines.open("outputs/aligned.jsonl", "a")
    for fname in tqdm(sorted(os.listdir(in_dir))):
        in_file = os.path.join(in_dir, fname)
        mv_file = os.path.join(mv_dir, fname)

        with codecs.open(in_file, "r", "utf-8") as fin:
            html = fin.read()

            soup = BeautifulSoup(html, 'html.parser')
            # -------------------- get unique games from this -------------------- #
            for header, summary in zip(soup.find_all("div", {"class": "heading has-desc size-9 bold hide-until-md"}),
                                       soup.find_all("div", {"class": "pad-0-25 mb-50"})):

                # get summary as a paragraph
                summary = summary.get_text().strip()
                summary = ' '.join([x.strip() for x in summary.split('\r\n\r\n')])

                # get tokens from header
                header = header.get_text().strip()
                tokens = [t.strip() for t in header.split() if len(t.strip()) > 0]

                # last 6 tokens are the date and time
                month, day, year, at, time, ampm = tokens[-6:]
                assert at == 'at'
                day = day.strip(',')
                datestr = "%s-%02d-%02d" % (year, months2num[month], int(day))

                # the remaining ones are the $away at $home teams
                title = ' '.join(tokens[:-6])
                away, home = [x.strip() for x in re.findall(pattern, title)[0]]

                assert len(home) > 0 and len(away) > 0

                # a team can only play one game in one day --> game_id can be uniquely identified
                this_game = all_games[(all_games.GAME_DATE == datestr) & (all_games.TEAM_NAME.isin([home, away]))]
                game_id = this_game['GAME_ID'].values
                if len(game_id) == 1:
                    game_id = game_id[0]
                elif len(game_id) == 2:
                    try:
                        assert game_id[0] == game_id[1]
                    except AssertionError:
                        print("game_id misformatted: {}, skipping this game".format(game_id))
                        continue

                    game_id = game_id[0]
                else:
                    print("game_id misformatted: {}, skipping this game".format(game_id))
                    discard += 1
                    continue

                # skip duplicated games
                if game_id in game_lkt:
                    dup += 1
                    continue
                else:
                    game_lkt[game_id] = True

                # get boxscore stats
                game_stats = BoxScoreTraditionalV2(game_id)
                player_stats = game_stats.player_stats.data

                # line score needs to be aggregated from two places
                team_stats_1 = game_stats.team_stats.data
                game_stats = BoxScoreSummaryV2(game_id)
                team_stats_2 = game_stats.line_score.data
                id2line = merge_line_scores(team_stats_1, team_stats_2)
                if id2line is None:
                    print("skipping this game")
                    discard += 1
                    continue

                # team_stats_1 is enough to distinguish home/away teams
                home_name, away_name, home_city, away_city, home_id, away_id = get_home_away(team_stats_1, home, away)

                home_line, vis_line, box_score = get_stats(player_stats, id2line, home_id, away_id)

                year, month, day = datestr.split('-')
                datestr = datetime.date(int(year), int(month), int(day))
                this_game_stats = {
                    "game_id": game_id,
                    "day": datestr.strftime("%0m_%0d_%y"),
                    "summary": summary,
                    "home_name": home_name,
                    "vis_name": away_name,
                    "home_city": home_city,
                    "vis_city": away_city,
                    "home_line": home_line,
                    "vis_line": vis_line,
                    "box_score": box_score
                }

                total += 1
                writer.write(this_game_stats)

        shutil.move(in_file, mv_file)

    writer.close()
    print("discard = {}".format(discard))
    print("total = {}".format(total))
    print("duplicated = {}".format(dup))
    print("unique games = {}".format(len(game_lkt)))

if __name__ == "__main__":
    print('get_games_from_htmls')
    get_games_from_htmls()
