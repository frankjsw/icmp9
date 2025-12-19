#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
"""
Xray配置文件生成器
从API获取国家列表，为每个国家生成Shadowsocks入口和出口配置，并测试Shadowsocks节点是否可用
"""

import json
import requests
import sys
import base64
import subprocess
import time
import socket
from typing import List, Dict, Any

# 配置常量
API_URL = "https://api.icmp9.com/online.php"
OUTPUT_FILE = "xray_config.json"
SS_SUBSCRIPTION_FILE = "shadowsocks_subscription.txt"
TUNNEL_DOMAIN = "tunnel.icmp9.com"
TUNNEL_PORT = 443

# Shadowsocks固定配置
SS_METHOD = "aes-256-gcm"
SS_PASSWORD = "123456"  # 自己设置一个密码

# VMess固定UUID
VMESS_UUID = "e9d0b62a-b2ca-4e0b-83fa-927947dd1f86"  # 自己设置一个UUID

# 基础端口配置
BASE_SS_PORT = 10001
BASE_SOCKS_PORT = 10808
BASE_REDIR_PORT = 10809

# 默认服务器IP
DEFAULT_SERVER_IP = "66.235.170.68"  # 改成你的服务器IP

# Xray配置文件路径
XRAY_CONFIG_PATH = "./xray_config.json"


def fetch_countries() -> List[Dict[str, str]]:
    """从API获取国家列表"""
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("success"):
            raise ValueError("API返回失败状态")
        
        countries = data.get("countries", [])
        print(f"成功获取 {len(countries)} 个国家/地区")
        return countries
    
    except requests.RequestException as e:
        print(f"获取API数据失败: {e}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError) as e:
        print(f"解析API数据失败: {e}", file=sys.stderr)
        sys.exit(1)


def create_ss_inbound(country_code: str, port: int) -> Dict[str, Any]:
    """创建Shadowsocks入站配置"""
    return {
        "tag": f"ss-{country_code}-in",
        "port": port,
        "listen": "0.0.0.0",
        "protocol": "shadowsocks",
        "settings": {
            "method": SS_METHOD,
            "password": SS_PASSWORD,
            "network": "tcp,udp"
        }
    }


def create_vmess_outbound(country_code: str) -> Dict[str, Any]:
    """创建VMess出站配置"""
    return {
        "tag": f"proxy-{country_code}",
        "protocol": "vmess",
        "settings": {
            "vnext": [
                {
                    "address": TUNNEL_DOMAIN,
                    "port": TUNNEL_PORT,
                    "users": [
                        {
                            "id": VMESS_UUID,
                            "alterId": 0,
                            "security": "auto"
                        }
                    ]
                }
            ]
        },
        "streamSettings": {
            "network": "ws",
            "security": "tls",
            "tlsSettings": {
                "serverName": TUNNEL_DOMAIN,
                "allowInsecure": False
            },
            "wsSettings": {
                "path": f"/{country_code}",
                "headers": {
                    "Host": TUNNEL_DOMAIN
                }
            }
        }
    }


def create_routing_rule(country_code: str) -> Dict[str, Any]:
    """创建路由规则"""
    return {
        "type": "field",
        "inboundTag": [f"ss-{country_code}-in"],
        "outboundTag": f"proxy-{country_code}"
    }


def generate_xray_config(countries: List[Dict[str, str]]) -> Dict[str, Any]:
    """生成完整的Xray配置"""
    
    # 基础配置
    config = {
        "log": {
            "loglevel": "warning"
        },
        "dns": {
            "servers": [
                "2001:4860:4860::8888",
                "2606:4700:4700::1111",
                "8.8.8.8",
                "1.1.1.1"
            ],
            "queryStrategy": "UseIPv4"
        },
        "inbounds": [
            {
                "tag": "socks-in",
                "port": BASE_SOCKS_PORT,
                "listen": "127.0.0.1",
                "protocol": "socks",
                "settings": {
                    "udp": True
                }
            },
            {
                "tag": "redir-in",
                "port": BASE_REDIR_PORT,
                "listen": "0.0.0.0",
                "protocol": "dokodemo-door",
                "settings": {
                    "network": "tcp",
                    "followRedirect": True
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls"]
                }
            }
        ],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vmess",
                "settings": {
                    "vnext": [
                        {
                            "address": TUNNEL_DOMAIN,
                            "port": TUNNEL_PORT,
                            "users": [
                                {
                                    "id": VMESS_UUID,
                                    "alterId": 0,
                                    "security": "auto"
                                }
                            ]
                        }
                    ]
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "tls",
                    "tlsSettings": {
                        "serverName": TUNNEL_DOMAIN,
                        "allowInsecure": False
                    },
                    "wsSettings": {
                        "path": "/us",
                        "headers": {
                            "Host": TUNNEL_DOMAIN
                        }
                    }
                }
            }
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "ip": ["geoip:private"],
                    "outboundTag": "direct"
                }
            ]
        }
    }
    
    # 为每个国家生成配置
    for idx, country in enumerate(countries):
        country_code = country["code"]
        country_name = country["name"]
        
        # 添加Shadowsocks入站
        ss_port = BASE_SS_PORT + idx
        inbound = create_ss_inbound(country_code, ss_port)
        config["inbounds"].append(inbound)
        
        # 添加VMess出站
        outbound = create_vmess_outbound(country_code)
        config["outbounds"].append(outbound)
        
        # 添加路由规则
        routing_rule = create_routing_rule(country_code)
        config["routing"]["rules"].append(routing_rule)
        
        print(f"  {country['emoji']} {country_name} ({country_code}): SS端口 {ss_port}")
    
    # 添加direct出站
    config["outbounds"].append({
        "tag": "direct",
        "protocol": "freedom"
    })
    
    return config


def generate_ss_link(country: Dict[str, str], port: int, server_ip: str = DEFAULT_SERVER_IP) -> str:
    """生成Shadowsocks链接
    
    格式: ss://base64(method:password)@server:port#remark
    """
    country_code = country["code"]
    country_name = country["name"]
    emoji = country.get("emoji", "")
    
    # 编码认证信息
    auth_str = f"{SS_METHOD}:{SS_PASSWORD}"
    auth_b64 = base64.urlsafe_b64encode(auth_str.encode()).decode().rstrip('=') 
    
    # 生成备注名称
    remark = f"icmp9-{emoji} {country_name} ({country_code.upper()})"
    remark_encoded = requests.utils.quote(remark)
    
    # 生成完整链接
    ss_link = f"ss://{auth_b64}@{server_ip}:{port}#{remark_encoded}"
    
    return ss_link


def save_ss_subscription(countries: List[Dict[str, str]], filename: str, server_ip: str = DEFAULT_SERVER_IP):
    """生成并保存Shadowsocks订阅文件"""
    try:
        ss_links = []
        
        for idx, country in enumerate(countries):
            port = BASE_SS_PORT + idx
            ss_link = generate_ss_link(country, port, server_ip)
            ss_links.append(ss_link)
        
        # 写入文件（每行一个链接）
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(ss_links))
        
        print(f"✅ Shadowsocks订阅文件已生成: {filename}")
        print(f"   包含 {len(ss_links)} 个节点链接")
        
    except IOError as e:
        print(f"保存Shadowsocks订阅文件失败: {e}", file=sys.stderr)
        sys.exit(1)


def save_config(config: Dict[str, Any], filename: str):
    """保存配置到文件"""
    try:
        with open(filename, 'w', encoding='utf
