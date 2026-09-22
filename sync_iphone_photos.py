#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iPhone 4s 全自動無線相片同步工具 (Sync iPhone 4s to 192.168.0.115 / disk1s2)
全自動連線 iPhone 4s，將相簿中所有照片與影片無感備份至 Mac mini 網路磁碟。
"""

import os
import sys
import time
import subprocess
import shutil
from datetime import datetime
from PIL import Image

IPHONE_DEFAULT_IP = "192.168.0.104"
SMB_TARGET_HOST = "192.168.0.115"
SMB_SHARE_NAME = "disk1s2"
SMB_MOUNT_POINT = "/Volumes/disk1s2"
PHOTO_DEST_DIR = os.path.join(SMB_MOUNT_POINT, "iPhone4s_Photos")
SSH_KEY_PATH = "/Users/weiyo/.ssh/id_rsa_iphone"

def ensure_smb_mounted():
    """確保 192.168.0.115/disk1s2 已掛載"""
    if os.path.ismount(SMB_MOUNT_POINT) or os.path.exists(SMB_MOUNT_POINT):
        try:
            os.makedirs(PHOTO_DEST_DIR, exist_ok=True)
            return True, PHOTO_DEST_DIR
        except Exception:
            pass

    try:
        cmd = ["osascript", "-e", f'mount volume "smb://user@{SMB_TARGET_HOST}/{SMB_SHARE_NAME}"']
        subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if os.path.exists(SMB_MOUNT_POINT):
            os.makedirs(PHOTO_DEST_DIR, exist_ok=True)
            return True, PHOTO_DEST_DIR
    except Exception as e:
        print(f"[SMB Mount Err] {e}")

    fallback = os.path.expanduser("~/iPhone4s_Photos")
    os.makedirs(fallback, exist_ok=True)
    return False, fallback

def find_iphone_ip():
    """檢測 iPhone 4s 目前在區網中的 IP"""
    res = subprocess.run(["ping", "-c", "1", "-W", "500", IPHONE_DEFAULT_IP], capture_output=True)
    if res.returncode == 0:
        return IPHONE_DEFAULT_IP

    arp_res = subprocess.run(["arp", "-a"], capture_output=True, text=True)
    for line in arp_res.stdout.splitlines():
        if "weiyotekiiphone" in line.lower() or "iphone" in line.lower():
            parts = line.split("(")
            if len(parts) > 1:
                ip = parts[1].split(")")[0]
                return ip
    return IPHONE_DEFAULT_IP

def sync_all(progress_callback=None):
    """執行全自動相片同步"""
    mounted, dest_dir = ensure_smb_mounted()
    thumbs_dir = os.path.join(dest_dir, ".thumbs")
    os.makedirs(dest_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)

    ip = find_iphone_ip()
    ssh_opts = [
        "-i", SSH_KEY_PATH,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "HostKeyAlgorithms=+ssh-rsa",
        "-o", "PubkeyAcceptedKeyTypes=+ssh-rsa",
        "-o", "ConnectTimeout=5"
    ]

    # 喚醒 iPhone 4s Wi-Fi 省電睡眠並重試連線 (iOS 6 鎖定時會進入 DTIM 低功耗)
    cmd = ["ssh"] + ssh_opts + [f"root@{ip}", "ls -l /private/var/mobile/Media/DCIM/*/*"]
    res = None
    for attempt in range(3):
        subprocess.run(["ping", "-c", "2", "-W", "800", ip], capture_output=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            break
        time.sleep(1)

    if not res or res.returncode != 0:
        err_msg = f"無法連線至 iPhone ({ip})，請點亮螢幕確保 Wi-Fi 連線: {res.stderr if res else ''}"
        print(f"[SYNC ERR] {err_msg}")
        return {"success": False, "error": err_msg}

    remote_items = []
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 9 and parts[0].startswith("-"):
            try:
                size_bytes = int(parts[4])
                full_path = parts[-1]
                fname = os.path.basename(full_path)
                if not fname.startswith("."):
                    remote_items.append((fname, full_path, size_bytes))
            except Exception:
                pass

    total_files = len(remote_items)
    print(f"[*] 找到 iPhone 4s ({ip}) 相簿內共有 {total_files} 個照片/影片")

    synced_count = 0
    skipped_count = 0
    synced_files = []

    for idx, (fname, rpath, rsize) in enumerate(remote_items):
        target_path = os.path.join(dest_dir, fname)

        if os.path.exists(target_path) and os.path.getsize(target_path) == rsize:
            skipped_count += 1
            if progress_callback:
                progress_callback(idx + 1, total_files, fname, "skipped")
            continue

        print(f"[{idx+1}/{total_files}] 下載中: {fname} ({round(rsize/1024/1024, 2)} MB)...", end="", flush=True)
        if progress_callback:
            progress_callback(idx + 1, total_files, fname, "downloading")

        scp_cmd = ["scp"] + ssh_opts + [f"root@{ip}:{rpath}", target_path]
        scp_res = subprocess.run(scp_cmd, capture_output=True, text=True)

        if scp_res.returncode == 0:
            synced_count += 1
            sz_mb = round(os.path.getsize(target_path) / (1024 * 1024), 2)
            print(f" 完成 ({sz_mb} MB)")
            synced_files.append({"name": fname, "size_mb": sz_mb})

            # 生成縮圖
            if fname.lower().endswith((".jpg", ".jpeg", ".png")):
                try:
                    with Image.open(target_path) as im:
                        if im.mode in ("RGBA", "P", "LA"):
                            im = im.convert("RGB")
                        im.thumbnail((200, 200))
                        im.save(os.path.join(thumbs_dir, fname), "JPEG", quality=80)
                except Exception as te:
                    print(f"  [Thumb Err] {te}")
        else:
            print(f" 失敗: {scp_res.stderr}")

    # 補全缺失的縮圖
    for fname, _, _ in remote_items:
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            src_file = os.path.join(dest_dir, fname)
            thumb_file = os.path.join(thumbs_dir, fname)
            if os.path.exists(src_file) and not os.path.exists(thumb_file):
                try:
                    with Image.open(src_file) as im:
                        if im.mode in ("RGBA", "P", "LA"):
                            im = im.convert("RGB")
                        im.thumbnail((200, 200))
                        im.save(thumb_file, "JPEG", quality=80)
                except Exception:
                    pass

    summary = {
        "success": True,
        "total": total_files,
        "synced": synced_count,
        "skipped": skipped_count,
        "dest_dir": dest_dir,
        "mounted": mounted,
        "target_host": SMB_TARGET_HOST,
        "files": synced_files
    }
    print(f"[+] 同步完成！新下載: {synced_count} 張, 已存在跳過: {skipped_count} 張, 儲存至: {dest_dir}")
    return summary

if __name__ == "__main__":
    sync_all()
