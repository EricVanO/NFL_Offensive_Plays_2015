import re
import urllib
import MySQLdb
import getpass

"""
Gets play-by-play data for each game in 2015 from pro-football-reference.com (PFR), organizes it into offensive plays for each team, and puts the data for each team into a  
MySQL table in a database called "NFL_Offensive_Plays_2015".
"""

def get_games():
    """
    Gets the basic information about each game in the 2015 NFL regular season. Returns a list of tuples. Each tuple corresponds to one game. 
    The first element of each tuple is the week, followed by the home team name, then the away team, then the url to the PFR boxscore. This is
    to be used by get_game_data.
    """
    game_site = urllib.urlopen('http://www.pro-football-reference.com/years/2015/games.htm')
    game_site_text = game_site.read()
    game_site.close()
    
    """
    The line below gets a list of tuples, with each tuple including the week number, winning team, an indication of whether the winning team was the
    home team, the losing team, and a relative url for the boxscore.
    """
    messy_info = re.findall(r'<th.*?data-stat="week_num".*?>(\d+)</th>.*?data-stat="winner".*?><strong><a href=".*?">(.*?)</a>.*?data-stat="game_location" >(.?)</td>.*?data-stat="loser" ><a href=".*?">(.*?)</a>.*?data-stat="boxscore_word" ><a href="(.*?)">boxscore', game_site_text)
    base_url = 'http://www.pro-football-reference.com'
    clean_info = []
    # The below for loop cleans the data in messy_info, giving the week, home team, away team, and the full url of the boxscore for each game.
    for tuple in messy_info:
        # If there is a third element of the tuple, this indicates that the home team was the losing team and needs to be the second element of the tuple in clean_info.
        if tuple[2]:
            clean_info.append((tuple[0], tuple[3], tuple[1], base_url + tuple[4]))
        else:
            clean_info.append((tuple[0], tuple[1], tuple[3], base_url + tuple[4]))
    return clean_info
            

def get_game_data(url):
    """
    Given a url of a Pro Football Reference boxscore, returns a list of tuples, where each tuple comes from a row in the corresponding play-by-play table, themselves
    corresponding to a play in the game. The first element of each tuple is the row class  (if there is one), which marks where there is a change of possession 
    (class="divider"), a penalty (class=" penalty"), a score (class=" score"), or a combination (class="divider penalty" or class="divider score"). The second element 
    of each tuple is the quarter; the third is the time remaining in the quarter; the fourth and fifth are the down and distance, respectively, if applicable. The sixth 
    element indicates which side of the field the play started on with a three-letter abbreviation of the team name, and the seventh gives the yard line it started on (for
    example, if the Lions started a play on their own 20 yard line, the sixth element would be 'DET', and the seventh would be '20'). The eighth element is a description of 
    the play. The ninth and tenth elements are the scores of the away and home teams, respectively.

    In summary: returns a list of tuples, where each tuple has the form:
    (row class, quarter, time remaining in quarter in the form of 'mm:ss', down, distance, side of field, yard line, play description, away score, home score).
    Each element in the tuple is a string.
    """
    # Open the page, get the text, and close the page.
    site = urllib.urlopen(url)
    sitetext = site.read()
    site.close()
    # I'll search starting from the play-by-play section of the page. This will ensure that I only get data from the play-by-play table.
    pbptext = sitetext.partition('Full Play-By-Play')[2]
    # Use findall to get the required information. Each group in the regex is described in the block comment above. 
    return re.findall(r'<tr (.*?)><th.*?data-stat="quarter" >(\d)</th><td.*?data-stat="qtr_time_remain" >(\d\d?:\d\d)</td><td.*?data-stat="down" >(\d?)</td><td.*?data-stat="yds_to_go" >(\d*)</td><td.*?data-stat="location" csk="0" >(\w\w\w) (\d+)</td><td.*data-stat="detail" >(.*?)</td><td.*?data-stat="pbp_score_aw" >(\d+)</td><td.*?data-stat="pbp_score_hm" >(\d+)</td>', pbptext)


def get_off_play_data(home_team, away_team, game_data):
    """
    Given game_data in the form of the output of get_game_data, get_off_play_data returns a tuple of two lists of lists, the first of which corresponds to the 
    home team, and the second of which corresponds to the away team. In each outer list are inner lists of data from offensive plays, including time remaining 
    in the game in seconds; the down; yards to go; field position indicated by a yardline between 0-100, with 0-50 indicating the play started on the offensive team's
    side of the field, and 50-100 indicating the play starting on the defending team's side; score differential, which is negative if the offensive team is losing
    and positive if the offensive team is winning; and a 0 if the play was a run, and a 1 if the play was a pass.

    In summary: returns two lists of lists, where each inner list has the form:
    [time remaining in seconds, down, to go, field position, score differential, 0 for run or 1 for pass]
    """ 
    # A dict of the team abbreviations used in PFR's play-by-play tables, associating them with the full names of the teams.
    team_dict = {'NWE':'New England Patriots', 'PIT':'Pittsburgh Steelers', 'CLT':'Indianapolis Colts', 'BUF':'Buffalo Bills', 'GNB':'Green Bay Packers', 'CHI':'Chicago Bears', 'NOR':'New Orleans Saints', 'CRD':'Arizona Cardinals', 'NYG':'New York Giants', 'DAL':'Dallas Cowboys', 'RAV':'Baltimore Ravens', 'DEN':'Denver Broncos', 'KAN':'Kansas City Chiefs', 'HTX':'Houston Texans', 'CAR':'Carolina Panthers', 'JAX':'Jacksonville Jaguars', 'CLE':'Cleveland Browns', 'NYJ':'New York Jets', 'CIN':'Cincinnati Bengals', 'RAI':'Oakland Raiders', 'SEA':'Seattle Seahawks', 'RAM':'St. Louis Rams', 'DET':'Detroit Lions', 'SDG':'San Diego Chargers', 'OTI':'Tennessee Titans', 'TAM':'Tampa Bay Buccaneers', 'MIA':'Miami Dolphins', 'WAS':'Washington Redskins', 'PHI':'Philadelphia Eagles', 'ATL':'Atlanta Falcons', 'MIN':'Minnesota Vikings', 'SFO':'San Francisco 49ers'}
    
    """
    The next few lines initialize the variable homeaway, which is 0 when the home team possesses the ball and 1 when the away team possesses the ball. It decides this by 
    looking at the location of the game's first play--the opening kickoff--and setting homeaway equal to zero if it's kicked from the home team's side of the field, and 
    one if it's kicked from the away team's side of the field. Since the opening kickoff is always kicked from the kicking team's side of the field, this will always 
    correctly identify the kicking team. Note that the inital value for homeaway is not the one corresponding to the team who first possesses the ball on offense, but 
    the code will automatically switch homeaway when it looks at the second play (the first play from scrimmage), which will have the "divider" tag. If the abbreviaton 
    for the kickoff team does not match either input team, it prints an error, but still initializes homeaway to 0 so that the rest of the function can run. This error 
    message will be useful if PFR ever changes its three-letter team name abbreviations.
    """
    if team_dict[game_data[0][5]] == home_team:
        homeaway = 0
    elif team_dict[game_data[0][5]] == away_team:
        homeaway = 1
    else:
        homeaway = 0
        print 'Error: starting team abbreviation in ' + away_team + ' @ ' + home_team + ' does not match home or away team. Setting homeaway to 0 by default.'
    
    """
    Initializing i, which I will iterate over in the following while loop, as well as home_data and away_data, the two lists of lists with offensive play data for the
    home and away teams, respectively. It also sets init_homeaway, saving the team who kicked off the game. This is useful becuase the team who kicks off the second
    half is always the team who did not kick off the first half. I do not want to base the second half kickoff team on field position because it is possible for a penalty
    called between halves to affect the location of the second half kickoff.
    """
    i = 0
    home_data = []
    away_data = []
    init_homeaway = homeaway
    

    """
    Here lies the primary while loop, which iterates over every element of game_data and fills in home_data and away_data with information about the offensive plays 
    run by each team.
    """
    while i < len(game_data):
        # st is a flag indicating whether the current play is a special teams or otherwise non-offensive play. It is by default 0 for a play, but can get switched later on.
        st = 0
        """
        At the start of the second half, I need to reinitialize homeaway, since there isn't a 'class=divider' flag in this case. I don't need to do anything else with the
        first play of the second half, since it is not an offensive play.
        """
        if game_data[i][1] == '3' and game_data[i-1][1] == '2':
            homeaway = (init_homeaway + 1) % 2
        else:
            """
            If the 'class=divider' flag is there, I need to tell the program that the teams have switched. In the first game of the 2015 season, PFR neglected to put this flag
            after the second-half kickoff, so I made it so that 'kicks off' in the previous play also indicates a change of possession. Onside kicks do not inlcude 'kicks off'
            in the play description, so there should be no confusion here.
            """
            if ('divider' in game_data[i][0]) or ('kicks off' in game_data[i-1][7]):
                homeaway = (homeaway + 1) % 2
            
            """
            This line gets the time remaining in the game in seconds. From left to right, it's given by (quarters after current quarter)*900 + 
            60*(minutes left in current quarter) + (seconds left in current quarter).
            """
            time_rem = (4-int(game_data[i][1]))*900 + 60*int(game_data[i][2].split(':')[0]) + int(game_data[i][2].split(':')[1])
            
            """
            If the play started on the possessor's side, set the position equal to the yard line. Otherwise, set position equal to 100-(yard line). This way, position is
            between 0 and 100, with 0 the offense's goal line and 100 the defense's goal line.
            """
            if (homeaway == 0 and team_dict[game_data[i][5]] == home_team) or (homeaway == 1 and team_dict[game_data[i][5]] == away_team):
                position = int(game_data[i][6])
            else:
                position = 100 - int(game_data[i][6])
            
            """
            Get the score differential, equal to (offense's score) - (defense's score). This is taken from the i-1 element of game_data because I want the score 
            differential before the play, not after. If it's the first play (i.e. the opening kickoff), I just set score_diff to zero.
            """
            if i > 0:
                score_diff = (2*homeaway-1)*(int(game_data[i-1][8])-int(game_data[i-1][9]))
            else:
                score_diff = 0

            """
            If the play was a passing play, that will be indicated by the word 'pass' or 'sacked' in the play description. In this case, I set a variable called runpass
            equal to 1. Otherwise, I set it to 0 (indicating a running play). This will misclassify passing plays where the quarterback scrambles for a gain.
            Hopefully, this doesn't happen too often; if it does, it will likely be for teams with quarterbacks that scramble often, like the Seahawks.
            """
            if 'pass' in game_data[i][7] or 'sacked' in game_data[i][7]:
                runpass = 1
            else: 
                runpass = 0

            """
            If the play is a kick, punt, field goal attempt, timeout, or two-point conversion attempt, or if a pre-snap penalty prevented a play from happening,
            or if PFR doesn't have a description of the play, the st flag gets set to 1. This tells the next step not to include it in home_data or away_data.
            """
            if ('kick' in game_data[i][7].lower()) or ('punt' in game_data[i][7].lower()) or ('field goal' in game_data[i][7].lower()) or ('timeout' in game_data[i][7].lower()) or ('conversion' in game_data[i][7].lower()) or ('no play' in game_data[i][7].lower()) or (' -- ' == game_data[i][7].lower()):
                st = 1
            # Add the relevant information (time remaining, down, distance, field position, score differential, runpass) to the correct list.
            if not st:
                if homeaway == 0:
                    home_data.append([time_rem, int(game_data[i][3]), int(game_data[i][4]), position, score_diff, runpass])
                elif homeaway == 1:
                    away_data.append([time_rem, int(game_data[i][3]), int(game_data[i][4]), position, score_diff, runpass])

        i += 1
    
    # Return both lists of offensive plays.
    return (home_data, away_data)

def main():
    # team_number is a dict associating numbers 1-32 with teams. If I ever apply this to other seasons, I need to write code to automatically generate this.
    team_number = {'Baltimore Ravens':1, 'Cincinnati Bengals':2, 'Cleveland Browns':3, 'Pittsburgh Steelers':4, 'Houston Texans':5, 'Indianapolis Colts':6, 'Jacksonville Jaguars':7, 'Tennessee Titans':8, 'Buffalo Bills':9, 'Miami Dolphins':10, 'New England Patriots':11, 'New York Jets':12, 'Denver Broncos':13, 'Kansas City Chiefs':14, 'Oakland Raiders':15, 'San Diego Chargers':16, 'Chicago Bears':17, 'Detroit Lions':18, 'Green Bay Packers':19, 'Minnesota Vikings':20, 'Atlanta Falcons':21, 'Carolina Panthers':22, 'New Orleans Saints':23, 'Tampa Bay Buccaneers':24, 'Dallas Cowboys':25, 'New York Giants':26, 'Philadelphia Eagles':27, 'Washington Redskins':28, 'Arizona Cardinals':29, 'St. Louis Rams':30, 'San Francisco 49ers':31, 'Seattle Seahawks':32}
    
    """
    The nested list called "plays" will eventually include all of the offensive plays used by the teams in each game. I initialize it as a list of 32 empty lists, one 
    empty list for each team.
    """
    plays = [[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]
    # Get the basic information--week number, home team, away team, and url of play-by-play data--for each game.
    games = get_games()
    for game in games:
        # For each game, get the plays by each team.
        (home_plays, away_plays) = get_off_play_data(game[1], game[2], get_game_data(game[3]))
        # Here, I add the week number to the play info for each game.
        for play in home_plays:
            play.insert(0, int(game[0]))
        for play in away_plays:
            play.insert(0, int(game[0]))
        # I add the info from each team into the relevant sub-list in plays.
        plays[team_number[game[1]]-1].append(home_plays)
        plays[team_number[game[2]]-1].append(away_plays)
    
    # Next, I need to export play data to a MySQL database. Here, I connect to the MySQL server.
    rootpass = getpass.getpass('Enter the MySQL root password: ')
    con = MySQLdb.connect('localhost', 'root', rootpass)
    cur = con.cursor()
    # Create and use the database NFL_Offensive_Plays_2015.
    cur.execute('DROP DATABASE IF EXISTS NFL_Offensive_Plays_2015')
    cur.execute('CREATE DATABASE NFL_Offensive_Plays_2015')
    cur.execute('USE NFL_Offensive_Plays_2015')
    # Put the data in "plays" into the database.
    for key in team_number:
        cur.execute("CREATE TABLE `" + key + "`(Id INT PRIMARY KEY AUTO_INCREMENT, `Week` INT, `Time Remaining` INT, `Down` INT, `To Go` INT, `Field Position` INT, `Score Differential` INT, `IsPass` INT)")
        for game in plays[team_number[key]-1]:
            for play in game:
                cur.execute("INSERT INTO `" + key + "`(`Week`, `Time Remaining`, `Down`, `To Go`, `Field Position`, `Score Differential`, `IsPass`) VALUES(" + str(play[0]) + ", " + str(play[1]) + ", " + str(play[2]) + ", " + str(play[3]) + ", " + str(play[4]) + ", " + str(play[5]) + ", " + str(play[6]) + ")")
    if con:
        con.close()

if __name__ == '__main__':
    main()