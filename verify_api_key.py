"""验证Claude API key是否有效"""
from anthropic import Anthropic, AuthenticationError, InternalServerError
import sys

def verify_api_key(api_key: str) -> bool:
    """验证API key是否有效"""
    
    # 检查格式
    if not api_key or not api_key.startswith('sk-ant-'):
        print("[ERROR] API key格式不正确")
        print("   正确的格式应该以 'sk-ant-' 开头")
        print("   当前的key:", api_key[:30] + "..." if len(api_key) > 30 else api_key)
        return False
    
    print("[OK] API key格式正确")
    
    # 测试API连接
    print("正在测试API连接...")
    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[
                {"role": "user", "content": "Hello, just testing if API works. Reply with 'OK'."}
            ]
        )
        print("[OK] API连接成功")
        print("  响应:", message.content[0].text[:50])
        return True
        
    except AuthenticationError as e:
        print("[ERROR] API认证失败")
        print("   错误:", str(e))
        print("   请检查API key是否正确")
        return False
        
    except InternalServerError as e:
        print("[ERROR] API服务器错误")
        print("   错误:", str(e))
        if "502" in str(e):
            print("   这通常表示API key无效或服务不可用")
        return False
        
    except Exception as e:
        print("[ERROR] 未知错误")
        print("   错误:", str(e))
        return False

if __name__ == "__main__":
    # 从.env文件读取API key
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('CLAUDE_API_KEY'):
                    api_key = line.split('=')[1].strip().strip('"')
                    break
        
        print("=" * 60)
        print("Claude API Key 验证工具")
        print("=" * 60)
        print()
        
        if verify_api_key(api_key):
            print()
            print("[SUCCESS] API key验证通过，可以正常使用")
            sys.exit(0)
        else:
            print()
            print("[FAILED] API key验证失败")
            print()
            print("请按照以下步骤获取有效的API key：")
            print("1. 访问 https://console.anthropic.com/")
            print("2. 注册或登录账号")
            print("3. 进入 API Keys 页面")
            print("4. 创建新的API key")
            print("5. 将API key复制到 .env 文件中")
            print()
            print("详细说明请查看 API_KEY_SETUP.md 文件")
            sys.exit(1)
            
    except FileNotFoundError:
        print("[ERROR] 找不到 .env 文件")
        print("   请先创建 .env 文件并配置 CLAUDE_API_KEY")
        sys.exit(1)
    except Exception as e:
        print("[ERROR] 读取配置文件失败:", str(e))
        sys.exit(1)
