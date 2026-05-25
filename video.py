import time
import urllib.parse
import hashlib
import json
import subprocess
from curl_cffi import requests

# ================= 1. Wbi 签名核心算法 (你已经掌握的) =================
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


# ================= 2. 视频下载主逻辑 =================

def download_bilibili_api(bvid: str, my_cookie: str):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://www.bilibili.com/video/{bvid}/',
        'Cookie': 'buvid3=73DFC423-B7D4-20CF-3AC6-0D1D1CD5E7E875098infoc; b_nut=1779518775; bsource=search_google; _uuid=C55C6D5C-E9106-AFEC-F5FD-123551177D5676196infoc; buvid_fp=0301ce0ff946fa11e7cb49b2c208d531; home_feed_column=5; browser_resolution=1536-776; buvid4=1BF815A0-C855-4E05-3062-6DDD8511682178017-026052314-wzZrYLNoZlxI9uV0LSzKNg%3D%3D; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzk3NzgwMDEsImlhdCI6MTc3OTUxODc0MSwicGx0IjotMX0.clW_gWwOg_zmqhVCh8qSJnGJfl138uF5xZNAkdJ_reI; bili_ticket_expires=1779777941; CURRENT_FNVAL=2000; lang=zh-Hans; sid=eqqf0qns; b_lsid=1EDF85F0_19E53B7FA7D'
    }

    try:
        # Step 1: 获取视频的 cid (这是必传参数)
        print(f"正在获取 {bvid} 的基本信息(cid)...")
        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        view_res = requests.get(view_api, headers=headers, impersonate="chrome120").json()

        if view_res['code'] != 0:
            print(f"获取视频信息失败: {view_res['message']}")
            return

        cid = view_res['data']['cid']
        print(f"成功获取 CID: {cid}")

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
        print("\n成功拿到音视频底层直链！准备下载...")

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
        subprocess.run(['ffmpeg', '-y', '-i', 'video.m4s', '-i', 'audio.m4s', '-c', 'copy', f'{bvid}.mp4'], check=True)
        print(f"\n🎉 视频处理完成！已保存为: {bvid}.mp4")

    except Exception as e:
        print(f"发生错误: {e}")


if __name__ == '__main__':
    # 填入你想要爬取的 BV 号
    TARGET_BVID = ""
    # ⚠️ 务必填入你浏览器最新的、完整的 Cookie
    MY_COOKIE = f""

    download_bilibili_api(TARGET_BVID, MY_COOKIE)
