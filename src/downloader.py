import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request


def download_file(url, output_dir, filename_hint, timeout=120):
    os.makedirs(output_dir, exist_ok=True)

    request = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://windfiles.com/',
        }
    )

    print(f"正在下载...")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')

            real_filename = _extract_filename_from_disposition(response.headers, filename_hint)
            output_path = os.path.join(output_dir, real_filename)

            print(f"真实文件名：{real_filename}")
            print(f"保存到：{output_path}")

            if 'html' in content_type:
                print("⚠️ 服务器返回了 HTML 页面（可能是限制页面），尝试 POST 方式...")
                return None

            data = response.read()
            if not data or len(data) < 100:
                print(f"⚠️ 下载数据过小 ({len(data)} 字节)，可能被限制")
                return None

            with open(output_path, 'wb') as f:
                f.write(data)

            print(f"✅ 下载完成：{output_path}（{len(data)/1024:.1f} KB）")
            return output_path
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:200]
        print(f"❌ HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"❌ 下载失败：{e}")
        return None


def _extract_filename_from_disposition(headers, default):
    cd = headers.get('Content-Disposition', '')
    if not cd:
        return default
    match = re.search(r'''filename[^;=\n]*=((['"])(.*?)\2|[^;\n]*)''', cd, re.IGNORECASE)
    if match:
        name = match.group(3) or match.group(0).split('=', 1)[1].strip().strip('"\'')
        if name:
            return name
    return default


def download_slow_via_post(dl_param, output_dir, filename_hint, timeout=120):
    os.makedirs(output_dir, exist_ok=True)

    post_data = b'btnAct=Start+Download+Now'

    request = urllib.request.Request(
        f'https://windfiles.com/download/jump?dl={dl_param}',
        data=post_data,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://windfiles.com/',
        }
    )

    print(f"正在通过 POST 获取下载...")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get('Content-Type', '')
            data = response.read()

            real_filename = _extract_filename_from_disposition(response.headers, filename_hint)
            output_path = os.path.join(output_dir, real_filename)

            print(f"真实文件名：{real_filename}")
            print(f"保存到：{output_path}")

            if 'html' in content_type:
                print(f"❌ POST 失败，服务器返回 HTML（可能触发了限制）")
                print(data[:500].decode('utf-8', errors='replace'))
                return None

            if not data or len(data) < 100:
                print(f"⚠️ POST 返回数据过小 ({len(data)} 字节)，可能失败")
                return None

            with open(output_path, 'wb') as f:
                f.write(data)

            print(f"✅ 下载完成：{output_path}（{len(data)/1024:.1f} KB）")
            return output_path
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300]
        print(f"❌ POST 下载失败 HTTP {e.code}: {body}")

        limit_patterns = [
            r'have downloaded \d+ files', r'upgrade.*VIP', r'try again',
            r'daily.*limit', r'limit.*reached', r'24 hours',
            r'每日.*下载', r'超过.*限制', r'升级.*VIP',
        ]
        for pat in limit_patterns:
            if re.search(pat, body, re.IGNORECASE):
                print("\n🔒 检测到每日下载限制（2 次/24h）")
                print("   使用 --proxy 切换 IP 即可绕过")
                break
        return None
    except Exception as e:
        print(f"❌ POST 下载失败：{e}")
        return None


def download_with_agent_browser(share_url, output_dir, proxy=None):
    from pathlib import Path

    env = os.environ.copy()
    if proxy:
        env['HTTP_PROXY'] = proxy
        env['HTTPS_PROXY'] = proxy
        env['http_proxy'] = proxy
        env['https_proxy'] = proxy

    result = subprocess.run(['which', 'agent-browser'], capture_output=True)
    if result.returncode != 0:
        print("错误：agent-browser 未安装")
        return None

    print("使用 agent-browser 进行下载...")

    subprocess.run(['agent-browser', 'open', share_url], env=env, check=True)
    time.sleep(2)

    result = subprocess.run(['agent-browser', 'snapshot', '-i'],
                          capture_output=True, text=True, env=env)
    snapshot_content = result.stdout

    share_filename = 'download.torrent'
    match = re.search(r'([A-Z0-9-]+\.torrent)', snapshot_content)
    if match:
        share_filename = match.group(1)
        print(f"文件名：{share_filename}")

    import windfiles_download as _wd
    html_content = _wd.fetch_page(share_url)

    match = re.search(r'/download/slow/\?dl=[^"\'>\s]+', html_content) if html_content else None
    if not match:
        print("错误：无法找到下载链接，尝试点击免费下载按钮...")

        match = re.search(r'link "Free Slow Download" \[ref=(e\d+)\]', snapshot_content)
        if match:
            free_btn_ref = match.group(1)
            print(f"点击免费下载按钮：{free_btn_ref}")
            subprocess.run(['agent-browser', 'click', free_btn_ref], env=env, check=True)
            time.sleep(95)

            result = subprocess.run(['agent-browser', 'snapshot', '-i'],
                                  capture_output=True, text=True, env=env)
    else:
        download_link = match.group(0)
        if not download_link.startswith('http'):
            download_link = 'https://windfiles.com' + download_link

        print(f"下载链接：{download_link}")

        subprocess.run(['agent-browser', 'open', download_link], env=env, check=True)
        time.sleep(2)

        result = subprocess.run(['agent-browser', 'snapshot', '-i', '-C'],
                              capture_output=True, text=True, env=env)
        snapshot_text = result.stdout

        cooldown_patterns = [
            r'wait.*10.*min', r'cool.?down', r'cooldown',
            r'please wait', r'try again later',
            r'you can only download', r'daily.*limit',
            r'already downloaded', r'10.*分钟内', r'冷却',
            r'请等待', r'请稍后', r'限制', r'已达到',
        ]
        for pat in cooldown_patterns:
            if re.search(pat, snapshot_text, re.IGNORECASE):
                print(f"❌ 检测到下载限制：页面包含冷却/限制提示")
                context_pat = r'.{0,40}' + pat + r'.{0,80}'
                cmatch = re.search(context_pat, snapshot_text, re.IGNORECASE)
                if cmatch:
                    print(f"   提示内容：{cmatch.group(0).strip()}")
                print("   10 分钟冷却期内无法下载，请稍后再试或使用 --proxy 切换 IP")
                return None

        match = re.search(r'button "Start Download Now" \[ref=(e\d+)\]', snapshot_text)
        if match:
            button_ref = match.group(1)
            print(f"点击下载按钮：{button_ref}")
            subprocess.run(['agent-browser', 'click', button_ref], env=env, check=True)
            time.sleep(2)

            result = subprocess.run(['agent-browser', 'snapshot', '-i', '-C'],
                                  capture_output=True, text=True, env=env)
            post_click_text = result.stdout
            limit_patterns = [
                r'You have downloaded \d+ files in the last 24 hours',
                r'Please upgrade to VIP or try again tomorrow',
                r'每日下载', r'下载次数', r'超过.*限制', r'升级.*VIP',
                r'Daily download limit', r'limit reached',
                r'you have reached.*limit', r'try again tomorrow',
            ]
            for pat in limit_patterns:
                if re.search(pat, post_click_text, re.IGNORECASE):
                    print(f"❌ 检测到每日下载限制")
                    cmatch = re.search(r'.{0,40}' + pat + r'.{0,80}', post_click_text, re.IGNORECASE)
                    if cmatch:
                        print(f"   提示内容：{cmatch.group(0).strip()}")
                    print("   未登录账号每日限制 2 次下载，请使用 --proxy 切换 IP 绕过")
                    return None
        else:
            preview = snapshot_text[:300]
            print(f"❌ 未找到下载按钮，页面内容：{preview}")
            return None

    downloads_dir = os.path.expanduser('~/Downloads')
    os.makedirs(output_dir, exist_ok=True)

    downloaded_file = None
    for wait_sec in range(30):
        time.sleep(1)

        if not os.path.exists(downloads_dir):
            continue

        for f in os.listdir(downloads_dir):
            if f.endswith('.torrent'):
                fp = os.path.join(downloads_dir, f)
                try:
                    if f.endswith('.crdownload'):
                        continue
                    mtime = os.path.getmtime(fp)
                    if time.time() - mtime < 60:
                        downloaded_file = fp
                        break
                except OSError:
                    continue
        if downloaded_file:
            break

    if not downloaded_file and os.path.exists(downloads_dir):
        for f in os.listdir(downloads_dir):
            if f == share_filename:
                fp = os.path.join(downloads_dir, f)
                if os.path.isfile(fp):
                    mtime = os.path.getmtime(fp)
                    if time.time() - mtime < 300:
                        downloaded_file = fp
                        break

    if downloaded_file:
        os.makedirs(output_dir, exist_ok=True)
        dest = os.path.join(output_dir, share_filename)
        shutil.copy2(downloaded_file, dest)
        actual_size = os.path.getsize(dest)
        print(f"✅ 文件已保存到：{dest}（{actual_size / 1024:.1f} KB）")
        return dest

    print("❌ 下载失败：未在 ~/Downloads 中找到新下载的 torrent 文件")
    return None
