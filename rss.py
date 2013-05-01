#!/usr/bin/env python3.3

import xml.etree.ElementTree as ET
import urllib.error as err
import urllib.request as URL
import webbrowser as WEB
import datetime as DT
import os
import sys

# import configuration:
data_folder = os.path.expanduser("~/.RSS_Reader_Data/")
sys.path.append(data_folder)
from options import *

#---------------------------- Initializing the Program ------------------------
xmlfeedlist = "{0}{1}".format(data_folder, subscription_file)
filefeedhist = "{0}{1}".format(data_folder, history_file)
# namespace for Atom feeds
atom = "{http://www.w3.org/2005/Atom}"

if os.path.isdir(data_folder):
    pass
else:
    print("Data Folder '{0}' does not exist. Creating in current directory.".format(data_folder))
    os.mkdir(data_folder)

if os.path.isdir(data_folder + read_items_folder):
    pass
else:
    print("Data Folder '{0}' does not exist. Creating in current directory.".format(read_items_folder))
    os.mkdir(data_folder + read_items_folder)

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
            print("Unrecognized format for feed '{0}'.".format(feed))
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
    print("Checking {0}...".format(feedname.replace("&#39;","'")))
    try:
        xmlpage = URL.urlopen(url)
    except err.URLError:
        print("No service. Please check network connection.")
        return
    try:
        page = ET.parse(xmlpage).getroot() 
    except ET.ParseError:
        print("Error in rss feed '{0}'.\n    (URL: {1})".format(feedname,url))
        return
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
                checkcontent = item.findtext("./{0}content".format(atom))
                if not checkcontent:
                    checkcontent = item.findtext("./{0}summary".format(atom))
                newcontent.text = checkcontent
                # putting newitem into unread items list
                unreaditems.append(newitem)
    else:
        print("Unrecognized format for '{0}'. Please check subscriptions file.".format(feedname))
        return

    toreaddict[feedname] = unreaditems

def showcheck(feedname, toreaddict):
    unreadcount = len(toreaddict[feedname])
    if unreadcount > 0:
        print(feedname.replace("&#39;","'"), ": Unread:", unreadcount)
        for item in toreaddict[feedname]:
            print ("    ", item.findtext("./title").replace("&#8217;","'"))
    else:
        print("No New Items for {0}.".format(feedname.replace("&#39;","'")))
   
def read(feedname, count=1, itemname=None): 
    curitem = markread(feedname, itemname)
    if curitem:
        # code to handle one weird type of rss feed I found
        content = curitem.findtext("./{http://purl.org/rss/1.0/modules/content/}encoded")
        if content == None:
            content = curitem.findtext("./description")

        title = curitem.findtext("./title")
        link = curitem.findtext("./link")
        # handling partial links (only for page title links).
        if link.strip().startswith("http://"):
            pass
        else:
            urlhead = feedlist.find("./feed[@title='{0}']".format(feedname)).get("htmlUrl")
            link = urlhead + link

        # writes the content to a html file, then opens it in browser.
        f = open('{0}{1}readitem{2}.html'.format(data_folder, read_items_folder, count), 'w')
        print(htmlhead.format(title, link, feedname), content, htmlend, file=f)
        # stdout handling; blocks output from browser to stdout
        devnull = open('/dev/null', 'w')
        oldstdout_fno = os.dup(sys.stdout.fileno())
        os.dup2(devnull.fileno(), 1)
        WEB.open('{0}{1}readitem{2}.html'.format(data_folder, read_items_folder, count))
        os.dup2(oldstdout_fno, 1)
        f.close()
    else:
        print("No New Items for {0}.".format(feedname.replace("&#39;","'")))

def markread(feedname, itemname=None):
    curfeed = toreaddict[feedname]
    if itemname:
        for item in curfeed:
            if itemname == item.findtext("./title"):
                curitem = item
                curfeed.remove(item)
        if not curitem:
            print("Item '{0}' not in feed {1}.".format(itemname, feedname))
            return None
    else: 
        if curfeed:
            curitem = curfeed.pop() 
        else:
            return None
    # add read item to feedhist
    curfeedhist = feedhist.find("./feed[@title='{0}']".format(feedname))
    itemhist = ET.SubElement(curfeedhist, "item")
    itemhist.attrib["title"] = curitem.findtext("./title")
    return curitem

def displayhelp():
    print("Type 'check' to check all feeds.")
    print("Type 'read {feedname}' to read the feed with that name.")
    print("Type 'subscribe {url}' to subscribe to a new feed.")
    print("Type 'quit' to return to the shell.")
    print("See readme for more information and commands.")

def checkall():
    for feed in feeddict.keys():
        check(feed, toreaddict)
    for feed in feeddict.keys():
        if len(toreaddict[feed]) > 0:
            showcheck(feed, toreaddict)

def markall(feedname):
    unreadcount = len(toreaddict[feedname])
    i = 0
    while i<unreadcount:
        markread(feedname)
        i += 1

def listall():
    i = 0
    for feed in feeddict.keys():
        print(feed.replace("&#39;","'"))
        i += 1
    print("\nTotal Count: {0}".format(i))

#------------------------ Command Prompt Utilities ----------------------------
def readprompt(): 
    usrin = input("> ").partition(" ")
    return usrin[0], usrin[2]

def shortened(sword, lword):
    return sword.lower() in lword.lower()

def yesno(prompt):
    yesno = input("{0} (y/n) ".format(prompt))
    return yesno.startswith("y")

#------------------------ Main runtime of program -----------------------------
checkall()
exit = False
while not exit:
    cmd,arg = readprompt()
    if cmd == "read":
        count = 1
        for feed in feeddict.keys():
            if shortened(arg, feed):
                read(feed, count)
                count += 1
    elif cmd == "readall":
        count = 1
        if arg:
            for feed in feeddict.keys():
                if shortened(arg, feed):
                    while toreaddict[feed]:
                        read(feed, count)
                        count += 1
        else:
            print("About to read all items from ALL feeds.")
            if yesno("Are you sure?"):
                for feed in feeddict.keys():
                    while toreaddict[feed]:
                        read(feed, count)
                        count += 1
    elif cmd == "readitem":
        itemlist = []
        count = 1
        print("Unread items matching query:")
        for feed in feeddict.keys():
            if shortened(arg, feed):
                for item in toreaddict[feed]:
                    itemname = item.findtext("./title")
                    print("    [{0}]: {1}".format(count, itemname))
                    itemlist.append((itemname, feed))
                    count += 1
        try:
            choice = int(input("Please select item: "))
        except ValueError:
            print("Number argument expected. Returning to main prompt.")
            continue
        try:
            readitem = itemlist[choice-1]
        except IndexError:
            print("Number not in choices. Returning to main prompt.")
            continue
        read(readitem[1], 1, readitem[0])
    elif cmd == "check":
        if arg:
            for feed in feeddict.keys():
                if shortened(arg, feed):
                    check(feed, toreaddict)
                    showcheck(feed, toreaddict)
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
            if yesno("Are you sure?"):
                for feed in feeddict.keys():
                    markall(feed)
    elif cmd == "subscribe":
        subscribe(arg)
    elif cmd == "unsubscribe":
        for feed in feeddict.keys():
            if shortened(arg, feed):
                print("Unsubscribing from {0}.".format(feed.replace("&#39;","'")))
                if yesno("Are you sure?"):
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
