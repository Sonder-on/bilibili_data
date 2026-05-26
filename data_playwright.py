from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        bid = input("请输入up主的id")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        print("正在访问 B 站并等待目标接口...")

        try:
            with page.expect_response(
                    lambda response: "wbi/arc/search" in response.url
                                     and response.status == 200
                                     and response.request.method == "GET",
                    timeout=15000
            ) as response_info:
                page.goto(f"https://space.bilibili.com/{bid}/upload/video")

            response = response_info.value
            json_data = response.json()

            api_code = json_data.get('code')
            print(f"\n🔍 API 真实返回 Code: {api_code}, Message: {json_data.get('message')}")

            if api_code != 0:
                print("⚠️ B 站拒绝了返回数据，完整响应内容如下：")
                print(json_data)
            else:
                print("✅ 成功提取到视频数据：\n")
                vlist = json_data.get('data', {}).get('list', {}).get('vlist', [])
                for video in vlist[:5]:
                    print(f"- 视频标题: {video.get('title')}")

        except Exception as e:
            print(f"❌ 抓取超时或失败: {e}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
