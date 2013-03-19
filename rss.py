#!/usr/bin/env python3.3

import xml.etree.ElementTree as ET
import urllib.error as err
import urllib.request as URL
import webbrowser as WEB
import subprocess
import os
import sys


#--------------------------- User-defined Options: -----------------
# This section can and should be modified by the user:
data_folder = ".RSS_Reader_Data/"
subscription_file = "subscriptions.xml"
history_file = "readhistory.xml"

#---------------------------- Initializing the Program ------------------------
# this is where the data is saved!
xmlfeedlist = "{0}{1}".format(data_folder, subscription_file)
filefeedhist = "{0}{1}".format(data_folder, history_file)
if os.path.isdir(data_folder):
    pass
else:
    print("Data Folder '{0}' does not exist. Creating in current directory.".format(datafolder))
    subprocess.call(["mkdir", "{0}".format(data_folder)])
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

# namespace for Atom feeds
atom = "{http://www.w3.org/2005/Atom}"

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
        feedhist = ET.SubElement(hist, "feed")
        feedhist.attrib["title"] = feed
        print("reading", feed)
        if page.tag == ("{0}feed".format(atom)):
            # Atom Format   
            for item in page.findall(".//{0}entry".format(atom)):
                itemhist = ET.SubElement(feedhist, "item")
                itemhist.attrib["title"] = item.findtext("./{0}title".format(atom))
        elif page.tag == "rss":
            # RSS Format
            for item in page.findall(".//item"):
                itemhist = ET.SubElement(feedhist, "item")
                itemhist.attrib["title"] = item.findtext("./title")
        else:
            print("Unrecognized format for feed '{0}'.".format(feed), file=sys.stderr)
    return hist

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
            title = page.findtext("./{0}title".format(atom)).replace("'","")
            htmlurl = page.find("./{0}link".format(atom)).get("href")
            feedtype = "atom"
        elif page.tag == "rss":
            # rss format
            title = page.findtext("./channel/title").replace("'","")
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

        curfeedhist = ET.SubElement(feedhist, "feed")
        curfeedhist.attrib["title"] = title

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
        print(feedname, ": Unread:", unreadcount)
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
        print("No New Items for {0}.".format(feedname))

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

#------------------------ Main runtime of program -----------------------------
checkall()
exit = False
while not exit:
    usrin = input("> ")
    cmd,_,arg = usrin.partition(" ")
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
    elif cmd == "mark":
        for feed in feeddict.keys():
            if arg.lower() in feed.lower():
                markread(feed)
    elif cmd == "markall":
        for feed in feeddict.keys():
            if arg.lower() in feed.lower():
                markall(feed)
    elif cmd == "subscribe":
        subscribe(arg)
    elif cmd == "unsubscribe":
        unsubscribe(arg)
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
