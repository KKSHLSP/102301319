## 大语言模型弹幕分析项目

本项目实现了一个用于采集、统计与可视化处理 B 站「大语言模型 / 大模型 / LLM」相关弹幕数据的 Python 工具包，涵盖：
- 弹幕爬取与本地缓存
- 弹幕频次统计与 Excel 导出
- 词云图可视化

所有命令均通过 `typer` 提供的 CLI 入口调用。

### 环境准备

1. 建议使用项目自带的 `.venv`（Python 3.13）：
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   export PYTHONPATH=src  # 让 python -m danmaku_analysis.* 命令可以直接运行
   ```
2. 若需维护离线样例，可使用 `typer` 提供的 `seed-sample` 命令复制示例数据。

### CLI 用法

所有命令均通过以下方式调用：
```bash
python -m danmaku_analysis.cli <command> [options]
```

可用子命令：
- `pipeline`：一键完成 **抓取 -> 统计 -> 词云生成**，结果分别写入 `data/reports/danmaku_stats.xlsx` 和 `data/reports/danmaku_wordcloud.png`。可用 `--max-videos` 控制抓取数量，`--font-path` 指定中文字体。
- `fetch`：根据配置的关键词（默认「大语言模型 / 大模型 / LLM」）抓取综合排序靠前的视频弹幕，并将数据以 JSON 缓存到 `data/raw/`。
  - 如遭遇 `412 Precondition Failed` 等风控，请在浏览器登录 B 站后复制完整 Cookie，并以环境变量传入：
    ```bash
    export BILIBILI_COOKIE='SESSDATA=xxx; bili_jct=xxx; ...'
    python -m danmaku_analysis.cli fetch
    ```
    可配合降低并发/放慢节奏减少 412：`python -m danmaku_analysis.cli fetch --concurrency 1 --sleep-interval 0.8 --max-videos 120`
- `seed-sample`：写入内置示例弹幕数据，便于离线调试或测试。
- `analyze`：从本地缓存读取弹幕，统计弹幕文本的出现次数（默认输出前 8 条）并导出 Excel，文件默认存放于 `data/reports/danmaku_stats.xlsx`。
- `visualize`：从本地缓存生成弹幕词云图，默认输出到 `data/reports/danmaku_wordcloud.png`。可以通过 `--font-path` 指定中文字体文件以获得更佳效果。

### 测试

运行单元测试：
```bash
python -m pytest
```

（如当前虚拟环境未安装 `pytest`，请先执行 `pip install pytest` 或使用 `pip install -r requirements.txt` 安装。）

### 已知限制

- 爬虫依赖 B 站公开接口，若触发访问频率限制，可在配置中调整并发或延迟参数。
- 词云生成对中文分词使用 `jieba`，若未安装则退化为逐条弹幕字符串拼接，效果会打折扣。
- 在受限网络环境中无法直接运行 `fetch` 命令，请先确认网络策略或使用 `seed-sample` 进行离线演示。
