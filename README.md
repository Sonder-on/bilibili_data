# b站数据及视频下载
1. 使用时需要下载所需的库
2. 需要手动添加**cookie**和**id**
3. 视频下载需要**ffmpeg**
4. **data.py**是通过python写b站的加密算法来**伪装浏览器**访问获取数据，**data_playwright.py**是利用playwright**拦截json请求**获取数据
