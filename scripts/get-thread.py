#!/usr/bin/env python3
"""
get-thread.py - Fetch thread posts as markdown

Usage: python get-thread.py <threadid> [--post-to-hastebin]
"""

import sqlite3
import sys
import json
from datetime import datetime
import urllib.request

DB_PATH = "/home/john/od-2006/posts_markdown.db"
HASTEBIN_URL = "http://45.79.58.143:7777"

def get_thread_markdown(threadid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get thread first post for title and OP detection
    c.execute('''
        SELECT postid, title, username, dateline 
        FROM thread_first_post 
        WHERE threadid = ?
    ''', (threadid,))
    first = c.fetchone()
    
    if not first:
        return None, f"Thread {threadid} not found"
    
    op_postid, thread_title, op_username, op_dateline = first
    thread_title = thread_title or f"Thread {threadid}"
    
    # Get all posts
    c.execute('''
        SELECT postid, username, userid, dateline, title, pagetext
        FROM posts
        WHERE threadid = ?
        ORDER BY dateline ASC
    ''', (threadid,))
    posts = c.fetchall()
    
    # Build markdown
    md = f"# {thread_title}\n\n"
    md += f"**Thread ID:** {threadid} | **Posts:** {len(posts)} | **Started:** {datetime.fromtimestamp(op_dateline).strftime('%Y-%m-%d')}\n\n"
    md += f"[Wayback Archive](https://web.archive.org/web/2006/http://www.originaldissent.com/forums/showthread.php?t={threadid})\n\n"
    md += "---\n\n"
    
    for postid, username, userid, dateline, title, pagetext in posts:
        dt = datetime.fromtimestamp(dateline).strftime('%Y-%m-%d %H:%M')
        role = " **[OP]**" if postid == op_postid else ""
        
        md += f"### {username}{role}\n"
        md += f"*{dt}* | [User Profile](/od/user/{userid})\n\n"
        
        # Clean up pagetext (basic BBCode artifacts)
        text = pagetext or "(no content)"
        text = text.replace("[quote]", "> ").replace("[/quote]", "\n")
        text = text.replace("[b]", "**").replace("[/b]", "**")
        text = text.replace("[i]", "*").replace("[/i]", "*")
        
        md += f"{text}\n\n"
        md += "---\n\n"
    
    conn.close()
    return md, None

def post_to_hastebin(content):
    """Post markdown to hastebin, return key"""
    req = urllib.request.Request(
        f"{HASTEBIN_URL}/documents",
        data=content.encode('utf-8'),
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get('key'), None
    except Exception as e:
        return None, str(e)

def main():
    if len(sys.argv) < 2:
        print("Usage: python get-thread.py <threadid> [--post-to-hastebin]", file=sys.stderr)
        sys.exit(1)
    
    threadid = int(sys.argv[1])
    post_to_haste = '--post-to-hastebin' in sys.argv
    
    md, err = get_thread_markdown(threadid)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    
    if post_to_haste:
        key, err = post_to_hastebin(md)
        if err:
            print(f"Hastebin error: {err}", file=sys.stderr)
            sys.exit(1)
        viewer_url = f"http://45.79.58.143:9002/view?url={HASTEBIN_URL}/raw/{key}&format=md"
        print(json.dumps({
            "hastebin_key": key,
            "raw_url": f"{HASTEBIN_URL}/raw/{key}",
            "viewer_url": viewer_url
        }))
    else:
        print(md)

if __name__ == "__main__":
    main()
