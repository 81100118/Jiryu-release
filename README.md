# 天凤客户端 地龍（じりゅう）

天凤非官方客户端

运行截图：

![image](https://github.com/81100118/Jiryu-release/blob/master/screenshots/1.png)

## 安装

### Windows

1. 安装Anaconda 
2. 安装依赖库：打开anaconda prompt，运行`pip install pygame`；运行`pip install websocket-client`
3. 使用git克隆此仓库

### Linux

以Ubuntu 20.04为例

1. 安装python3：ubuntu 20.04自带python3，不用安装
2. 安装pip：`sudo apt-get install pip3`
3. 安装依赖库：`sudo apt-get install python3-pygame`   `pip3 install websocket-client`
4. 使用git克隆此仓库

## 使用

更改设置：修改`settings.py`，改ID和个室号，还有一些高级设置

运行客户端：`python client_gui.py` （若默认python不是python3，则`python3 client_gui.py`）

客户端人机交互：鼠标操作，左键按按钮，右键摸切/确认（相当于官方客户端的OK按钮）。副露时不会显示吃碰按钮，若要吃碰，直接在手牌里选需要亮出的牌；若要大明杠，直接按“杠”按钮（选手牌会被认为是碰）。如果选择一张牌之后第二张牌只有一种合法选择，则会自动选择。

倒计时不显示，剩余小于等于5秒时，每秒会发出声音提醒，倒计时结束后【不会】自动摸切/确认。开局、每小局结束都需要按右键确认。

## 已知问题

1. 无法打雀庄 无法打大会室 无法打无赤
2. 登录时有不小的概率掉线（SSL错误），重连即可，不影响对局（除非掉线重连的时候出这个错）
3. 连续快速播放音效时，音效可能漏放
4. 和牌役比较多的时候会显示不下

## 免责声明

**此客户端非官方客户端，因此有被封号的风险。**

**虽然此客户端经过测试，但作者对此客户端的可用性、安全性不做任何保证。**

**牌山由天凤服务器生成，此客户端无法出千、无法透视，也无法改变任何人的运气。**

**使用此客户端即表示接受所有风险，包括但不限于被封号、被封IP、数据（如ID、牌谱）丢失、数据泄露、掉线无法重连、掉段等。**



****

参考代码：

https://cdn.tenhou.net/3/1718.js 天凤Web版代码（版本不断更新中，更新后链接可能会失效）

[MahjongRepository/tenhou-python-bot ](https://github.com/MahjongRepository/tenhou-python-bot) Bot for *tenhou*.net riichi mahjong server written in Python

[EndlessCheng/mahjong-helper](https://github.com/EndlessCheng/mahjong-helper) 日本麻将助手：牌效+防守+记牌（支持雀魂、天凤）

牌画、背景：

天凤

语音：

雀魂

音效：

天凤、雀魂