# 部署到魔搭创空间

目标：得到一个国内能直接打开的在线链接，写进简历和 README，HR 点开就能试。

魔搭（ModelScope）创空间是阿里的免费应用托管平台，免费的 CPU 规格是 2 核 16 GB，跑这个项目足够。整个过程大约 30 分钟，第一次构建要等几分钟。

> 说明：魔搭的官方文档在开发环境里打不开，下面的步骤根据公开教程和魔搭的部署说明整理。界面上的按钮名字可能略有不同，遇到对不上的地方，以页面提示为准，并把实际情况告诉 Claude，好更新这份文档。

## 0. 准备

1. **魔搭账号**：在 [modelscope.cn](https://modelscope.cn) 注册并登录。
2. **访问令牌**：右上角头像 → 访问令牌（Access Token），复制一个令牌。推送代码时当密码用。
3. **git 和 git-lfs**：
   - Windows：安装 [Git for Windows](https://git-scm.com/download/win)，自带 git-lfs。
   - Mac：`brew install git git-lfs`。
   - 然后运行一次 `git lfs install`。
4. **演示专用的 API key**：在 [DeepSeek 开放平台](https://platform.deepseek.com) 新建一个 key，名字写“魔搭演示”，和自己本地用的 key 分开。万一泄露，只作废这一个。账户里充少量钱就行，用完会停，不会多扣。
   - 想零成本，也可以只用智谱的免费模型 GLM-4-Flash（[open.bigmodel.cn](https://open.bigmodel.cn) 申请 key）。不过它在评测里只答对约 63%（DeepSeek 约 97%），给 HR 演示不建议用它。

## 1. 新建创空间

魔搭首页右上角 **创建 → 创建创空间**，按下面填：

| 项目 | 填什么 |
|---|---|
| 英文名称 | `askdata`（会出现在链接里） |
| 中文名称 | 智能问数助手 |
| 是否公开 | **公开**（HR 才能打开） |
| SDK | **Streamlit** |
| 硬件 | **CPU basic**（免费） |
| 镜像 | 选带 `py311` 的那一个，比如 `ubuntu22.04-py311-...` |
| 主文件 | `app.py`（如果有这一项） |

创建好后，链接是 `https://modelscope.cn/studios/<你的用户名>/askdata`。

> 2026 年 11 月的新界面：创建表单里只填名称、公开、License 和封面，SDK、硬件和镜像挪到了创建后的三步页面（空间文件 → 部署设置 → 确认并部署）。建好后不要再打开“创建创空间”的表单，不然会多建一个空间。先做第 3 步把代码推上去，再回到空间页面填部署设置。

## 2. 填环境变量

在空间页面的 **部署设置** 里填（以后要改，在右上角 **空间管理** 里找）。`DEEPSEEK_API_KEY` 填在 **密文变量**，别人看不到值；其余几项填在 **明文变量**。**关联云资源** 选免费的 CPU，**镜像版本** 选带 `py311` 的，**OAuth 设置** 保持关闭。

| 变量名 | 值 | 作用 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 第 0 步新建的演示 key | 必填（或者填下面的智谱 key） |
| `ZHIPUAI_API_KEY` | 智谱的 key | 可选。演示时建议不填，见下一行 |
| `ASKDATA_MODELS` | `deepseek-flash` | 只开放 DeepSeek Flash：便宜，评测准确率约 97%。GLM-4-Flash 免费但只有约 63%，访客选了它容易看到错答案 |
| `ASKDATA_MAX_QUESTIONS` | `10` | 每个访客最多问 10 次 |
| `ASKDATA_DAILY_LIMIT` | `300` | 全站每天最多回答 300 次，第二天清零 |

一个问题一般调用模型 2 到 3 次，每次约 2 千到 3 千 tokens（主要是表结构说明）。每天上限 300 次，花费心里就有底了。

**key 只填在这里**，不要写进代码、README 或者聊天记录里。

## 3. 上传代码

在本项目的根目录打开终端（Windows 用 Git Bash 或 PowerShell）：

```bash
# 把创空间的仓库克隆到本项目旁边的文件夹
git clone https://www.modelscope.cn/studios/<你的用户名>/askdata.git ../askdata-studio

# 同步网页需要的文件，并提交、推送
python scripts/publish_modelscope.py ../askdata-studio
```

推送时如果要求登录：**用户名填 `oauth2`，密码填第 0 步复制的访问令牌**。要在看得见的终端窗口里运行，不然没地方输入。

Windows 上登录成功后，令牌会存进“凭据管理器”，以后推送不用再输。

> Windows 的 Git 凭据管理器有时会把魔搭误认成 GitLab：提示 `missing OAuth configuration ... gitlab`，登录框一闪就失败。同步脚本已经自动处理了；自己手动推送时，命令写成 `git -c credential.provider=generic push`，就会直接问用户名和密码。

脚本只复制网页需要的文件（`app.py`、`askdata/`、`data/olist/`、`requirements.txt`、`.streamlit/`，以及 README 用到的 `docs/images/`），并保留创空间 README 开头那段配置。以后改了代码，再运行一次这条命令就会更新。

## 4. 启动和检查

1. 推送后创空间会自动构建。没有自动开始的话，在页面上点 **部署** 或 **上线**。
2. 第一次要等几分钟。在 **日志** 里能看到安装依赖和启动的过程，看到 `You can now view your Streamlit app` 就是启动好了。
3. 打开链接，点两三个示例问题，确认：有结论、有图、“执行过程”里能看到 SQL。
4. 用手机打开一次，确认能用。

都没问题后：

- 把链接填到 README 顶部的“在线体验”，把链接写进简历；
- 告诉 Claude 链接，Claude 会补上 README 的演示截图和动图。

## 常见问题

**日志里有 `ModuleNotFoundError`**
依赖没装上。确认 `requirements.txt` 已经推送上去，然后重新部署。

**日志里有 `unexpected keyword argument`，或者页面报 Streamlit 的错**
平台装的 Streamlit 版本太旧。换成 Docker 方式：

1. 新建一个创空间，SDK 选 **Docker**（这种方式要求账号绑定阿里云并实名认证，按页面提示完成）；
2. 运行同步脚本后，把 `deploy/Dockerfile` 复制到 `../askdata-studio/` 的根目录，再提交推送：
   ```bash
   cp deploy/Dockerfile ../askdata-studio/
   cd ../askdata-studio && git add Dockerfile && git commit -m "改用 Docker 部署" && git push
   ```
3. Dockerfile 已经按平台要求监听 7860 端口。

**页面提示“还没有配置 DEEPSEEK_API_KEY”**
环境变量名拼错了，或者改完变量没有重启。改好后在页面上点重启或重新部署。

**上传文件时报 403**
魔搭把网页嵌在自己的页面里，有的浏览器会拦掉校验用的 cookie。在创空间页面找“新窗口打开”，或者直接打开应用自己的网址再上传。内置数据的问答不受影响。

**打开很慢，或者显示正在启动**
免费空间长时间没人访问可能会休眠，第一次打开要等一会儿。集中投递简历前，自己先打开一次。

**在创空间网页上上传文件失败，或者打开链接看到一段 403 的 JSON**
这是魔搭的网关拦截了浏览器请求。不要按报错里的提示去改请求或设置，改用第 3 步的 Git 方式上传。

**推送被拒绝，提示 non-fast-forward**
创空间仓库里有你没拉下来的改动（比如在网页上改过 README）。先在 `../askdata-studio` 里运行 `git pull`，再重新运行同步脚本。不要用强制推送，平台不允许。

**部署设置里“关联云资源”和“镜像版本”一直是空的，不停弹 Forbidden**
这两个下拉框的内容是页面向魔搭请求来的，请求被拒就是空的。先确认账号已经绑定阿里云并实名（免费算力来自阿里云）；然后用无痕窗口或 Edge 打开，排除浏览器扩展；还不行就等十几分钟再试，连续操作太多可能被网关临时限制。在马来西亚实测过，最后能加载出来，所以人在境外不一定是原因。一直不行就联系魔搭客服，或者先用下面的 Streamlit Community Cloud。

## 备用方案一：Streamlit Community Cloud

Streamlit 官方的免费托管，直接从 GitHub 仓库部署，不用上传文件，境外访问顺畅。缺点是中国大陆打开 `streamlit.app` 可能很慢或打不开，所以 README 里最好再放一个演示动图。

1. 打开 [share.streamlit.io](https://share.streamlit.io)，用 GitHub 账号登录，按提示授权。
2. 点 **Create app** → 从 GitHub 部署：仓库选 `timmyknew/askdata`，分支 `main`，主文件 `app.py`。
3. **App URL** 可以改成好记的名字，比如 `askdata-<你的名字>`，链接就是 `https://askdata-<你的名字>.streamlit.app`。
4. 点 **Advanced settings**：Python 版本选 3.11 或 3.12；**Secrets** 里粘贴下面几行（只在这里填 key）：

   ```toml
   DEEPSEEK_API_KEY = "演示专用的 key"
   ASKDATA_MODELS = "deepseek-flash"
   ASKDATA_MAX_QUESTIONS = "10"
   ASKDATA_DAILY_LIMIT = "300"
   ```

   Streamlit 启动时会把这些顶层的值放进环境变量，代码不用改。
5. 点 **Deploy**，等几分钟装完依赖就能打开。以后往 `main` 推代码，网页会自动更新。

免费应用 12 小时左右没人访问会休眠，访客要点一下按钮唤醒，等半分钟。集中投递简历前自己先打开一次。

## 备用方案二：只放演示动图

在本地运行，录一段演示动图放进 README 和简历，不依赖任何平台，也不耽误投递。
