import requests
import re
import time

def fetch_bilibili_danmaku(bvid):
    # 伪装请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://www.bilibili.com/video/{bvid}/'
    }

    try:
        # ================= 1. 获取视频的 cid =================
        print(f"\n正在获取视频 {bvid} 的底层 CID...")
        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        view_res = requests.get(view_api, headers=headers).json()

        if view_res['code'] != 0:
            print(f"❌ 获取视频信息失败: {view_res['message']}")
            return

        cid = view_res['data']['cid']
        title = view_res['data']['title']
        print(f"✅ 成功获取！\n视频标题: {title}\nCID: {cid}")

        # ================= 2. 请求弹幕 XML 接口 =================
        print(f"\n正在下载弹幕数据...")
        # B站提供的基础 XML 弹幕接口 (list.so)
        danmaku_api = f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}"
        dm_res = requests.get(danmaku_api, headers=headers)
        
        # B站弹幕接口返回的是 deflated XML，这里强制用 utf-8 解码
        dm_res.encoding = 'utf-8'
        xml_text = dm_res.text

        # ================= 3. 正则提取弹幕文本 =================
        # 弹幕在 XML 中的格式为: <d p="参数,参数,...">弹幕内容</d>
        # 我们用正则提取标签中间的内容
        danmaku_list = re.findall(r'<d p=".*?">(.*?)</d>', xml_text)

        if not danmaku_list:
            print("⚠️ 未找到任何弹幕。")
            return

        print(f"🎉 成功提取 {len(danmaku_list)} 条弹幕！")

        # ================= 4. 打印预览并保存 =================
        print("\n【弹幕预览 (前10条)】")
        for i, dm in enumerate(danmaku_list[:10], 1):
            print(f" {i}. {dm}")
        if len(danmaku_list) > 10:
            print(" ...")

        # 写入 TXT 文件
        filename = f"弹幕_{bvid}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            for dm in danmaku_list:
                f.write(dm + '\n')
                
        print(f"\n📁 所有弹幕已成功保存至当前目录下的: {filename}")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == '__main__':
    print("====================================================")
    print("             B站 视频弹幕下载器 (交互版)")
    print("====================================================\n")
    
    # 交互式获取 BV 号
    target_bvid = input("👉 请输入想要爬取弹幕的视频 BV 号 (例如 BV17D4y1n7uC): ").strip()
    
    # 简单的格式校验
    while not target_bvid.startswith("BV"):
        target_bvid = input("❌ BV 号格式错误 (必须以 BV 开头)，请重新输入: ").strip()
    
    fetch_bilibili_danmaku(target_bvid)
