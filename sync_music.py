import sqlite3
import os
import re
import subprocess

TARGET_DIR = "/Users/weiyo/.gemini/antigravity/scratch/retro_dashboard/music"
os.makedirs(TARGET_DIR, exist_ok=True)

with open("/tmp/iphone_music_files.txt") as f:
    remote_paths = [line.strip() for line in f if line.strip()]

path_map = {}
for p in remote_paths:
    fname = os.path.basename(p)
    path_map[fname] = p

conn = sqlite3.connect("/tmp/MediaLibrary.sqlitedb")
cur = conn.cursor()
songs = []
for row in cur.execute("SELECT title, location, file_size FROM item_extra WHERE location != ''"):
    title = row[0]
    loc = os.path.basename(row[1])
    size = row[2]
    remote_p = path_map.get(loc)
    if remote_p:
        clean = re.sub(r"[\/\\:\*\?\"<>\|]", "_", title).strip()
        clean = re.sub(r"\s*-\s*.*\(youtube\)", "", clean)
        clean = re.sub(r"\s*\(Official Video\).*", "", clean)
        clean = clean.strip()
        if len(clean) > 60:
            clean = clean[:60].strip()
        ext = os.path.splitext(loc)[1]
        target_name = f"{clean}{ext}"
        songs.append((remote_p, target_name, size, title))

# Sort by size ascending
songs.sort(key=lambda x: x[2])

print(f"Total songs to sync: {len(songs)}")

askpass_path = "/tmp/askpass.sh"
with open(askpass_path, "w") as f:
    f.write("#!/bin/sh\necho 'alpine'\n")
os.chmod(askpass_path, 0o755)

env = os.environ.copy()
env["SSH_ASKPASS_REQUIRE"] = "force"
env["SSH_ASKPASS"] = askpass_path

for idx, (remote_p, target_name, size, orig_title) in enumerate(songs):
    dest = os.path.join(TARGET_DIR, target_name)
    if os.path.exists(dest) and os.path.getsize(dest) == size:
        print(f"[{idx+1}/{len(songs)}] Already synced: {target_name}")
        continue

    print(f"[{idx+1}/{len(songs)}] Syncing ({size//1024//1024}MB): {target_name}...")
    cmd = [
        "scp", "-O",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "HostKeyAlgorithms=+ssh-rsa",
        "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa",
        f"root@192.168.0.127:{remote_p}",
        dest
    ]
    res = subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if res.returncode == 0:
        print(f" -> OK: {target_name}")
    else:
        print(f" -> Error: {res.stderr.decode()}")

print("Sync completed!")
