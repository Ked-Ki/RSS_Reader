#!/usr/bin/env python3.3

import xml.etree.ElementTree as ET
import urllib.error as err
import urllib.request as URL
import webbrowser as WEB
import datetime as DT
import subprocess
import os
import sys


#----------------------------- User-defined Options: --------------------------
# This section can and should be modified by the user:
data_folder = ".RSS_Reader_Data/"
subscription_file = "subscriptions.xml"
history_file = "readhistory.xml"
updatelen = 7

#---------------------------- Initializing the Program ------------------------
xmlfeedlist = "{0}{1}".format(data_folder, subscription_file)
filefeedhist = "{0}{1}".format(data_folder, history_file)
# namespace for Atom feeds
atom = "{http://www.w3.org/2005/Atom}"

if os.path.isdir(data_folder):
    pass
else:
    print("Data Folder '{0}' does not exist. Creating in current directory.".format(data_folder))
    subprocess.call(["mkdir", "{0}".format(data_folder)])

# Google Reader Data Import
if len(sys.argv) > 1 and sys.argv[1] == "import": 
    greader = ET.parse(sys.argv[2]).getroot()
    feedlist = ET.Element("feedlist")
    for outline in greader.findall(".//outline[@type]"):
        feedurl = outline.get("xmlUrl")
        feedtitle = outline.get("title")
        print("Importing {0}".format(feedtitle))
        feed = ET.SubElement(feedlist, "feed")
        feed.attrib["title"] = feedtitle.replace("'","&#39;")
        feed.attrib["htmlUrl"] = outline.get("htmlUrl")
        # some feedburner feeds don't natively come in xml, so this is to patch that
        if "feedburner" in feedurl:
            feedurl = feedurl + "?format=xml"
        feed.attrib["xmlUrl"] = feedurl 
        # Google Reader's data does not mark b/w atom and rss feeds, so we check ourselves:
        try:
            xmlpage = URL.urlopen(feedurl)
        except err.URLError:
            print("No service. Please check network connection.")
            print("Import terminating.")
            sys.exit()
        page = ET.parse(xmlpage).getroot()
        if page.tag == "{0}feed".format(atom):
            feed.attrib["type"] = "atom"
        elif page.tag == "rss":
            feed.attrib["type"] = "rss"
        else:
            print("Unrecognized format for feed '{0}'.".format(feed), file=sys.stderr)
            feedlist.remove(feed)
else: 
    if os.path.isfile(xmlfeedlist):
        try:
            feedlist = ET.parse(xmlfeedlist).getroot()
        except ET.ParseError:
            print("'{0}' corrupted. Please check file.".format(xmlfeedlist))
            print("Exiting")
            sys.exit()
    else:
        feedlist = ET.Element("feedlist")

feeddict = {feed.get("title") : (feed.get("xmlUrl"), feed.get("type")) 
        for feed in feedlist.findall(".//feed")}

# dictionary to translate RSS formatted months to numbers:
months = { "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12, 
           "January": 1, "February": 2, "March": 3, "April": 4, "June": 6,
           "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
           "December": 12 }
# function to translate various date formats to the date type
def todate(pubdate):
    if pubdate[0].isalpha(): # Example: Tue, 19 Mar 2013
        date = pubdate.split(" ")
        itemdate = DT.date(int(date[3]), months[date[2]], int(date[1]))
    elif pubdate[0].isdigit(): # Corresponding to ISO 8601
        if "T" in pubdate:
            date = pubdate.partition("T")[0].split("-")
        else:
            date = pubdate.partition(" ")[0].split("-")
        itemdate = DT.date(int(date[0]),int(date[1]),int(date[2])) 
    return itemdate

# build initial read library.
def buildreadhist():
    hist = ET.Element("readhistory")
    for feed, (url, feedtype) in feeddict.items():
        try:
            xmlpage = URL.urlopen(url)
        except err.URLError:
            print("No service. Please check network connection.")
            print("Read history build unrecoverable. Exiting.")
            sys.exit()
        page = ET.parse(xmlpage).getroot()
        print("reading", feed.replace("&#39;","'"))
        bulkupdatehist(feed, hist, page)
    return hist

# puts all items older than updatelen days ago into history_file
def bulkupdatehist(feed, hist, page):
    feedhist = ET.SubElement(hist, "feed")
    feedhist.attrib["title"] = feed
    if page.tag == ("{0}feed".format(atom)):
        # Atom Format   
        for item in page.findall(".//{0}entry".format(atom)):
            pubdate = item.findtext("./{0}updated".format(atom))
            itemdate = todate(pubdate)
            if itemdate.today() - itemdate > DT.timedelta(days=updatelen):
                itemhist = ET.SubElement(feedhist, "item")
                itemhist.attrib["title"] = item.findtext("./{0}title".format(atom))
    elif page.tag == "rss":
        # RSS Format
        for item in page.findall(".//item"):
            pubdate = item.findtext("./pubDate")
            if pubdate: # the <pubDate> tag is optional in RSS format
                itemdate = todate(pubdate)
                if itemdate.today() - itemdate > DT.timedelta(days=updatelen):
                    itemhist = ET.SubElement(feedhist, "item")
                    itemhist.attrib["title"] = item.findtext("./title")
    else:
        print("Unrecognized format for feed '{0}'.".format(feed.replace("&#39;","'")))
        hist.remove(feedhist)

if os.path.isfile(filefeedhist):
    try:
        feedhist = ET.parse(filefeedhist).getroot()
    except ET.ParseError:
        print("'{0}' corrupted; building new history file".format(filefeedhist))
        feedhist = buildreadhist()
else:
    print("'{0}' not found; building new history.".format(filefeedhist))
    feedhist = buildreadhist()

# used when calling the read function
toreaddict = dict.fromkeys(feeddict.keys(), [])
# used to output html
htmlhead = """<html>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8" />
<head>
<title>Update from {2}</title>
</head>
<body>
<h1><a href="{1}">{0}</a></h1>
"""
htmlend = """</body>
</html>
"""
#----------- Functionalities of reader (subscribe, read, check, etc) ------------
def subscribe(feedurl):
    if not feedurl.startswith("http://"):
        feedurl = "http://" + feedurl 
    # feedburner feeds aren't always in xml format, so we fix that here
    if "feedburner" in feedurl:
        feedurl = feedurl + "?format=xml"
    if feedlist.find("./feed[@xmlUrl='{0}']".format(feedurl)):
        return
    else:
        try:
            xmlpage = URL.urlopen(feedurl)
        except err.URLError:
            print("No service. Please check network connection.")
            print("Subscribe function stopped.")
            return 
        page = ET.parse(xmlpage).getroot() 
        if page.tag == ("{0}feed".format(atom)):
            # atom format
            title = page.findtext("./{0}title".format(atom)).replace("'","&#39;")
            htmlurl = page.find("./{0}link".format(atom)).get("href")
            feedtype = "atom"
        elif page.tag == "rss":
            # rss format
            title = page.findtext("./channel/title").replace("'","&#39;")
            htmlurl = page.findtext("./channel/link")
            feedtype = "rss"
        else:
            print("Unrecognized format for '{0}'".format(feedurl))
            return

        feed = ET.SubElement(feedlist, "feed") 
        feed.attrib["title"] = title
        feed.attrib["htmlUrl"] = htmlurl
        feed.attrib["xmlUrl"] = feedurl
        feed.attrib["type"] = feedtype

        bulkupdatehist(title, feedhist, page)

        feeddict.setdefault(title, (feedurl, feedtype))

def unsubscribe(feedname):
    if feedname in feeddict.keys():
        feed = feedlist.find("./feed[@title='{0}']".format(feedname))
        feedlist.remove(feed)

        curfeedhist = feedhist.find("./feed[@title='{0}']".format(feedname))
        feedhist.remove(curfeedhist)

        feeddict.pop(feedname)
    else:
        print("Not subscribed to '{0}'".format(feedname))
        return


def check(feedname, toreaddict):
    (url,feedtype) = feeddict[feedname]
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
    # checks readhistory for items already read
    for readitem in curfeed.findall(".//item"):
        readitems.append(readitem.get("title"))
    # checks the feed (online) for items not in readitems and places them in unreaditems
    if feedtype == "rss":
        for item in page.findall(".//item"):
            if item.findtext("./title") in readitems:
                pass
            else:
                unreadcount += 1
                unreaditems.append(item)
    elif feedtype == "atom":
        for item in page.findall(".//{0}entry".format(atom)):
            title = item.findtext("./{0}title".format(atom))
            if title in readitems:
                pass
            else:
                unreadcount += 1
                # this part actually creates a new item element, so the read function
                # only needs to deal with one type of content.

                # creating a new item element in regular RSS format.
                newitem = ET.Element("item")
                newtitle = ET.SubElement(newitem, "title")
                newlink = ET.SubElement(newitem, "link")
                newcontent = ET.SubElement(newitem, "description")
                # filling newitem with data
                newtitle.text = title
                newlink.text = item.find("./{0}link".format(atom)).get("href")
                newcontent.text = item.findtext("./{0}content".format(atom))
                # putting newitem into unread items list
                unreaditems.append(newitem)
    else:
        print("Unrecognized format for '{0}'. Please check subscriptions file.".format(feedname))
        return

    toreaddict[feedname] = unreaditems
    if unreadcount > 0:
        print(feedname.replace("&#39;","'"), ": Unread:", unreadcount)
        for item in toreaddict[feedname]:
            print ("    ", item.findtext("./title"))
   

def read(feedname): 
    curitem = markread(feedname)
    if curitem:
        # code to handle one weird type of rss feed I found
        content = curitem.findtext("./{http://purl.org/rss/1.0/modules/content/}encoded")
        if content == None:
            content = curitem.findtext("./description")

        title = curitem.findtext("./title")
        link = curitem.findtext("./link")
        # handling partial links (only for page title links).
        if link.startswith("http://"):
            pass
        else:
            urlhead = feedlist.find("./feed[@title='{0}']".format(feedname)).get("htmlUrl")
            link = urlhead + link

        # writes the content to a html file, then opens it in browser.
        f = open('{0}readitem.html'.format(data_folder), 'w')
        print(htmlhead.format(title, link, feedname), content, htmlend, file=f)
        # stdout handling; blocks output from browser to stdout
        devnull = open('/dev/null', 'w')
        oldstdout_fno = os.dup(sys.stdout.fileno())
        os.dup2(devnull.fileno(), 1)
        WEB.open('{0}readitem.html'.format(data_folder))
        os.dup2(oldstdout_fno, 1)
    else:
        print("No New Items for {0}.".format(feedname.replace("&#39;","'")))

def markread(feedname):
    curfeed = toreaddict[feedname]
    if curfeed:
        curitem = curfeed.pop()
        # add read item to feedhist
        curfeedhist = feedhist.find("./feed[@title='{0}']".format(feedname))
        itemhist = ET.SubElement(curfeedhist, "item")
        itemhist.attrib["title"] = curitem.findtext("./title")
        return curitem
    else:
        return None

def displayhelp():
    print("Type 'check' to check all feeds.")
    print("Type 'read {feedname}' to read the feed with that name.")
    print("Type 'subscribe {url}' to subscribe to a new feed.")
    print("Type 'quit' to return to the shell.")
    print("See readme for more information and commands.")

def checkall():
    for feed in feeddict.keys(): 
        check(feed, toreaddict)

def markall(feedname):
    unreadcount = len(toreaddict[feedname])
    i = 0
    while i<unreadcount:
        markread(feedname)
        i += 1

def listall():
    for feed in feeddict.keys():
        print(feed.replace("&#39;","'"))

#------------------------ Command Prompt Utilities ----------------------------
def readprompt(): 
    usrin = input("> ").partition(" ")
    return usrin[0], usrin[2]

def shortened(sword, lword):
    return sword.lower() in lword.lower()

def yesno():
    yesno = input("Are you sure? (y/n) ")
    return yesno.startswith("y")


#------------------------ Main runtime of program -----------------------------
checkall()
exit = False
while not exit:
    cmd,arg = readprompt()
    if cmd == "read":
        for feed in feeddict.keys():
            if shortened(arg, feed):
                read(feed)
    elif cmd == "check":
        if arg:
            for feed in feeddict.keys():
                if shortened(arg, feed):
                    check(feed, toreaddict)
                    if toreaddict[feed]:
                        pass
                    else:
                        print("No New Items for {0}.".format(feed.replace("&#39;","'")))
        else:
            checkall()
    elif cmd == "mark":
        for feed in feeddict.keys():
            if shortened(arg, feed):
                markread(feed)
    elif cmd == "markall": 
        if arg:
            for feed in feeddict.keys():
                if shortened(arg, feed):
                    markall(feed)
        else:
            print("Marking ALL items from ALL feeds read!")
            if yesno():
                for feed in feeddict.keys():
                    markall(feed)
    elif cmd == "subscribe":
        subscribe(arg)
    elif cmd == "unsubscribe":
        for feed in feeddict.keys():
            if shortened(arg, feed):
                print("Unsubscribing from {0}.".format(feed.replace("&#39;","'")))
                if yesno():
                    unsubscribe(feed)
                    break
    elif cmd == "list":
        listall()
    elif cmd == "help":
        displayhelp()
    elif cmd == "quit":
        print("Exiting.")
        exit = True
    else:
        print("Unrecognized command '{0}'. Type 'help' for more info.".format(cmd))

#---------------------- End of program run ------------------------------------

# saving changes 
ET.ElementTree(feedhist).write(filefeedhist)
ET.ElementTree(feedlist).write(xmlfeedlist) 
