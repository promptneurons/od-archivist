#!/usr/bin/env python3
"""
get-user.py - Fetch user activity as markdown (RSS-style thread list)

Usage: python get-user.py <userid> [--post-to-hastebin]
       python get-user.py --name "il ragno" [--post-to-hastebin]
"""

import sqlite3
import sys
import json
from datetime import datetime
import urllib.request
import urllib.parse

DB_PATH = "/home/john/od-2006/posts_markdown.db"
HASTEBIN_URL = "http://45.79.58.143:7777"

def get_user_by_name(username):
    """Look up userid by username"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT userid, username FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    return result

def get_user_markdown(userid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get user info
    c.execute('SELECT userid, username FROM users WHERE userid = ?', (userid,))
    user = c.fetchone()
    if not user:
        return None, f"User {userid} not found"
    
    userid, username = user
    
    # Get threads started
    c.execute('''
        SELECT uts.threadid, tfp.title, tfp.dateline,
               (SELECT COUNT(*) FROM posts WHERE threadid = uts.threadid) as post_count
        FROM user_threads_started uts
        JOIN thread_first_post tfp ON uts.threadid = tfp.threadid
        WHERE uts.userid = ?
        ORDER BY tfp.dateline DESC
    ''', (userid,))
    started = c.fetchall()
    
    # Get threads commented (but not started)
    c.execute('''
        SELECT utc.threadid, tfp.title, tfp.dateline,
               (SELECT COUNT(*) FROM posts WHERE threadid = utc.threadid AND userid = ?) as user_posts
        FROM user_threads_commented utc
        JOIN thread_first_post tfp ON utc.threadid = tfp.threadid
        WHERE utc.userid = ?
        ORDER BY tfp.dateline DESC
    ''', (userid, userid))
    commented = c.fetchall()
    
    # Total post count
    c.execute('SELECT COUNT(*) FROM posts WHERE userid = ?', (userid,))
    total_posts = c.fetchone()[0]
    
    conn.close()
    
    # Build markdown
    md = f"# {username}\n\n"
    md += f"**User ID:** {userid} | **Total Posts:** {total_posts:,}\n\n"
    md += f"**Threads Started:** {len(started)} | **Threads Commented:** {len(commented)}\n\n"
    md += "---\n\n"
    
    if started:
        md += "## Threads Started\n\n"
        md += "| Date | Title | Posts |\n"
        md += "|------|-------|-------|\n"
        for threadid, title, dateline, post_count in started[:100]:  # Limit to 100
            dt = datetime.fromtimestamp(dateline).strftime('%Y-%m-%d')
            safe_title = (title or f"Thread {threadid}")[:60]
            md += f"| {dt} | [{safe_title}](/od/thread/{threadid}) | {post_count} |\n"
        if len(started) > 100:
            md += f"\n*...and {len(started) - 100} more threads*\n"
        md += "\n"
    
    if commented:
        md += "## Threads Commented\n\n"
        md += "| Date | Title | User Posts |\n"
        md += "|------|-------|------------|\n"
        for threadid, title, dateline, user_posts in commented[:100]:
            dt = datetime.fromtimestamp(dateline).strftime('%Y-%m-%d')
            safe_title = (title or f"Thread {threadid}")[:60]
            md += f"| {dt} | [{safe_title}](/od/thread/{threadid}) | {user_posts} |\n"
        if len(commented) > 100:
            md += f"\n*...and {len(commented) - 100} more threads*\n"
    
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
        print("Usage: python get-user.py <userid> [--post-to-hastebin]", file=sys.stderr)
        print("       python get-user.py --name \"il ragno\" [--post-to-hastebin]", file=sys.stderr)
        sys.exit(1)
    
    post_to_haste = '--post-to-hastebin' in sys.argv
    
    # Handle --name lookup
    if '--name' in sys.argv:
        name_idx = sys.argv.index('--name')
        if name_idx + 1 >= len(sys.argv):
            print("Error: --name requires a username", file=sys.stderr)
            sys.exit(1)
        username = sys.argv[name_idx + 1]
        result = get_user_by_name(username)
        if not result:
            print(f"Error: User '{username}' not found", file=sys.stderr)
            sys.exit(1)
        userid = result[0]
    else:
        userid = int(sys.argv[1])
    
    md, err = get_user_markdown(userid)
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
