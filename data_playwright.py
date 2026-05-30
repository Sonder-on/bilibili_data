import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth


def main():
    print("====================================================")
    print("      B站 UP主全量数据爬虫 (Playwright 拦截版 + VUI修复)")
    print("====================================================\n")

    bid = input("👉 请输入目标 UP 主的 UID (例如 1346921): ").strip()

    # 用来存储我们要收集的所有数据
    up_data = {
        "mid": bid,
        "name": "",
        "sign": "",
        "official_title": "",
        "follower": 0,
        "videos": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # ⚠️ 如果抓取多页时遇到 B站强制登录拦截，请解除下面代码的注释并填入你的 Cookie
        # context.add_cookies([
        #     {"name": "SESSDATA", "value": "你的SESSDATA", "domain": ".bilibili.com", "path": "/"},
        #     {"name": "bili_jct", "value": "你的bili_jct", "domain": ".bilibili.com", "path": "/"}
        # ])

        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        # ================= 1. 定义全局拦截器 =================
        def handle_response(response):
            # 只拦截 GET 请求和状态码为 200 的成功响应
            if response.request.method != "GET" or response.status != 200:
                return

            url = response.url
            try:
                # 拦截：UP主基础信息 (ID, 名字, 签名, 认证)
                if "x/space/wbi/acc/info" in url:
                    data = response.json().get("data", {})
                    up_data["name"] = data.get("name", "")
                    up_data["sign"] = data.get("sign", "")
                    up_data["official_title"] = data.get("official", {}).get("title", "无")
                    print(f"✅ 成功获取 UP主信息: {up_data['name']}")

                # 拦截：UP主粉丝数据
                elif "x/relation/stat" in url:
                    data = response.json().get("data", {})
                    if "follower" in data:
                        up_data["follower"] = data.get("follower", 0)
                        print(f"✅ 成功获取粉丝数: {up_data['follower']}")

                # 拦截：视频列表页数据
                elif "x/space/wbi/arc/search" in url:
                    vlist = response.json().get("data", {}).get("list", {}).get("vlist", [])
                    for video in vlist:
                        up_data["videos"].append({
                            "title": video.get("title"),
                            "play": video.get("play"),
                            "length": video.get("length"),
                            "created": video.get("created"),
                            "bvid": video.get("bvid")
                        })
                    print(f"📦 抓取到本页 {len(vlist)} 条视频，总计已获取 {len(up_data['videos'])} 条")

            except Exception as e:
                # 忽略非JSON格式或其他解析错误
                pass

        # 挂载拦截器
        page.on("response", handle_response)

        # ================= 2. 访问主页并触发初始请求 =================
        print(f"\n🚀 正在访问 UP主主页...")
        # 直接访问视频列表 TAB 页，这样会同时触发基础信息和视频列表请求
        page.goto(f"https://space.bilibili.com/{bid}/upload/video", wait_until="networkidle")

        # ================= 3. 自动翻页逻辑 =================
        page_num = 1
        while True:
            # 1. 模拟鼠标滚轮向下滚动，触发懒加载组件渲染
            page.mouse.wheel(0, 2000)

            # 2. 适当休眠，给页面渲染新版 VUI 组件的时间
            time.sleep(2)

            try:
                # 3. 等待新版分页组件出现（最长等待 5 秒）
                page.wait_for_selector(".vui_pagenation--btn-side", state="attached", timeout=5000)

                # side 按钮通常有两个（上一页、下一页），取最后一个即为“下一页”
                next_btn = page.locator(".vui_pagenation--btn-side").last
            except Exception:
                print("⚠️ 等待 5 秒后仍未找到分页组件，说明可能只有一页、已经到底或网络卡顿。")
                break

            # 4. 检查下一页按钮是否被禁用（动态绑定的 disabled 样式）
            class_attr = next_btn.get_attribute("class")
            if class_attr and "vui_button--disabled" in class_attr:
                print("\n🎉 已经到达最后一页，所有视频抓取完毕！")
                break

            print(f"➡️ 准备翻页，前往第 {page_num + 1} 页...")
            page_num += 1

            try:
                # 5. 点击下一页的同时，等待新的视频接口返回数据
                with page.expect_response(
                        lambda r: "x/space/wbi/arc/search" in r.url and r.status == 200,
                        timeout=15000
                ):
                    # force=True 防止被悬浮窗（如客服、反馈按钮）遮挡导致点击失败
                    next_btn.click(force=True)
            except Exception as e:
                print(f"❌ 翻页等待数据超时，强制结束: {e}")
                break

        # ================= 4. 打印最终结果 =================
        print("\n====================================================")
        print(f"📝 最终抓取结果汇报：")
        print(f"👤 UP主昵称: {up_data['name']} (UID: {up_data['mid']})")
        print(f"👥 粉丝数量: {up_data['follower']}")
        print(f"🏅 官方认证: {up_data['official_title']}")
        print(f"✍️ 个性签名: {up_data['sign']}")
        print(f"🎬 视频总数: {len(up_data['videos'])} 个")
        print("====================================================\n")

        # 打印前几个视频作为验证
        for i, v in enumerate(up_data['videos'][:5]):
            print(f"{i + 1}. {v['title']} (播放: {v['play']}, 时长: {v['length']})")
        if len(up_data['videos']) > 5:
            print("...")

        browser.close()


if __name__ == "__main__":
    main()
