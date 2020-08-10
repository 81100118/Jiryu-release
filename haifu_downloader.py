import requests

class HaifuDownloader:
	h={'Host': 'tenhou.net', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363'}
	@classmethod
	def fetch_haifu_text(cls, log):
		resp = requests.get("https://tenhou.net/3/mjlog2xml_.cgi?" + log, headers=cls.h)
		return resp.text
	@classmethod
	def fetch_haifu_file(cls, log):
		resp = requests.get("http://tenhou.net/0/log/find.cgi", params={'log': log, 'tw': '0'})
		return resp.content
		