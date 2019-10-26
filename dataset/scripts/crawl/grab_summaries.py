from __future__ import absolute_import, division, print_function, unicode_literals
import os, sys
import datetime
import codecs
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

def scrape_rotowire():
    try:
        os.makedirs("outputs/rotowire_raw")
    except OSError as ex:
        if "File exists" in ex:
            print(ex)
        else:
            raise ex

    start_day = datetime.date(2017, 3, 30)
    day = datetime.date(2019, 6, 12)

    while day >= start_day:
        url = "http://www.rotowire.com/basketball/game-recaps.php?date=%s" % day.strftime("%Y-%m-%d")
        response = urllib2.urlopen(url)
        html = response.read().decode('utf-8', 'ignore')
        with codecs.open("outputs/rotowire_raw/games_%s.html" % day.strftime("%Y-%m-%d"), "w+", "utf-8") as f:
            f.write(html)
        day = day - datetime.timedelta(days=1)
