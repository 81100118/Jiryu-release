# 天凤客户端 地龍（じりゅう）

天凤非官方客户端

运行截图：

![image](https://github.com/81100118/Jiryu-release/blob/master/screenshots/1.png)
（图片需要科学上网才能显示）
## 安装

### Windows

1. 安装Anaconda 
2. 安装依赖库：打开anaconda prompt，运行`pip install pygame`；运行`pip install websocket-client`
3. 使用git克隆此仓库

### Linux

以Ubuntu 20.04为例

1. 安装python3：ubuntu 20.04自带python3，不用安装
2. 安装pip：`sudo apt-get install python3-pip`
3. 安装依赖库：`sudo apt-get install python3-pygame`   `pip3 install websocket-client`
4. 使用git克隆此仓库

## 使用

更改设置：修改`settings.py`，改ID和个室号，还有一些高级设置

运行客户端：`python client_gui.py` （若默认python不是python3，则`python3 client_gui.py`）

客户端人机交互：鼠标操作，左键按按钮，右键摸切/确认（相当于官方客户端的OK按钮）。副露时不会显示吃碰按钮，若要吃碰，直接在手牌里选需要亮出的牌；若要大明杠，直接按“杠”按钮（选手牌会被认为是碰）。如果选择一张牌之后第二张牌只有一种合法选择，则会自动选择。人机对战中按鼠标中键退出，真人对战中按鼠标中线拔线。掉线时按鼠标中键重连。

倒计时不显示，剩余小于等于5秒时，每秒会发出声音提醒，倒计时结束后【不会】自动摸切/确认。**开局、每小局结束都需要按右键确认。**

## 已知问题

1. 无法打雀庄 无法打大会室 无法打无赤
2. 登录时有不小的概率掉线（SSL错误），重连即可，不影响对局（除非掉线重连的时候出这个错）
3. 连续快速播放音效时，音效可能漏放（已解决）
4. 和牌役比较多的时候会显示不下（问题已减轻，现在能显示12种役）

## 免责声明

**此客户端非官方客户端，因此有被封号的风险。**

**虽然此客户端经过测试，但作者对此客户端的可用性、安全性不做任何保证。**

**牌山由天凤服务器生成，此客户端无法出千、无法透视，也无法改变任何人的运气。**

**使用此客户端即视为接受所有风险，包括但不限于被封号、被封IP、数据（如ID、牌谱）丢失、数据泄露、掉线无法重连、掉段等。**

## 更新履历
2020.08.10
- 修复了一个小问题

2020.08.11
- 修复了readme里的bug

2020.08.19
- 修复了一炮多响无法正确显示的bug

2020.10.14
- 修复了声音延迟及丢失的问题
- 增加短卡顿提示功能

2020.12.14
- 修复了没有收到服务器的立直确认消息就允许切牌的bug
- 修复了断线重连后无法下载牌谱的bug
- 优化了发送心跳('<Z/>')的线程，退出之后不用等待了
- 优化了显示：副露时选择副露的牌时牌不再是红的
- 增加了发送错误时自动断线的功能，可以在settings.py设置是否开启此功能（默认开启）

2020.12.21
- 更改了部分对象的new的时机
- 优化了和牌时役种显示
- 增加了settings.py里的一些选项
- 增加了人机对战按鼠标中键退出的功能
- 增加了高亮显示相同牌的功能，可以在settings.py设置是否开启此功能（默认开启）

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