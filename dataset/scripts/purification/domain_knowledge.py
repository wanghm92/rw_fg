from nba_api.stats.static.players import players
import pandas as pd

class Domain_Knowledge:

    def __init__(self):

        self.all_nba_teams = ['Atlanta Hawks', 'Boston Celtics', 'Brooklyn Nets', 'Charlotte Hornets',
                             'Chicago Bulls', 'Cleveland Cavaliers', 'Detroit Pistons', 'Indiana Pacers',
                             'Miami Heat', 'Milwaukee Bucks', 'New York Knicks', 'Orlando Magic',
                             'Philadelphia 76ers', 'Toronto Raptors', 'Washington Wizards', 'Dallas Mavericks',
                             'Denver Nuggets', 'Golden State Warriors', 'Houston Rockets', 'Los Angeles Clippers',
                             'Los Angeles Lakers', 'Memphis Grizzlies', 'Minnesota Timberwolves', 'New Orleans Pelicans',
                             'Oklahoma City Thunder', 'Phoenix Suns', 'Portland Trail Blazers', 'Sacramento Kings',
                             'San Antonio Spurs', 'Utah Jazz']

        self.two_word_cities = ['New York', 'Golden State', 'Los Angeles', 'New Orleans', 'Oklahoma City', 'San Antonio']

        self.two_word_teams = ['Trail Blazers']

        self.team2alias = {
            '76ers': 'Sixers',
            'Thunder': 'OKC',
            'Cavaliers': 'Cavs',
            'Mavericks': 'Mavs',
            'Timberwolves': 'Wolves'
        }

        self.alias2team = {
            'Cavs': 'Cavaliers',
            'Mavs': 'Mavericks',
            'OKC': 'Thunder',
            'Sixers': '76ers',
            'Wolves': 'Timberwolves'
        }

        self.alias2player = {
            'The_Greek_Freak': 'Giannis_Antetokounmpo',
            'Melo': 'Carmelo_Anthony',
            'KD': 'Kevin_Durant',

        }
        self.prons = dict.fromkeys(
            ["he", "He", "him", "Him", "his", "His", "they", "They", "them", "Them", "their", "Their", "team"], True)

        self.singular_prons = dict.fromkeys(["he", "He", "him", "Him", "his", "His"], True)

        self.plural_prons = dict.fromkeys(["they", "They", "them", "Them", "their", "Their"], True)

        self.all_nba_players = pd.DataFrame(data=players)

        self.player_lookup = dict.fromkeys([x[3] for x in players], True)

        self.arenas = [
            'AT_&_T_Center',
            'Air_Canada_Centre',
            'American_Airlines_Arena',
            'American_Airlines_Center',
            'Amway_Center',
            'BMO_Harris_Bradley_Center',
            'Bankers_Life_Fieldhouse',
            'Barclays_Center',
            'Chesapeake_Energy_Arena',
            'EnergySolutions_Arena',
            'Fed_Ex_Forum_Arena',
            'Golden_One_Center',
            'Madison_Square_Garden',
            'Mexico_City_Arena',
            'Moda_Center',
            'Oracle_Arena',
            'Pepsi_Center',
            'Philips_Arena',
            'Quicken_Loans_Arena',
            'Sleep_Train_Arena',
            'Smoothie_King_Center',
            'Spectrum_Center',
            'Staples_Center',
            'TD_Garden',
            'Talking_Stick_Resort_Arena',
            'Target_Center',
            'The_Palace_of_Auburn_Hills',
            'Time_Warner_Cable_Arena',
            'Toyota_Center',
            'US_Airways_Center',
            'United_Center',
            'Verizon_Center',
            'Vivint_Smart_Home_Arena',
            'Wells_Fargo_Center'
        ]

        # Jazz: EnergySolutions_Arena renamed as Vivint_Smart_Home_Arena in 2015
        # Kings: used Sleep_Train_Arena before Golden_One_Center
        # Suns: Talking_Stick_Resort_Arena was US_Airways_Center before 2015
        # Lakers and Clippers share Staples_Center
        self.team2arenas = {
            '76ers': ['Wells_Fargo_Center'],
            'Bucks': ['BMO_Harris_Bradley_Center'],
            'Bulls': ['United_Center'],
            'Cavaliers': ['Quicken_Loans_Arena'],
            'Celtics': ['TD_Garden'],
            'Clippers': ['Staples_Center'],
            'Grizzlies': ['Fed_Ex_Forum_Arena'],
            'Hawks': ['Philips_Arena'],
            'Heat': ['American_Airlines_Arena'],
            'Hornets': ['Spectrum_Center'],
            'Jazz': ['Vivint_Smart_Home_Arena', 'EnergySolutions_Arena'],
            'Kings': ['Golden_One_Center', 'Sleep_Train_Arena'],
            'Knicks': ['Madison_Square_Garden'],
            'Lakers': ['Staples_Center'],
            'Magic': ['Amway_Center'],
            'Mavericks': ['American_Airlines_Center'],
            'Nets': ['Barclays_Center'],
            'Nuggets': ['Pepsi_Center'],
            'Pacers': ['Bankers_Life_Fieldhouse'],
            'Pelicans': ['Smoothie_King_Center'],
            'Pistons': ['The_Palace_of_Auburn_Hills'],
            'Raptors': ['Air_Canada_Center'],
            'Rockets': ['Toyota_Center'],
            'Spurs': ['AT_&_T_Center'],
            'Suns': ['Talking_Stick_Resort_Arena', 'US_Airways_Center'],
            'Thunder': ['Chesapeake_Energy_Arena'],
            'Timberwolves': ['Target_Center'],
            'Trail_Blazers': ['Moda_Center'],
            'Warriors': ['Oracle_Arena'],
            'Wizards': ['Verizon_Center']
        }

        self.line_keys_ext = [
            'TEAM-PTS',
            'TEAM-PTS_HALF-FIRST', 'TEAM-PTS_HALF-SECOND', 'TEAM-PTS_HALF_DIFF-FIRST', 'TEAM-PTS_HALF_DIFF-SECOND',
            'TEAM-PTS_QTR1', 'TEAM-PTS_QTR2', 'TEAM-PTS_QTR3', 'TEAM-PTS_QTR4',
            'TEAM-PTS_QTR-1to3', 'TEAM-PTS_QTR-2to4',
            'TEAM-PTS_QTR_DIFF-FIRST', 'TEAM-PTS_QTR_DIFF-SECOND', 'TEAM-PTS_QTR_DIFF-THIRD',
            'TEAM-PTS_QTR_DIFF-FOURTH',
            'TEAM-PTS_SUM-BENCH', 'TEAM-PTS_SUM-START', 'TEAM-PTS_TOTAL_DIFF',
            'TEAM-FG3A', 'TEAM-FG3M', 'TEAM-FG3_PCT', 'TEAM-FGA', 'TEAM-FGM', 'TEAM-FG_PCT',
            'TEAM-FTA', 'TEAM-FTM', 'TEAM-FT_PCT',
            'TEAM-REB', 'TEAM-OREB', 'TEAM-DREB',
            'TEAM-AST', 'TEAM-BLK', 'TEAM-STL', 'TEAM-TOV',
            'TEAM-WINS', 'TEAM-LOSSES',
            'TEAM-ALIAS', 'TEAM-ARENA', 'TEAM-CITY', 'TEAM-NAME',
        ]


