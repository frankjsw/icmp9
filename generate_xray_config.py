import subprocess
import time
import socket

# 其他代码保持不变...

def test_shadowsocks_node(server_ip: str, port: int, method: str, password: str) -> bool:
    """测试Shadowsocks节点是否可用"""
    try:
        # 使用 ss-local 命令行客户端来测试节点的可用性
        ss_local_cmd = [
            "ss-local",  # Shadowsocks本地客户端
            "-s", server_ip,  # 服务器地址
            "-p", str(port),  # 端口
            "-m", method,  # 加密方式
            "-k", password,  # 密码
            "-b", "127.0.0.1",  # 本地监听地址
            "-l", "1080",  # 本地端口
            "--fast-open",  # 启用快速连接
            "--dns-mode", "udp_only"  # 使用UDP DNS解析
        ]
        
        # 启动ss-local并连接
        subprocess.Popen(ss_local_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待一会儿让客户端启动
        time.sleep(2)

        # 测试连接到本地端口 (socks代理)
        sock = socket.create_connection(('127.0.0.1', 1080), timeout=5)
        sock.close()
        
        print(f"✅ Shadowsocks节点 {server_ip}:{port} 可用")
        return True
    except (subprocess.SubprocessError, socket.error) as e:
        print(f"❌ Shadowsocks节点 {server_ip}:{port} 无法连接: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Xray配置文件生成器")
    print("=" * 60)
    
    # 获取国家列表
    print("\n正在从API获取国家列表...")
    countries = fetch_countries()
    
    # 测试每个国家的节点是否可用
    for idx, country in enumerate(countries):
        country_code = country["code"]
        ss_port = BASE_SS_PORT + idx
        
        # 测试Shadowsocks节点
        test_shadowsocks_node(DEFAULT_SERVER_IP, ss_port, SS_METHOD, SS_PASSWORD)
    
    # 生成配置
    print("\n正在生成Xray配置...")
    config = generate_xray_config(countries)
    
    # 保存Xray配置
    try:
        import os
        os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
        save_config(config, XRAY_CONFIG_PATH)
    except (IOError, PermissionError) as e:
        print(f"⚠️  无法写入系统路径 {XRAY_CONFIG_PATH}: {e}")
        print(f"   请使用 sudo 运行或手动复制 {OUTPUT_FILE} 到 {XRAY_CONFIG_PATH}")
    
    # 生成Shadowsocks订阅文件
    print("\n正在生成Shadowsocks订阅文件...")
    save_ss_subscription(countries, SS_SUBSCRIPTION_FILE)
    
    print("\n" + "=" * 60)
    print("配置摘要:")
    print(f"  - 总入站数: {len(config['inbounds'])}")
    print(f"  - 总出站数: {len(config['outbounds'])}")
    print(f"  - 路由规则数: {len(config['routing']['rules'])}")
    print(f"  - Shadowsocks端口范围: {BASE_SS_PORT} - {BASE_SS_PORT + len(countries) - 1}")
    print(f"\n提示: Shadowsocks订阅文件已使用服务器IP: {DEFAULT_SERVER_IP}")
    print("=" * 60)


if __name__ == "__main__":
    main()
