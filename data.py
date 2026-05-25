import time
import random
import math
import urllib.parse
import hashlib
from curl_cffi import requests

# ================= 1. Wbi 算法核心配置 =================
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52
]


def get_mixin_key(orig: str) -> str:
    return ''.join([orig[i] for i in MIXIN_KEY_ENC_TAB if i < len(orig)])[:32]


def enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    params = params.copy()
    mixin_key = get_mixin_key(img_key + sub_key)
    curr_time = round(time.time())
    params['wts'] = curr_time
    params = dict(sorted(params.items()))

    query_list = []
    for k, v in params.items():
        v = str(v)
        v = v.replace("!", "").replace("'", "").replace("(", "").replace(")", "").replace("*", "")
        query_list.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(v)}")

    query_str = '&'.join(query_list)
    hash_str = query_str + mixin_key
    w_rid = hashlib.md5(hash_str.encode('utf-8')).hexdigest()
    params['w_rid'] = w_rid
    return params


def get_wbi_keys(headers: dict) -> tuple:
    resp = requests.get(
        'https://api.bilibili.com/x/web-interface/nav',
        headers=headers,
        impersonate="chrome120"
    )
    resp.raise_for_status()
    json_data = resp.json()
    img_url = json_data['data']['wbi_img']['img_url']
    sub_url = json_data['data']['wbi_img']['sub_url']
    img_key = img_url.split('/')[-1].split('.')[0]
    sub_key = sub_url.split('/')[-1].split('.')[0]
    return img_key, sub_key


# ================= 2. 数据打印辅助函数 =================
def print_video_samples(vlist, current_page, crawled_count):
    """只打印每页的前 3 条数据，并汇报总进度"""
    if not vlist:
        return crawled_count

    print(f"   [第 {current_page} 页视频抽样]:")
    # 只取前 3 条打印
    for video in vlist[:3]:
        title = video.get('title', '')
        # 如果标题太长，截断一下保持控制台整洁
        if len(title) > 25:
            title = title[:25] + "..."
        play = video.get('play', 0)
        length = video.get('length', '00:00')
        print(f"      - {title} (时长: {length} | 播放量: {play})")

    if len(vlist) > 3:
        print("      - ... (剩余视频省略打印)")

    crawled_count += len(vlist)
    print(f"   ✅ 更新进度：目前共计已爬取 {crawled_count} 条视频数据\n")
    return crawled_count


# ================= 3. 主程序任务执行 =================
if __name__ == '__main__':
    # 目标 UP 主 UID
    TARGET_MID = 1346921
    PAGE_SIZE = 40
    crawled_count = 0  # 用于记录已爬取的视频总数

    # 配置 Headers 与 Cookie
    dynamic_cookie = "buvid3=73DFC423-B7D4-20CF-3AC6-0D1D1CD5E7E875098infoc; b_nut=1779518775; _uuid=C55C6D5C-E9106-AFEC-F5FD-123551177D5676196infoc; buvid_fp=0301ce0ff946fa11e7cb49b2c208d531; buvid4=1BF815A0-C855-4E05-3062-6DDD8511682178017-026052314-wzZrYLNoZlxI9uV0LSzKNg%3D%3D; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzk3NzgwMDEsImlhdCI6MTc3OTUxODc0MSwicGx0IjotMX0.clW_gWwOg_zmqhVCh8qSJnGJfl138uF5xZNAkdJ_reI; bili_ticket_expires=1779777941; lang=zh-Hans; CURRENT_QUALITY=0; rpdid=|(Ju~|~km|J)0J'u~~mlku)uu; CURRENT_FNVAL=2000; bsource=search_google; home_feed_column=4; browser_resolution=980-776; bmg_af_switch=1; bmg_src_def_domain=i1.hdslb.com; sid=4klikom6; b_lsid=28D2778A_19E5E35EE30"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Origin': 'https://space.bilibili.com',
        'Referer': f'https://space.bilibili.com/{TARGET_MID}/',
        'cookie': dynamic_cookie,
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site'
    }

    try:
        print("\n正在获取 Wbi Keys...")
        img_key, sub_key = get_wbi_keys(headers)

        # ==========================================
        # 任务一：爬取并展示 UP 主个人信息
        # ==========================================
        print("\n▶️ 开始任务一：获取 UP 主个人信息")
        info_params = {
            'mid': TARGET_MID,
            'token': '',
            'platform': 'web',
            'web_location': '1550101',
            'dm_img_list': '[]',
            'dm_img_str': 'V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ',
            'dm_cover_img_str': 'QU5HTEUgKEludGVsLCBJbnRlbChSKSBVSEQgR3JhcGhpY3MgKDB4MDAwMDlBNjgpIERpcmVjdDNEMTEgdnNfNV8wIHBzXzVfMCwgRDNEMTEpR29vZ2xlIEluYy4gKEludGVsKQ',
            'dm_img_inter': '{"ds":[],"wh":[2819,1473,57],"of":[39,78,39]}'
        }
        signed_info_params = enc_wbi(info_params, img_key, sub_key)

        info_url = "https://api.bilibili.com/x/space/wbi/acc/info"
        info_res = requests.get(info_url, params=signed_info_params, headers=headers, impersonate="chrome120",
                                timeout=10)
        info_res.encoding = 'utf-8'

        if info_res.status_code == 200:
            info_data = info_res.json()
            if info_data.get('code') == 0:
                user_info = info_data.get('data', {})
                name = user_info.get('name', '未知')
                face = user_info.get('face', '')
                sign = user_info.get('sign', '无签名')
                title = user_info.get('official', {}).get('title', '')

                print(
                    f"   【UP主信息】\n   昵称: {name}\n   UID: {TARGET_MID}\n   签名: {sign}\n   认证: {title if title else '无'}")
            else:
                print(f"❌ UP主信息接口返回错误: {info_data}")
        else:
            print(f"❌ UP主信息请求失败，HTTP 状态码: {info_res.status_code}")

        # 休眠一下，防止频繁请求被风控
        time.sleep(1.5)

        # ==========================================
        # 任务二：爬取并展示 UP 主视频列表（翻页）
        # ==========================================
        print("\n▶️ 开始任务二：获取 UP 主视频列表")
        base_video_params = {
            'ps': PAGE_SIZE,
            'tid': 0,
            'special_type': '',
            'order': 'pubdate',
            'mid': TARGET_MID,
            'index': 0,
            'keyword': '',
            'order_avoided': 'true',
            'platform': 'web',
            'web_location': '333.1387',
            'dm_img_list': '[]',
            'dm_img_str': '',
            'dm_cover_img_str': '',
            'dm_img_inter': '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}'
        }

        print("🚀 请求第 1 页以获取视频总数...")
        first_page_params = base_video_params.copy()
        first_page_params['pn'] = 1
        signed_video_params = enc_wbi(first_page_params, img_key, sub_key)

        video_url = "https://api.bilibili.com/x/space/wbi/arc/search"
        video_res = requests.get(video_url, params=signed_video_params, headers=headers, impersonate="chrome120",
                                 timeout=10)
        video_res.encoding = 'utf-8'

        if video_res.status_code != 200:
            print(f"❌ 视频列表初始请求失败，HTTP 状态码: {video_res.status_code}")
            exit(1)

        video_data = video_res.json()
        if video_data.get('code') != 0:
            print(f"❌ 视频列表接口返回错误: {video_data}")
            exit(1)

        total_count = video_data['data']['page']['count']
        total_pages = math.ceil(total_count / PAGE_SIZE)
        print(f"📊 该UP主共有 {total_count} 条视频，每页 {PAGE_SIZE} 条，共需爬取 {total_pages} 页。\n")

        # 处理第一页数据
        vlist = video_data['data']['list']['vlist']
        crawled_count = print_video_samples(vlist, current_page=1, crawled_count=crawled_count)

        # 循环爬取后续页码
        for current_page in range(2, total_pages + 1):
            sleep_time = random.uniform(2.0, 4.0)
            print(f"😴 随机休眠 {sleep_time:.2f} 秒，准备爬取第 {current_page} 页...")
            time.sleep(sleep_time)

            page_params = base_video_params.copy()
            page_params['pn'] = current_page
            signed_video_params = enc_wbi(page_params, img_key, sub_key)

            video_res = requests.get(video_url, params=signed_video_params, headers=headers, impersonate="chrome120",
                                     timeout=10)
            video_res.encoding = 'utf-8'

            if video_res.status_code == 200:
                page_data = video_res.json()
                if page_data.get('code') == 0:
                    page_vlist = page_data['data']['list']['vlist']
                    crawled_count = print_video_samples(page_vlist, current_page, crawled_count)
                else:
                    print(f"⚠️ 第 {current_page} 页视频列表接口返回错误: {page_data}")
            else:
                print(f"❌ 第 {current_page} 页请求失败，状态码: {video_res.status_code}")

        print(f"\n🎉 全部任务完成！最终总共爬取了 {crawled_count} 条视频数据。")

    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
