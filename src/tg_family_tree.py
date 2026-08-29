#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
TG Family Tree v4
=================

PyQt6 + QtWebEngine edition.

Security / genealogy invariants
-------------------------------
BLUE name/code:
    Permanent forever. No code path in this application edits/deletes it.

WHITE/default information:
    Provisional research layer. It may be automatically added, superseded,
    corrected, or removed later. Every automatic change is recorded in audit_log.

Baseline freeze:
    People/facts that existed when v4 initializes remain frozen until
    2026-09-07 14:00 local time, except that the automation may create NEW
    white provisional facts/people without altering the frozen baseline.

Publishing:
    Every day at 06:00 (persistent systemd user timer) Python creates
    761327132.txt itself, commits/pushes it to GitHub and Hugging Face,
    downloads both public copies, and marks success only if they match.

Research:
    Every day at 16:00 (persistent systemd user timer), background research
    gathers public search-result candidates and stores them. No CAPTCHA bypass,
    login bypass, or anti-bot evasion is attempted.

Embedded Web:
    The browser is inside the PyQt6 GUI. The current selected genealogy person
    is the browser's research context. Loaded public pages are automatically
    snapshotted, parsed, attached to that person, and may create/update white
    provisional facts or provisional relatives.
"""

from __future__ import annotations
import argparse
import datetime as dt
import difflib
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from xml.etree import ElementTree as ET

try:
    from PyQt6.QtCore import QDateTime, QTimer, Qt, QUrl, pyqtSignal, QObject
    from PyQt6.QtGui import QAction, QColor, QFont, QDesktopServices
    from PyQt6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
        QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
        QMessageBox, QPushButton, QPlainTextEdit, QProgressBar, QSplitter,
        QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QTreeWidget,
        QTreeWidgetItem, QVBoxLayout, QWidget, QHeaderView
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except Exception as exc:
    print("TG Family Tree v4 requires PyQt6 + QtWebEngine.", file=sys.stderr)
    print("On Debian/Ubuntu install: sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine", file=sys.stderr)
    print(f"Import error: {exc}", file=sys.stderr)
    raise

APP_ID="tg-family-tree"
DATA_HOME=Path(os.environ.get("XDG_DATA_HOME",Path.home()/".local/share"))/APP_ID
CONFIG_HOME=Path(os.environ.get("XDG_CONFIG_HOME",Path.home()/".config"))/APP_ID
DB_PATH=DATA_HOME/"family_tree_v4.sqlite3"
LEGACY_V3_DB=DATA_HOME/"family_tree_v3.sqlite3"
PUBLISH_DIR=DATA_HOME/"publish-v4"
RESEARCH_DIR=DATA_HOME/"research-v4"
CACHE_DIR=DATA_HOME/"web-cache"
CONFIG_PATH=CONFIG_HOME/"config-v4.json"
RUNTIME=Path(os.environ.get("XDG_RUNTIME_DIR",f"/tmp/tg-family-tree-{os.getuid()}"))
SOCKET_PATH=RUNTIME/"context-v4.sock"
RESEARCHER_ODT=Path("/opt/family-tree/Researcher.odt")
PROOF_NAME="761327132.txt"

COUNTDOWN_DEADLINE=dt.datetime(2026,8,29,23,55,0)
RESEARCH_START=dt.datetime(2026,8,29,16,0,0)
BASELINE_UNLOCK=dt.datetime(2026,9,7,14,0,0)

SEED_PEOPLE=[{"person_no": 1, "name": "Me", "details": ""}, {"person_no": 2, "name": "Dudley McCabe", "details": "1946–2019 San Diego, San Diego, California, USA"}, {"person_no": 3, "name": "Mom", "details": ""}, {"person_no": 4, "name": "Lester McCabe", "details": "6 May 1926 Butler, Pennsylvania, USA 26 May 1985 Kittanning, Armstrong, Pennsylvania, USA"}, {"person_no": 5, "name": "Noma Vade Smith", "details": "B:19 Mar 1927 San Diego, California D:20 Dec 1991 San Diego County, California, USA"}, {"person_no": 6, "name": "Grandpa", "details": ""}, {"person_no": 7, "name": "Grandma", "details": ""}, {"person_no": 8, "name": "John McCabe", "details": "B:9 Feb 1896 Allegheny County Pittsburgh PA D:Aug 1982 Chestnut Ridge Cemetery, Eldersville, Washington, Pennsylvania, USA"}, {"person_no": 9, "name": "Alice S Elliott", "details": "B:12 June 1906 Butler, Pennsylvania D:24 Dec 1951 New Castle, Pennsylvania"}, {"person_no": 10, "name": "Archie T Smith", "details": "B:21 Sept., 1894 Greeley, Weld Co. Colorado, USA D:8 May, 1973 San Diego, San Diego Co., California, USA"}, {"person_no": 11, "name": "Polly Myrtle Bowman", "details": "B:18 May 1887 Morgan County, Indiana, USA D:24 Jun 1955 San Diego, San Diego, California, United States"}, {"person_no": 12, "name": "Burke C Maynard", "details": "B:11 Jun 1904 North Dakota D:05 Dec 1986 Morro Bay, San Luis Obispo, California, USA"}, {"person_no": 13, "name": "Amelia B Hetdke", "details": "B:28 Dec 1904 North Dakota D:15 May 1979 Morro Bay, San Luis Obispo, California, USA"}, {"person_no": 14, "name": "Percy W Shapley", "details": "B:6 May 1901 Floyd, Floyd, Iowa, USA D:11 Sep 1946 Pasco, Franklin, Washington"}, {"person_no": 15, "name": "Minnie Schlorff", "details": "B:1 Mar 1905 10920 Mackinaw Avenue, Chicago, Illinois D:12 Apr 1946 Minneapolis, Hennepin, Minnesota, United States"}, {"person_no": 16, "name": "Edward Mccabe", "details": "B:Mar1861 Scotland D:1900 Pennsylvania"}, {"person_no": 17, "name": "Sarah McAvoy", "details": "B:13 Apr 1862 Derwent Street, Cockermouth, Cumberland, England D:1934 Pennsylvania"}, {"person_no": 18, "name": "James N Elliott", "details": "B:12 Oct 1855 Center Twp Butler County, Pennsylvania D:1 Nov 1926 Center, Butler, Pennsylvania, USA"}, {"person_no": 19, "name": "Elizabeth McQuiston", "details": "B:7 Jan 1887 Pennsylvania D:27 Aug 1940 New Castle, Lawrence, Pennsylvania"}, {"person_no": 20, "name": "Albert Franklin Smith", "details": "B:15 Mar., 1862 Mattoon, Coles Co., Illinois, USA D:20 Dec., 1946 Fairlawn Burial Park , Hutchinson, Reno Co., Kansas, USA"}, {"person_no": 21, "name": "Rose Ann Prickett", "details": "B:30 Jul 1869 Braceville, Grundy County, Illinois, USA D:28 Oct 1952 Yuma, Yuma County, Colorado, USA"}, {"person_no": 22, "name": "Thomas S Bowman", "details": "B:Feb 1863 Eminence, Morgan, Indiana, USA D:1904 Eminence, Morgan, Indiana, USA"}, {"person_no": 23, "name": "Nancy Jane Lambert", "details": "B:8 Jun 1864 Morgan County, Indiana, USA D:5 Nov 1946 Jefferson County, Indiana, USA"}, {"person_no": 24, "name": "William R Maynard", "details": "B:13 Dec 1878 Dassel, Meeker Co., Minnesota D:24 Nov 1958 Brooksville, Hernando County, Florida"}, {"person_no": 25, "name": "Gail Agnes Hillman", "details": "B:21 Sep 1884 Cannon Falls, Goodhue, Minnesota D:12 Apr 1982 Saint Paul, Ramsey, Minnesota, USA"}, {"person_no": 26, "name": "Robert R Hedtke", "details": "B:18 Jan 1876 Sibley, Minnesota D:13 FEB 1954 Fresno, California, USA"}, {"person_no": 27, "name": "Amelia Kiehlbauch", "details": "B:12 Jan 1880 Tyndall, Bon Homme, South Dakota, United States D:29 Aug 1969 , Fresno, California, USA"}, {"person_no": 28, "name": "William Shapley", "details": "B:10 Oct 1871 Minneota, Jackson, Minnesota D:1925-1928"}, {"person_no": 29, "name": "Olive G Stafford", "details": "B:30 Apr 1876 Calamus, Wisconsin D:22 May 1946 Charles City, Floyd, Iowa, USA"}, {"person_no": 30, "name": "William John Ludwig Sclorf", "details": "B:21JUL1867 Pomerania, Prussia D:1937 Wisconsin, USA"}, {"person_no": 31, "name": "Mary Johannsen", "details": "B:28 Nov 1868 Tondern, Schleswig-Holstein, Deutschland D:1951 Shawano County, Wisconsin, United States"}, {"person_no": 32, "name": "James McCabe", "details": "B:About 1840 Ireland"}, {"person_no": 33, "name": "Mary", "details": "B:Abt 1844 Ireland"}, {"person_no": 34, "name": "James McAvoy", "details": "B:17 Mar 1833 Ireland D:24 Oct 1906 Scott, Allegheny, Pennsylvania, USA"}, {"person_no": 35, "name": "Rosamund Sloan", "details": "B:1838 Ireland D:10 Nov 1912 Scott, Allegheny, Pennsylvania, USA"}, {"person_no": 36, "name": "James Elliott", "details": "B:Apr 1817 Somerset County, Pennsylvania, USA D:1906 Butler County, Pennsylvania"}, {"person_no": 37, "name": "Margaret Elliott", "details": "B:Oct 1824 Venango Co, PA D:19 Nov 1903 Somerset, Pennsylvania, United States"}, {"person_no": 38, "name": "Charles McQuiston", "details": "B:25MAR1850 Butler County, Pennsylvania D:31 Jul 1917 Butler, Butler, Pennsylvania, USA"}, {"person_no": 39, "name": "Mary Thorpe", "details": "B:27 January 1863 Pennsylvania D:30 May 1944 New Castle, Lawrence, Pennsylvania, USA"}, {"person_no": 40, "name": "John Isaac Smith", "details": "B:18 Feb 1821 Pittsburgh, Allegheny, Pennsylvania D:7 Dec 1916 Wray, Yuma County, Colorado"}, {"person_no": 41, "name": "Ruanna Hamilton", "details": "B:27 Jul 1827 Gnadenhutten, Tuscarawas, Ohio, USA D:19 Feb 1908 Monegaw Springs, St Clair County, Missouri, USA"}, {"person_no": 42, "name": "Charles Prickett", "details": "B:16 Oct 1829 Apakesha Grove, Champaign, Ohio, USA D:10 Jul 1903 Vernon, Yuma, Colorado, USA"}, {"person_no": 43, "name": "Adaline A Holderman", "details": "B:24 Apr 1835 Marion County, Ohio, USA D:28 Sep 1918 Yuma County, Colorado, USA"}, {"person_no": 44, "name": "Abel Bowman", "details": "B:25 Dec 1830 Lincoln County, North Carolina, USA D:4 Nov 1905 Ashland, Morgan County, Indiana, USA"}, {"person_no": 45, "name": "Mary Martha Shumaker", "details": "B:2 Apr 1837 Eminence, Morgan County, Indiana, USA D:Abt. 1923 Morgan County, Illinois, USA"}, {"person_no": 46, "name": "Aaron Lorenzo Lambert", "details": "B:13 Oct 1830 ,Randolph, North Carolina, United States D:19 Jan 1910 ,Morgan, Indiana, United States"}, {"person_no": 47, "name": "Tabitha Ann Brown", "details": "B:10 Aug 1838 Hall, Morgan, Indiana, United States D:27 Apr 1915 Hall, Morgan, Indiana, USA"}, {"person_no": 48, "name": "George Maynard", "details": "B:27 Aug 1852 Prestonsburg, Floyd Co, Kentucky, USA D:2 May 1932 Minot, Ward, North Dakota, USA"}, {"person_no": 49, "name": "Margaret Rose Sansom", "details": "B:11 FEB 1859 Logan Co, KY (Wynne Co, West Virginia) D:28 Dec 1928 Rosehill, Covington, Alabama, United States"}, {"person_no": 50, "name": "Fred Ernest Hillman", "details": "B:21 Aug 1857 Minnesota, USA D:4 Dec 1950 Bald Eagle Center, Cass County, Minnesota, USA"}, {"person_no": 51, "name": "Agnes Maria Platt", "details": "Born: 27 April 1857 – Palmyra, Jefferson County, Wisconsin, United States)(Died: 23 February 1946 – Ramsey County, Minnesota, United States"}, {"person_no": 52, "name": "August Friedrich Hedtke", "details": "Born: 23 August 1847 – Alt Paleschken, Kreis Berent, Regierungsbezirk Danzig, West Prussia) (Died: 31 January 1918 – Henderson, Sibley County, Minnesota, United States"}, {"person_no": 53, "name": "Amelia Carolina Luedtke", "details": "Born: February 1850 – Pomerania, Prussia)(Died: 24 April 1925 – Henderson, Sibley County, Minnesota, United States"}, {"person_no": 54, "name": "Josef Kiehlbauch", "details": "B:1 Jan 1850 Neuberg, Russia D:14 Sep 1908 Chicago, Cook, Illinois, USA"}, {"person_no": 55, "name": "Barbara Beck", "details": "B:22 Jan 1850 Lustdorf, Russia D:15 July 1923 Tyndall, Bon Homme, South Dakota"}, {"person_no": 56, "name": "Patrick Henry Shapley", "details": "B:10 APR 1846 Emmett, Calhoun, Michigan"}, {"person_no": 57, "name": "Mary Rice", "details": "B:Feb 1849 Wisconsin, USA"}, {"person_no": 58, "name": "William Mark Stafford", "details": ""}, {"person_no": 59, "name": "Alice Waite", "details": "B:27 November 1840 Lorain, Lorain, Ohio D:4 July 1914 Gardena, Bottineau, North Dakota, USA"}, {"person_no": 62, "name": "Johannsen", "details": "B:25 September 1833 D:26 March 1919"}, {"person_no": 63, "name": "Elena M Johannsen", "details": "B:24 June 1836 D:3 June 1920"}, {"person_no": 68, "name": "John McAvoy", "details": "B:abt 1797 Ireland"}, {"person_no": 69, "name": "Sarah Ann McAvoy", "details": "B:abt 1797 Newry, Ireland"}, {"person_no": 70, "name": "John Sloan", "details": "B:May 1820 County Down, Ireland D:1 August 1900 Washington Township, Cambria County, Pennsylvania, USA"}, {"person_no": 71, "name": "Ann McGowan", "details": "B:Abt. 1822 County Down, Ireland D:Bef. 1900"}, {"person_no": 72, "name": "James Elliott", "details": "B:Apr 1817 Somerset County, Pennsylvania, USA D:1906 Butler County, Pennsylvania"}, {"person_no": 73, "name": "Margaret Scott", "details": "B:10 Feb 1793 Mercer, Franklin Co., Pennsylvania, United States D:1 Apr 1868 Butler, Butler Co., Pennsylvania, United States"}, {"person_no": 74, "name": "Johann Jacob Friedrich Huber", "details": "B:11 Jan 1804 Attlisberg, Waldshut, Baden-Württemberg, Germany D:7 May 1877 Attlisberg, Waldshut, Baden-Württemberg, Germany"}, {"person_no": 75, "name": "Frederika Regkukel", "details": "B:1800 Attlisberg, Waldshut, Baden-Wuerttemberg, Germany D:1830 Attlisberg, Waldshut, Baden-Wuerttemberg, Germany"}, {"person_no": 76, "name": "Charles McQuistion", "details": "B:23 Nov 1813 Butler, Pennsylvania, United States D:22 Dec 1872 Butler County, Pennsylvania, United States"}, {"person_no": 77, "name": "Rebecca Grannis", "details": "B:26 Mar 1819 Massachusetts D:31 Oct 1905 Near Slippery Rock, Butler County, Pennsylvania, USA"}, {"person_no": 78, "name": "William Thorpe", "details": "B:abt 1826 New Jersey D:Abt 1893 Pennsylvania"}, {"person_no": 79, "name": "Mary Jane Sumner", "details": "B:1839 Pennsylvania D:before 1880 Pennsylvania"}, {"person_no": 80, "name": "William Smith", "details": "B:1790-12-11 Metal Township, Franklin County, Pennsylvania D:1857-04-25 Tuscarawas County, Ohio"}, {"person_no": 81, "name": "Lucy Ann Kreidler", "details": "B:15 Feb 1795 Maryland, United States D:1890 Mattoon, Coles, Illinois, United States"}, {"person_no": 82, "name": "Thomas Cleophas Hamilton", "details": "B:1 Feb 1784 Lincoln County, North Carolina, USA D:23 Feb 1872 Gnadenhutten, Tuscarawas County, Ohio, USA"}, {"person_no": 83, "name": "Sarah Elizabeth Marlow", "details": "B:Feb 1799 , Prince George's, Maryland, USA D:07 Sep 1838 Gnadenhutten, Tuscarawas, Ohio, USA"}, {"person_no": 84, "name": "James Prickett", "details": "B:ABT 1795 Champaign County, Illinois D:14 NOV 1843 Kendall, Illinois, USA"}, {"person_no": 85, "name": "Rebecca Wisham", "details": "B:25 Aug 1799 Gloucester County, New Jersey, USA D:07 Sep 1844 Newark, Kendall County, Illinois,USA"}, {"person_no": 86, "name": "Jacob Holderman Sr", "details": "1808-1864"}, {"person_no": 87, "name": "Mercy Caroline Loveland", "details": "B:08 Oct 1811 Delaware, Ohio, United States D:19 May 1886 Cottage Grove, Lane, Oregon, United States"}, {"person_no": 88, "name": "George W Bowman Jr", "details": "B:Oct 1787 Lincoln County, North Carolina, United States of America D:5 Aug 1874 Morgan County, Indiana, USA"}, {"person_no": 89, "name": "Mary Catherine Eisenhower", "details": "B:13 Feb 1798 Lincoln, North Carolina, United States D:1 Sep 1865 Morgan County, Indiana, USA"}, {"person_no": 90, "name": "Thomas J Shoemake", "details": "B:20 Apr 1797 Washington County, Kentucky, USA D:20 Apr 1846 Eminence, Morgan, Indiana, USA"}, {"person_no": 91, "name": "Jemima Blunk", "details": "B:Nov 1802 Harrison, Indiana, USA D:1882 Adams, Morgan County, Indiana, USA"}, {"person_no": 92, "name": "Henry Ira Lambert", "details": "B:24 MAY 1796 North Carolina, United States D:1868 Hendricks County, Indiana, United States"}, {"person_no": 93, "name": "Sarah 'Sally' M Craven", "details": "B:1809 Randolph, North Carolina, United States D:27 JAN 1887 Center Valley, Indiana, United States"}, {"person_no": 94, "name": "John W Brown", "details": "B:15 Oct 1817 Kentucky, USA D:27 Feb 1903 Morgan, Indiana, USA"}, {"person_no": 95, "name": "Nancy Jan Wilhite", "details": "B:Abt. 1819 Kentucky, USA D:11 Apr 1890 Morgan, Indiana, USA"}, {"person_no": 96, "name": "William Maynard", "details": "B:18 May 1830 Pike County, Kentucky, United States of America D:25 March 1908 Pierce County, Washington, United States of America"}, {"person_no": 97, "name": "Sarah Parsons", "details": "B:9 Aug 1821 Kentucky D:14 Mar 1891 Bertha, Todd County, Minnesota, United States of America"}, {"person_no": 98, "name": "Riley Sansom", "details": "B:10 Feb 1831 pike county kentucky D:6 Apr 1905 Riverside, Snohomish, Washington, USA"}, {"person_no": 99, "name": "Sarah Sally Kline", "details": "B:20 Jul 1836 Glen Alum , Logan, Virginia/West Virginia D:6 September 1928 Snohomish, Snohomish, Washington, United States"}, {"person_no": 100, "name": "Levi Colburn Hillman", "details": "B:25 Jan 1822 Conway, Franklin, Massachusetts, USA D:11 Mar 1861 Randolph, Dakota, Minnesota, USA"}, {"person_no": 101, "name": "Mary Marinda Shelly", "details": "B:1830 Connecticut D:11 Mar 1897 Randolph, Dakota County, MN"}, {"person_no": 102, "name": "David C Platt", "details": "B:16 May 1823 Berne, Clinton, New York, United States D:23 Oct 1904 Cannon Falls, Goodhue, Minnesota, United States"}, {"person_no": 103, "name": "Miranda McLane", "details": "B:12 Mar 1817 Alburgh, Grand Isle, Vermont, United States D:24 Jul 1861 Werner, Janeau, Wisconsin, United States"}, {"person_no": 104, "name": "Johann E Hedtke", "details": "B:5 Dec 1819 West Prussia D:28 Aug 1894 Chaska, Carver, Minnesota, United States"}, {"person_no": 105, "name": "Florentine Henriette Florence Hedtke", "details": "B:31 Jul 1828 Neu or Alt Paleschken, Berent, Danzig, West Prussia D:18 Feb 1901 Chaska, Carver, Minnesota, USA"}, {"person_no": 108, "name": "Joseph Sr Kiehlbauch", "details": "B:22 Jan 1826 Neuberg, Cherson Prov, New Odessa, Russia D:29 May 1902 Tyndall, Bon Homme, South Dakota, USA"}, {"person_no": 109, "name": "Johanna Knoepfle", "details": "B:25 Jul 1824 Alexanderhilf, Grossliebental District, Odessa, Russia D:21 Apr 1910 Medina, Stutsman Co., North Dakota"}, {"person_no": 110, "name": "Constantin Beck", "details": "B:16 May 1812 Wuerttemberg, Germany D:04 Aug 1857 Luftsdorf, Odessa"}, {"person_no": 111, "name": "Barbara Maier/Beck", "details": "B:18 May 1811 D:11 Jun 1856 Odessa, Odessa, Odessa, Kherson, Russia"}, {"person_no": 112, "name": "William Shapley", "details": "B:ABT 1798/9 Granville, Washington, New York D:BET 1861 AND 1864 Iowa"}, {"person_no": 113, "name": "Clarissa Gridley", "details": "B:ABT 1804 New York"}, {"person_no": 114, "name": "Ica Foster Rice", "details": "B:1805 Charlotteville Twp, Norfolk co., Canada D:01 Jan 1859 McLoughlin Canyon, Tonasket, Okanogan, Washington"}, {"person_no": 115, "name": "Kezia Bair", "details": "B:1810 Pennsylvania D:20 Apr 1856 Riverton, Fremont, Iowa"}, {"person_no": 116, "name": "Joseph W Stafford", "details": "B:1804 New York"}, {"person_no": 117, "name": "Hulda Sylvah", "details": "B:1811 Pennsylvania, United States D:1862 Wisconsin"}, {"person_no": 118, "name": "Barton J Waite", "details": "B:1792 New York, United States D:1862/1870 Calamus, Dodge, Wisconsin, United States"}, {"person_no": 119, "name": "Susannah Clark Bacon", "details": "B:20 August 1790 Randolph, Orange, Vermont, USA D:December 1870 Lorain, Lorain, Ohio, USA"}, {"person_no": 127, "name": "Lorenz Hinrichsen", "details": "B:29 July 1804 D:18 June 1854"}, {"person_no": 128, "name": "Sophia Margaretha Hinrichsen", "details": "B:25 December 1809 D:17 July 1866"}]
KNOWN_CODES={"2": "TG943760", "3": "TG264819", "4": "TG708346", "5": "TG315902", "6": "TG879461", "7": "TG150984", "8": "TG628417", "9": "TG492705", "10": "TG713289", "11": "TG856134", "12": "TG239670", "13": "TG984215", "15": "TG742018", "16": "TG307645", "17": "TG918273", "18": "TG654890", "19": "TG270541", "20": "TG839162", "21": "TG501784", "22": "TG962430", "23": "TG348671", "24": "TG715094", "25": "TG286753", "26": "TG903148", "27": "TG472690", "28": "TG618235", "29": "TG759401", "31": "TG324786", "34": "TG891052", "35": "TG540918", "36": "TG673245", "37": "TG182976", "38": "TG804631", "39": "TG295740", "40": "TG917384", "41": "TG463829", "42": "TG728195", "43": "TG356814", "44": "TG940672", "45": "TG215839", "46": "TG684510", "47": "TG370924", "48": "TG859743", "49": "TG502168", "50": "TG796320", "51": "TG148675", "52": "TG923450", "53": "TG610982", "54": "TG274361", "55": "TG835097", "56": "TG491628", "57": "TG762503", "58": "TG318940", "59": "TG907216", "63": "TG654173"}
PARENT_OVERRIDES={"17": [34, 35], "63": [127, 128]}
GENEALOGY_SITES=[["FamilySearch", "https://www.familysearch.org/search/"], ["Ancestry", "https://www.ancestry.com/search/"], ["MyHeritage", "https://www.myheritage.com/research"], ["Find a Grave", "https://www.findagrave.com/memorial/search"], ["WikiTree", "https://www.wikitree.com/wiki/Special:SearchPerson"], ["Geni", "https://www.geni.com/search"], ["Geneanet", "https://en.geneanet.org/genealogy/"], ["Findmypast", "https://www.findmypast.com/search"], ["American Ancestors", "https://www.americanancestors.org/databases"], ["FamilyTreeDNA", "https://www.familytreedna.com/"], ["Fold3", "https://www.fold3.com/"], ["Newspapers.com", "https://www.newspapers.com/"], ["NewspaperArchive", "https://newspaperarchive.com/"], ["Chronicling America", "https://www.loc.gov/chronicling-america/"], ["National Archives (US)", "https://www.archives.gov/research/genealogy"], ["USGenWeb", "https://www.usgenweb.org/"], ["BillionGraves", "https://billiongraves.com/"], ["Archives.com", "https://www.archives.com/"], ["Library and Archives Canada", "https://library-archives.canada.ca/eng/collection/research-help/genealogy-family-history/Pages/genealogy-family-history.aspx"], ["IrishGenealogy.ie", "https://www.irishgenealogy.ie/"], ["ScotlandsPeople", "https://www.scotlandspeople.gov.uk/"], ["FreeBMD", "https://www.freebmd.org.uk/"], ["Google Books", "https://books.google.com/"], ["Internet Archive", "https://archive.org/"]]

BLUE="#0066cc"

SCHEMA=r"""
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS people(
    id INTEGER PRIMARY KEY,
    person_no INTEGER UNIQUE,
    display_name TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    name_permanent INTEGER NOT NULL DEFAULT 0 CHECK(name_permanent IN(0,1)),
    baseline_record INTEGER NOT NULL DEFAULT 0 CHECK(baseline_record IN(0,1)),
    public INTEGER NOT NULL DEFAULT 1 CHECK(public IN(0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS identifiers(
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN('TG','AKA_TE')),
    permanent INTEGER NOT NULL DEFAULT 0 CHECK(permanent IN(0,1)),
    source TEXT NOT NULL DEFAULT 'generated',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS relationships(
    id INTEGER PRIMARY KEY,
    child_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    parent_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'parent',
    confidence REAL NOT NULL DEFAULT 1.0,
    notes TEXT NOT NULL DEFAULT '',
    permanent INTEGER NOT NULL DEFAULT 0 CHECK(permanent IN(0,1)),
    baseline_record INTEGER NOT NULL DEFAULT 0 CHECK(baseline_record IN(0,1)),
    source_url TEXT NOT NULL DEFAULT '',
    UNIQUE(child_id,parent_id,relation)
);

CREATE TABLE IF NOT EXISTS facts(
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.5,
    source_url TEXT NOT NULL DEFAULT '',
    source_title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN('active','superseded','rejected')),
    permanent INTEGER NOT NULL DEFAULT 0 CHECK(permanent IN(0,1)),
    baseline_record INTEGER NOT NULL DEFAULT 0 CHECK(baseline_record IN(0,1)),
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_id,field,value,source_url)
);

CREATE TABLE IF NOT EXISTS web_pages(
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    text_sha256 TEXT NOT NULL,
    cache_file TEXT NOT NULL DEFAULT '',
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_id,url,text_sha256)
);

CREATE TABLE IF NOT EXISTS research_candidates(
    id INTEGER PRIMARY KEY,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    source_site TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    snippet TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.25,
    status TEXT NOT NULL DEFAULT 'staged',
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(person_id,url)
);

CREATE TABLE IF NOT EXISTS audit_log(
    id INTEGER PRIMARY KEY,
    event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    old_value TEXT NOT NULL DEFAULT '',
    new_value TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS state(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

def now_local(): return dt.datetime.now()
def baseline_locked(): return now_local() < BASELINE_UNLOCK

def ensure_dirs():
    for p in (DATA_HOME,CONFIG_HOME,PUBLISH_DIR,RESEARCH_DIR,CACHE_DIR,RUNTIME):
        p.mkdir(parents=True,exist_ok=True)

def db():
    ensure_dirs()
    c=sqlite3.connect(DB_PATH,timeout=30)
    c.row_factory=sqlite3.Row
    c.executescript(SCHEMA)
    return c

def audit(c,actor,action,etype,eid=None,old="",new="",reason="",url=""):
    c.execute("""INSERT INTO audit_log(actor,action,entity_type,entity_id,old_value,new_value,reason,source_url)
                 VALUES(?,?,?,?,?,?,?,?)""",(actor,action,etype,eid,str(old),str(new),reason,url))

def get_person_by_no(c,no):
    return c.execute("SELECT * FROM people WHERE person_no=?",(no,)).fetchone()

def get_person_by_name(c,name):
    return c.execute("SELECT * FROM people WHERE display_name=? COLLATE NOCASE",(name,)).fetchone()

def identifiers_for(c,pid):
    return list(c.execute("SELECT * FROM identifiers WHERE person_id=? ORDER BY permanent DESC,kind,code",(pid,)))

def primary_code(c,pid):
    rows=identifiers_for(c,pid)
    if not rows: return ""
    return rows[0]["code"]

def code_exists(c,code):
    return c.execute("SELECT 1 FROM identifiers WHERE code=?",(code,)).fetchone() is not None

def add_identifier(c,pid,code,kind,permanent=False,source="generated"):
    code=code.strip().upper()
    old=c.execute("SELECT * FROM identifiers WHERE code=?",(code,)).fetchone()
    if old:
        if old["person_id"]!=pid: raise ValueError(f"Identifier {code} already belongs to another person.")
        if permanent and not old["permanent"]:
            c.execute("UPDATE identifiers SET permanent=1,source=? WHERE id=?",(source,old["id"]))
            audit(c,"system","confirm","identifier",old["id"],old["code"],old["code"],"confirmed identifier")
        return
    cur=c.execute("INSERT INTO identifiers(person_id,code,kind,permanent,source) VALUES(?,?,?,?,?)",
                  (pid,code,kind,1 if permanent else 0,source))
    audit(c,"system","create","identifier",cur.lastrowid,"",code,source)

def generate_tg(c):
    while True:
        x=f"TG{secrets.randbelow(900000)+100000:06d}"
        if not code_exists(c,x): return x

def generate_aka(c):
    nums=[]
    for r in c.execute("SELECT code FROM identifiers WHERE kind='AKA_TE'"):
        m=re.fullmatch(r"AKA_TE(\d+)",r["code"])
        if m: nums.append(int(m.group(1)))
    n=max(nums+[324542])+1
    while code_exists(c,f"AKA_TE{n:06d}"): n+=1
    return f"AKA_TE{n:06d}"

def parent_ids(c,pid):
    return [r["parent_id"] for r in c.execute("SELECT parent_id FROM relationships WHERE child_id=? AND relation='parent'",(pid,))]

def is_descendant_of(c,pid,ancestor):
    if pid==ancestor:return False
    seen=set(); stack=[pid]
    while stack:
        cur=stack.pop()
        if cur in seen:continue
        seen.add(cur)
        for par in parent_ids(c,cur):
            if par==ancestor:return True
            stack.append(par)
    return False

def is_sibling_of(c,pid,target):
    if pid==target:return False
    a=set(parent_ids(c,pid)); b=set(parent_ids(c,target))
    return bool(a and b and a.intersection(b))

def desired_generated_kind(c,pid):
    doug=get_person_by_no(c,2); mom=get_person_by_no(c,3)
    if mom and pid==mom["id"]: return "AKA_TE"
    if doug and (is_descendant_of(c,pid,doug["id"]) or is_sibling_of(c,pid,doug["id"])): return "AKA_TE"
    return "TG"

def ensure_identifier_policy(c,pid):
    p=c.execute("SELECT * FROM people WHERE id=?",(pid,)).fetchone()
    if not p:return
    ids=identifiers_for(c,pid)
    if p["person_no"] in (2,3):
        kinds={x["kind"] for x in ids}
        if "TG" not in kinds:add_identifier(c,pid,generate_tg(c),"TG",False,"generated")
        if "AKA_TE" not in kinds:add_identifier(c,pid,generate_aka(c),"AKA_TE",False,"generated")
        return
    want=desired_generated_kind(c,pid)
    for x in ids:
        if not x["permanent"] and x["kind"]!=want:
            audit(c,"system","delete","identifier",x["id"],x["code"],"",f"branch policy changed to {want}")
            c.execute("DELETE FROM identifiers WHERE id=?",(x["id"],))
    if not any(x["kind"]==want for x in identifiers_for(c,pid)):
        add_identifier(c,pid,generate_aka(c) if want=="AKA_TE" else generate_tg(c),want,False,"generated")

def migrate_legacy(c):
    if not LEGACY_V3_DB.exists():return
    old=sqlite3.connect(LEGACY_V3_DB); old.row_factory=sqlite3.Row
    try:
        tabs={r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "people" not in tabs:return
        idmap={}
        for op in old.execute("SELECT * FROM people"):
            t=get_person_by_no(c,op["person_no"]) if op["person_no"] is not None else None
            if t is None:t=get_person_by_name(c,op["display_name"])
            if t is None:
                cur=c.execute("""INSERT INTO people(person_no,display_name,details,name_permanent,baseline_record,public)
                                 VALUES(?,?,?,?,1,?)""",
                              (op["person_no"],op["display_name"],op["details"],
                               int(op["name_permanent"]),int(op["public"])))
                nid=cur.lastrowid
            else:
                nid=t["id"]
            idmap[op["id"]]=nid
        if "identifiers" in tabs:
            for x in old.execute("SELECT * FROM identifiers"):
                if x["person_id"] in idmap:
                    try:add_identifier(c,idmap[x["person_id"]],x["code"],x["kind"],bool(x["permanent"]),x["source"])
                    except ValueError:pass
        if "relationships" in tabs:
            for r in old.execute("SELECT * FROM relationships"):
                a=idmap.get(r["child_id"]); b=idmap.get(r["parent_id"])
                if a and b:
                    c.execute("""INSERT OR IGNORE INTO relationships(child_id,parent_id,relation,confidence,notes,permanent,baseline_record)
                                 VALUES(?,?,?,?,?,?,1)""",(a,b,r["relation"],r["confidence"],r["notes"],r["permanent"]))
    finally:old.close()

def seed():
    c=db()
    if c.execute("SELECT value FROM state WHERE key='v4_seeded'").fetchone():
        for p in c.execute("SELECT id FROM people"):ensure_identifier_policy(c,p["id"])
        c.commit();c.close();return
    by_no={}
    for p in SEED_PEOPLE:
        c.execute("""INSERT OR IGNORE INTO people(person_no,display_name,details,name_permanent,baseline_record,public)
                     VALUES(?,?,?,?,1,1)""",(p["person_no"],p["name"],p.get("details",""),0))
        by_no[p["person_no"]]=get_person_by_no(c,p["person_no"])["id"]
    if 1 not in by_no:
        c.execute("INSERT INTO people(person_no,display_name,details,baseline_record) VALUES(1,'Me','',1)")
        by_no[1]=get_person_by_no(c,1)["id"]
    for no,pid in list(by_no.items()):
        pars=[2,3] if no==1 else PARENT_OVERRIDES.get(str(no),[2*no,2*no+1])
        for par in pars:
            if par in by_no:
                c.execute("""INSERT OR IGNORE INTO relationships(child_id,parent_id,relation,confidence,permanent,baseline_record)
                             VALUES(?,?, 'parent',1.0,1,1)""",(pid,by_no[par]))
    for ns,code in KNOWN_CODES.items():
        no=int(ns)
        if no in by_no:
            add_identifier(c,by_no[no],code,"TG",True,"confirmed-source")
            c.execute("UPDATE people SET name_permanent=1 WHERE id=?",(by_no[no],))
    add_identifier(c,by_no[1],"AKA_TE324543","AKA_TE",True,"confirmed-user")
    c.execute("UPDATE people SET name_permanent=1 WHERE id=?",(by_no[1],))
    if 2 in by_no:
        add_identifier(c,by_no[2],"AKA_TE324544","AKA_TE",True,"confirmed-user")
        c.execute("UPDATE people SET name_permanent=1 WHERE id=?",(by_no[2],))
    migrate_legacy(c)
    for p in c.execute("SELECT id FROM people"):ensure_identifier_policy(c,p["id"])
    c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('v4_seeded','1')")
    c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('baseline_frozen_at',?)",(now_local().isoformat(),))
    c.commit();c.close()

def load_config():
    d={"github_remote":"","hf_remote":"","branch":"main","github_proof_url":"","hf_proof_url":"",
       "researcher_odt":str(RESEARCHER_ODT),"auto_extract":True,"auto_create_relatives":True,
       "fact_update_threshold":0.72,"relationship_threshold":0.84,
       "hf_repo_id":"we6jbo/tg-family-tree-dataset",
       "hf_cli":str(Path.home()/".local/share/tg-family-tree-tools/venv/bin/hf")}
    if CONFIG_PATH.exists():
        try:d.update(json.loads(CONFIG_PATH.read_text()))
        except Exception:pass
    return d

def save_config(cfg):
    ensure_dirs();CONFIG_PATH.write_text(json.dumps(cfg,indent=2)+"\n");os.chmod(CONFIG_PATH,0o600)

def run(cmd,cwd=None,check=True):
    p=subprocess.run(cmd,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if check and p.returncode:raise RuntimeError(p.stdout.strip() or "command failed")
    return p.stdout.strip()

# ------------------------- provisional fact engine -------------------------

MONTHS="January February March April May June July August September October November December Jan Feb Mar Apr Jun Jul Aug Sep Sept Oct Nov Dec".split()
DATE_RE=re.compile(r"\b(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\b(?:17|18|19|20)\d{2}\b)",re.I)
REL_PATTERNS=[
    ("parent",re.compile(r"\b(?:son|daughter|child)\s+of\s+([A-Z][A-Za-z'’.\- ]{2,60})\s+and\s+([A-Z][A-Za-z'’.\- ]{2,60})",re.I)),
    ("father",re.compile(r"\bfather(?:\s+was|\s*:|\s+is)?\s+([A-Z][A-Za-z'’.\- ]{2,60})",re.I)),
    ("mother",re.compile(r"\bmother(?:\s+was|\s*:|\s+is)?\s+([A-Z][A-Za-z'’.\- ]{2,60})",re.I)),
    ("spouse",re.compile(r"\b(?:wife|husband|spouse)(?:\s+was|\s*:|\s+is|\s+of)?\s+([A-Z][A-Za-z'’.\- ]{2,60})",re.I)),
]

def clean_candidate_name(s):
    s=re.sub(r"\s+"," ",s).strip(" ,.;:-")
    # prevent giant sentence fragments
    words=s.split()
    if len(words)>6:s=" ".join(words[:6])
    if len(s)<3 or len(s)>80:return ""
    stop={"the","this","that","united states","family","county","born","died"}
    if s.casefold() in stop:return ""
    return s

def add_fact(c,pid,field,value,confidence,url="",title="",actor="web-auto"):
    value=re.sub(r"\s+"," ",value).strip()
    if not value:return None
    old=c.execute("""SELECT * FROM facts WHERE person_id=? AND field=? AND value=? AND source_url=?""",
                  (pid,field,value,url)).fetchone()
    if old:
        c.execute("UPDATE facts SET last_seen=CURRENT_TIMESTAMP,confidence=MAX(confidence,?) WHERE id=?",(confidence,old["id"]))
        return old["id"]
    cur=c.execute("""INSERT INTO facts(person_id,field,value,confidence,source_url,source_title,status,permanent,baseline_record)
                     VALUES(?,?,?,?,?,?,'active',0,0)""",(pid,field,value,confidence,url,title))
    new_id=cur.lastrowid
    audit(c,actor,"create","fact",new_id,"",f"{field}={value}",f"confidence={confidence:.2f}",url)

    # Automation may replace weaker WHITE facts, but never permanent facts and never
    # a frozen baseline fact before the Sep 7 unlock.
    competitors=list(c.execute("""SELECT * FROM facts
        WHERE person_id=? AND field=? AND id<>? AND status='active' AND permanent=0""",(pid,field,new_id)))
    for comp in competitors:
        can_change=(not comp["baseline_record"]) or (not baseline_locked())
        if can_change and confidence >= float(comp["confidence"])+0.08:
            c.execute("UPDATE facts SET status='superseded' WHERE id=?",(comp["id"],))
            audit(c,actor,"supersede","fact",comp["id"],
                  f"{comp['field']}={comp['value']}",f"{field}={value}",
                  f"higher-confidence provisional fact {confidence:.2f}>{comp['confidence']:.2f}",url)
    return new_id

def find_or_create_provisional_person(c,name,reason,url=""):
    name=clean_candidate_name(name)
    if not name:return None
    p=get_person_by_name(c,name)
    if p:return p["id"]
    cur=c.execute("""INSERT INTO people(person_no,display_name,details,name_permanent,baseline_record,public)
                     VALUES(NULL,?,'Automated provisional research record',0,0,1)""",(name,))
    pid=cur.lastrowid
    ensure_identifier_policy(c,pid)
    audit(c,"web-auto","create","person",pid,"",name,reason,url)
    return pid

def add_provisional_relationship(c,subject_pid,other_pid,relation,confidence,url,title=""):
    # relation is from subject's perspective where possible.
    if relation in ("father","mother","parent"):
        child,parent=subject_pid,other_pid; rel="parent"
    elif relation=="spouse":
        child,parent=subject_pid,other_pid; rel="spouse"
    else:
        child,parent=subject_pid,other_pid; rel=relation
    old=c.execute("SELECT * FROM relationships WHERE child_id=? AND parent_id=? AND relation=?",(child,parent,rel)).fetchone()
    if old:return old["id"]
    cur=c.execute("""INSERT INTO relationships(child_id,parent_id,relation,confidence,notes,permanent,baseline_record,source_url)
                     VALUES(?,?,?,?,?,0,0,?)""",(child,parent,rel,confidence,f"Automated provisional extraction from {title}",url))
    audit(c,"web-auto","create","relationship",cur.lastrowid,"",f"{rel}:{child}->{parent}",
          f"confidence={confidence:.2f}",url)
    ensure_identifier_policy(c,other_pid)
    return cur.lastrowid

def extract_web_facts(pid,text,url,title):
    cfg=load_config()
    if not cfg.get("auto_extract",True):return {"facts":0,"people":0,"relationships":0,"reason":"auto_extract disabled"}
    c=db(); p=c.execute("SELECT * FROM people WHERE id=?",(pid,)).fetchone()
    if not p:c.close();return {"facts":0,"people":0,"relationships":0,"reason":"no context person"}
    normalized=re.sub(r"\s+"," ",text)
    name=p["display_name"]
    loc=normalized.casefold().find(name.casefold())
    if loc<0:
        # Store source association but don't infer facts when the target's name isn't on page.
        c.close();return {"facts":0,"people":0,"relationships":0,"reason":"context name not found on page"}
    context=normalized[max(0,loc-1200):min(len(normalized),loc+5000)]
    facts=rels=persons=0

    # Date facts near contextual keywords.
    for m in DATE_RE.finditer(context):
        before=context[max(0,m.start()-80):m.start()].casefold()
        field="date_mention"
        conf=.52
        if re.search(r"\b(born|birth|baptized|christened)\b",before):
            field="birth_date";conf=.78
        elif re.search(r"\b(died|death|buried|burial)\b",before):
            field="death_date";conf=.78
        elif re.search(r"\b(married|marriage|wed)\b",before):
            field="marriage_date";conf=.70
        if add_fact(c,pid,field,m.group(0),conf,url,title):facts+=1

    # Place-like phrases around explicit born/died wording.
    place_patterns=[
        ("birth_place",re.compile(r"\b(?:born|birth)\b.{0,45}?\b(?:in|at)\s+([A-Z][A-Za-z .,'’\-]{2,100})(?=[.;]|(?:\s+(?:on|and|to|who)\b))",re.I)),
        ("death_place",re.compile(r"\b(?:died|death)\b.{0,45}?\b(?:in|at)\s+([A-Z][A-Za-z .,'’\-]{2,100})(?=[.;]|(?:\s+(?:on|and|to|who)\b))",re.I)),
    ]
    for field,pat in place_patterns:
        for m in pat.finditer(context):
            val=m.group(1).strip(" ,")
            if 3<=len(val)<=100:
                if add_fact(c,pid,field,val,.74,url,title):facts+=1

    # Relationships. These are deliberately white/provisional.
    if cfg.get("auto_create_relatives",True):
        for kind,pat in REL_PATTERNS:
            for m in pat.finditer(context):
                names=list(m.groups())
                for raw in names:
                    nm=clean_candidate_name(raw)
                    if not nm or nm.casefold()==name.casefold():continue
                    other=find_or_create_provisional_person(c,nm,f"extracted as {kind} of {name}",url)
                    if other:
                        persons+=1
                        conf=.86 if kind in ("father","mother","parent") else .80
                        if conf>=float(cfg.get("relationship_threshold",.84)) or kind in ("father","mother","parent"):
                            add_provisional_relationship(c,pid,other,kind,conf,url,title);rels+=1

    c.commit();c.close()
    return {"facts":facts,"people":persons,"relationships":rels,"reason":"processed"}

# ------------------------- web capture / search -------------------------

def save_web_capture(pid,url,title,text):
    ensure_dirs()
    digest=hashlib.sha256(text.encode("utf-8","replace")).hexdigest()
    cache=CACHE_DIR/f"{digest}.txt"
    if not cache.exists():cache.write_text(text,encoding="utf-8")
    c=db()
    c.execute("""INSERT OR IGNORE INTO web_pages(person_id,url,title,text_sha256,cache_file)
                 VALUES(?,?,?,?,?)""",(pid,url,title,digest,str(cache)))
    c.commit();c.close()
    return digest

def duckduckgo_search(query,limit=10):
    """Best-effort public search. Does not bypass blocks or CAPTCHAs."""
    url="https://html.duckduckgo.com/html/?q="+urllib.parse.quote_plus(query)
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 TGFamilyTree/4.1"})
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read(2_000_000).decode("utf-8","replace")
    out=[]
    # DDG result anchors use class result__a.
    for m in re.finditer(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',raw,re.I|re.S):
        href=html.unescape(m.group(1)); title=re.sub("<[^>]+>","",m.group(2));title=html.unescape(title).strip()
        if href.startswith("//duckduckgo.com/l/?"):
            q=urllib.parse.parse_qs(urllib.parse.urlparse("https:"+href).query)
            href=q.get("uddg",[href])[0]
        out.append((title,href))
        if len(out)>=limit:break
    return out

def extract_odt_text(path):
    with zipfile.ZipFile(path) as z:root=ET.fromstring(z.read("content.xml"))
    out=[]
    for e in root.iter():
        if e.tag.endswith("}p") or e.tag.endswith("}h"):
            s="".join(e.itertext()).strip()
            if s:out.append(re.sub(r"\s+"," ",s))
    return out

def research_names_from_odt(path):
    lines=extract_odt_text(path)
    pat=re.compile(r"^\s*\d+\s*[\.\-–]?\s*[└^]?(.*?)\s*(?:\(|$)")
    names=[];seen=set()
    for line in lines:
        m=pat.match(line)
        if not m:continue
        n=clean_candidate_name(re.sub(r"[└^]"," ",m.group(1)))
        if n and n.casefold() not in seen:
            seen.add(n.casefold());names.append(n)
    return names

def run_background_research():
    if now_local()<RESEARCH_START:
        print(f"Research begins {RESEARCH_START}");return
    cfg=load_config(); path=Path(cfg.get("researcher_odt",str(RESEARCHER_ODT)))
    if not path.exists():raise FileNotFoundError(path)
    names=research_names_from_odt(path)[:60]
    c=db(); total=0
    for name in names:
        p=get_person_by_name(c,name)
        pid=p["id"] if p else None
        query=f'"{name}" genealogy'
        try:
            results=duckduckgo_search(query,7)
        except Exception as e:
            audit(c,"research-timer","search-error","person",pid,"","",str(e))
            continue
        for title,url in results:
            c.execute("""INSERT OR IGNORE INTO research_candidates(person_id,query,source_site,url,title,snippet,confidence,status)
                         VALUES(?,?, 'DuckDuckGo',?,?, '',0.30,'staged')""",(pid,query,url,title))
            total+=1
    c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('last_research_run',?)",(now_local().isoformat(),))
    c.commit();c.close()
    print(f"Staged {total} public research-result links.")

# ------------------------- publication proof -------------------------

def export_public():
    seed();ensure_dirs();c=db()
    people=[]
    for p in c.execute("SELECT * FROM people WHERE public=1 ORDER BY COALESCE(person_no,999999),display_name"):
        ids=[dict(x) for x in identifiers_for(c,p["id"])]
        facts=[dict(x) for x in c.execute("""SELECT field,value,confidence,source_url,source_title,status,permanent
                                            FROM facts WHERE person_id=? AND status='active' ORDER BY field,confidence DESC""",(p["id"],))]
        people.append({"person_no":p["person_no"],"display_name":p["display_name"],"details":p["details"],
                       "name_permanent":bool(p["name_permanent"]),
                       "identifiers":[{"code":x["code"],"kind":x["kind"],"permanent":bool(x["permanent"])} for x in ids],
                       "provisional_facts":facts})
    rel=[dict(x) for x in c.execute("""SELECT a.display_name child,b.display_name parent,r.relation,r.confidence,
             r.notes,r.permanent,r.source_url FROM relationships r JOIN people a ON a.id=r.child_id
             JOIN people b ON b.id=r.parent_id WHERE a.public=1 AND b.public=1""")]
    c.close()
    data={"generated_at":now_local().astimezone().isoformat(),"people":people,"relationships":rel}
    f=PUBLISH_DIR/"family_tree.json";f.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    src=sqlite3.connect(DB_PATH);dst=sqlite3.connect(PUBLISH_DIR/"family_tree.sqlite3");src.backup(dst);dst.close();src.close()
    return f

def create_proof_file():
    f=export_public();digest=hashlib.sha256(f.read_bytes()).hexdigest()
    content=("TG FAMILY TREE AUTOMATED PUBLISH PROOF\n"
             f"proof_id={PROOF_NAME[:-4]}\n"
             f"generated_by={Path(__file__).name}\n"
             f"generated_at={now_local().astimezone().isoformat()}\n"
             f"tree_sha256={digest}\n"
             f"nonce={secrets.token_hex(16)}\n")
    p=PUBLISH_DIR/PROOF_NAME;p.write_text(content);return p

def fetch_text(url,timeout=20):
    req=urllib.request.Request(url,headers={"User-Agent":"TGFamilyTree/4.1"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read(2_000_000).decode("utf-8","replace")

def verify_proof_online():
    cfg=load_config();local=PUBLISH_DIR/PROOF_NAME
    if not local.exists():return False,"Local proof does not exist."
    expected=local.read_text().strip()
    urls={"GitHub":cfg.get("github_proof_url","").strip(),"Hugging Face":cfg.get("hf_proof_url","").strip()}
    if not all(urls.values()):return False,"Both public proof URLs must be configured."
    lines=[];ok=True
    for n,u in urls.items():
        try:
            got=fetch_text(u).strip();same=(got==expected);ok &= same
            lines.append(f"{n}: {'VERIFIED' if same else 'CONTENT MISMATCH'}")
        except Exception as e:ok=False;lines.append(f"{n}: ERROR {e}")
    c=db()
    c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('proof_last_check',?)",(now_local().isoformat(),))
    if ok:c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('proof_verified_at',?)",(now_local().isoformat(),))
    c.commit();c.close()
    return ok,"\n".join(lines)

def ensure_publish_repo(cfg):
    """GitHub uses git; Hugging Face uses the official hf CLI."""
    if not (PUBLISH_DIR/".git").exists():
        run(["git","init","-b",cfg.get("branch","main")],cwd=PUBLISH_DIR)
        run(["git","config","user.name","TG Family Tree Publisher"],cwd=PUBLISH_DIR)
        run(["git","config","user.email","we6jbo@users.noreply.github.com"],cwd=PUBLISH_DIR)
    rem=set(run(["git","remote"],cwd=PUBLISH_DIR,check=False).split())
    u=cfg.get("github_remote","").strip()
    if u:
        if "github" in rem:run(["git","remote","set-url","github",u],cwd=PUBLISH_DIR)
        else:run(["git","remote","add","github",u],cwd=PUBLISH_DIR)

def upload_huggingface(cfg):
    hf_cli=Path(cfg.get("hf_cli","")).expanduser()
    repo_id=cfg.get("hf_repo_id","").strip()
    if not repo_id:
        raise RuntimeError("Hugging Face dataset repo ID is not configured.")
    if not hf_cli.exists():
        raise RuntimeError(f"Hugging Face CLI not found at {hf_cli}. Run the repository setup script.")
    return run([
        str(hf_cli),"upload",repo_id,str(PUBLISH_DIR),".",
        "--repo-type","dataset",
        "--commit-message",f"Automated TG Family Tree publish {dt.date.today().isoformat()}"
    ])

def daily_sync(force=False):
    seed();today=dt.date.today().isoformat();c=db()
    last=c.execute("SELECT value FROM state WHERE key='last_upload_date'").fetchone();c.close()
    if last and last["value"]==today and not force:
        print("Already verified today.");return
    cfg=load_config()
    if not cfg.get("github_remote"):
        raise RuntimeError("GitHub remote is not configured.")
    if not cfg.get("hf_repo_id"):
        raise RuntimeError("Hugging Face dataset repo ID is not configured.")
    create_proof_file();ensure_publish_repo(cfg)
    run(["git","add","-A"],cwd=PUBLISH_DIR)
    if run(["git","status","--porcelain"],cwd=PUBLISH_DIR):
        run(["git","commit","-m",f"Automated family-tree publish {today}"],cwd=PUBLISH_DIR)
    branch=cfg.get("branch","main")
    run(["git","push","github",f"HEAD:{branch}"],cwd=PUBLISH_DIR)
    upload_huggingface(cfg)
    ok=False;msg=""
    for delay in (0,5,15,30):
        if delay:time.sleep(delay)
        ok,msg=verify_proof_online()
        if ok:break
    c=db()
    c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('last_upload_verified',?)",("1" if ok else "0",))
    if ok:c.execute("INSERT OR REPLACE INTO state(key,value) VALUES('last_upload_date',?)",(today,))
    c.commit();c.close()
    print(msg)
    if not ok:raise RuntimeError("Push happened, but dual public verification failed.")

# ------------------------- systemd -------------------------

def install_timers():
    unit=Path.home()/".config/systemd/user";unit.mkdir(parents=True,exist_ok=True)
    script=Path(__file__).resolve()
    (unit/"tg-family-tree-sync.service").write_text(f"""[Unit]
Description=Publish and verify TG Family Tree
[Service]
Type=oneshot
ExecStart={sys.executable} {script} --daily-sync
""")
    (unit/"tg-family-tree-sync.timer").write_text("""[Unit]
Description=Daily verified TG Family Tree publisher
[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true
Unit=tg-family-tree-sync.service
[Install]
WantedBy=timers.target
""")
    (unit/"tg-family-tree-research.service").write_text(f"""[Unit]
Description=TG Family Tree background research
[Service]
Type=oneshot
ExecStart={sys.executable} {script} --research
""")
    (unit/"tg-family-tree-research.timer").write_text("""[Unit]
Description=Daily TG Family Tree research
[Timer]
OnCalendar=*-*-* 16:00:00
Persistent=true
Unit=tg-family-tree-research.service
[Install]
WantedBy=timers.target
""")
    run(["systemctl","--user","daemon-reload"])
    run(["systemctl","--user","enable","--now","tg-family-tree-sync.timer","tg-family-tree-research.timer"])
    return run(["systemctl","--user","list-timers","tg-family-tree-*","--no-pager"],check=False)

# ------------------------- GUI -------------------------

class WorkerSignals(QObject):
    done=pyqtSignal(object)
    error=pyqtSignal(str)

def async_call(fn,done=None,error=None):
    sig=WorkerSignals()
    if done:sig.done.connect(done)
    if error:sig.error.connect(error)
    def runit():
        try:sig.done.emit(fn())
        except Exception as e:sig.error.emit(str(e))
    threading.Thread(target=runit,daemon=True).start()
    return sig

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__();seed()
        self.setWindowTitle("TG Family Tree v4.1")
        self.resize(1350,880)
        self.context_pid=None
        self.context_name=""
        self.context_code=""
        self.worker_refs=[]
        self.tabs=QTabWidget();self.setCentralWidget(self.tabs)
        self.build_tree_tab()
        self.build_browser_tab()
        self.build_facts_tab()
        self.build_research_tab()
        self.build_audit_tab()
        self.build_publish_tab()
        self.build_countdown_tab()
        self.refresh_tree()
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000);self.tick()

    def blue_font(self):
        f=QFont();f.setBold(True);return f

    # ----- Tree
    def build_tree_tab(self):
        w=QWidget();lay=QVBoxLayout(w)
        info=QLabel("Blue name + blue code = permanent forever. White/default = provisional or mutable.")
        lay.addWidget(info)
        self.tree=QTreeWidget();self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Person","Permanent ID(s)","Provisional ID(s)","Details / provisional facts","Status"])
        self.tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self.tree_selected)
        lay.addWidget(self.tree)
        row=QHBoxLayout()
        b=QPushButton("Refresh");b.clicked.connect(self.refresh_tree);row.addWidget(b)
        self.remove_btn=QPushButton("Remove selected NON-PERMANENT person");self.remove_btn.clicked.connect(self.remove_selected);row.addWidget(self.remove_btn)
        row.addStretch();lay.addLayout(row)
        self.tabs.addTab(w,"Family Tree")

    def refresh_tree(self):
        self.tree.clear();c=db()
        people={r["id"]:dict(r) for r in c.execute("SELECT * FROM people")}
        pars={}
        for r in c.execute("SELECT child_id,parent_id FROM relationships WHERE relation='parent'"):
            pars.setdefault(r["child_id"],[]).append(r["parent_id"])
        seen=set()
        def make(pid,parent=None):
            if pid in seen:return
            seen.add(pid);p=people[pid];ids=identifiers_for(c,pid)
            facts=list(c.execute("""SELECT field,value,confidence FROM facts WHERE person_id=? AND status='active'
                                   ORDER BY confidence DESC LIMIT 5""",(pid,)))
            detail=p["details"]
            if facts:
                detail+=((" | " if detail else "")+"; ".join(f"{x['field']}={x['value']} ({x['confidence']:.2f})" for x in facts))
            permanent_codes="  ".join(x["code"] for x in ids if x["permanent"])
            provisional_codes="  ".join(x["code"] for x in ids if not x["permanent"])
            status="BLUE/PERMANENT" if p["name_permanent"] else ("BASELINE FROZEN" if p["baseline_record"] and baseline_locked() else "WHITE/PROVISIONAL")
            item=QTreeWidgetItem([p["display_name"],permanent_codes,provisional_codes,detail,status])
            item.setData(0,Qt.ItemDataRole.UserRole,pid)
            # ONLY the permanent name and permanent identifier column are blue.
            if p["name_permanent"]:
                item.setForeground(0,QColor(BLUE));item.setFont(0,self.blue_font())
            if permanent_codes:
                item.setForeground(1,QColor(BLUE));item.setFont(1,self.blue_font())
            if parent:parent.addChild(item)
            else:self.tree.addTopLevelItem(item)
            for par in pars.get(pid,[]):make(par,item)
        r=get_person_by_no(c,1)
        if r:make(r["id"])
        for pid in people:
            if pid not in seen:make(pid)
        c.close()
        self.tree.expandToDepth(2)

    def tree_selected(self):
        items=self.tree.selectedItems()
        if not items:return
        pid=items[0].data(0,Qt.ItemDataRole.UserRole)
        c=db();p=c.execute("SELECT * FROM people WHERE id=?",(pid,)).fetchone()
        if p:
            self.context_pid=pid;self.context_name=p["display_name"];self.context_code=primary_code(c,pid)
            self.browser_context.setText(f"Research context: {self.context_name}   {self.context_code}")
            self.fact_context.setText(f"{self.context_name}   {self.context_code}")
            self.refresh_facts()
        c.close()

    def remove_selected(self):
        if not self.context_pid:return
        c=db();p=c.execute("SELECT * FROM people WHERE id=?",(self.context_pid,)).fetchone()
        ids=identifiers_for(c,self.context_pid)
        if p["name_permanent"] or any(x["permanent"] for x in ids):
            c.close();QMessageBox.critical(self,"Permanent","Blue permanent people/codes can never be removed.");return
        if p["baseline_record"] and baseline_locked():
            c.close();QMessageBox.warning(self,"Frozen",f"Baseline remains frozen until {BASELINE_UNLOCK}.");return
        if QMessageBox.question(self,"Remove",f"Remove provisional person {p['display_name']}?")!=QMessageBox.StandardButton.Yes:
            c.close();return
        audit(c,"user","delete","person",p["id"],p["display_name"],"","manual provisional removal")
        c.execute("DELETE FROM people WHERE id=?",(p["id"],));c.commit();c.close()
        self.context_pid=None;self.refresh_tree()

    # ----- Browser
    def build_browser_tab(self):
        w=QWidget();outer=QVBoxLayout(w)
        self.browser_context=QLabel("Research context: select a person in Family Tree first.")
        self.browser_context.setStyleSheet("font-weight:600")
        outer.addWidget(self.browser_context)
        nav=QHBoxLayout()
        self.back=QPushButton("←");self.forward=QPushButton("→");self.reload=QPushButton("Reload")
        self.url=QLineEdit();self.url.setPlaceholderText("URL or search terms")
        go=QPushButton("Go / Search")
        for x in (self.back,self.forward,self.reload):nav.addWidget(x)
        nav.addWidget(self.url,1);nav.addWidget(go);outer.addLayout(nav)
        quick=QHBoxLayout()
        for name,url in GENEALOGY_SITES[:8]:
            b=QPushButton(name);b.clicked.connect(lambda checked=False,n=name,u=url:self.search_site(n,u));quick.addWidget(b)
        outer.addLayout(quick)
        split=QSplitter(Qt.Orientation.Horizontal)
        self.web=QWebEngineView()
        side=QWidget();sl=QVBoxLayout(side)
        sl.addWidget(QLabel("Automatic page analysis"))
        self.web_status=QPlainTextEdit();self.web_status.setReadOnly(True)
        sl.addWidget(self.web_status,1)
        save=QPushButton("Analyze current page now");save.clicked.connect(self.analyze_current_page);sl.addWidget(save)
        split.addWidget(self.web);split.addWidget(side);split.setSizes([1000,300])
        outer.addWidget(split,1)
        self.back.clicked.connect(self.web.back);self.forward.clicked.connect(self.web.forward);self.reload.clicked.connect(self.web.reload)
        go.clicked.connect(self.navigate)
        self.web.urlChanged.connect(lambda u:self.url.setText(u.toString()))
        self.web.loadFinished.connect(self.page_loaded)
        self.tabs.addTab(w,"Web Browser")

    def navigate(self):
        s=self.url.text().strip()
        if not s:return
        if re.match(r"^https?://",s,re.I):self.web.setUrl(QUrl(s))
        else:
            q=s
            if self.context_name and self.context_name.casefold() not in q.casefold():q=f'"{self.context_name}" {q}'
            self.web.setUrl(QUrl("https://www.google.com/search?q="+urllib.parse.quote_plus(q)))

    def search_site(self,name,base):
        if not self.context_name:
            QMessageBox.information(self,"Select person","Select a person in Family Tree first.");return
        q=urllib.parse.quote_plus(self.context_name)
        if name=="FamilySearch":u=f"https://www.familysearch.org/search/record/results?q.givenName={q}"
        elif name=="Ancestry":u=f"https://www.ancestry.com/search/?name={q}"
        elif name=="Find a Grave":u=f"https://www.findagrave.com/memorial/search?lastname={q}"
        elif name=="WikiTree":u=f"https://www.wikitree.com/index.php?title=Special:SearchPerson&wpSearch={q}"
        else:u=base
        self.web.setUrl(QUrl(u))

    def page_loaded(self,ok):
        if not ok:return
        self.analyze_current_page()

    def analyze_current_page(self):
        if not self.context_pid:
            self.web_status.setPlainText("Select a Family Tree person before analyzing.")
            return
        pid=self.context_pid;url=self.web.url().toString();title=self.web.title()
        def got_text(text):
            if not text:return
            save_web_capture(pid,url,title,text)
            result=extract_web_facts(pid,text,url,title)
            self.web_status.setPlainText(
                f"Captured: {title}\n{url}\n\n"
                f"Facts created/seen: {result['facts']}\n"
                f"Candidate people: {result['people']}\n"
                f"Relationships: {result['relationships']}\n"
                f"Result: {result['reason']}"
            )
            self.refresh_tree();self.refresh_facts()
        self.web.page().toPlainText(got_text)

    # ----- Facts
    def build_facts_tab(self):
        w=QWidget();lay=QVBoxLayout(w)
        self.fact_context=QLabel("Select a person.");lay.addWidget(self.fact_context)
        self.facts=QTableWidget(0,7);self.facts.setHorizontalHeaderLabels(["Field","Value","Confidence","Source","Status","Permanent","ID"])
        self.facts.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.facts)
        row=QHBoxLayout()
        sup=QPushButton("Supersede selected WHITE fact");sup.clicked.connect(self.supersede_fact);row.addWidget(sup)
        rej=QPushButton("Reject selected WHITE fact");rej.clicked.connect(self.reject_fact);row.addWidget(rej)
        row.addStretch();lay.addLayout(row)
        self.tabs.addTab(w,"Provisional Facts")

    def refresh_facts(self):
        self.facts.setRowCount(0)
        if not self.context_pid:return
        c=db()
        rows=list(c.execute("""SELECT * FROM facts WHERE person_id=? ORDER BY status='active' DESC,confidence DESC,last_seen DESC""",(self.context_pid,)))
        for r in rows:
            i=self.facts.rowCount();self.facts.insertRow(i)
            vals=[r["field"],r["value"],f"{r['confidence']:.2f}",r["source_title"] or r["source_url"],r["status"],str(bool(r["permanent"])),str(r["id"])]
            for j,v in enumerate(vals):self.facts.setItem(i,j,QTableWidgetItem(v))
        c.close()

    def selected_fact_id(self):
        r=self.facts.currentRow()
        if r<0:return None
        try:return int(self.facts.item(r,6).text())
        except:return None

    def fact_change(self,status):
        fid=self.selected_fact_id()
        if not fid:return
        c=db();f=c.execute("SELECT * FROM facts WHERE id=?",(fid,)).fetchone()
        if not f:c.close();return
        if f["permanent"]:
            c.close();QMessageBox.critical(self,"Permanent","Permanent fact cannot change.");return
        p=c.execute("SELECT * FROM people WHERE id=?",(f["person_id"],)).fetchone()
        if f["baseline_record"] and baseline_locked():
            c.close();QMessageBox.warning(self,"Frozen",f"Baseline fact frozen until {BASELINE_UNLOCK}.");return
        old=f["status"];c.execute("UPDATE facts SET status=? WHERE id=?",(status,fid))
        audit(c,"user","update","fact",fid,old,status,"manual fact disposition",f["source_url"])
        c.commit();c.close();self.refresh_facts();self.refresh_tree()
    def supersede_fact(self):self.fact_change("superseded")
    def reject_fact(self):self.fact_change("rejected")

    # ----- Research queue
    def build_research_tab(self):
        w=QWidget();lay=QVBoxLayout(w)
        top=QHBoxLayout()
        runb=QPushButton("Run automated research now");runb.clicked.connect(self.run_research_now);top.addWidget(runb)
        inst=QPushButton("Install/refresh 6AM + 4PM timers");inst.clicked.connect(self.install_timer_gui);top.addWidget(inst)
        top.addStretch();lay.addLayout(top)
        self.research_table=QTableWidget(0,5);self.research_table.setHorizontalHeaderLabels(["Person","Query","Site","Title","URL"])
        self.research_table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
        self.research_table.cellDoubleClicked.connect(self.open_research_result)
        lay.addWidget(self.research_table)
        self.tabs.addTab(w,"Research Queue")
        self.refresh_research()

    def refresh_research(self):
        c=db();rows=list(c.execute("""SELECT rc.*,p.display_name FROM research_candidates rc
                                     LEFT JOIN people p ON p.id=rc.person_id ORDER BY rc.collected_at DESC LIMIT 500"""))
        self.research_table.setRowCount(0)
        for r in rows:
            i=self.research_table.rowCount();self.research_table.insertRow(i)
            for j,v in enumerate([r["display_name"] or "",r["query"],r["source_site"],r["title"],r["url"]]):
                self.research_table.setItem(i,j,QTableWidgetItem(v))
        c.close()

    def run_research_now(self):
        sig=async_call(run_background_research,lambda _:self.refresh_research(),lambda e:QMessageBox.warning(self,"Research",e))
        self.worker_refs.append(sig)

    def install_timer_gui(self):
        sig=async_call(install_timers,lambda x:QMessageBox.information(self,"Timers",str(x)),lambda e:QMessageBox.warning(self,"Timers",e))
        self.worker_refs.append(sig)

    def open_research_result(self,row,col):
        url=self.research_table.item(row,4).text()
        person=self.research_table.item(row,0).text()
        if person:
            c=db();p=get_person_by_name(c,person)
            if p:
                self.context_pid=p["id"];self.context_name=p["display_name"];self.context_code=primary_code(c,p["id"])
                self.browser_context.setText(f"Research context: {self.context_name}   {self.context_code}")
            c.close()
        self.web.setUrl(QUrl(url));self.tabs.setCurrentIndex(self.tabs.indexOf(self.web.parentWidget()) if False else 1)

    # ----- Audit
    def build_audit_tab(self):
        w=QWidget();lay=QVBoxLayout(w)
        b=QPushButton("Refresh audit");b.clicked.connect(self.refresh_audit);lay.addWidget(b)
        self.audit_box=QPlainTextEdit();self.audit_box.setReadOnly(True);lay.addWidget(self.audit_box)
        self.tabs.addTab(w,"Audit History");self.refresh_audit()

    def refresh_audit(self):
        c=db();rows=list(c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1000"));c.close()
        self.audit_box.setPlainText("\n\n".join(
            f"#{r['id']} {r['event_time']} [{r['actor']}] {r['action']} {r['entity_type']}:{r['entity_id']}\n"
            f"OLD: {r['old_value']}\nNEW: {r['new_value']}\nWHY: {r['reason']}\nSOURCE: {r['source_url']}"
            for r in rows
        ))

    # ----- Publishing
    def build_publish_tab(self):
        w=QWidget();lay=QFormLayout(w);cfg=load_config();self.pub={}
        fields=[("GitHub git remote","github_remote"),
                ("Hugging Face dataset repo ID","hf_repo_id"),
                ("GitHub public 761327132.txt URL","github_proof_url"),
                ("HF public 761327132.txt URL","hf_proof_url")]
        for label,key in fields:
            e=QLineEdit(cfg.get(key,""));self.pub[key]=e;lay.addRow(label,e)
        save=QPushButton("Save settings");save.clicked.connect(self.save_pub);lay.addRow(save)
        push=QPushButton("RUN PYTHON UPLOAD + DUAL ONLINE VERIFICATION NOW");push.clicked.connect(self.push_now);lay.addRow(push)
        verify=QPushButton("Verify public proof only");verify.clicked.connect(self.verify_now);lay.addRow(verify)
        self.pub_status=QPlainTextEdit();self.pub_status.setReadOnly(True);lay.addRow(self.pub_status)
        self.tabs.addTab(w,"Publishing")

    def save_pub(self):
        cfg=load_config()
        for k,e in self.pub.items():cfg[k]=e.text().strip()
        save_config(cfg);self.pub_status.appendPlainText("Saved.")
    def push_now(self):
        self.save_pub()
        sig=async_call(lambda:daily_sync(True),
                       lambda _:self.pub_status.appendPlainText("SUCCESS: upload + both online verifications."),
                       lambda e:self.pub_status.appendPlainText("FAILED: "+e))
        self.worker_refs.append(sig)
    def verify_now(self):
        self.save_pub()
        sig=async_call(verify_proof_online,
                       lambda x:self.pub_status.appendPlainText(x[1]),
                       lambda e:self.pub_status.appendPlainText("ERROR: "+e))
        self.worker_refs.append(sig)

    # ----- Countdown
    def build_countdown_tab(self):
        w=QWidget();lay=QVBoxLayout(w)
        h=QLabel("Automated publishing proof countdown");h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.setStyleSheet("font-size:22px;font-weight:bold");lay.addWidget(h)
        self.count=QLabel("");self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count.setStyleSheet("font-family:monospace;font-size:38px;font-weight:bold");lay.addWidget(self.count)
        self.count_status=QLabel("Stops early only after GitHub + Hugging Face public proof both verify.")
        self.count_status.setAlignment(Qt.AlignmentFlag.AlignCenter);lay.addWidget(self.count_status)
        lay.addStretch();self.tabs.addTab(w,"Countdown")

    def tick(self):
        c=db();v=c.execute("SELECT value FROM state WHERE key='proof_verified_at'").fetchone();c.close()
        if v:
            self.count.setText("VERIFIED ✓");self.count_status.setText(f"Stopped: both public copies verified at {v['value']}.");return
        rem=max(dt.timedelta(0),COUNTDOWN_DEADLINE-now_local());s=int(rem.total_seconds())
        self.count.setText(f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}")
        if s==0:self.count_status.setText("Deadline reached without a recorded dual public verification.")

def resolve_text(text):
    seed();c=db();q=text.casefold();out=[]
    for r in c.execute("""SELECT p.id,p.display_name,i.code,i.permanent FROM people p JOIN identifiers i ON i.person_id=p.id"""):
        score=0
        if r["code"].casefold() in q or r["display_name"].casefold() in q:score=1
        else:
            ratio=difflib.SequenceMatcher(None,r["display_name"].casefold(),q).ratio()
            if ratio>=.60:score=min(.89,ratio)
        if score:out.append({"person":r["display_name"],"code":r["code"],"permanent":bool(r["permanent"]),"confidence":score})
    c.close();return sorted(out,key=lambda x:x["confidence"],reverse=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--daily-sync",action="store_true")
    ap.add_argument("--force-sync",action="store_true")
    ap.add_argument("--verify-proof",action="store_true")
    ap.add_argument("--research",action="store_true")
    ap.add_argument("--install-timers",action="store_true")
    ap.add_argument("--resolve")
    args=ap.parse_args();seed()
    if args.daily_sync or args.force_sync:daily_sync(args.force_sync);return
    if args.verify_proof:
        ok,msg=verify_proof_online();print(msg);raise SystemExit(0 if ok else 1)
    if args.research:run_background_research();return
    if args.install_timers:print(install_timers());return
    if args.resolve is not None:print(json.dumps(resolve_text(args.resolve),indent=2));return
    app=QApplication(sys.argv);win=MainWindow();win.show();raise SystemExit(app.exec())

if __name__=="__main__":
    main()
