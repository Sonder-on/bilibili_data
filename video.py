import time
import urllib.parse
import hashlib
import json
import subprocess
from curl_cffi import requests

# ================= 1. Wbi 签名核心算法 =================
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]

def get_mixin_key(orig: str) -> str:
    return ''.join([orig[i] for i in MIXIN_KEY_ENC_TAB if i < len(orig)])[:32]

def enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    mixin_key = get_mixin_key(img_key + sub_key)
    params['wts'] = round(time.time())
    params = dict(sorted(params.items()))
    query_list = []
    for k, v in params.items():
        v = str(v).replace("!", "").replace("'", "").replace("(", "").replace(")", "").replace("*", "")
        query_list.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")
    query_str = '&'.join(query_list)
    w_rid = hashlib.md5((query_str + mixin_key).encode('utf-8')).hexdigest()
    params['w_rid'] = w_rid
    return params

def get_wbi_keys(headers: dict) -> tuple:
    resp = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=headers, impersonate="chrome120")
    json_data = resp.json()
    img_key = json_data['data']['wbi_img']['img_url'].split('/')[-1].split('.')[0]
    sub_key = json_data['data']['wbi_img']['sub_url'].split('/')[-1].split('.')[0]
    return img_key, sub_key

# ================= 2. 视频信息与下载主逻辑 =================
def process_bilibili_video(bvid: str, my_cookie: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://www.bilibili.com/video/{bvid}/',
        'Cookie': my_cookie
    }

    try:
        # Step 1: 获取视频基本信息 (包含统计数据和 cid、aid)
        print(f"\n正在获取 {bvid} 的基本信息...")
        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        view_res = requests.get(view_api, headers=headers, impersonate="chrome120").json()

        if view_res['code'] != 0:
            print(f"获取视频信息失败: {view_res['message']}")
            return

        video_data = view_res['data']
        cid = video_data['cid']
        aid = video_data['aid']  # 获取评论时需要用到底层 av 号 (aid)
        title = video_data['title']
        
        # ====== 提取并打印所有的视频交互数据 ======
        stat = video_data['stat']
        play = stat.get('view', 0)
        danmaku = stat.get('danmaku', 0)
        reply = stat.get('reply', 0)
        favorite = stat.get('favorite', 0)
        coin = stat.get('coin', 0)
        like = stat.get('like', 0)

        print("\n" + "="*40)
        print(f"📺 视频标题: {title}")
        print(f"▶️ 播放量: {play}")
        print(f"👍 点赞数: {like}")
        print(f"🪙 投币数: {coin}")
        print(f"⭐ 收藏数: {favorite}")
        print(f"💬 弹幕数: {danmaku}")
        print(f"📝 评论数: {reply}")
        print("="*40 + "\n")
        
        # ====== 抓取并打印最新评论文本 ======
        print("正在抓取最新评论预览...")
        # type=1 代表视频评论，oid 是视频的 aid，mode=3 代表按时间排序
        reply_api = f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3"
        reply_res = requests.get(reply_api, headers=headers, impersonate="chrome120").json()
        
        print("\n【评论区节选】:")
        if reply_res['code'] == 0 and 'replies' in reply_res['data'] and reply_res['data']['replies']:
            # 只取前 5 条评论打印
            for i, reply_item in enumerate(reply_res['data']['replies'][:5], 1): 
                uname = reply_item['member']['uname']
                message = reply_item['content']['message']
                # 简单处理掉里面的换行符，让控制台排版更好看
                message = message.replace('\n', '  ')
                print(f"  {i}. {uname}: {message}")
        else:
            print("  暂无评论或获取评论失败。")
        print("\n" + "-"*40)

        # Step 2: 准备 Wbi 签名获取播放直链
        print("正在计算 Wbi 签名请求播放地址...")
        img_key, sub_key = get_wbi_keys(headers)

        playurl_params = {
            'bvid': bvid,
            'cid': cid,
            'qn': 112,  # 尝试请求 1080P 高码率
            'fnval': 4048,  # 4048 代表请求 DASH 格式 (音视频分离)
            'fnver': 0,
            'fourk': 1
        }

        signed_params = enc_wbi(playurl_params, img_key, sub_key)
        playurl_api = "https://api.bilibili.com/x/player/wbi/playurl"

        play_res = requests.get(playurl_api, params=signed_params, headers=headers, impersonate="chrome120").json()

        if play_res['code'] != 0:
            print(f"获取播放地址失败: {play_res['message']}")
            return

        # 提取最高画质的视频和音频直链
        dash_data = play_res['data']['dash']
        video_url = dash_data['video'][0]['baseUrl']
        audio_url = dash_data['audio'][0]['baseUrl']
        print("成功拿到音视频底层直链！准备下载...")

        # Step 3: 下载文件 (注意：下载时必须带上 Referer)
        def download_file(stream_url, filename):
            print(f"正在下载 {filename} ...")
            # 同样使用 curl_cffi 防止 CDN 拦截
            response = requests.get(stream_url, headers=headers, impersonate="chrome120", stream=True)
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            print(f"{filename} 下载完成！")

        download_file(video_url, 'video.m4s')
        download_file(audio_url, 'audio.m4s')

        # Step 4: FFmpeg 合并
        print("\n正在调用 FFmpeg 合并音视频...")
        # 为了防止视频标题中含有不合法字符导致无法保存文件，做一下清理
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        out_filename = f"{safe_title}_{bvid}.mp4"
        
        subprocess.run(['ffmpeg', '-y', '-i', 'video.m4s', '-i', 'audio.m4s', '-c', 'copy', out_filename], check=True)
        print(f"\n🎉 视频处理完成！已保存为: {out_filename}")

    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    print("====================================================")
    print("      B站 视频下载 & 数据抓取器 (交互版)")
    print("====================================================\n")
    
    # 交互式获取 BV 号
    target_bvid = input("👉 请输入想要处理的视频 BV 号 (例如 BV1DXLu6QE5e): ").strip()
    while not target_bvid.startswith("BV"):
        target_bvid = input("❌ BV 号格式错误 (必须以 BV 开头)，请重新输入: ").strip()

    # 交互式获取 Cookie
    my_cookie = input("\n👉 请输入你的 B站 Cookie (如果不输入，可能会限制画质或无法获取数据): ").strip()
    
    process_bilibili_video(target_bvid, my_cookie)
