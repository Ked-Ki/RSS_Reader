#!/usr/bin/env python3.3

import xml.etree.ElementTree as ET
import urllib.error as err
import urllib.request as URL
import webbrowser as WEB
import os
import sys

# this is where the data is saved!
xmlfeedlist = "RSS_Reader_Data/subscriptions.xml"
filefeedhist = "RSS_Reader_Data/readhistory.xml"
#---------------------------- Initializing the Program ------------------------
if os.path.isfile(xmlfeedlist):
    feedlist = ET.parse(xmlfeedlist).getroot()
else:
    feedlist = ET.Element("feedlist")

feeddict = {feed.get("title") : feed.get("xmlUrl") for feed in feedlist.findall(".//feed")}

# build initial read library.
def buildreadhist():
    hist = ET.Element("readhistory")
    for feed, url in feeddict.items():
        xmlpage = URL.urlopen(url) 
        page = ET.parse(xmlpage).getroot()
        feedhist = ET.SubElement(hist, "feed")
        feedhist.attrib["title"] = feed
        print("reading", feed)
        '''if page.tag == "{http://www.w3.org/2005/Atom}feed":
            # Atom Format (didn't really work)     
            for item in page.findall("..//entry"):
                itemhist = ET.SubElement(feedhist, "item")
                itemhist.attrib["title"] = item.findtext("./title")'''
        if page.tag == "rss":
            # RSS Format
            for item in page.findall(".//item"):
                itemhist = ET.SubElement(feedhist, "item")
                itemhist.attrib["title"] = item.findtext("./title")
        else:
            print("Unrecognized format for feed '{0}'.".format(feed), file=sys.stderr)
    ET.ElementTree(hist).write(filefeedhist)
    print("Read History Built. Please restart program.")
    sys.exit()

if os.path.isfile(filefeedhist):
    feedhist = ET.parse(filefeedhist).getroot()
else:
    buildreadhist()

# used when calling the read function
toreaddict = dict.fromkeys(feeddict.keys(), [])
# used to output html
htmlhead = """<html>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<body>
<h1><a href="{1}">{0}</a></h1>
"""
htmlend = """</body>
</html>
"""
#------------- Functionalities of reader (subscribe, read, check) -------------
def subscribe(feedurl):
    if feedlist.find("./feed[@xmlUrl='{0}']".format(feedurl)):
        return
    else:
        xmlpage = URL.urlopen(feedurl) 
        page = ET.parse(xmlpage).getroot()
        feed = ET.SubElement(feedlist, "feed")
        title = page.findtext("./channel/title")
        feed.attrib["title"] = title
        feed.attrib["htmlUrl"] = page.findtext("./channel/link")
        feed.attrib["xmlUrl"] = feedurl
        feed.attrib["type"] = "rss"
        
        curfeedhist = ET.SubElement(feedhist, "feed")
        curfeedhist.attrib["title"] = title

def check(feedname, toreaddict):
    url = feeddict[feedname]
    try:
        xmlpage = URL.urlopen(url)
    except err.URLError:
        print("No service. Please check network connection.")
        return
    page = ET.parse(xmlpage).getroot() 
    curfeed = feedhist.find("./feed[@title='{0}']".format(feedname))
    unreadcount = 0
    readitems = []
    unreaditems = []

    for readitem in curfeed.findall(".//item"):
        readitems.append(readitem.get("title"))
    for item in page.findall(".//item"):
        if item.findtext("./title") in readitems:
            pass
        else:
            unreadcount += 1
            unreaditems.append(item)
    toreaddict[feedname] = unreaditems
    if unreadcount > 0:
        print(feedname, ": Unread:", unreadcount)
        for item in toreaddict[feedname]:
            print ("    ", item.findtext("./title"))
   

def read(feedname): 
    curfeed = toreaddict[feedname]
    if curfeed:
        curitem = curfeed.pop()

        # code to handle multiple types of rss feeds
        content = curitem.findtext("./{http://purl.org/rss/1.0/modules/content/}encoded")
        if content == None:
            content = curitem.findtext("./description")

        title = curitem.findtext("./title")
        link = curitem.findtext("./link")

        # writes the content to a html file, then opens it in browser.
        f = open('readitem.html', 'w')
        print(htmlhead.format(title, link), content, htmlend, file=f)
        # stdout handling; blocks output from browser to stdout
        devnull = open('/dev/null', 'w')
        oldstdout_fno = os.dup(sys.stdout.fileno())
        os.dup2(devnull.fileno(), 1)
        WEB.open('readitem.html')
        os.dup2(oldstdout_fno, 1)

        # add read item to feedhist
        curfeedhist = feedhist.find("./feed[@title='{0}']".format(feedname))
        itemhist = ET.SubElement(curfeedhist, "item")
        itemhist.attrib["title"] = title
    else:
        print("No New Items for {0}.".format(feedname))

def displayhelp():
    print("Type 'check' to check all feeds.")
    print("Type 'read {feedname}' to read the feed with that name.")
    print("Type 'subscribe {url}' to subscribe to a new feed.")
    print("Type 'quit' to return to the shell.")
    print("See readme for more information.")

def checkall():
    for feed in feeddict.keys():
        check(feed, toreaddict)

#------------------------ Main runtime of program -----------------------------
checkall()
while True:
    usrin = input("> ")
    cmd,_ , arg = usrin.partition(" ")
    if cmd == "read":
        for feed in feeddict.keys():
            if arg.lower() in feed.lower():
                read(feed)
    elif cmd == "check":
        if arg:
            for feed in feeddict.keys():
                if arg.lower() in feed.lower():
                    check(feed, toreaddict)
                    if toreaddict[feed]:
                        pass
                    else:
                        print("No New Items for {0}.".format(feed))
        else:
            checkall()
    elif cmd == "subscribe":
        subscribe(arg)
    elif cmd == "help":
        displayhelp()
    elif cmd == "quit":
        print("Exiting.")
        sys.exit()
    else:
        print("Unrecognized command '{0}'. Type 'help' for more info.".format(cmd))

#---------------------- End of program run ------------------------------------

# saving changes 
ET.ElementTree(feedhist).write(filefeedhist)
ET.ElementTree(feedlist).write(xmlfeedlist)
    
# write some sort of readme, and throw it at someone to use
